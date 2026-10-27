"""
Initial System Setup and Onboarding Wizard Dialog.
Shown on first launch to configure shop profile, GST state, and root Administrator credentials.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox, QGroupBox, QFormLayout, QCheckBox
)

from src.core.database import DatabaseManager
from src.services.db_init_service import setup_initial_shop_and_admin
from src.services.settings_service import BUSINESS_PROFILES_METADATA


INDIAN_STATES = [
    ("33", "Tamil Nadu"),
    ("29", "Karnataka"),
    ("32", "Kerala"),
    ("36", "Telangana"),
    ("37", "Andhra Pradesh"),
    ("27", "Maharashtra"),
    ("07", "Delhi"),
    ("24", "Gujarat"),
    ("09", "Uttar Pradesh"),
    ("19", "West Bengal"),
    ("08", "Rajasthan"),
    ("03", "Punjab"),
    ("06", "Haryana"),
    ("23", "Madhya Pradesh"),
    ("21", "Odisha"),
    ("10", "Bihar"),
]


class OnboardingDialog(QDialog):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager

        self.setWindowTitle("Initial Setup Wizard - AJ Billing Software")
        self.setFixedSize(540, 640)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # Header
        title = QLabel("Welcome to AJ Billing Software")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        layout.addWidget(title)

        subtitle = QLabel("Configure your business profile, GST details, and create your Administrator account.")
        subtitle.setStyleSheet("color: #64748B; font-size: 12px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Shop Details Group
        shop_group = QGroupBox("1. Shop & GST Profile")
        shop_group.setStyleSheet("font-weight: 600; color: #1E293B;")
        form1 = QFormLayout(shop_group)
        form1.setLabelAlignment(Qt.AlignRight)

        self.shop_id_input = QLineEdit()
        self.shop_id_input.setText("SHOP_01")
        self.shop_id_input.setPlaceholderText("e.g. SHOP_01, SHOP_02, SHOP_03 (Assigned by Developer)")
        form1.addRow("Client / Shop License ID *:", self.shop_id_input)

        self.shop_name_input = QLineEdit()
        self.shop_name_input.setPlaceholderText("e.g. Sri Murugan Supermarket")
        form1.addRow("Shop Trade Name *:", self.shop_name_input)

        self.legal_name_input = QLineEdit()
        self.legal_name_input.setPlaceholderText("e.g. Sri Murugan Retail Pvt Ltd")
        form1.addRow("Legal Entity Name:", self.legal_name_input)

        self.gstin_input = QLineEdit()
        self.gstin_input.setPlaceholderText("e.g. 33ABCDE1234F1Z5 (15 digits)")
        self.gstin_input.setMaxLength(15)
        form1.addRow("Shop GSTIN:", self.gstin_input)

        self.state_combo = QComboBox()
        for code, name in INDIAN_STATES:
            self.state_combo.addItem(f"{name} ({code})", (code, name))
        form1.addRow("Home State (POS) *:", self.state_combo)

        self.profile_combo = QComboBox()
        for key, meta in BUSINESS_PROFILES_METADATA.items():
            self.profile_combo.addItem(f"{meta['display_name']}", key)
        form1.addRow("Business Category *:", self.profile_combo)

        layout.addWidget(shop_group)

        # Administrator Credentials Group
        admin_group = QGroupBox("2. Administrator Account")
        admin_group.setStyleSheet("font-weight: 600; color: #1E293B;")
        form2 = QFormLayout(admin_group)
        form2.setLabelAlignment(Qt.AlignRight)

        self.admin_name_input = QLineEdit()
        self.admin_name_input.setPlaceholderText("e.g. Store Manager")
        form2.addRow("Full Name *:", self.admin_name_input)

        self.admin_user_input = QLineEdit()
        self.admin_user_input.setText("admin")
        form2.addRow("Username *:", self.admin_user_input)

        self.admin_pass_input = QLineEdit()
        self.admin_pass_input.setEchoMode(QLineEdit.Password)
        self.admin_pass_input.setPlaceholderText("Minimum 6 characters")
        form2.addRow("Password *:", self.admin_pass_input)

        self.admin_pass_confirm = QLineEdit()
        self.admin_pass_confirm.setEchoMode(QLineEdit.Password)
        self.admin_pass_confirm.setPlaceholderText("Re-type password")
        form2.addRow("Confirm Password *:", self.admin_pass_confirm)

        layout.addWidget(admin_group)

        # Starter Catalog Option
        self.load_catalog_check = QCheckBox("Pre-load starter Supermarket catalog (80+ grocery products, barcodes & GST)")
        self.load_catalog_check.setChecked(True)
        self.load_catalog_check.setStyleSheet("color: #064E3B; font-weight: 600; padding: 4px 0;")
        layout.addWidget(self.load_catalog_check)

        layout.addStretch()

        # Submit button
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.submit_btn = QPushButton("Complete Initial Setup")
        self.submit_btn.setObjectName("PrimaryBtn")
        self.submit_btn.setFixedHeight(40)
        self.submit_btn.setMinimumWidth(200)
        self.submit_btn.clicked.connect(self._handle_setup)
        btn_box.addWidget(self.submit_btn)

        layout.addLayout(btn_box)

    def _handle_setup(self):
        shop_id = self.shop_id_input.text().strip().upper() or "SHOP_01"
        shop_name = self.shop_name_input.text().strip()
        legal_name = self.legal_name_input.text().strip() or shop_name
        gstin = self.gstin_input.text().strip().upper()
        state_code, state_name = self.state_combo.currentData()
        profile_key = self.profile_combo.currentData()

        admin_name = self.admin_name_input.text().strip()
        admin_user = self.admin_user_input.text().strip()
        admin_pass = self.admin_pass_input.text()
        admin_pass_conf = self.admin_pass_confirm.text()

        if not shop_name:
            QMessageBox.warning(self, "Validation Error", "Please enter the shop trade name.")
            self.shop_name_input.setFocus()
            return

        if not admin_name or not admin_user:
            QMessageBox.warning(self, "Validation Error", "Please provide administrator name and username.")
            return

        if len(admin_pass) < 6:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 6 characters long.")
            self.admin_pass_input.setFocus()
            return

        if admin_pass != admin_pass_conf:
            QMessageBox.warning(self, "Validation Error", "Passwords do not match. Please re-enter.")
            self.admin_pass_confirm.clear()
            self.admin_pass_confirm.setFocus()
            return

        try:
            setup_initial_shop_and_admin(
                db_manager=self.db,
                shop_name=shop_name,
                legal_name=legal_name,
                gstin=gstin,
                state_code=state_code,
                state_name=state_name,
                admin_username=admin_user,
                admin_password=admin_pass,
                admin_full_name=admin_name,
                business_profile=profile_key,
            )

            from src.services.settings_service import SettingsService
            SettingsService(self.db).set_cloud_shop_id(shop_id)

            # Auto-seed starter catalog if checked
            if self.load_catalog_check.isChecked():
                try:
                    from src.services.auth_service import UserSession
                    from src.services.master_catalog_service import seed_starter_catalog
                    from src.models import User
                    with self.db.session() as s:
                        admin_u = s.query(User).filter_by(username=admin_user).first()
                        if admin_u:
                            admin_sess = UserSession(admin_u.id, admin_u.username, admin_u.full_name, True, set())
                            seed_starter_catalog(self.db, admin_sess)
                except Exception as cat_err:
                    print(f"Warning: could not seed starter catalog: {cat_err}")

            QMessageBox.information(
                self,
                "Setup Completed",
                f"Shop '{shop_name}' configured successfully!\n"
                f"You can now log in using Administrator username '{admin_user}'."
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Setup Error", f"Failed to initialize shop:\n{exc}")
