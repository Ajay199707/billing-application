"""
Automated unit tests for Price Management, Auditable Price History,
Barcode Generator, and Controlled Sales Returns (Restock vs Damaged).
"""

from decimal import Decimal
import pytest
from src.services.auth_service import UserSession
from src.services.product_service import ProductService
from src.services.price_service import PriceService
from src.services.billing_service import BillingService, CartItemInput, PaymentInput
from src.services.inventory_service import InventoryService
from src.services.barcode_service import BarcodeService


@pytest.fixture
def admin_session():
    return UserSession(
        user_id=1, username="admin", full_name="Store Admin", is_admin=True, permissions={"all"}, token="admin_tok"
    )


def test_price_update_and_history_logging(db_manager, test_shop_and_admin, admin_session):
    prod_service = ProductService(db_manager)
    price_service = PriceService(db_manager)

    uoms = prod_service.list_uoms()
    taxes = prod_service.list_tax_profiles()

    # 1. Create a product
    pid = prod_service.create_product(
        current_session=admin_session,
        name="Ponni Boiled Rice 5kg",
        sku="RICE-PONNI-5KG",
        barcode="8901234567890",
        unit_id=uoms[0]["id"],
        tax_profile_id=taxes[0]["id"],
        purchase_cost=Decimal("230.00"),
        selling_price=Decimal("270.00"),
        mrp=Decimal("290.00"),
        initial_stock=Decimal("50.000"),
    )
    assert pid > 0

    # 2. Update price with an explicit reason
    price_service.update_product_price(
        current_session=admin_session,
        product_id=pid,
        new_selling_price=Decimal("285.00"),
        new_purchase_cost=Decimal("240.00"),
        new_mrp=Decimal("300.00"),
        change_reason="Supplier Tariff Hike Q3",
    )

    # 3. Verify price updated on product
    res = prod_service.resolve_barcode("8901234567890")
    assert res["selling_price"] == 285.0
    assert res["purchase_cost"] == 240.0

    # 4. Verify historical audit trail
    history = price_service.get_price_history(pid)
    assert len(history) == 1
    h = history[0]
    assert h["old_price"] == 270.0
    assert h["new_price"] == 285.0
    assert h["old_cost"] == 230.0
    assert h["new_cost"] == 240.0
    assert h["reason"] == "Supplier Tariff Hike Q3"
    assert h["changed_by"] in ("admin", "System Administrator")


def test_bulk_price_preview_and_apply(db_manager, test_shop_and_admin, admin_session):
    prod_service = ProductService(db_manager)
    price_service = PriceService(db_manager)

    uoms = prod_service.list_uoms()
    taxes = prod_service.list_tax_profiles()
    cat_id = prod_service.get_or_create_category(admin_session, "Beverages")

    # Create 2 beverage products
    p1 = prod_service.create_product(
        current_session=admin_session,
        name="Filter Coffee 200g",
        sku="COFFEE-200G",
        unit_id=uoms[0]["id"],
        tax_profile_id=taxes[0]["id"],
        selling_price=Decimal("100.00"),
        category_id=cat_id,
    )
    p2 = prod_service.create_product(
        current_session=admin_session,
        name="Green Tea 100g",
        sku="TEA-GREEN-100G",
        unit_id=uoms[0]["id"],
        tax_profile_id=taxes[0]["id"],
        selling_price=Decimal("200.00"),
        category_id=cat_id,
    )

    # 1. Preview 10% increase on Beverages
    previews = price_service.preview_bulk_updates(
        category_id=cat_id,
        percent_change=Decimal("10.00"),
        flat_change=Decimal("0.00"),
        target_field="selling_price",
    )
    assert len(previews) == 2
    p1_prev = next(p for p in previews if p["product_id"] == p1)
    p2_prev = next(p for p in previews if p["product_id"] == p2)
    assert p1_prev["old_val"] == 100.0
    assert p1_prev["new_val"] == 110.0
    assert p2_prev["old_val"] == 200.0
    assert p2_prev["new_val"] == 220.0

    # 2. Apply bulk increase
    applied_count = price_service.apply_bulk_updates(
        current_session=admin_session,
        category_id=cat_id,
        percent_change=Decimal("10.00"),
        flat_change=Decimal("0.00"),
        target_field="selling_price",
        change_reason="Seasonal Price Revision",
    )
    assert applied_count == 2

    # Verify both products logged PriceHistory
    hist1 = price_service.get_price_history(p1)
    hist2 = price_service.get_price_history(p2)
    assert len(hist1) == 1 and hist1[0]["new_price"] == 110.0
    assert len(hist2) == 1 and hist2[0]["new_price"] == 220.0


