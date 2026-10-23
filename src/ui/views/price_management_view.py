"""
Price Management View.
Provides inline retail price/cost management, gross margin calculations,
price history audit dialogs, and bulk price updates by category/brand.
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox, QDoubleSpinBox, QInputDialog
)

from src.services.price_service import PriceService
from src.services.product_service import ProductService
from src.services.auth_service import UserSession
from src.ui.dialogs.bulk_price_update_dialog import BulkPriceUpdateDialog
from src.ui.dialogs.price_history_dialog import PriceHistoryDialog


class PriceManagementView(QWidget):
    def __init__(
        self,
        price_service: PriceService,
        product_service: ProductService,
        current_session: UserSession,
        parent=None,
    ):
        super().__init__(parent)
        self.price_service = price_service
        self.product_service = product_service
        self.current_session = current_session
        self.products: List[Dict[str, Any]] = []

        self._init_ui()
        self._load_filters()
        self.refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Bar
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Price & Margin Management")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Manage wholesale costs, MRPs, retail selling prices, gross margins, and price history audit trails.")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.bulk_btn = QPushButton("⚡ Bulk Price Revision")
        self.bulk_btn.setObjectName("SecondaryBtn")
        self.bulk_btn.setFixedHeight(36)
        self.bulk_btn.clicked.connect(self._handle_bulk_update)
        top_bar.addWidget(self.bulk_btn)

        layout.addLayout(top_bar)

        # Filter Controls Bar
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by product name, SKU, or barcode...")
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.refresh_table)
        filter_bar.addWidget(self.search_input, 3)

        self.cat_filter = QComboBox()
        self.cat_filter.setFixedHeight(36)
        self.cat_filter.addItem("All Categories", None)
        self.cat_filter.currentIndexChanged.connect(self.refresh_table)
        filter_bar.addWidget(self.cat_filter, 2)

        self.brand_filter = QComboBox()
        self.brand_filter.setFixedHeight(36)
        self.brand_filter.addItem("All Brands", None)
        self.brand_filter.currentIndexChanged.connect(self.refresh_table)
        filter_bar.addWidget(self.brand_filter, 2)

        layout.addLayout(filter_bar)

        # Main Price Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Product Name", "SKU", "Category", "Brand", "Cost (₹)", "MRP (₹)", "Selling Price (₹)", "Margin %", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table)

        # Footer Count
        self.count_lbl = QLabel("Showing 0 products")
        self.count_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(self.count_lbl)

    def _load_filters(self):
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        self.cat_filter.addItem("All Categories", None)
        for c in self.product_service.list_categories():
            self.cat_filter.addItem(c["name"], c["id"])
        self.cat_filter.blockSignals(False)

        self.brand_filter.blockSignals(True)
        self.brand_filter.clear()
        self.brand_filter.addItem("All Brands", None)
        for b in self.product_service.list_brands():
            self.brand_filter.addItem(b["name"], b["id"])
        self.brand_filter.blockSignals(False)

    def refresh_table(self):
        query = self.search_input.text().strip()
        cat_id = self.cat_filter.currentData()
        brand_id = self.brand_filter.currentData()

        products, total = self.product_service.search_products(
            query=query,
            category_id=cat_id,
            active_only=False,
            limit=500,
        )

        if brand_id:
            products = [p for p in products if p.get("brand_id") == brand_id or p.get("brand_name") == self.brand_filter.currentText()]

        self.products = products
        self.table.setRowCount(len(products))

        for row, p in enumerate(products):
            # 0. Name
            self.table.setItem(row, 0, QTableWidgetItem(p["name"]))
            # 1. SKU
            self.table.setItem(row, 1, QTableWidgetItem(p["sku"]))
            # 2. Category
            self.table.setItem(row, 2, QTableWidgetItem(p["category_name"]))
            # 3. Brand
            self.table.setItem(row, 3, QTableWidgetItem(p["brand_name"]))
            # 4. Cost
            cost = p["purchase_cost"]
            self.table.setItem(row, 4, QTableWidgetItem(f"₹ {cost:.2f}"))
            # 5. MRP
            mrp = p.get("mrp", p["selling_price"])
            self.table.setItem(row, 5, QTableWidgetItem(f"₹ {mrp:.2f}"))
            # 6. Selling Price
            price = p["selling_price"]
            self.table.setItem(row, 6, QTableWidgetItem(f"₹ {price:.2f}"))

            # 7. Gross Margin % = (Selling - Cost) / Selling * 100
            if price > 0:
                margin_pct = ((price - cost) / price) * 100.0
            else:
                margin_pct = 0.0
            margin_item = QTableWidgetItem(f"{margin_pct:.1f}%")
            if margin_pct < 5.0:
                margin_item.setForeground(Qt.red)
            elif margin_pct > 25.0:
                margin_item.setForeground(Qt.darkGreen)
            self.table.setItem(row, 7, margin_item)

            # 8. Actions Box: Edit Price & View History
            act_box = QWidget()
            act_layout = QHBoxLayout(act_box)
            act_layout.setContentsMargins(6, 4, 6, 4)
            act_layout.setSpacing(6)
            act_layout.setAlignment(Qt.AlignCenter)

            edit_btn = QPushButton("Edit")
            edit_btn.setObjectName("TableActionBtn")
            edit_btn.setFixedHeight(28)
            edit_btn.setMinimumWidth(55)
            edit_btn.clicked.connect(lambda _, prod=p: self._handle_edit_single_price(prod))
            act_layout.addWidget(edit_btn)

            hist_btn = QPushButton("History")
            hist_btn.setObjectName("TableActionBtn")
            hist_btn.setFixedHeight(28)
            hist_btn.setMinimumWidth(65)
            hist_btn.clicked.connect(lambda _, pid=p["id"], name=p["name"]: self._view_history(pid, name))
            act_layout.addWidget(hist_btn)

            self.table.setCellWidget(row, 8, act_box)

        self.count_lbl.setText(f"Showing {len(products)} of {total} products")

    def _handle_edit_single_price(self, p: Dict[str, Any]):
        curr_price = p["selling_price"]
        new_price, ok = QInputDialog.getDouble(
            self,
            f"Update Price: {p['name']}",
            f"Enter new Selling Price (Current: ₹{curr_price:.2f}):",
            float(curr_price),
            0.0,
            1000000.0,
            2,
        )
        if not ok or Decimal(str(new_price)) == Decimal(str(curr_price)):
            return

        reason, ok_r = QInputDialog.getText(
            self,
            "Price Update Reason",
            "Enter reason for price change (for audit history):",
            QLineEdit.Normal,
            "Market Adjustment",
        )
        if not ok_r:
            return

        try:
            self.price_service.update_product_price(
                current_session=self.current_session,
                product_id=p["id"],
                new_selling_price=Decimal(str(new_price)),
                change_reason=reason.strip() or "Market Adjustment",
            )
            QMessageBox.information(self, "Price Updated", f"Price for '{p['name']}' updated to ₹{new_price:.2f}")
            self.refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not update price: {e}")

    def _view_history(self, product_id: int, product_name: str):
        dlg = PriceHistoryDialog(self.price_service, product_id, product_name, parent=self)
        dlg.exec()

    def _handle_bulk_update(self):
        dlg = BulkPriceUpdateDialog(self.price_service, self.product_service, self.current_session, parent=self)
        if dlg.exec():
            self.refresh_table()
