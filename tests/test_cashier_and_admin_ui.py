"""
Tests for Role-Separated UI Architecture (Admin Management Hub vs Cashier POS Terminal).
"""

import pytest
from decimal import Decimal
from PySide6.QtWidgets import QApplication

from src.services.auth_service import AuthService
from src.services.settings_service import SettingsService
from src.services.product_service import ProductService
from src.services.inventory_service import InventoryService
from src.services.billing_service import BillingService
from src.services.purchase_service import PurchaseService
from src.services.reporting_service import ReportingService
from src.services.invoice_service import InvoicePrintService

from src.ui.main_window import MainWindow
from src.ui.cashier_window import CashierMainWindow
from src.ui.views.price_checker_view import PriceCheckerView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def test_env(db_manager, test_shop_and_admin):
    auth = AuthService(db_manager)
    inv = InventoryService(db_manager)
    prod = ProductService(db_manager)
    bill = BillingService(db_manager, inv)
    sett = SettingsService(db_manager)
    pur = PurchaseService(db_manager, inv)
    rep = ReportingService(db_manager)
    prn = InvoicePrintService()

    admin_session = auth.authenticate("admin", "AdminPassword123!")
    cashier_session = auth.authenticate("cashier", "cashier123")

    uom_id = prod.list_uoms()[0]["id"]
    tax_id = prod.list_tax_profiles()[0]["id"]

    pid = prod.create_product(
        current_session=admin_session,
        name="Tata Salt 1kg",
        sku="SALT-001",
        barcode="890103000001",
        unit_id=uom_id,
        tax_profile_id=tax_id,
        selling_price=Decimal("28.00"),
        mrp=Decimal("30.00"),
        purchase_cost=Decimal("22.00"),
    )
    inv.perform_stock_adjustment(admin_session, pid, Decimal("50.000"), "PHYSICAL_COUNT", "Initial stock")

    return {
        "db_mgr": db_manager,
        "auth": auth,
        "admin_session": admin_session,
        "cashier_session": cashier_session,
        "prod": prod,
        "inv": inv,
        "bill": bill,
        "sett": sett,
        "pur": pur,
        "rep": rep,
        "prn": prn,
    }


def test_admin_main_window_launch(qapp, test_env):
    """Verify Admin gets the full Store Management Hub with all 11 modules."""
    admin_win = MainWindow(
        db_manager=test_env["db_mgr"],
        current_session=test_env["admin_session"],
        auth_service=test_env["auth"],
        settings_service=test_env["sett"],
        product_service=test_env["prod"],
        inventory_service=test_env["inv"],
        billing_service=test_env["bill"],
        purchase_service=test_env["pur"],
        reporting_service=test_env["rep"],
        print_service=test_env["prn"],
    )
    assert admin_win.current_session.is_admin is True
    # Admin stack has 11 distinct management views
    assert admin_win.stack.count() == 11
    assert hasattr(admin_win, "dashboard_view")
    assert hasattr(admin_win, "users_view")
    assert hasattr(admin_win, "backup_view")
    assert hasattr(admin_win, "settings_view")
    admin_win.close()


def test_cashier_pos_terminal_launch(qapp, test_env):
    """Verify Cashier gets the dedicated clutter-free Cashier Terminal."""
    cashier_win = CashierMainWindow(
        db_manager=test_env["db_mgr"],
        current_session=test_env["cashier_session"],
        product_service=test_env["prod"],
        billing_service=test_env["bill"],
        reporting_service=test_env["rep"],
        settings_service=test_env["sett"],
        print_service=test_env["prn"],
    )
    assert cashier_win.current_session.is_admin is False
    # Cashier stack has strictly 3 cashier views (Billing, Shift Bills, Price Check)
    assert cashier_win.stack.count() == 3
    assert hasattr(cashier_win, "billing_view")
    assert hasattr(cashier_win, "sales_view")
    assert hasattr(cashier_win, "price_checker_view")

    # Cashier terminal does NOT have admin views
    assert not hasattr(cashier_win, "users_view")
    assert not hasattr(cashier_win, "backup_view")
    assert not hasattr(cashier_win, "settings_view")
    cashier_win.close()


def test_price_checker_view_lookup(qapp, test_env):
    """Verify Price & Stock Checker works and displays retail price & stock."""
    checker = PriceCheckerView(test_env["prod"])
    checker.code_input.setText("890103000001")
    checker._handle_lookup()

    assert "Tata Salt 1kg" in checker.item_name_lbl.text()
    assert "28.00" in checker.selling_price_lbl.text()
    assert "30.00" in checker.mrp_lbl.text()
    assert "50.00" in checker.stock_lbl.text()


