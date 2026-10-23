"""
Tests for manual typing, auto-saving to memory, and suggestion of Categories and Brands.
"""

from decimal import Decimal
import pytest
from src.services.auth_service import UserSession
from src.services.product_service import ProductService


@pytest.fixture
def admin_session():
    return UserSession(
        user_id=1, username="admin", full_name="Admin", is_admin=True, permissions={"all"}, token="tok"
    )


def test_get_or_create_category_and_brand(db_manager, test_shop_and_admin, admin_session):
    service = ProductService(db_manager)

    # 1. Blank or "None" returns None
    assert service.get_or_create_category(admin_session, "") is None
    assert service.get_or_create_category(admin_session, "None") is None
    assert service.get_or_create_brand(admin_session, "") is None
    assert service.get_or_create_brand(admin_session, "none") is None

    # 2. Type new category manually: saves to memory
    cat_id1 = service.get_or_create_category(admin_session, "Grains & Rice")
    assert cat_id1 is not None

    # 3. Type same category again (case-insensitive): returns existing ID
    cat_id2 = service.get_or_create_category(admin_session, "grains & rice")
    assert cat_id2 == cat_id1

    # 4. Type new brand manually: saves to memory
    brand_id1 = service.get_or_create_brand(admin_session, "India Gate")
    assert brand_id1 is not None

    # 5. Type same brand again: returns existing ID
    brand_id2 = service.get_or_create_brand(admin_session, "india gate")
    assert brand_id2 == brand_id1

    # 6. Verify they appear in listed categories and brands for future suggestions
    all_cats = service.list_categories()
    cat_names = [c["name"] for c in all_cats]
    assert "Grains & Rice" in cat_names

    all_brands = service.list_brands()
    brand_names = [b["name"] for b in all_brands]
    assert "India Gate" in brand_names
