"""
Dedicated Cashier POS Terminal Window.
Streamlined, high-speed interface optimized for cashiers with zero administrative clutter:
- Fast POS Billing (Barcode scanner wedge, multiplier scanning, electronic scale barcodes)
- Shift Receipts & 1-Click Reprint
- Rapid Price & Stock Lookup (without exposing wholesale cost or profit margins)
- Prominent keyboard shortcuts and single-click Sign Out / Shift End.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QLabel, QFrame, QMessageBox
)

from src.core.database import DatabaseManager
from src.services.auth_service import UserSession
from src.services.product_service import ProductService
from src.services.billing_service import BillingService
from src.services.reporting_service import ReportingService
from src.services.settings_service import SettingsService
from src.services.invoice_service import InvoicePrintService

from src.ui.views.billing_view import BillingView
from src.ui.views.sales_view import SalesView
from src.ui.views.price_checker_view import PriceCheckerView


class CashierMainWindow(QMainWindow):
    def __init__(
        self,
        db_manager: DatabaseManager,
        current_session: UserSession,
        product_service: ProductService,
        billing_service: BillingService,
        reporting_service: ReportingService,
        settings_service: SettingsService,
        print_service: InvoicePrintService,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db_manager
        self.current_session = current_session
        self.product_service = product_service
        self.billing_service = billing_service
        self.reporting_service = reporting_service
        self.settings_service = settings_service
        self.print_service = print_service

        self.setWindowTitle(f"POS Cashier Terminal - {self.current_session.full_name}")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 680)

        self._init_ui()
        self._setup_shortcuts()

    def _init_ui(self):
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---------------- Top Cashier Header Bar ----------------
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #064E3B; border-bottom: 2px solid #047857; padding: 8px 16px;")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(12, 6, 12, 6)

        # Shop Brand & Counter Info
        brand_box = QVBoxLayout()
        shop_info = self.settings_service.get_shop_info()
        shop_title = QLabel(f"🛒 {shop_info.get('name', 'Supermarket')} - POS Terminal")
        shop_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #FFFFFF;")
        brand_box.addWidget(shop_title)

        counter_lbl = QLabel(f"Counter #1 | Cashier: {self.current_session.full_name} (@{self.current_session.username})")
        counter_lbl.setStyleSheet("font-size: 12px; color: #A7F3D0; font-weight: 600;")
        brand_box.addWidget(counter_lbl)
        tb_layout.addLayout(brand_box)

        tb_layout.addSpacing(30)

        # Cashier Navigation Tabs
        tab_style = """
            QPushButton {
                background-color: #047857;
                color: #ECFDF5;
                font-weight: 600;
                border-radius: 6px;
                padding: 0 16px;
                border: 1px solid #065F46;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:checked {
                background-color: #10B981;
                color: #FFFFFF;
                font-weight: 700;
                border: 1px solid #34D399;
            }
        """

        self.nav_billing_btn = QPushButton("🛒 Active Billing (F1)")
        self.nav_billing_btn.setCheckable(True)
        self.nav_billing_btn.setChecked(True)
        self.nav_billing_btn.setFixedHeight(38)
        self.nav_billing_btn.setStyleSheet(tab_style)
        self.nav_billing_btn.clicked.connect(lambda: self.switch_cashier_view(0))
        tb_layout.addWidget(self.nav_billing_btn)

        self.nav_receipts_btn = QPushButton("🧾 Shift Bills & Reprint (F6)")
        self.nav_receipts_btn.setCheckable(True)
        self.nav_receipts_btn.setFixedHeight(38)
        self.nav_receipts_btn.setStyleSheet(tab_style)
        self.nav_receipts_btn.clicked.connect(lambda: self.switch_cashier_view(1))
        tb_layout.addWidget(self.nav_receipts_btn)

        self.nav_price_btn = QPushButton("🔍 Price & Stock Check (F7)")
        self.nav_price_btn.setCheckable(True)
        self.nav_price_btn.setFixedHeight(38)
        self.nav_price_btn.setStyleSheet(tab_style)
        self.nav_price_btn.clicked.connect(lambda: self.switch_cashier_view(2))
        tb_layout.addWidget(self.nav_price_btn)

        tb_layout.addStretch()

        # Open Extra Terminal Window
        self.new_terminal_btn = QPushButton("🖥️ New Terminal Window (Ctrl+N)")
        self.new_terminal_btn.setFixedHeight(36)
        self.new_terminal_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #FFFFFF;
                font-weight: 700;
                border-radius: 6px;
                padding: 0 14px;
                border: 1px solid #10B981;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.new_terminal_btn.clicked.connect(self._spawn_new_terminal)
        tb_layout.addWidget(self.new_terminal_btn)

        # Sign Out / End Shift Button
        self.logout_btn = QPushButton("🚪 End Shift / Sign Out")
        self.logout_btn.setFixedHeight(36)
        self.logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                font-weight: 700;
                border-radius: 6px;
                padding: 0 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        self.logout_btn.clicked.connect(self._handle_logout)
        tb_layout.addWidget(self.logout_btn)

        root_layout.addWidget(top_bar)

        # ---------------- Center Stacked Views ----------------
        self.stack = QStackedWidget()

        # 0. POS Billing View
        self.billing_view = BillingView(
            self.billing_service,
            self.product_service,
            self.settings_service,
            self.print_service,
            self.current_session,
        )
        self.stack.addWidget(self.billing_view)

        # 1. Shift Sales & Reprint View
        self.sales_view = SalesView(
            self.billing_service,
            self.reporting_service,
            self.settings_service,
            self.print_service,
            self.current_session,
        )
        self.stack.addWidget(self.sales_view)

        # 2. Quick Price & Stock Checker View
        self.price_checker_view = PriceCheckerView(
            self.product_service,
        )
        self.stack.addWidget(self.price_checker_view)

        root_layout.addWidget(self.stack)

        # ---------------- Bottom Cashier Hotkey Guide Bar ----------------
        shortcut_bar = QFrame()
        shortcut_bar.setStyleSheet("background-color: #ECFDF5; border-top: 1px solid #A7F3D0; padding: 6px 16px;")
        sb_layout = QHBoxLayout(shortcut_bar)
        sb_layout.setContentsMargins(12, 4, 12, 4)

        shortcuts = [
            ("F1", "Active Bill"),
            ("F2", "Scan Barcode"),
            ("F3", "Search Items"),
            ("F4", "Clear Cart"),
            ("F6", "Shift Bills"),
            ("F7", "Price Check"),
            ("F8", "Reprint Receipt"),
            ("F9", "Hold Bill"),
            ("F10", "Recall Bill"),
            ("F12", "Settle Sale"),
        ]

        for key, desc in shortcuts:
            pill = QLabel(f"<b>[{key}]</b> {desc}")
            pill.setStyleSheet("font-size: 11px; color: #065F46; margin-right: 14px;")
            sb_layout.addWidget(pill)

        sb_layout.addStretch()
        root_layout.addWidget(shortcut_bar)

        # Start focused on Billing
        self.switch_cashier_view(0)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F1"), self, lambda: self.switch_cashier_view(0))
        QShortcut(QKeySequence("F6"), self, lambda: self.switch_cashier_view(1))
        QShortcut(QKeySequence("F7"), self, lambda: self.switch_cashier_view(2))
        QShortcut(QKeySequence("Ctrl+N"), self, self._spawn_new_terminal)

    def _spawn_new_terminal(self):
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
        new_win.setWindowTitle(f"POS Cashier Terminal - {self.current_session.full_name} (Window #{len(self._spawned_terminals) + 1})")
        new_win.show()

    def switch_cashier_view(self, index: int):
        self.stack.setCurrentIndex(index)
        self.nav_billing_btn.setChecked(index == 0)
        self.nav_receipts_btn.setChecked(index == 1)
        self.nav_price_btn.setChecked(index == 2)

        if index == 0:
            self.billing_view.barcode_input.setFocus()
        elif index == 1:
            self.sales_view.refresh_sales()
        elif index == 2:
            self.price_checker_view.set_focus_input()

    def _handle_logout(self):
        reply = QMessageBox.question(
            self,
            "End Shift / Sign Out",
            f"Are you sure you want to end shift and sign out, {self.current_session.full_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.logged_out = True
            self.close()