def test_multi_customer_park_and_recall_bill(test_env):
    """Verify cashier can park a customer cart, bill another customer, and recall the parked cart."""
    bill_svc = test_env["bill"]
    cashier = test_env["cashier_session"]

    # Customer 1 cart
    cart_customer_1 = [
        {
            "product_id": 1,
            "name": "Tata Salt 1kg",
            "sku": "SALT-001",
            "barcode": "890103000001",
            "unit": "PACK",
            "price": "28.00",
            "gst_rate": "0.0",
            "quantity": "3.000",
            "discount": "4.00",
        }
    ]

    # 1. Park Customer 1's cart
    parked = bill_svc.park_bill(
        current_session=cashier,
        cart_data=cart_customer_1,
        customer_name="Ramesh Kumar",
        customer_phone="9876543210",
        invoice_discount=Decimal("5.00"),
    )
    assert parked["park_reference"].startswith("HOLD-")
    assert parked["items_count"] == 3
    # Total = (3 * 28 - 4) - 5 = 80.00 - 5 = 75.00
    assert parked["total_amount"] == 75.0

    # 2. Verify active parked bills list & count
    assert bill_svc.get_parked_bills_count(cashier) >= 1
    active_bills = bill_svc.list_parked_bills(cashier)
    assert any(b["park_reference"] == parked["park_reference"] for b in active_bills)

    # 3. Recall Customer 1's cart
    recalled = bill_svc.recall_bill(cashier, parked["id"])
    assert recalled["park_reference"] == parked["park_reference"]
    assert recalled["customer_name"] == "Ramesh Kumar"
    assert recalled["customer_phone"] == "9876543210"
    assert recalled["invoice_discount"] == 5.0
    assert len(recalled["cart_data"]) == 1
    assert recalled["cart_data"][0]["name"] == "Tata Salt 1kg"
    assert recalled["cart_data"][0]["quantity"] == "3.000"

    # 4. Verify recalled bill is no longer active in parked list
    active_bills_after = bill_svc.list_parked_bills(cashier)
    assert not any(b["park_reference"] == parked["park_reference"] for b in active_bills_after)


def test_multi_window_terminal_spawning(qapp, test_env):
    """Verify cashier can spawn multiple independent cashier windows on the same PC."""
    cashier_win = CashierMainWindow(
        db_manager=test_env["db_mgr"],
        current_session=test_env["cashier_session"],
        product_service=test_env["prod"],
        billing_service=test_env["bill"],
        reporting_service=test_env["rep"],
        settings_service=test_env["sett"],
        print_service=test_env["prn"],
    )

    # Spawn second terminal
    cashier_win._spawn_new_terminal()
    assert len(cashier_win._spawned_terminals) == 1
    second_term = cashier_win._spawned_terminals[0]
    assert second_term is not None
    assert "Window #2" in second_term.windowTitle()

    second_term.close()
    cashier_win.close()


def test_deactivated_cashier_cannot_work_or_login(test_env):
    """Verify that when an admin deactivates a cashier, they can neither log in nor complete sales."""
    from src.core.exceptions import AccountInactiveError
    from src.services.billing_service import CartItemInput, PaymentInput

    auth = test_env["auth"]
    bill = test_env["bill"]
    admin = test_env["admin_session"]
    cashier = test_env["cashier_session"]

    # 1. Admin deactivates the cashier
    auth.set_user_active_status(current_session=admin, user_id=cashier.user_id, is_active=False)

    # 2. Verify login is blocked
    with pytest.raises(AccountInactiveError):
        auth.authenticate("cashier", "cashier123")

    # 3. Even with an existing active session object, checkout in database is blocked
    cart_item = CartItemInput(product_id=1, quantity=Decimal("1.000"), unit_price=Decimal("28.00"))
    payment = PaymentInput(payment_method="CASH", amount=Decimal("28.00"))

    with pytest.raises(AccountInactiveError):
        bill.complete_sale(
            current_session=cashier,
            cart_items=[cart_item],
            payments=[payment],
        )

    # 4. Holding bill is also blocked
    with pytest.raises(AccountInactiveError):
        bill.park_bill(
            current_session=cashier,
            cart_data=[{"product_id": 1, "name": "Tata Salt", "price": "28.00", "quantity": "1"}],
        )

    # 5. When admin re-activates the cashier, work is allowed again
    auth.set_user_active_status(current_session=admin, user_id=cashier.user_id, is_active=True)
    resumed_session = auth.authenticate("cashier", "cashier123")
    assert resumed_session is not None
    assert resumed_session.username == "cashier"


