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
