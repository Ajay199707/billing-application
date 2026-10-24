"""
Application Entry Point and Bootstrap Lifecycle.
Handles startup initialization, onboarding wizard detection, login flow, and Main Window display.
"""

import sys
import ctypes
import logging
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from src.core.config import AppConfig, get_asset_path
from src.core.database import get_db_manager
from src.core.logging import setup_logging
from src.models import Shop, User
from src.services.db_init_service import initialize_database
from src.services.auth_service import AuthService
from src.services.settings_service import SettingsService
from src.services.product_service import ProductService
from src.services.inventory_service import InventoryService
from src.services.billing_service import BillingService
from src.services.purchase_service import PurchaseService
from src.services.reporting_service import ReportingService
from src.services.invoice_service import InvoicePrintService

from src.ui.styles import APP_STYLESHEET
from src.ui.dialogs.onboarding_dialog import OnboardingDialog
from src.ui.dialogs.login_dialog import LoginDialog
from src.ui.main_window import MainWindow
from src.ui.cashier_window import CashierMainWindow

logger = logging.getLogger(__name__)


def run_app():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AJSoftware.AJBillingSoftware.POS.1_0")
    except Exception:
        pass
    # Setup structured logging
    setup_logging()
    logger.info("Starting AJ Billing Software & POS Application...")

    app = QApplication(sys.argv)
    app.setApplicationName("AJ Billing Software")
    app.setOrganizationName("AJ Software")
    app.setStyleSheet(APP_STYLESHEET)

    icon_path = get_asset_path("app_icon.ico")
    if not icon_path.exists():
        icon_path = get_asset_path("app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Load configuration
    app_cfg = AppConfig.load()
    db_mgr = get_db_manager(app_cfg.database)

    # Initialize tables and seed base metadata
    try:
        initialize_database(db_mgr, create_tables=True)
    except Exception as exc:
        logger.error(f"Failed to initialize database: {exc}")

    # Check if Shop and Admin User exist; if not, trigger Onboarding Wizard
    with db_mgr.session() as session:
        has_shop = session.query(Shop).first() is not None
        has_admin = session.query(User).filter_by(is_admin=True).first() is not None

    if not has_shop or not has_admin:
        logger.info("First launch detected: launching Onboarding Setup Wizard...")
        onboarding = OnboardingDialog(db_manager=db_mgr)
        if onboarding.exec() != QDialog.Accepted:
            logger.info("Onboarding cancelled by user. Exiting application.")
            sys.exit(0)

    # Services
    auth_service = AuthService(db_mgr)
    settings_service = SettingsService(db_mgr)
    product_service = ProductService(db_mgr)
    inventory_service = InventoryService(db_mgr)
    billing_service = BillingService(db_mgr, inventory_service)
    purchase_service = PurchaseService(db_mgr, inventory_service)
    reporting_service = ReportingService(db_mgr)
    print_service = InvoicePrintService()

    # User Authentication & Session Loop
    while True:
        login_dialog = LoginDialog(auth_service=auth_service)
        if login_dialog.exec() != QDialog.Accepted or not login_dialog.authenticated_session:
            logger.info("Login cancelled or closed. Exiting application.")
            break

        session = login_dialog.authenticated_session
        logger.info(f"User '{session.username}' authenticated (is_admin={session.is_admin}). Launching UI...")

        # Branch UI based on user role:
        # Administrator -> Full Store Management Hub (11 modules)
        # Cashier -> Streamlined POS Terminal (Active Bill, Shift Bills, Price Check)
        if session.is_admin:
            window = MainWindow(
                db_manager=db_mgr,
                current_session=session,
                auth_service=auth_service,
                settings_service=settings_service,
                product_service=product_service,
                inventory_service=inventory_service,
                billing_service=billing_service,
                purchase_service=purchase_service,
                reporting_service=reporting_service,
                print_service=print_service,
            )
        else:
            window = CashierMainWindow(
                db_manager=db_mgr,
                current_session=session,
                product_service=product_service,
                billing_service=billing_service,
                reporting_service=reporting_service,
                settings_service=settings_service,
                print_service=print_service,
            )

        window.showMaximized()
        app.exec()

        if not getattr(window, "logged_out", False):
            logger.info("Application closed by user.")
            break

        logger.info(f"User '{session.username}' signed out. Returning to login screen...")

    sys.exit(0)
