"""
Authentication Login Dialog for Cashiers and Administrators.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame
)

from src.core.exceptions import InvalidCredentialsError, AccountInactiveError
from src.services.auth_service import AuthService, UserSession


class LoginDialog(QDialog):
    def __init__(self, auth_service: AuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.authenticated_session: UserSession | None = None

        self.setWindowTitle("Sign In - AJ Billing Software")
        self.setFixedSize(380, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Title and Header
        title_lbl = QLabel("AJ Billing Software")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #064E3B;")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        sub_lbl = QLabel("Enter your credentials to access the shop counter")
        sub_lbl.setStyleSheet("font-size: 12px; color: #64748B;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setWordWrap(True)
        layout.addWidget(sub_lbl)

        layout.addSpacing(10)

        # Username Input
        user_lbl = QLabel("Username")
        user_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #334155;")
        layout.addWidget(user_lbl)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("e.g. admin or cashier1")
        layout.addWidget(self.user_input)

        # Password Input
        pass_lbl = QLabel("Password")
        pass_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #334155;")
        layout.addWidget(pass_lbl)

        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setPlaceholderText("••••••••••••")
        layout.addWidget(self.pass_input)

        layout.addSpacing(12)

        # Login Button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("PrimaryBtn")
        self.login_btn.setFixedHeight(38)
        self.login_btn.clicked.connect(self._handle_login)
        layout.addWidget(self.login_btn)

        # Connect Enter key to submit
        self.user_input.returnPressed.connect(self.pass_input.setFocus)
        self.pass_input.returnPressed.connect(self._handle_login)

        # Focus username initially
        self.user_input.setFocus()

    def _handle_login(self):
        username = self.user_input.text().strip()
        password = self.pass_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Validation Error", "Please enter both username and password.")
            return

        try:
            session = self.auth_service.authenticate(username=username, password=password)
            self.authenticated_session = session
            self.accept()
        except InvalidCredentialsError:
            QMessageBox.critical(self, "Authentication Failed", "Invalid username or password. Please try again.")
            self.pass_input.clear()
            self.pass_input.setFocus()
        except AccountInactiveError:
            QMessageBox.critical(self, "Account Deactivated", "This account is inactive. Please contact the administrator.")
        except Exception as exc:
            QMessageBox.critical(self, "Login Error", f"An unexpected error occurred:\n{exc}")
