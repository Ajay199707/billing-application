"""
Unit tests for Cloud Catalog Sync Service.
Tests offline sync, price preservation, and new product addition.
"""

import pytest
from decimal import Decimal
from src.services.auth_service import UserSession
from src.services.cloud_sync_service import sync_catalog_from_cloud


MOCK_CLOUD_DATA = {
    "catalog_version": "1.0.1",
    "last_updated": "2026-10-25",
    "description": "Test Cloud Master Catalog",
    "products": [
        {
            "sku": "GR-ATT-001",
            "name": "Aashirvaad Superior MP Sharbati Atta 5kg",
            "category": "Flours & Grains",
            "brand": "Aashirvaad",
            "unit": "KG",
            "tax_profile": "GST_0",
            "barcode": "8901725131238",
            "mrp": 275.0,
            "purchase_cost": 220.0,
            "selling_price": 250.0,
            "reorder_level": 5.0,
        },
        {
            "sku": "GR-OIL-001",
            "name": "Fortune Sunlite Refined Sunflower Oil 1L",
            "category": "Edible Oils & Ghee",
            "brand": "Fortune",
            "unit": "L",
            "tax_profile": "GST_5",
            "barcode": "8906007281014",
            "mrp": 140.0,
            "purchase_cost": 110.0,
            "selling_price": 128.0,
            "reorder_level": 10.0,
        },
    ],
}


def test_sync_new_products(db_manager, test_shop_and_admin):
    from src.services.auth_service import AuthService
    auth = AuthService(db_manager)
    admin_session = auth.authenticate("admin", "AdminPassword123!")

    result = sync_catalog_from_cloud(
        db_manager=db_manager,
        current_session=admin_session,
        cloud_data=MOCK_CLOUD_DATA,
        preserve_shop_prices=True,
    )

    assert result["status"] == "success"
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["total_cloud"] == 2
    assert result["version"] == "1.0.1"


def test_preserve_shop_pricing_on_resync(db_manager, test_shop_and_admin):
    from src.services.auth_service import AuthService
    auth = AuthService(db_manager)
    admin_session = auth.authenticate("admin", "AdminPassword123!")

    # First sync: create products
    sync_catalog_from_cloud(
        db_manager=db_manager,
        current_session=admin_session,
        cloud_data=MOCK_CLOUD_DATA,
        preserve_shop_prices=True,
    )

    # Shop owner changes price to custom value
    with db_manager.session() as session:
        from src.models import Product
        p = session.query(Product).filter_by(sku="GR-ATT-001").first()
        p.selling_price = Decimal("265.00")
        p.purchase_cost = Decimal("230.00")
        if p.inventory_balance:
            p.inventory_balance.quantity_on_hand = Decimal("40.00")
        session.commit()

    # Cloud syncs again with updated description/MRP from cloud
    updated_cloud = {
        "catalog_version": "1.0.2",
        "last_updated": "2026-10-26",
        "products": [
            {
                "sku": "GR-ATT-001",
                "name": "Aashirvaad Superior MP Sharbati Atta 5kg (New Pack)",
                "category": "Flours & Grains",
                "brand": "Aashirvaad",
                "unit": "KG",
                "tax_profile": "GST_0",
                "barcode": "8901725131238",
                "mrp": 290.0,
                "purchase_cost": 235.0,  # Cloud cost
                "selling_price": 270.0,  # Cloud price
                "reorder_level": 8.0,
            }
        ],
    }

    res2 = sync_catalog_from_cloud(
        db_manager=db_manager,
        current_session=admin_session,
        cloud_data=updated_cloud,
        preserve_shop_prices=True,
    )

    assert res2["created"] == 0
    assert res2["updated"] == 1

    # Verify shop's custom selling price and stock were NOT overwritten!
    with db_manager.session() as session:
        from src.models import Product
        p = session.query(Product).filter_by(sku="GR-ATT-001").first()
        assert p.name == "Aashirvaad Superior MP Sharbati Atta 5kg (New Pack)"
        assert p.mrp == Decimal("290.00")
        assert p.selling_price == Decimal("265.00")  # Kept shop's price!
        assert p.purchase_cost == Decimal("230.00")  # Kept shop's cost!
        if p.inventory_balance:
            assert p.inventory_balance.quantity_on_hand == Decimal("40.00")

MOCK_SHOP_PRICING = {
    "shop_id": "SHOP_01",
    "version": "1.0.0",
    "price_updates": [
        {
            "sku": "GR-ATT-001",
            "selling_price": 285.0,
            "purchase_cost": 240.0,
            "mrp": 300.0,
        },
        {
            "barcode": "8906007281014",
            "selling_price": 139.0,
            "purchase_cost": 115.0,
        },
    ],
}


def test_shop_specific_pricing_update(db_manager, test_shop_and_admin):
    from src.services.auth_service import AuthService
    from src.services.cloud_sync_service import sync_shop_pricing_from_cloud
    auth = AuthService(db_manager)
    admin_session = auth.authenticate("admin", "AdminPassword123!")

    # 1. First populate catalog items
    sync_catalog_from_cloud(
        db_manager=db_manager,
        current_session=admin_session,
        cloud_data=MOCK_CLOUD_DATA,
        preserve_shop_prices=True,
    )

    # 2. Apply shop 01 custom pricing
    res = sync_shop_pricing_from_cloud(
        db_manager=db_manager,
        current_session=admin_session,
        shop_id="SHOP_01",
        pricing_data=MOCK_SHOP_PRICING,
    )

    assert res["status"] == "success"
    assert res["updated"] == 2
    assert res["shop_id"] == "SHOP_01"

    # 3. Verify prices in database
    with db_manager.session() as session:
        from src.models import Product
        p1 = session.query(Product).filter_by(sku="GR-ATT-001").first()
        assert p1.selling_price == Decimal("285.00")
        assert p1.purchase_cost == Decimal("240.00")
        assert p1.mrp == Decimal("300.00")

        p2 = session.query(Product).filter_by(barcode="8906007281014").first()
        assert p2.selling_price == Decimal("139.00")
        assert p2.purchase_cost == Decimal("115.00")


def test_shop_specific_creates_new_custom_product(db_manager, test_shop_and_admin):
    """Verify that new products defined in shop pricing file are created in local database."""
    from src.services.auth_service import AuthService
    from src.services.cloud_sync_service import sync_shop_pricing_from_cloud
    auth = AuthService(db_manager)
    admin_session = auth.authenticate("admin", "AdminPassword123!")

    custom_data = {
        "shop_id": "SHOP_01",
        "version": "1.0.1",
        "price_updates": [
            {
                "name": "aaa",
                "sku": "AAA-111",
                "barcode": "1006",
                "selling_price": 100.0,
                "purchase_cost": 98.0,
                "mrp": 95.0,
            }
        ],
    }

    res = sync_shop_pricing_from_cloud(
        db_manager=db_manager,
        current_session=admin_session,
        shop_id="SHOP_01",
        pricing_data=custom_data,
    )

    assert res["status"] == "success"
    assert res["created"] == 1
    assert res["updated"] == 0

    with db_manager.session() as session:
        from src.models import Product
        p = session.query(Product).filter_by(barcode="1006").first()
        assert p is not None
        assert p.name == "aaa"
        assert p.sku == "AAA-111"
        assert p.selling_price == Decimal("100.00")
        assert p.purchase_cost == Decimal("98.00")
        assert p.mrp == Decimal("95.00")
