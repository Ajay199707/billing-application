"""
Bulk Price Revision Dialog with Safety Confirmation Preview.
Allows scheduled or immediate percentage/flat price adjustments across categories and brands.
"""

from decimal import Decimal
from typing import Optional, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QDoubleSpinBox, QMessageBox, QGroupBox, QGridLayout
)

from src.services.price_service import PriceService
from src.services.product_service import ProductService
from src.services.auth_service import UserSession


class BulkPriceUpdateDialog(QDialog):
    def __init__(self, price_service: PriceService, product_service: ProductService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.price_service = price_service
        self.product_service = product_service
        self.current_session = current_session

        self.setWindowTitle("Bulk Price Revision & Safety Preview")
        self.setMinimumSize(850, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._load_filters()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Bulk Price Adjustment")
        header.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        layout.addWidget(header)

        sub = QLabel("Select criteria, configure price adjustments, and review the safety preview before applying changes.")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        layout.addWidget(sub)

        # Config Box
        cfg_group = QGroupBox("Adjustment Configuration")
        grid = QGridLayout(cfg_group)
        grid.setSpacing(10)

        # 1. Target Field
        grid.addWidget(QLabel("Target Price:"), 0, 0)
        self.target_combo = QComboBox()
        self.target_combo.addItem("Selling Price (Retail)", "selling_price")
        self.target_combo.addItem("MRP (Maximum Retail Price)", "mrp")
        self.target_combo.addItem("Purchase Cost (Wholesale)", "purchase_cost")
        grid.addWidget(self.target_combo, 0, 1)

        # 2. Scope / Category Filter
        grid.addWidget(QLabel("Scope (Category):"), 0, 2)
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("All Categories", None)
        grid.addWidget(self.cat_combo, 0, 3)

        # 3. Scope / Brand Filter
        grid.addWidget(QLabel("Scope (Brand):"), 1, 0)
        self.brand_combo = QComboBox()
        self.brand_combo.addItem("All Brands", None)
        grid.addWidget(self.brand_combo, 1, 1)

        # 4. Reason
        grid.addWidget(QLabel("Revision Reason:"), 1, 2)
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("e.g., Annual Inflation Adjustment / Vendor Rate Hike")
        grid.addWidget(self.reason_input, 1, 3)

        # 5. Percentage Change
        grid.addWidget(QLabel("Percentage Change (%):"), 2, 0)
        self.pct_spin = QDoubleSpinBox()
        self.pct_spin.setRange(-90.0, 500.0)
        self.pct_spin.setSingleStep(0.5)
        self.pct_spin.setSuffix(" %")
        grid.addWidget(self.pct_spin, 2, 1)

        # 6. Flat Amount Change
        grid.addWidget(QLabel("Flat Addition / Subtraction (₹):"), 2, 2)
        self.flat_spin = QDoubleSpinBox()
        self.flat_spin.setRange(-10000.0, 10000.0)
        self.flat_spin.setSingleStep(1.0)
        self.flat_spin.setPrefix("₹ ")
        grid.addWidget(self.flat_spin, 2, 3)

        layout.addWidget(cfg_group)

        # Preview Button
        preview_btn_bar = QHBoxLayout()
        self.preview_btn = QPushButton("🔍 Calculate Safety Preview")
        self.preview_btn.setObjectName("SecondaryBtn")
        self.preview_btn.setFixedHeight(34)
        self.preview_btn.clicked.connect(self._handle_preview)
        preview_btn_bar.addWidget(self.preview_btn)
        preview_btn_bar.addStretch()

        self.summary_lbl = QLabel("0 products will be affected.")
        self.summary_lbl.setStyleSheet("font-weight: 600; color: #2563EB;")
        preview_btn_bar.addWidget(self.summary_lbl)
        layout.addLayout(preview_btn_bar)

        # Preview Table
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(7)
        self.preview_table.setHorizontalHeaderLabels([
            "Product Name", "SKU", "Category", "Brand", "Current (₹)", "Proposed (₹)", "Diff (₹)"
        ])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.preview_table)

        # Bottom Buttons
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("SecondaryBtn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_bar.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Confirm & Apply Price Revisions")
        self.apply_btn.setObjectName("PrimaryBtn")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._handle_apply)
        btn_bar.addWidget(self.apply_btn)

        layout.addLayout(btn_bar)

    def _load_filters(self):
        cats = self.product_service.list_categories()
        for c in cats:
            self.cat_combo.addItem(c["name"], c["id"])

        brands = self.product_service.list_brands()
        for b in brands:
            self.brand_combo.addItem(b["name"], b["id"])

    def _handle_preview(self):
        target_fld = self.target_combo.currentData()
        cat_id = self.cat_combo.currentData()
        brand_id = self.brand_combo.currentData()
        pct = Decimal(str(self.pct_spin.value()))
        flat = Decimal(str(self.flat_spin.value()))

        if pct == Decimal("0.00") and flat == Decimal("0.00"):
            QMessageBox.warning(self, "No Change Configured", "Please enter a non-zero percentage or flat adjustment amount.")
            return

        previews = self.price_service.preview_bulk_updates(
            category_id=cat_id,
            brand_id=brand_id,
            percent_change=pct,
            flat_change=flat,
            target_field=target_fld,
        )

        self.preview_table.setRowCount(len(previews))
        for row, item in enumerate(previews):
            self.preview_table.setItem(row, 0, QTableWidgetItem(item["name"]))
            self.preview_table.setItem(row, 1, QTableWidgetItem(item["sku"]))
            self.preview_table.setItem(row, 2, QTableWidgetItem(item["category"]))
            self.preview_table.setItem(row, 3, QTableWidgetItem(item["brand"]))
            self.preview_table.setItem(row, 4, QTableWidgetItem(f"{item['old_val']:.2f}"))

            new_val_item = QTableWidgetItem(f"{item['new_val']:.2f}")
            new_val_item.setForeground(Qt.darkGreen if item["difference"] >= 0 else Qt.darkRed)
            self.preview_table.setItem(row, 5, new_val_item)

            diff_item = QTableWidgetItem(f"{item['difference']:+.2f}")
            diff_item.setForeground(Qt.darkGreen if item["difference"] >= 0 else Qt.darkRed)
            self.preview_table.setItem(row, 6, diff_item)

        self.summary_lbl.setText(f"Preview ready: {len(previews)} products will be updated.")
        self.apply_btn.setEnabled(len(previews) > 0)

    def _handle_apply(self):
        reply = QMessageBox.question(
            self,
            "Confirm Price Revision",
            f"Are you sure you want to apply these price revisions to {self.preview_table.rowCount()} products?\n"
            "This will create an auditable Price History entry for each product.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        target_fld = self.target_combo.currentData()
        cat_id = self.cat_combo.currentData()
        brand_id = self.brand_combo.currentData()
        pct = Decimal(str(self.pct_spin.value()))
        flat = Decimal(str(self.flat_spin.value()))
        reason = self.reason_input.text().strip() or "Bulk Price Revision"

        try:
            count = self.price_service.apply_bulk_updates(
                current_session=self.current_session,
                category_id=cat_id,
                brand_id=brand_id,
                percent_change=pct,
                flat_change=flat,
                target_field=target_fld,
                change_reason=reason,
            )
            QMessageBox.information(self, "Success", f"Successfully revised prices for {count} products.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply price revisions: {e}")
