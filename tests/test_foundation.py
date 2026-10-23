"""
Tests for security hashing, database manager, seed initialization, and RBAC models.
"""

import pytest
from src.core.security import hash_password, verify_password, needs_rehash
from src.models import (
    User,
    Role,
    Permission,
    UnitOfMeasure,
    ProductTaxProfile,
    ExpenseCategory,
    Shop,
)


def test_argon2id_hashing():
    raw_pass = "SecurePOS@2026"
    hashed = hash_password(raw_pass)

    assert hashed.startswith("$argon2id$")
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    assert needs_rehash(hashed) is False


def test_database_seeding(db_session):
    roles = db_session.query(Role).all()
    role_names = [r.name for r in roles]
    assert "Administrator" in role_names
    assert "Cashier" in role_names
    assert "Inventory Manager" in role_names

    perms = db_session.query(Permission).all()
    assert len(perms) >= 15

    uoms = db_session.query(UnitOfMeasure).all()
    uom_codes = [u.code for u in uoms]
    assert "PCS" in uom_codes
    assert "KG" in uom_codes
    assert "G" in uom_codes
    assert "L" in uom_codes

    tax_profiles = db_session.query(ProductTaxProfile).all()
    rates = [float(tp.gst_rate) for tp in tax_profiles]
    assert 0.0 in rates
    assert 5.0 in rates
    assert 12.0 in rates
    assert 18.0 in rates
    assert 28.0 in rates

    expenses = db_session.query(ExpenseCategory).all()
    assert len(expenses) >= 5


def test_admin_provisioning_and_rbac(test_shop_and_admin, db_manager):
    shop, admin = test_shop_and_admin

    assert shop.name == "SuperMart Retail"
    assert shop.gstin == "33ABCDE1234F1Z5"
    assert shop.state_code == "33"

    with db_manager.session() as session:
        user = session.query(User).filter_by(username="admin").first()
        assert user is not None
        assert user.is_admin is True
        assert verify_password("AdminPassword123!", user.password_hash) is True
        assert user.has_permission("pos:checkout") is True
        assert user.has_permission("users:manage") is True
        assert user.has_permission("any_random_perm") is True  # Admin has all permissions
