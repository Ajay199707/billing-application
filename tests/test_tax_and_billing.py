"""
Comprehensive unit and integration tests for GST Tax Engine,
POS Checkout, Atomic Stock Deductions, and Sales Returns.
"""

from decimal import Decimal
import pytest

from src.core.exceptions import (
    InsufficientStockError,
    PaymentMismatchedError,
    EmptyCartError,
)
from src.services.auth_service import UserSession
from src.services.product_service import ProductService
from src.services.inventory_service import InventoryService
from src.services.billing_service import BillingService, CartItemInput, PaymentInput
from src.services.tax_service import TaxEngine


@pytest.fixture
def test_session():
    return UserSession(
        user_id=1,
        username="cashier1",
        full_name="Test Cashier",
        is_admin=True,
        permissions={"all"},
        token="test_tok",
    )


def test_tax_engine_intrastate():
    line = TaxEngine.calculate_line_item(
        product_id=1,
        product_name="Basmati Rice 1kg",
        hsn_sac_code="1006",
        unit_code="KG",
        quantity=Decimal("2.000"),
        unit_price=Decimal("100.00"),
        gst_rate=Decimal("5.00"),
        seller_state_code="33",
        buyer_state_code="33",  # Intra-state
        line_discount=Decimal("0.00"),
        is_tax_inclusive=False,
    )
    assert line.is_interstate is False
    assert line.taxable_value == Decimal("200.00")
    assert line.cgst_amount == Decimal("5.00")  # 2.5% of 200
    assert line.sgst_amount == Decimal("5.00")  # 2.5% of 200
    assert line.igst_amount == Decimal("0.00")
    assert line.line_total == Decimal("210.00")


def test_tax_engine_interstate():
    line = TaxEngine.calculate_line_item(
        product_id=2,
        product_name="Power Drill Machine",
        hsn_sac_code="8467",
        unit_code="PCS",
        quantity=Decimal("1.000"),
        unit_price=Decimal("2000.00"),
        gst_rate=Decimal("18.00"),
        seller_state_code="33",
        buyer_state_code="29",  # Inter-state (Karnataka)
        line_discount=Decimal("100.00"),
        is_tax_inclusive=False,
    )
    assert line.is_interstate is True
    assert line.taxable_value == Decimal("1900.00")
    assert line.cgst_amount == Decimal("0.00")
    assert line.sgst_amount == Decimal("0.00")
    assert line.igst_amount == Decimal("342.00")  # 18% of 1900
    assert line.line_total == Decimal("2242.00")


def test_tax_engine_tax_inclusive():
    # MRP = ₹105 with 5% GST inclusive -> Taxable = 100, Tax = 5
    line = TaxEngine.calculate_line_item(
        product_id=3,
        product_name="Wheat Flour Pack",
        hsn_sac_code="1101",
        unit_code="PACK",
        quantity=Decimal("1.000"),
        unit_price=Decimal("105.00"),
        gst_rate=Decimal("5.00"),
        seller_state_code="33",
        buyer_state_code="33",
        is_tax_inclusive=True,
    )
    assert line.line_total == Decimal("105.00")
    assert line.taxable_value == Decimal("100.00")
    assert (line.cgst_amount + line.sgst_amount) == Decimal("5.00")


def test_billing_checkout_success(db_manager, test_shop_and_admin, test_session):
    prod_service = ProductService(db_manager)
    inv_service = InventoryService(db_manager)
    billing_service = BillingService(db_manager, inv_service)

    # 1. Create a product with initial stock 10
    prod_id = prod_service.create_product(
        current_session=test_session,
        name="Organic Tea 500g",
        sku="TEA-ORG-500",
        barcode="8901234567890",
        unit_id=1,  # PCS
        tax_profile_id=4,  # GST 18%
        selling_price=Decimal("200.00"),
        purchase_cost=Decimal("140.00"),
        initial_stock=Decimal("10.000"),
    )

    # Verify initial stock
    balance, total_mv, is_match = inv_service.reconcile_product_stock(prod_id)
    assert balance == Decimal("10.000")

    # 2. Checkout 3 units
    # Price = 3 * 200 = 600. GST 18% = 108. Total = 708.
    cart = [CartItemInput(product_id=prod_id, quantity=Decimal("3.000"))]
    payments = [
        PaymentInput(payment_method="CASH", amount=Decimal("500.00")),
        PaymentInput(payment_method="UPI", amount=Decimal("208.00"), transaction_reference="UPI/123456"),
    ]

    sale_result = billing_service.complete_sale(
        current_session=test_session,
        cart_items=cart,
        payments=payments,
    )

    assert sale_result["grand_total"] == 708.00
    assert sale_result["payment_status"] == "PAID"
    assert len(sale_result["payments"]) == 2
    assert sale_result["invoice_number"].startswith("INV-")

    # 3. Verify stock decreased from 10 to 7
    balance, total_mv, is_match = inv_service.reconcile_product_stock(prod_id)
    assert balance == Decimal("7.000")