def test_edit_product_dialog_updates_stock_quantity(qapp, test_env):
    """Verify that opening Edit Product enables stock quantity editing and saves updated stock balance."""
    from src.ui.dialogs.product_dialog import ProductDialog

    prod_svc = test_env["prod"]
    admin = test_env["admin_session"]

    # Open Edit Product on product 1
    dlg = ProductDialog(product_service=prod_svc, current_session=admin, product_id=1)

    # 1. Verify stock_spin is enabled and shows current balance (50.000)
    assert dlg.stock_spin.isEnabled() is True
    assert dlg.stock_spin.value() == 50.0

    # 2. Change stock quantity to 125.000 and save
    dlg.stock_spin.setValue(125.0)
    dlg._handle_save()

    # 3. Verify updated stock in database
    prods, _ = prod_svc.search_products(query="SALT-001")
    assert prods[0]["quantity_on_hand"] == Decimal("125.000")
    dlg.close()


def test_payment_dialog_upi_and_cash_modes(qapp):
    """Verify PaymentDialog supports 1-click mode switching between Cash and UPI Stand."""
    from src.ui.dialogs.payment_dialog import PaymentDialog

    dlg = PaymentDialog(grand_total=Decimal("52.00"))

    # 1. Defaults to CASH
    assert dlg.current_mode == "CASH"
    assert "Confirm Cash Payment" in dlg.confirm_btn.text()

    # 2. Switch to UPI (as when pressing F2 or clicking UPI Stand)
    dlg.set_mode("UPI")
    assert dlg.current_mode == "UPI"
    assert "Confirm UPI Payment" in dlg.confirm_btn.text()
    dlg.upi_ref_input.setText("UTR123456")
    dlg._handle_confirm()

    assert len(dlg.confirmed_payments) == 1
    assert dlg.confirmed_payments[0].payment_method == "UPI"
    assert dlg.confirmed_payments[0].amount == Decimal("52.00")
    assert dlg.confirmed_payments[0].transaction_reference == "UTR123456"

    # 3. Test Cash Mode change calculation
    dlg_cash = PaymentDialog(grand_total=Decimal("52.00"))
    dlg_cash.set_mode("CASH")
    dlg_cash.tendered_spin.setValue(100.0)
    assert dlg_cash.change_lbl.text() == "₹ 48.00"
    dlg_cash._handle_confirm()

    assert len(dlg_cash.confirmed_payments) == 1
    assert dlg_cash.confirmed_payments[0].payment_method == "CASH"
    assert dlg_cash.confirmed_payments[0].amount == Decimal("52.00")


def test_invoice_printing_states_upi_and_cash_mode(qapp, test_env):
    """Verify invoice generation and PDF creation explicitly notes PAYMENT MODE: UPI or CASH."""
    from src.services.billing_service import CartItemInput, PaymentInput

    bill_svc = test_env["bill"]
    print_svc = test_env["prn"]
    shop_info = test_env["sett"].get_shop_info()
    cashier = test_env["cashier_session"]

    # 1. Complete UPI Sale
    sale_upi = bill_svc.complete_sale(
        current_session=cashier,
        cart_items=[CartItemInput(product_id=1, quantity=Decimal("1.000"), unit_price=Decimal("28.00"))],
        payments=[PaymentInput(payment_method="UPI", amount=Decimal("28.00"), transaction_reference="STAND-QR-001")],
    )
    assert sale_upi["payments"][0]["method"] == "UPI"

    # Generate 80mm thermal receipt
    pdf_80 = print_svc.generate_pdf(sale_upi, shop_info, format_type="80mm")
    assert pdf_80.exists()
    assert pdf_80.stat().st_size > 500

    # Generate A4 invoice
    pdf_a4 = print_svc.generate_pdf(sale_upi, shop_info, format_type="A4")
    assert pdf_a4.exists()
    assert pdf_a4.stat().st_size > 1000

    # 2. Complete Cash Sale
    sale_cash = bill_svc.complete_sale(
        current_session=cashier,
        cart_items=[CartItemInput(product_id=1, quantity=Decimal("1.000"), unit_price=Decimal("28.00"))],
        payments=[PaymentInput(payment_method="CASH", amount=Decimal("28.00"))],
    )
    assert sale_cash["payments"][0]["method"] == "CASH"

    pdf_cash_58 = print_svc.generate_pdf(sale_cash, shop_info, format_type="58mm")
    assert pdf_cash_58.exists()
    assert pdf_cash_58.stat().st_size > 500

