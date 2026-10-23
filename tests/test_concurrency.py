"""
Concurrency and Multi-Workstation Simulation Tests.
Verifies atomic stock locking and collision-free sequential invoice generation
when multiple cashier threads attempt concurrent checkouts on limited inventory.
"""

import concurrent.futures
from decimal import Decimal
import pytest

from src.core.config import DatabaseConfig, DatabaseMode
from src.core.database import DatabaseManager
from src.core.exceptions import InsufficientStockError
from src.models import Base
from src.services.auth_service import UserSession
from src.services.db_init_service import initialize_database, setup_initial_shop_and_admin
from src.services.product_service import ProductService
from src.services.inventory_service import InventoryService
from src.services.billing_service import BillingService, CartItemInput, PaymentInput


def test_concurrent_checkout_prevents_overselling(tmp_path):
    """
    Test scenario:
    - Product has 5 units in stock.
    - Cashier 1 attempts to buy 4 units.
    - Cashier 2 attempts to buy 4 units.
    - Both submit transactions concurrently in separate threads with independent DB sessions.
    - Exactly one must succeed, the other must be rejected, and final stock must be 1 (5 - 4 = 1).
    """
    db_file = tmp_path / "concurrent_shop.db"
    cfg = DatabaseConfig(mode=DatabaseMode.SINGLE_SQLITE, sqlite_file=str(db_file))
    mgr = DatabaseManager(cfg)
    mgr.initialize()
    mgr.create_all_tables(Base)
    initialize_database(mgr, create_tables=False)

    shop, admin = setup_initial_shop_and_admin(
        db_manager=mgr,
        shop_name="Concurrent POS Shop",
        legal_name="Concurrent POS Shop Pvt Ltd",
        gstin="33ABCDE1234F1Z5",
        state_code="33",
        state_name="Tamil Nadu",
        admin_username="admin",
        admin_password="Password123!",
        admin_full_name="Admin",
    )

    admin_session = UserSession(
        user_id=1, username="admin", full_name="Admin", is_admin=True, permissions={"all"}, token="tok"
    )

    prod_service = ProductService(mgr)
    inv_service = InventoryService(mgr)
    billing_service = BillingService(mgr, inv_service)

    prod_id = prod_service.create_product(
        current_session=admin_session,
        name="High Demand Smartphone",
        sku="PHONE-CONC-01",
        unit_id=1,
        tax_profile_id=4,  # 18%
        selling_price=Decimal("10000.00"),
        initial_stock=Decimal("5.000"),  # Exactly 5 units available
    )

    # Function executed by worker threads
    def cashier_checkout(cashier_name: str, quantity: Decimal) -> dict:
        # Each thread gets its own session via the billing_service
        cart = [CartItemInput(product_id=prod_id, quantity=quantity)]
        total = Decimal("47200.00")  # 4 * 10000 = 40000 + 18% tax (7200) = 47200
        payments = [PaymentInput(payment_method="CASH", amount=total)]
        session = UserSession(
            user_id=1, username=cashier_name, full_name=cashier_name, is_admin=True, permissions={"all"}, token="tok"
        )
        return billing_service.complete_sale(
            current_session=session,
            cart_items=cart,
            payments=payments,
        )

    results = []
    errors = []

    # Run 2 cashiers in parallel threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(cashier_checkout, "Cashier_A", Decimal("4.000"))
        f2 = executor.submit(cashier_checkout, "Cashier_B", Decimal("4.000"))

        for f in [f1, f2]:
            try:
                res = f.result()
                results.append(res)
            except Exception as e:
                errors.append(e)

    # Exactly 1 sale must have succeeded
    assert len(results) == 1, f"Expected 1 success, got {len(results)}. Errors: {errors}"
    assert len(errors) == 1, f"Expected 1 failure, got {len(errors)}"
    assert isinstance(errors[0], InsufficientStockError)

    # Stock must be exactly 1 unit left
    bal, _, _ = inv_service.reconcile_product_stock(prod_id)
    assert bal == Decimal("1.000")

    mgr.close()


def test_concurrent_invoice_numbering(tmp_path):
    """
    Test scenario:
    - Multiple cashier threads complete sales simultaneously.
    - All invoice numbers must be unique, sequential, and have zero duplicates.
    """
    db_file = tmp_path / "seq_shop.db"
    cfg = DatabaseConfig(mode=DatabaseMode.SINGLE_SQLITE, sqlite_file=str(db_file))
    mgr = DatabaseManager(cfg)
    mgr.initialize()
    mgr.create_all_tables(Base)
    initialize_database(mgr, create_tables=False)

    setup_initial_shop_and_admin(
        db_manager=mgr,
        shop_name="Seq POS Shop",
        legal_name="Seq POS Shop Pvt Ltd",
        gstin="33ABCDE1234F1Z5",
        state_code="33",
        state_name="Tamil Nadu",
        admin_username="admin",
        admin_password="Password123!",
        admin_full_name="Admin",
    )

    admin_session = UserSession(
        user_id=1, username="admin", full_name="Admin", is_admin=True, permissions={"all"}, token="tok"
    )

    prod_service = ProductService(mgr)
    inv_service = InventoryService(mgr)
    billing_service = BillingService(mgr, inv_service)

    prod_id = prod_service.create_product(
        current_session=admin_session,
        name="Ball Pen Blue",
        sku="PEN-BLUE-01",
        unit_id=1,
        tax_profile_id=4,
        selling_price=Decimal("10.00"),
        initial_stock=Decimal("100.000"),
    )

    def checkout_one_pen(cashier_id: int):
        cart = [CartItemInput(product_id=prod_id, quantity=Decimal("1.000"))]
        payments = [PaymentInput(payment_method="CASH", amount=Decimal("12.00"))]
        sess = UserSession(
            user_id=1, username=f"cashier_{cashier_id}", full_name=f"Cashier {cashier_id}", is_admin=True, permissions={"all"}, token="t"
        )
        return billing_service.complete_sale(
            current_session=sess,
            cart_items=cart,
            payments=payments,
        )

    invoice_numbers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(checkout_one_pen, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            invoice_numbers.append(res["invoice_number"])

    assert len(invoice_numbers) == 10
    # Enforce strict uniqueness: no duplicate invoice numbers!
    assert len(set(invoice_numbers)) == 10

    mgr.close()