def test_billing_rejects_insufficient_stock(db_manager, test_shop_and_admin, test_session):
    prod_service = ProductService(db_manager)
    inv_service = InventoryService(db_manager)
    billing_service = BillingService(db_manager, inv_service)

    prod_id = prod_service.create_product(
        current_session=test_session,
        name="Limited Edition Perfume",
        sku="PERF-LTD-01",
        unit_id=1,
        tax_profile_id=4,
        selling_price=Decimal("1500.00"),
        initial_stock=Decimal("2.000"),
    )

    # Try selling 5 units when only 2 are in stock
    cart = [CartItemInput(product_id=prod_id, quantity=Decimal("5.000"))]
    payments = [PaymentInput(payment_method="CASH", amount=Decimal("8850.00"))]

    with pytest.raises(InsufficientStockError) as exc_info:
        billing_service.complete_sale(
            current_session=test_session,
            cart_items=cart,
            payments=payments,
        )

    assert "Insufficient stock" in str(exc_info.value)

    # Stock should remain untouched at 2
    balance, _, _ = inv_service.reconcile_product_stock(prod_id)
    assert balance == Decimal("2.000")


def test_billing_rejects_mismatched_payment(db_manager, test_shop_and_admin, test_session):
    prod_service = ProductService(db_manager)
    inv_service = InventoryService(db_manager)
    billing_service = BillingService(db_manager, inv_service)

    prod_id = prod_service.create_product(
        current_session=test_session,
        name="Notebook A4",
        sku="NOTE-A4",
        unit_id=1,
        tax_profile_id=4,
        selling_price=Decimal("100.00"),
        initial_stock=Decimal("10.000"),
    )

    cart = [CartItemInput(product_id=prod_id, quantity=Decimal("1.000"))]
    # Total with 18% tax is 118, but cashier enters 100
    payments = [PaymentInput(payment_method="CASH", amount=Decimal("100.00"))]

    with pytest.raises(PaymentMismatchedError):
        billing_service.complete_sale(
            current_session=test_session,
            cart_items=cart,
            payments=payments,
        )


def test_billing_idempotency_prevents_duplicate_billing(db_manager, test_shop_and_admin, test_session):
    prod_service = ProductService(db_manager)
    inv_service = InventoryService(db_manager)
    billing_service = BillingService(db_manager, inv_service)

    prod_id = prod_service.create_product(
        current_session=test_session,
        name="Wireless Mouse",
        sku="MOUSE-W-01",
        unit_id=1,
        tax_profile_id=4,
        selling_price=Decimal("500.00"),
        initial_stock=Decimal("10.000"),
    )

    cart = [CartItemInput(product_id=prod_id, quantity=Decimal("1.000"))]
    payments = [PaymentInput(payment_method="CARD", amount=Decimal("590.00"), transaction_reference="CARD-9921")]

    # First attempt with unique idempotency key
    key = "txn_idempotent_test_123"
    res1 = billing_service.complete_sale(
        current_session=test_session,
        cart_items=cart,
        payments=payments,
        idempotency_key=key,
    )

    # Second attempt with same idempotency key (simulating network timeout retry)
    res2 = billing_service.complete_sale(
        current_session=test_session,
        cart_items=cart,
        payments=payments,
        idempotency_key=key,
    )

    assert res1["invoice_number"] == res2["invoice_number"]

    # Stock must have decreased only by 1 unit (10 - 1 = 9), NOT double deducted!
    balance, _, _ = inv_service.reconcile_product_stock(prod_id)
    assert balance == Decimal("9.000")