def test_barcode_generation():
    # Test Code-128 generation
    png_bytes_128 = BarcodeService.generate_barcode_image_bytes("GROCERY-101", "code128")
    assert len(png_bytes_128) > 100
    assert png_bytes_128.startswith(b"\x89PNG")  # Valid PNG signature

    # Test EAN-13 generation
    png_bytes_ean = BarcodeService.generate_barcode_image_bytes("8901030010011", "ean13")
    assert len(png_bytes_ean) > 100
    assert png_bytes_ean.startswith(b"\x89PNG")


def test_controlled_sales_return_restock_toggle(db_manager, test_shop_and_admin, admin_session):
    prod_service = ProductService(db_manager)
    inv_service = InventoryService(db_manager)
    billing_service = BillingService(db_manager, inv_service)

    uoms = prod_service.list_uoms()
    taxes = prod_service.list_tax_profiles()

    pid = prod_service.create_product(
        current_session=admin_session,
        name="Farm Milk 1L",
        sku="MILK-1L",
        unit_id=uoms[0]["id"],
        tax_profile_id=taxes[0]["id"],
        selling_price=Decimal("60.00"),
        initial_stock=Decimal("10.000"),
    )

    # 1. Sale of 2 packets
    cart = [CartItemInput(product_id=pid, quantity=Decimal("2.000"))]
    payments = [PaymentInput(payment_method="CASH", amount=Decimal("120.00"))]
    sale_res = billing_service.complete_sale(admin_session, cart_items=cart, payments=payments)
    inv_no = sale_res["invoice_number"]
    assert inv_no is not None

    # Stock should be 8
    p_info = prod_service.resolve_barcode(sku_str := "MILK-1L")
    assert p_info["available_qty"] == 8.0

    sale_data = billing_service.get_invoice(inv_no)
    sale_item_id = sale_data["items"][0]["id"]

    # 2. Return 1 packet marked as DAMAGED (restock_inventory=False)
    ret_no1 = billing_service.process_sales_return(
        current_session=admin_session,
        invoice_number=inv_no,
        return_items=[(sale_item_id, Decimal("1.000"))],
        reason="Packaging Leaking",
        refund_method="CASH",
        restock_inventory=False,  # Damaged! Do not add to saleable inventory
    )
    assert ret_no1.startswith("RET-")

    # Stock MUST STILL BE 8 (not increased to 9 because damaged goods are not saleable)
    p_info = prod_service.resolve_barcode(sku_str)
    assert p_info["available_qty"] == 8.0

    # 3. Return remaining 1 packet as GOOD (restock_inventory=True)
    ret_no2 = billing_service.process_sales_return(
        current_session=admin_session,
        invoice_number=inv_no,
        return_items=[(sale_item_id, Decimal("1.000"))],
        reason="Customer Overpurchased",
        refund_method="CASH",
        restock_inventory=True,  # Good condition, restock!
    )
    assert ret_no2.startswith("RET-")

    # Stock MUST NOW BE 9 (8 + 1)
    p_info = prod_service.resolve_barcode(sku_str)
    assert p_info["available_qty"] == 9.0
