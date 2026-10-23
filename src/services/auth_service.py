"""
Authentication and Role-Based Access Control (RBAC) service.
Handles user logins, session state, password updates, and user management.
"""

import json
import logging
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from src.core.database import DatabaseManager
from src.core.security import hash_password, verify_password, generate_session_token
from src.core.exceptions import (
    InvalidCredentialsError,
    AccountInactiveError,
    PermissionDeniedError,
    BillingSystemError,
)
from src.models import User, Role, Permission, AuditLog

logger = logging.getLogger(__name__)


class UserSession:
    """Represents an authenticated active user session."""
    def __init__(self, user_id: int, username: str, full_name: str, is_admin: bool, permissions: set[str], token: str):
        self.user_id = user_id
        self.username = username
        self.full_name = full_name
        self.is_admin = is_admin
        self.permissions = permissions
        self.token = token

    def has_permission(self, code: str) -> bool:
        if self.is_admin or "all" in self.permissions or code in self.permissions:
            return True
        return False


class AuthService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def authenticate(self, username: str, password: str, client_ip: str = "127.0.0.1") -> UserSession:
        """Authenticates a user and returns their UserSession with loaded permissions."""
        with self.db.session() as session:
            user = session.query(User).filter_by(username=username).first()
            if not user or not verify_password(password, user.password_hash):
                self._record_audit(
                    session, user_id=None, action="LOGIN_FAILED", entity="User", entity_id=username,
                    details={"reason": "Invalid credentials", "ip": client_ip}
                )
                raise InvalidCredentialsError()

            if not user.is_active:
                self._record_audit(
                    session, user_id=user.id, action="LOGIN_BLOCKED", entity="User", entity_id=str(user.id),
                    details={"reason": "Account is inactive", "ip": client_ip}
                )
                raise AccountInactiveError()

            user.last_login_at = datetime.now(timezone.utc)

            # Collect all permissions
            permissions = set()
            if user.is_admin:
                permissions.add("all")
            for role in user.roles:
                for perm in role.permissions:
                    permissions.add(perm.code)

            token = generate_session_token()

            self._record_audit(
                session, user_id=user.id, action="LOGIN_SUCCESS", entity="User", entity_id=str(user.id),
                details={"ip": client_ip}
            )

            return UserSession(
                user_id=user.id,
                username=user.username,
                full_name=user.full_name,
                is_admin=user.is_admin,
                permissions=permissions,
                token=token,
            )

    def create_user(
        self,
        current_session: UserSession,
        username: str,
        password: str,
        full_name: str,
        role_names: List[str],
        phone: Optional[str] = None,
        email: Optional[str] = None,
        is_admin: bool = False,
    ) -> int:
        """Creates a new user account with assigned roles."""
        if not current_session.has_permission("users:manage"):
            raise PermissionDeniedError("users:manage")

        with self.db.session() as session:
            existing = session.query(User).filter_by(username=username).first()
            if existing:
                raise BillingSystemError(f"Username '{username}' is already in use.", code="DUPLICATE_USER")

            user = User(
                username=username,
                password_hash=hash_password(password),
                full_name=full_name,
                phone=phone,
                email=email,
                is_admin=is_admin,
                is_active=True,
            )

            for r_name in role_names:
                role = session.query(Role).filter_by(name=r_name).first()
                if role:
                    user.roles.append(role)

            session.add(user)
            session.flush()

            self._record_audit(
                session,
                user_id=current_session.user_id,
                action="USER_CREATED",
                entity="User",
                entity_id=str(user.id),
                details={"username": username, "roles": role_names, "is_admin": is_admin},
            )
            return user.id

    def update_password(self, current_session: UserSession, user_id: int, new_password: str) -> None:
        """Updates user password."""
        if current_session.user_id != user_id and not current_session.has_permission("users:manage"):
            raise PermissionDeniedError("users:manage")

        with self.db.session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                raise BillingSystemError(f"User with ID {user_id} not found.", code="USER_NOT_FOUND")

            user.password_hash = hash_password(new_password)
            self._record_audit(
                session,
                user_id=current_session.user_id,
                action="PASSWORD_CHANGED",
                entity="User",
                entity_id=str(user.id),
            )

    def set_user_active_status(self, current_session: UserSession, user_id: int, is_active: bool) -> None:
        """Activates or deactivates a user account."""
        if not current_session.has_permission("users:manage"):
            raise PermissionDeniedError("users:manage")
        if current_session.user_id == user_id and not is_active:
            raise BillingSystemError("Administrators cannot deactivate their own account.", code="CANNOT_SELF_DEACTIVATE")

        with self.db.session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                raise BillingSystemError(f"User with ID {user_id} not found.", code="USER_NOT_FOUND")
            user.is_active = is_active
            self._record_audit(
                session,
                user_id=current_session.user_id,
                action="USER_STATUS_UPDATED",
                entity="User",
                entity_id=str(user.id),
                details={"is_active": is_active},
            )

    def list_users(self, current_session: UserSession) -> List[dict]:
        """Lists all registered users with their assigned roles."""
        if not current_session.has_permission("users:manage"):
            raise PermissionDeniedError("users:manage")

        with self.db.session() as session:
            users = session.query(User).all()
            return [
                {
                    "id": u.id,
                    "username": u.username,
                    "full_name": u.full_name,
                    "phone": u.phone,
                    "email": u.email,
                    "is_active": u.is_active,
                    "is_admin": u.is_admin,
                    "roles": [r.name for r in u.roles],
                    "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                }
                for u in users
            ]

    def _record_audit(
        self,
        session: Session,
        user_id: Optional[int],
        action: str,
        entity: str,
        entity_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity_name=entity,
            entity_id=entity_id,
            details_json=json.dumps(details) if details else None,
            created_at=datetime.now(timezone.utc),
        )
        session.add(log)
