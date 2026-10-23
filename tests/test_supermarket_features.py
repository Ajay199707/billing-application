"""
Automated unit tests for Supermarket specific POS features:
1. Electronic weighing scale EAN-13 barcodes (prefix 20/21) with embedded weight.
2. Product barcode resolution and loose produce short-code mapping.
3. Quantity multiplier scanning parsing.
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


def test_supermarket_scale_barcode_and_produce(db_manager, test_shop_and_admin, admin_session):
    prod_service = ProductService(db_manager)

    # 1. Create a loose produce item: Fresh Onion (Unit KG, Short code 101)
    uoms = prod_service.list_uoms()
    kg_uom = next(u for u in uoms if u["code"] == "KG")
    tax_profiles = prod_service.list_tax_profiles()
    gst_0 = next(t for t in tax_profiles if "0%" in t["name"])

    cat_id = prod_service.get_or_create_category(admin_session, "Fresh Vegetables")
    brand_id = prod_service.get_or_create_brand(admin_session, "Farm Fresh")

    onion_id = prod_service.create_product(
        current_session=admin_session,
        name="Fresh Onions (Loose)",
        sku="VEG-101",
        barcode="101",
        unit_id=kg_uom["id"],
        tax_profile_id=gst_0["id"],
        selling_price=Decimal("35.00"),
        purchase_cost=Decimal("22.00"),
        category_id=cat_id,
        brand_id=brand_id,
        initial_stock=Decimal("150.000"),
    )
    assert onion_id > 0

    # 2. Test direct lookup by short code
    res_direct = prod_service.resolve_barcode("101")
    assert res_direct is not None
    assert res_direct["product_id"] == onion_id
    assert res_direct["name"] == "Fresh Onions (Loose)"
    assert res_direct["unit_code"] == "KG"

    # 3. Test Electronic Weighing Scale Barcode
    # Format: Prefix '20' + 5-digit item code '00101' + 5-digit weight '01750' (1.750 kg) + 1 checksum digit '5'
    # Barcode: 20 00101 01750 5
    scale_barcode = "2000101017505"
    res_scale = prod_service.resolve_barcode(scale_barcode)
    assert res_scale is not None
    assert res_scale["product_id"] == onion_id
    assert res_scale["scanned_quantity"] == 1.750  # Exactly 1.750 kg!

    # 4. Another scale barcode: 850 grams = 0.850 kg
    scale_barcode_850g = "2000101008502"
    res_scale_850g = prod_service.resolve_barcode(scale_barcode_850g)
    assert res_scale_850g is not None
    assert res_scale_850g["product_id"] == onion_id
    assert res_scale_850g["scanned_quantity"] == 0.850


def test_supermarket_fmcg_packaged_item(db_manager, test_shop_and_admin, admin_session):
    prod_service = ProductService(db_manager)

    uoms = prod_service.list_uoms()
    pcs_uom = next(u for u in uoms if u["code"] == "PCS")
    tax_profiles = prod_service.list_tax_profiles()
    gst_18 = next(t for t in tax_profiles if "18%" in t["name"])

    cat_id = prod_service.get_or_create_category(admin_session, "Personal Care")
    brand_id = prod_service.get_or_create_brand(admin_session, "Dettol")

    soap_id = prod_service.create_product(
        current_session=admin_session,
        name="Dettol Original Bathing Soap 125g",
        sku="DET-SOAP-125",
        barcode="8901396300123",
        unit_id=pcs_uom["id"],
        tax_profile_id=gst_18["id"],
        selling_price=Decimal("45.00"),
        purchase_cost=Decimal("36.00"),
        mrp=Decimal("50.00"),
        category_id=cat_id,
        brand_id=brand_id,
        initial_stock=Decimal("50.000"),
    )
    assert soap_id > 0

    # Verify standard EAN-13 barcode lookup
    res = prod_service.resolve_barcode("8901396300123")
    assert res is not None
    assert res["product_id"] == soap_id
    assert res["name"] == "Dettol Original Bathing Soap 125g"
    assert res.get("scanned_quantity") is None  # Standard item, default 1
