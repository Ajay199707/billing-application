"""
Settings and Configuration View.
Manages Shop Profile, Business Category rules, Receipt Formatting,
and Multi-Computer PostgreSQL Connection configuration.
"""

from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QComboBox, QCheckBox, QDoubleSpinBox,
    QTextEdit, QMessageBox, QGroupBox, QFormLayout, QStackedWidget, QFrame
)

from src.core.config import DatabaseMode, AppConfig
from src.core.database import DatabaseManager
from src.services.settings_service import SettingsService, BUSINESS_PROFILES_METADATA
from src.services.auth_service import UserSession


class SettingsView(QWidget):
    def __init__(
        self,
        settings_service: SettingsService,
        db_manager: DatabaseManager,
        current_session: UserSession,
        parent=None,
    ):
        super().__init__(parent)
        self.settings_service = settings_service
        self.db = db_manager
        self.current_session = current_session

        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("System Configuration & Shop Settings")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Configure trade profile, receipt print layouts, and multi-workstation database networking")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.save_btn = QPushButton("💾 Save All Settings")
        self.save_btn.setObjectName("PrimaryBtn")
        self.save_btn.setFixedHeight(36)
        self.save_btn.clicked.connect(self._handle_save)
        top_bar.addWidget(self.save_btn)

        layout.addLayout(top_bar)

        # Tabs: 1. Shop Profile, 2. Database & Networking
        self.tabs = QTabWidget()

        # Tab 1: Shop Profile
        tab1 = QWidget()
        t1_layout = QVBoxLayout(tab1)
        form1 = QFormLayout()
        form1.setLabelAlignment(Qt.AlignRight)

        self.shop_name_input = QLineEdit()
        form1.addRow("Shop Trade Name *:", self.shop_name_input)

        self.legal_name_input = QLineEdit()
        form1.addRow("Legal Entity Name:", self.legal_name_input)

        self.gstin_input = QLineEdit()
        self.gstin_input.setMaxLength(15)
        form1.addRow("GSTIN (Tax ID):", self.gstin_input)

        self.phone_input = QLineEdit()
        form1.addRow("Contact Phone:", self.phone_input)

        self.email_input = QLineEdit()
        form1.addRow("Contact Email:", self.email_input)

        self.address_input = QLineEdit()
        form1.addRow("Address Line 1:", self.address_input)

        self.city_input = QLineEdit()
        form1.addRow("City / Town:", self.city_input)

        self.state_code_input = QLineEdit()
        self.state_code_input.setMaxLength(2)
        form1.addRow("State Code (e.g. 33 for TN):", self.state_code_input)

        self.profile_combo = QComboBox()
        for k, meta in BUSINESS_PROFILES_METADATA.items():
            self.profile_combo.addItem(f"{meta['display_name']} - {meta['description']}", k)
        form1.addRow("Business Category *:", self.profile_combo)

        self.prefix_input = QLineEdit()
        form1.addRow("Invoice Prefix:", self.prefix_input)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["80mm", "58mm", "A4"])
        form1.addRow("Default Receipt Paper Size:", self.format_combo)

        self.neg_stock_check = QCheckBox("Allow negative stock (Permits sales when inventory is 0)")
        form1.addRow("Stock Policy:", self.neg_stock_check)

        self.footer_input = QTextEdit()
        self.footer_input.setFixedHeight(50)
        form1.addRow("Receipt Footer Message:", self.footer_input)

        t1_layout.addLayout(form1)
        t1_layout.addStretch()
        self.tabs.addTab(tab1, "Shop & Business Profile")

        # Tab 2: Database Connectivity & Multi-Computer
        tab2 = QWidget()
        t2_layout = QVBoxLayout(tab2)
        form2 = QFormLayout()
        form2.setLabelAlignment(Qt.AlignRight)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Single Computer - SQLite WAL (Zero Setup)", DatabaseMode.SINGLE_SQLITE)
        self.mode_combo.addItem("Single Computer - Local PostgreSQL Server", DatabaseMode.LOCAL_POSTGRES)
        self.mode_combo.addItem("Multi-Computer - Shared Network PostgreSQL Server", DatabaseMode.REMOTE_POSTGRES)
        self.mode_combo.currentIndexChanged.connect(self._toggle_db_inputs)
        form2.addRow("Deployment Mode *:", self.mode_combo)

        self.host_input = QLineEdit("localhost")
        form2.addRow("Database Host (IP / Server Name):", self.host_input)

        self.port_input = QLineEdit("5432")
        form2.addRow("Port Number:", self.port_input)

        self.db_name_input = QLineEdit("billing_db")
        form2.addRow("Database Name:", self.db_name_input)

        self.user_input = QLineEdit("postgres")
        form2.addRow("Database Username:", self.user_input)

        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setPlaceholderText("Leave unchanged to preserve stored password")
        form2.addRow("Database Password:", self.pass_input)

        t2_layout.addLayout(form2)

        # Connection Test Button and Status Label
        test_box = QHBoxLayout()
        self.test_btn = QPushButton("Test Database Connection")
        self.test_btn.setObjectName("SecondaryBtn")
        self.test_btn.clicked.connect(self._handle_test_connection)
        test_box.addWidget(self.test_btn)

        self.test_status_lbl = QLabel()
        self.test_status_lbl.setStyleSheet("font-weight: 600;")
        test_box.addWidget(self.test_status_lbl)
        test_box.addStretch()
        t2_layout.addLayout(test_box)

        t2_layout.addStretch()
        self.tabs.addTab(tab2, "Database & Multi-Workstation")

        # Tab 3: Developer & Cloud Administration (Protected by Master PIN)
        tab3 = QWidget()
        t3_layout = QVBoxLayout(tab3)
        t3_layout.setContentsMargins(16, 16, 16, 16)
        t3_layout.setSpacing(14)

        self.dev_stack = QStackedWidget()

        # Page 0: Locked State
        lock_page = QWidget()
        lock_layout = QVBoxLayout(lock_page)
        lock_layout.setAlignment(Qt.AlignCenter)

        lock_card = QFrame()
        lock_card.setStyleSheet("background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 24px;")
        card_layout = QVBoxLayout(lock_card)
        card_layout.setSpacing(12)

        lock_title = QLabel("🔒 Developer Administration Area")
        lock_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        lock_title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(lock_title)

        lock_desc = QLabel(
            "This configuration area is restricted to the Developer / Software Provider.\n"
            "It configures client license IDs, multi-tenant databases, and MongoDB sync."
        )
        lock_desc.setStyleSheet("font-size: 12px; color: #64748B;")
        lock_desc.setAlignment(Qt.AlignCenter)
        lock_desc.setWordWrap(True)
        card_layout.addWidget(lock_desc)

        pin_box = QHBoxLayout()
        pin_lbl = QLabel("Developer PIN:")
        pin_lbl.setStyleSheet("font-weight: 600; color: #1E293B;")
        self.dev_pin_input = QLineEdit()
        self.dev_pin_input.setEchoMode(QLineEdit.Password)
        self.dev_pin_input.setPlaceholderText("Enter Developer PIN")
        self.dev_pin_input.setMaximumWidth(180)
        self.dev_pin_input.returnPressed.connect(self._handle_unlock_developer)
        pin_box.addStretch()
        pin_box.addWidget(pin_lbl)
        pin_box.addWidget(self.dev_pin_input)
        pin_box.addStretch()
        card_layout.addLayout(pin_box)

        self.dev_unlock_btn = QPushButton("Unlock Developer Settings")
        self.dev_unlock_btn.setObjectName("PrimaryBtn")
        self.dev_unlock_btn.setFixedHeight(36)
        self.dev_unlock_btn.clicked.connect(self._handle_unlock_developer)
        card_layout.addWidget(self.dev_unlock_btn)

        self.dev_lock_status = QLabel("")
        self.dev_lock_status.setStyleSheet("color: #DC2626; font-size: 11px; font-weight: 600;")
        self.dev_lock_status.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.dev_lock_status)

        lock_layout.addWidget(lock_card)
        self.dev_stack.addWidget(lock_page)

        # Page 1: Unlocked State
        unlocked_page = QWidget()
        unlocked_layout = QVBoxLayout(unlocked_page)
        unlocked_layout.setContentsMargins(0, 0, 0, 0)
        unlocked_layout.setSpacing(12)

        # Header Bar
        dev_bar = QHBoxLayout()
        dev_badge = QLabel("🔓 Developer Mode Active — Software Provider Access")
        dev_badge.setStyleSheet("color: #047857; font-weight: 700; font-size: 13px;")
        dev_bar.addWidget(dev_badge)
        dev_bar.addStretch()

        self.dev_relock_btn = QPushButton("🔒 Re-Lock")
        self.dev_relock_btn.setObjectName("SecondaryBtn")
        self.dev_relock_btn.setFixedHeight(30)
        self.dev_relock_btn.clicked.connect(self._handle_relock_developer)
        dev_bar.addWidget(self.dev_relock_btn)
        unlocked_layout.addLayout(dev_bar)

        # Client Identifier
        id_group = QGroupBox("1. Independent Client / Shop License Identification")
        id_group.setStyleSheet("font-weight: 600; color: #1E293B;")
        form_id = QFormLayout(id_group)
        self.cloud_shop_id_input = QLineEdit()
        self.cloud_shop_id_input.setPlaceholderText("e.g. SHOP_01, SHOP_02, SHOP_03")
        form_id.addRow("Client / Shop License ID *:", self.cloud_shop_id_input)
        id_hint = QLabel("Unique identifier assigned to this independent client shop. Used for sales partitioning and remote catalog updates.")
        id_hint.setStyleSheet("font-size: 11px; color: #64748B; font-weight: normal;")
        form_id.addRow("", id_hint)
        unlocked_layout.addWidget(id_group)

        # MongoDB Cloud Sync Group
        mongo_group = QGroupBox("2. Central MongoDB Cloud Database Sync")
        mongo_group.setStyleSheet("font-weight: 600; color: #1E293B;")
        form_m = QFormLayout(mongo_group)

        self.mongo_enable_check = QCheckBox("Enable Background MongoDB Cloud Sync")
        self.mongo_enable_check.setStyleSheet("color: #059669; font-weight: 700;")
        form_m.addRow("", self.mongo_enable_check)

        self.mongo_uri_input = QLineEdit()
        self.mongo_uri_input.setPlaceholderText("e.g. mongodb+srv://username:password@cluster0.mongodb.net/")
        form_m.addRow("MongoDB Atlas URI:", self.mongo_uri_input)

        self.mongo_db_input = QLineEdit("aj_billing_cloud")
        form_m.addRow("Database Name:", self.mongo_db_input)

        m_test_box = QHBoxLayout()
        self.mongo_test_btn = QPushButton("Test MongoDB Connection")
        self.mongo_test_btn.setObjectName("SecondaryBtn")
        self.mongo_test_btn.clicked.connect(self._handle_test_mongo)
        m_test_box.addWidget(self.mongo_test_btn)

        self.mongo_test_lbl = QLabel()
        self.mongo_test_lbl.setStyleSheet("font-weight: 600;")
        m_test_box.addWidget(self.mongo_test_lbl)
        m_test_box.addStretch()
        form_m.addRow("", m_test_box)

        m_desc = QLabel(
            "💡 When enabled, every completed bill and stock update is automatically synced to your central MongoDB Atlas cluster in the background.\n"
            "• Local POS checkout stays 100% offline and instant (zero lag).\n"
            "• Records in MongoDB are partitioned by 'client_id' and tagged with the shop's trade name."
        )
        m_desc.setStyleSheet("font-size: 11px; color: #475569; font-weight: normal; padding: 6px 0;")
        m_desc.setWordWrap(True)
        form_m.addRow("", m_desc)

        unlocked_layout.addWidget(mongo_group)
        unlocked_layout.addStretch()

        self.dev_stack.addWidget(unlocked_page)
        t3_layout.addWidget(self.dev_stack)
        self.tabs.addTab(tab3, "Developer & Cloud")

        layout.addWidget(self.tabs)

    def load_settings(self):
        try:
            shop = self.settings_service.get_shop_info()
            self.shop_name_input.setText(shop.get("name", ""))
            self.legal_name_input.setText(shop.get("legal_name", ""))
            self.gstin_input.setText(shop.get("gstin", ""))
            self.phone_input.setText(shop.get("phone", ""))
            self.email_input.setText(shop.get("email", ""))
            self.address_input.setText(shop.get("address_line1", ""))
            self.city_input.setText(shop.get("city", ""))
            self.state_code_input.setText(shop.get("state_code", "33"))
            self.prefix_input.setText(shop.get("invoice_prefix", "INV-"))
            self.footer_input.setPlainText(shop.get("invoice_footer_text", ""))
            self.neg_stock_check.setChecked(shop.get("enable_negative_stock", False))

            idx = self.profile_combo.findData(shop.get("business_profile", "general"))
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)

            idx_f = self.format_combo.findText(shop.get("receipt_format", "80mm"))
            if idx_f >= 0:
                self.format_combo.setCurrentIndex(idx_f)

            # DB config
            cfg = self.db.config
            db_idx = self.mode_combo.findData(cfg.mode)
            if db_idx >= 0:
                self.mode_combo.setCurrentIndex(db_idx)
            self.host_input.setText(cfg.host)
            self.port_input.setText(str(cfg.port))
            self.db_name_input.setText(cfg.database)
            self.user_input.setText(cfg.username)

            self._toggle_db_inputs()

            # Load Shop Code & MongoDB Config
            try:
                self.cloud_shop_id_input.setText(self.settings_service.get_cloud_shop_id())
                from src.services.mongo_service import MongoSyncService
                m_cfg = MongoSyncService(self.db).get_config()
                self.mongo_enable_check.setChecked(m_cfg.get("enabled", False))
                self.mongo_uri_input.setText(m_cfg.get("uri", ""))
                self.mongo_db_input.setText(m_cfg.get("database_name", "aj_billing_cloud"))
            except Exception:
                pass

        except Exception as e:
            pass

    def _toggle_db_inputs(self):
        mode = self.mode_combo.currentData()
        is_pg = (mode != DatabaseMode.SINGLE_SQLITE)
        self.host_input.setEnabled(is_pg)
        self.port_input.setEnabled(is_pg)
        self.db_name_input.setEnabled(is_pg)
        self.user_input.setEnabled(is_pg)
        self.pass_input.setEnabled(is_pg)

    def _handle_test_connection(self):
        ok, msg = self.db.test_connection()
        if ok:
            self.test_status_lbl.setText("✓ Database connection verified successfully!")
            self.test_status_lbl.setStyleSheet("color: #16A34A; font-weight: 600;")
        else:
            self.test_status_lbl.setText(f"✕ Connection failed: {msg}")
            self.test_status_lbl.setStyleSheet("color: #DC2626; font-weight: 600;")

    def _handle_save(self):
        details = {
            "name": self.shop_name_input.text().strip(),
            "legal_name": self.legal_name_input.text().strip(),
            "gstin": self.gstin_input.text().strip().upper(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "address_line1": self.address_input.text().strip(),
            "city": self.city_input.text().strip(),
            "state_code": self.state_code_input.text().strip(),
            "business_profile": self.profile_combo.currentData(),
            "invoice_prefix": self.prefix_input.text().strip(),
            "receipt_format": self.format_combo.currentText(),
            "enable_negative_stock": self.neg_stock_check.isChecked(),
            "invoice_footer_text": self.footer_input.toPlainText().strip(),
        }

        try:
            self.settings_service.update_shop_details(self.current_session, details)
            if hasattr(self, "cloud_shop_id_input") and self.cloud_shop_id_input.text().strip():
                self.settings_service.set_cloud_shop_id(self.cloud_shop_id_input.text().strip())

            # Save MongoDB Configuration
            if hasattr(self, "mongo_uri_input"):
                from src.services.mongo_service import MongoSyncService
                MongoSyncService(self.db).save_config(
                    uri=self.mongo_uri_input.text().strip(),
                    database_name=self.mongo_db_input.text().strip(),
                    enabled=self.mongo_enable_check.isChecked(),
                )

            QMessageBox.information(self, "Settings Saved", "System and Shop configuration updated successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Settings", str(e))

    def _handle_test_mongo(self):
        from src.services.mongo_service import MongoSyncService
        uri = self.mongo_uri_input.text().strip()
        ok, msg = MongoSyncService(self.db).test_connection(uri)
        if ok:
            self.mongo_test_lbl.setText(f"✓ {msg}")
            self.mongo_test_lbl.setStyleSheet("color: #16A34A; font-weight: 600;")
        else:
            self.mongo_test_lbl.setText(f"✕ {msg}")
            self.mongo_test_lbl.setStyleSheet("color: #DC2626; font-weight: 600;")

    def _handle_unlock_developer(self):
        entered_pin = self.dev_pin_input.text().strip()
        if entered_pin in ("9988", "1234"):
            self.dev_lock_status.setText("")
            self.dev_pin_input.clear()
            self.dev_stack.setCurrentIndex(1)
        else:
            self.dev_lock_status.setText("Invalid Developer PIN. Access denied.")
            self.dev_pin_input.clear()
            self.dev_pin_input.setFocus()

    def _handle_relock_developer(self):
        self.dev_stack.setCurrentIndex(0)
        self.dev_lock_status.setText("")
