"""
Main Desktop Application Window with Sidebar Navigation Drawer and View Stack.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStackedWidget, QLabel, QFrame, QMessageBox
)

from src.core.database import DatabaseManager
from src.services.auth_service import AuthService, UserSession
from src.services.product_service import ProductService
from src.services.inventory_service import InventoryService
from src.services.billing_service import BillingService
from src.services.purchase_service import PurchaseService
from src.services.reporting_service import ReportingService
from src.services.settings_service import SettingsService
from src.services.invoice_service import InvoicePrintService
from src.services.backup_service import BackupService
from src.services.price_service import PriceService

from src.ui.views.dashboard_view import DashboardView
from src.ui.views.billing_view import BillingView
from src.ui.views.products_view import ProductsView
from src.ui.views.price_management_view import PriceManagementView
from src.ui.views.inventory_view import InventoryView
from src.ui.views.purchases_view import PurchasesView
from src.ui.views.sales_view import SalesView
from src.ui.views.reports_view import ReportsView
from src.ui.views.users_view import UsersView
from src.ui.views.settings_view import SettingsView
from src.ui.views.backup_view import BackupView


class MainWindow(QMainWindow):
    def __init__(
        self,
        db_manager: DatabaseManager,
        current_session: UserSession,
        auth_service: AuthService,
        settings_service: SettingsService,
        product_service: ProductService,
        inventory_service: InventoryService,
        billing_service: BillingService,
        purchase_service: PurchaseService,
        reporting_service: ReportingService,
        print_service: InvoicePrintService,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db_manager
        self.current_session = current_session
        self.auth_service = auth_service
        self.settings_service = settings_service
        self.product_service = product_service
        self.inventory_service = inventory_service
        self.billing_service = billing_service
        self.purchase_service = purchase_service
        self.reporting_service = reporting_service
        self.print_service = print_service

        self.setWindowTitle("AJ Billing Software - Retail Billing, Inventory & Shop Management")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 620)

        self.nav_buttons = []
        self._init_ui()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, self._trigger_auto_sync_on_startup)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---------------- Left Sidebar ----------------
        sidebar = QFrame()
        sidebar.setObjectName("SidebarWidget")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(8, 10, 8, 10)
        side_layout.setSpacing(2)

        # App Brand Header
        brand_lbl = QLabel("AJ BILLING POS")
        brand_lbl.setStyleSheet("color: #064E3B; font-size: 15px; font-weight: 800; padding: 6px 12px; letter-spacing: 1px;")
        side_layout.addWidget(brand_lbl)

        role_str = "Administrator" if self.current_session.is_admin else "Cashier"
        user_lbl = QLabel(f"👤 {self.current_session.full_name} ({role_str})")
        user_lbl.setStyleSheet("color: #047857; font-size: 11px; padding: 0 12px 12px 12px;")
        side_layout.addWidget(user_lbl)

        # Navigation Items (Text, Index, Required Permission)
        nav_items = [
            ("📊  Dashboard", 0, "reports:view"),
            ("🛒  Billing / POS", 1, "pos:checkout"),
            ("📦  Products", 2, "products:view"),
            ("💰  Price Management", 3, "products:manage"),
            ("📈  Inventory", 4, "inventory:view"),
            ("📥  Purchases", 5, "purchases:view"),
            ("🧾  Sales History", 6, "pos:reprint"),
            ("📑  Reports & Tax", 7, "reports:view"),
            ("👥  User Management", 8, "users:manage"),
            ("⚙️  Shop Settings", 9, "settings:manage"),
            ("💾  Backup & Restore", 10, "backup:manage"),
        ]

        for label, idx, perm in nav_items:
            # Check permissions
            if not self.current_session.has_permission(perm) and not self.current_session.is_admin:
                continue

            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, i=idx: self.switch_view(i))
            side_layout.addWidget(btn)
            self.nav_buttons.append((idx, btn))

        side_layout.addStretch()

        # Open Dedicated Cashier Window
        new_term_btn = QPushButton("🖥️  Open POS Terminal")
        new_term_btn.setObjectName("SecondaryBtn")
        new_term_btn.setToolTip("Open an independent Cashier POS terminal window (Ctrl+N)")
        new_term_btn.setStyleSheet("""
            QPushButton {
                background-color: #D1FAE5;
                color: #065F46;
                font-weight: 700;
                border: 1px solid #A7F3D0;
                border-radius: 6px;
                padding: 8px 14px;
                margin: 4px 8px;
            }
            QPushButton:hover {
                background-color: #A7F3D0;
                color: #064E3B;
            }
        """)
        new_term_btn.clicked.connect(self._spawn_cashier_terminal)
        side_layout.addWidget(new_term_btn)

        # Logout Button
        logout_btn = QPushButton("🚪  Sign Out")
        logout_btn.setObjectName("SecondaryBtn")
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                color: #DC2626;
                font-weight: 700;
                border: 1px solid #FECACA;
                border-radius: 6px;
                padding: 8px 14px;
                margin: 4px 8px;
            }
            QPushButton:hover {
                background-color: #FECACA;
                color: #B91C1C;
            }
        """)
        logout_btn.clicked.connect(self._handle_logout)
        side_layout.addWidget(logout_btn)

        root_layout.addWidget(sidebar)

        # ---------------- Right Stacked Views ----------------
        self.stack = QStackedWidget()

        # 0. Dashboard
        self.dashboard_view = DashboardView(self.reporting_service, self.settings_service)
        self.stack.addWidget(self.dashboard_view)

        # 1. Billing / POS
        self.billing_view = BillingView(
            self.billing_service, self.product_service, self.settings_service, self.print_service, self.current_session
        )
        self.stack.addWidget(self.billing_view)

        # 2. Products
        self.products_view = ProductsView(self.product_service, self.current_session)
        self.stack.addWidget(self.products_view)

        # 3. Price Management
        self.price_service = PriceService(self.db)
        self.price_view = PriceManagementView(
            self.price_service, self.product_service, self.current_session
        )
        self.stack.addWidget(self.price_view)

        # 4. Inventory
        self.inventory_view = InventoryView(self.inventory_service, self.product_service, self.current_session)
        self.stack.addWidget(self.inventory_view)

        # 5. Purchases
        self.purchases_view = PurchasesView(self.purchase_service, self.product_service, self.current_session)
        self.stack.addWidget(self.purchases_view)

        # 6. Sales History
        self.sales_view = SalesView(
            self.billing_service, self.reporting_service, self.settings_service, self.print_service, self.current_session
        )
        self.stack.addWidget(self.sales_view)

        # 7. Reports & Tax
        self.reports_view = ReportsView(self.reporting_service)
        self.stack.addWidget(self.reports_view)

        # 8. User Management
        self.users_view = UsersView(self.auth_service, self.current_session)
        self.stack.addWidget(self.users_view)

        # 9. Settings
        self.settings_view = SettingsView(self.settings_service, self.db, self.current_session)
        self.stack.addWidget(self.settings_view)

        # 10. Backup & Restore
        self.backup_service = BackupService(self.db)
        self.backup_view = BackupView(self.backup_service, self.current_session)
        self.stack.addWidget(self.backup_view)

        root_layout.addWidget(self.stack)

        # Select first view (POS for Cashier, Dashboard for Admin)
        start_idx = 0 if self.current_session.is_admin else 1
        self.switch_view(start_idx)

        # Global shortcut to spawn a separate POS Terminal window
        QShortcut(QKeySequence("Ctrl+N"), self, self._spawn_cashier_terminal)

    def switch_view(self, index: int):
        self.stack.setCurrentIndex(index)
        for idx, btn in self.nav_buttons:
            btn.setChecked(idx == index)

        # Refresh active view
        if index == 0:
            self.dashboard_view.refresh_metrics()
        elif index == 1:
            self.billing_view.barcode_input.setFocus()
        elif index == 2:
            self.products_view.refresh_products()
        elif index == 3:
            self.price_view.refresh_table()
        elif index == 4:
            self.inventory_view.refresh_all()
        elif index == 5:
            self.purchases_view.refresh_purchases()
        elif index == 6:
            self.sales_view.refresh_sales()
        elif index == 7:
            self.reports_view.refresh_all_reports()
        elif index == 8:
            self.users_view.refresh_users()
        elif index == 9:
            self.settings_view.load_settings()
        elif index == 10:
            self.backup_view.refresh_backups()

    def _spawn_cashier_terminal(self):
        from src.ui.cashier_window import CashierMainWindow
        if not hasattr(self, "_spawned_terminals"):
            self._spawned_terminals = []
        new_win = CashierMainWindow(
            db_manager=self.db,
            current_session=self.current_session,
            product_service=self.product_service,
            billing_service=self.billing_service,
            reporting_service=self.reporting_service,
            settings_service=self.settings_service,
            print_service=self.print_service,
        )
        self._spawned_terminals.append(new_win)
        new_win.setWindowTitle(f"POS Cashier Terminal (Opened by {self.current_session.full_name})")
        new_win.show()

    def _handle_logout(self):
        reply = QMessageBox.question(
            self, "Sign Out", "Are you sure you want to sign out?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.logged_out = True
            self.close()

    def _trigger_auto_sync_on_startup(self):
        """Asynchronously checks GitHub for new catalog items and shop price updates."""
        from concurrent.futures import ThreadPoolExecutor
        from PySide6.QtCore import QTimer
        from src.services.cloud_sync_service import run_auto_sync_on_startup

        shop_id = "SHOP_01"
        try:
            shop_id = self.settings_service.get_cloud_shop_id()
        except Exception:
            pass

        def _worker():
            try:
                return run_auto_sync_on_startup(
                    db_manager=self.db,
                    current_session=self.current_session,
                    shop_id=shop_id,
                )
            except Exception as e:
                return {"success": False, "error": str(e)}

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_worker)

        def _check_result():
            if future.done():
                try:
                    res = future.result()
                    if res.get("success") and (res.get("new_products", 0) > 0 or res.get("shop_prices_updated", 0) > 0 or res.get("shop_products_created", 0) > 0):
                        msg = f"☁️ {res.get('message', 'Cloud Sync Complete')}"
                        self.statusBar().showMessage(msg, 12000)
                        curr_widget = self.stack.currentWidget()
                        if hasattr(curr_widget, "refresh_products"):
                            curr_widget.refresh_products()
                        elif hasattr(curr_widget, "update_totals"):
                            curr_widget.update_totals()
                except Exception:
                    pass
                poll_timer.stop()

        poll_timer = QTimer(self)
        poll_timer.setInterval(500)
        poll_timer.timeout.connect(_check_result)
        poll_timer.start()
