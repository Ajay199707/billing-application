"""
Purchases and Goods Receipt Management View.
Allows store managers to record procurement invoices and replenish stock.
"""

from decimal import Decimal
from datetime import date
from typing import List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QComboBox, QDoubleSpinBox, QMessageBox, QDateEdit, QFormLayout
)

from src.services.purchase_service import PurchaseService, PurchaseItemInput
from src.services.product_service import ProductService
from src.services.auth_service import UserSession


class RecordPurchaseDialog(QDialog):
    def __init__(self, purchase_service: PurchaseService, product_service: ProductService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.purchase_service = purchase_service
        self.product_service = product_service
        self.current_session = current_session
        self.items: List[PurchaseItemInput] = []

        self.setWindowTitle("Record Supplier Purchase Invoice")
        self.setFixedSize(680, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Supplier & Invoice Form
        form = QFormLayout()

        self.sup_combo = QComboBox()
        suppliers = self.purchase_service.list_suppliers()
        for s in suppliers:
            self.sup_combo.addItem(f"{s['name']} (GST: {s['gstin'] or 'None'})", s["id"])
        form.addRow("Supplier *:", self.sup_combo)

        self.inv_no_input = QLineEdit()
        self.inv_no_input.setPlaceholderText("e.g. SUPP-2026-9901")
        form.addRow("Supplier Bill No *:", self.inv_no_input)

        layout.addLayout(form)

        # Add Item Section
        item_bar = QHBoxLayout()
        self.prod_combo = QComboBox()
        prods, _ = self.product_service.search_products(limit=500)
        for p in prods:
            self.prod_combo.addItem(p["name"], p)
        item_bar.addWidget(self.prod_combo, 3)

        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 10000)
        self.qty_spin.setValue(10.0)
        self.qty_spin.setPrefix("Qty: ")
        item_bar.addWidget(self.qty_spin, 2)

        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0, 1000000)
        self.cost_spin.setPrefix("₹ ")
        self.cost_spin.setDecimals(2)
        item_bar.addWidget(self.cost_spin, 2)

        add_item_btn = QPushButton("+ Add Item")
        add_item_btn.setObjectName("SecondaryBtn")
        add_item_btn.clicked.connect(self._add_item_row)
        item_bar.addWidget(add_item_btn, 2)

        layout.addLayout(item_bar)

        # Items Table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(["Product Name", "Qty", "Cost (₹)", "GST %", "Total (₹)"])
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        layout.addWidget(self.items_table)

        # Total Label
        self.total_lbl = QLabel("Grand Total: ₹ 0.00")
        self.total_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #16A34A;")
        layout.addWidget(self.total_lbl)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Confirm Purchase & Receive Stock")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._handle_save)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def _add_item_row(self):
        p_data = self.prod_combo.currentData()
        if not p_data:
            return

        qty = Decimal(str(self.qty_spin.value()))
        cost = Decimal(str(self.cost_spin.value())) or Decimal(str(p_data["purchase_cost"]))
        rate = Decimal(str(p_data["gst_rate"]))

        item_in = PurchaseItemInput(
            product_id=p_data["id"],
            quantity=qty,
            unit_cost=cost,
            gst_rate=rate,
        )
        self.items.append(item_in)

        # Refresh table
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        self.items_table.setItem(row, 0, QTableWidgetItem(p_data["name"]))
        self.items_table.setItem(row, 1, QTableWidgetItem(f"{qty:.2f}"))
        self.items_table.setItem(row, 2, QTableWidgetItem(f"{cost:.2f}"))
        self.items_table.setItem(row, 3, QTableWidgetItem(f"{rate:.1f}%"))

        sub = qty * cost
        tax = sub * (rate / Decimal("100"))
        tot = sub + tax
        self.items_table.setItem(row, 4, QTableWidgetItem(f"{tot:.2f}"))

        self._update_total()

    def _update_total(self):
        tot = Decimal("0.00")
        for itm in self.items:
            sub = itm.quantity * itm.unit_cost
            tax = sub * (itm.gst_rate / Decimal("100"))
            tot += (sub + tax)
        self.total_lbl.setText(f"Grand Total: ₹ {tot:.2f}")

    def _handle_save(self):
        sup_id = self.sup_combo.currentData()
        inv_no = self.inv_no_input.text().strip()

        if not sup_id:
            QMessageBox.warning(self, "Validation Error", "Please select a supplier.")
            return
        if not inv_no:
            QMessageBox.warning(self, "Validation Error", "Please enter the supplier invoice number.")
            self.inv_no_input.setFocus()
            return
        if not self.items:
            QMessageBox.warning(self, "Empty Purchase", "Please add at least one product.")
            return

        try:
            po_num = self.purchase_service.record_purchase(
                current_session=self.current_session,
                supplier_id=sup_id,
                supplier_invoice_no=inv_no,
                items=self.items,
            )
            QMessageBox.information(self, "Success", f"Purchase Order {po_num} recorded and stock updated!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Purchase", str(e))


class PurchasesView(QWidget):
    def __init__(self, purchase_service: PurchaseService, product_service: ProductService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.purchase_service = purchase_service
        self.product_service = product_service
        self.current_session = current_session

        self._init_ui()
        self.refresh_purchases()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Purchases & Goods Receipts")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Record vendor invoices, track inward inventory, and manage trade suppliers")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.add_po_btn = QPushButton("+ Record Purchase Bill")
        self.add_po_btn.setObjectName("PrimaryBtn")
        self.add_po_btn.clicked.connect(self._open_record_dialog)
        top_bar.addWidget(self.add_po_btn)

        layout.addLayout(top_bar)

        # Purchases Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "PO Number", "Supplier", "Supplier Bill No", "Date", "Items", "Tax (₹)", "Total (₹)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def refresh_purchases(self):
        purchases = self.purchase_service.list_purchases(limit=100)
        self.table.setRowCount(len(purchases))

        for row, p in enumerate(purchases):
            self.table.setItem(row, 0, QTableWidgetItem(p["purchase_number"]))
            self.table.setItem(row, 1, QTableWidgetItem(p["supplier_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(p["supplier_invoice_no"]))
            self.table.setItem(row, 3, QTableWidgetItem(p["purchase_date"]))
            self.table.setItem(row, 4, QTableWidgetItem(str(p["items_count"])))
            self.table.setItem(row, 5, QTableWidgetItem(f"₹ {p['tax_total']:,.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"₹ {p['grand_total']:,.2f}"))

    def _open_record_dialog(self):
        dlg = RecordPurchaseDialog(self.purchase_service, self.product_service, self.current_session, parent=self)
        if dlg.exec():
            self.refresh_purchases()
