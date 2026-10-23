"""
Inventory Balances and Auditable Stock Movement Ledger View.
Includes physical stock count corrections and damaged/expired stock write-offs.
"""

from decimal import Decimal
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QComboBox, QDoubleSpinBox, QTextEdit, QMessageBox, QFormLayout
)

from src.services.inventory_service import InventoryService
from src.services.product_service import ProductService
from src.services.auth_service import UserSession


class StockAdjustmentDialog(QDialog):
    def __init__(self, product_service: ProductService, inventory_service: InventoryService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.product_service = product_service
        self.inventory_service = inventory_service
        self.current_session = current_session

        self.setWindowTitle("Manual Stock Adjustment / Correction")
        self.setFixedSize(450, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()

        self.product_combo = QComboBox()
        prods, _ = self.product_service.search_products(limit=500)
        for p in prods:
            self.product_combo.addItem(f"{p['name']} (Stock: {p['quantity_on_hand']:.2f})", p["id"])
        form.addRow("Select Product *:", self.product_combo)

        self.reason_combo = QComboBox()
        self.reason_combo.addItems(["CORRECTION", "DAMAGE", "EXPIRY", "PHYSICAL_COUNT"])
        form.addRow("Adjustment Reason *:", self.reason_combo)

        self.new_qty_spin = QDoubleSpinBox()
        self.new_qty_spin.setRange(0, 100000)
        self.new_qty_spin.setDecimals(3)
        form.addRow("Actual Physical Count *:", self.new_qty_spin)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Provide reason or audit notes...")
        self.notes_input.setFixedHeight(70)
        form.addRow("Notes / Audit Trail:", self.notes_input)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Commit Adjustment")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._handle_save)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def _handle_save(self):
        prod_id = self.product_combo.currentData()
        reason = self.reason_combo.currentText()
        new_qty = Decimal(str(self.new_qty_spin.value()))
        notes = self.notes_input.toPlainText().strip()

        if not prod_id:
            QMessageBox.warning(self, "Validation Error", "Please select a product.")
            return

        try:
            self.inventory_service.perform_stock_adjustment(
                current_session=self.current_session,
                product_id=prod_id,
                new_quantity=new_qty,
                reason=reason,
                notes=notes,
            )
            QMessageBox.information(self, "Success", "Stock adjustment recorded in audit ledger.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Adjustment Error", str(e))


class InventoryView(QWidget):
    def __init__(
        self,
        inventory_service: InventoryService,
        product_service: ProductService,
        current_session: UserSession,
        parent=None,
    ):
        super().__init__(parent)
        self.inventory_service = inventory_service
        self.product_service = product_service
        self.current_session = current_session

        self._init_ui()
        self.refresh_all()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Bar
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Inventory Control & Stock Ledger")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Track real-time stock balances and immutable audit movement logs")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.adjust_btn = QPushButton("✎ Adjust Stock / Physical Count")
        self.adjust_btn.setObjectName("PrimaryBtn")
        self.adjust_btn.clicked.connect(self._open_adjustment_dialog)
        top_bar.addWidget(self.adjust_btn)

        layout.addLayout(top_bar)

        # Tabs: 1. Balances, 2. Ledger
        self.tabs = QTabWidget()

        # Tab 1: Current Balances
        tab1 = QWidget()
        t1_layout = QVBoxLayout(tab1)
        self.balance_table = QTableWidget()
        self.balance_table.setColumnCount(6)
        self.balance_table.setHorizontalHeaderLabels([
            "Product Name", "SKU", "Available Stock", "Reorder Level", "Unit", "Status"
        ])
        self.balance_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.balance_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.balance_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.balance_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.balance_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.balance_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.balance_table.verticalHeader().setDefaultSectionSize(36)
        self.balance_table.verticalHeader().setVisible(False)
        t1_layout.addWidget(self.balance_table)
        self.tabs.addTab(tab1, "Stock Balances")

        # Tab 2: Stock Ledger Movements
        tab2 = QWidget()
        t2_layout = QVBoxLayout(tab2)
        self.ledger_table = QTableWidget()
        self.ledger_table.setColumnCount(7)
        self.ledger_table.setHorizontalHeaderLabels([
            "Timestamp", "Product Name", "Movement Type", "Change Qty", "Balance After", "Reference", "Notes"
        ])
        self.ledger_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ledger_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ledger_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ledger_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.ledger_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.ledger_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.ledger_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.ledger_table.verticalHeader().setDefaultSectionSize(36)
        self.ledger_table.verticalHeader().setVisible(False)
        t2_layout.addWidget(self.ledger_table)
        self.tabs.addTab(tab2, "Audit Movements Ledger")

        layout.addWidget(self.tabs)

    def refresh_all(self):
        self._refresh_balances()
        self._refresh_ledger()

    def _refresh_balances(self):
        products, _ = self.product_service.search_products(limit=500)
        self.balance_table.setRowCount(len(products))

        for row, p in enumerate(products):
            self.balance_table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.balance_table.setItem(row, 1, QTableWidgetItem(p["sku"]))

            stock = p["quantity_on_hand"]
            reorder = p["reorder_level"]

            s_item = QTableWidgetItem(f"{stock:.2f}")
            self.balance_table.setItem(row, 2, s_item)
            self.balance_table.setItem(row, 3, QTableWidgetItem(f"{reorder:.2f}"))
            self.balance_table.setItem(row, 4, QTableWidgetItem(p["unit_code"]))

            if stock <= 0:
                status_item = QTableWidgetItem("OUT OF STOCK")
                status_item.setForeground(Qt.red)
            elif stock <= reorder:
                status_item = QTableWidgetItem("LOW STOCK")
                status_item.setForeground(Qt.darkYellow)
            else:
                status_item = QTableWidgetItem("IN STOCK")
                status_item.setForeground(Qt.darkGreen)

            self.balance_table.setItem(row, 5, status_item)

    def _refresh_ledger(self):
        movements = self.inventory_service.get_stock_ledger(limit=100)
        self.ledger_table.setRowCount(len(movements))

        for row, m in enumerate(movements):
            self.ledger_table.setItem(row, 0, QTableWidgetItem(m["created_at"]))
            self.ledger_table.setItem(row, 1, QTableWidgetItem(m["product_name"]))
            self.ledger_table.setItem(row, 2, QTableWidgetItem(m["movement_type"]))

            qty_val = m["quantity"]
            q_item = QTableWidgetItem(f"{qty_val:+.2f}")
            if qty_val > 0:
                q_item.setForeground(Qt.darkGreen)
            else:
                q_item.setForeground(Qt.red)
            self.ledger_table.setItem(row, 3, q_item)

            self.ledger_table.setItem(row, 4, QTableWidgetItem(f"{m['balance_after']:.2f}"))
            self.ledger_table.setItem(row, 5, QTableWidgetItem(f"{m['reference_type']}: {m['reference_id']}"))
            self.ledger_table.setItem(row, 6, QTableWidgetItem(m["notes"]))

    def _open_adjustment_dialog(self):
        dlg = StockAdjustmentDialog(self.product_service, self.inventory_service, self.current_session, parent=self)
        if dlg.exec():
            self.refresh_all()
