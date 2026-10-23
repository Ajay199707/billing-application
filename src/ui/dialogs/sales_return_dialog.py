"""
Controlled Sales Return and Refund Dialog.
Allows cashiers to process item returns, specify return reason, refund method,
and choose whether goods should be restocked or written off as damaged/expired.
"""

from decimal import Decimal
from typing import Dict, Any, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QDoubleSpinBox, QCheckBox, QMessageBox, QFrame
)

from src.services.billing_service import BillingService
from src.services.auth_service import UserSession


class SalesReturnDialog(QDialog):
    def __init__(self, billing_service: BillingService, sale_dict: Dict[str, Any], current_session: UserSession, parent=None):
        super().__init__(parent)
        self.billing_service = billing_service
        self.sale = sale_dict
        self.current_session = current_session
        self.spinboxes: List[QDoubleSpinBox] = []

        self.setWindowTitle(f"Process Return - Invoice {self.sale['invoice_number']}")
        self.setMinimumSize(780, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel(f"Return for Invoice: {self.sale['invoice_number']}")
        header.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        layout.addWidget(header)

        sub = QLabel(f"Date: {self.sale['sale_date']} | Customer: {self.sale['customer_name']} | Grand Total: ₹{self.sale['grand_total']:.2f}")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        layout.addWidget(sub)

        # Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Item Description", "Unit Price (₹)", "Sold Qty", "Return Qty", "Line Total (₹)", "Refund Total (₹)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)

        items = self.sale.get("items", [])
        self.table.setRowCount(len(items))

        for row, itm in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(itm["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"{itm['unit_price']:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{itm['quantity']:.3f}"))

            # Return Qty Spinbox
            spin = QDoubleSpinBox()
            spin.setRange(0.0, float(itm["quantity"]))
            spin.setValue(0.0)
            spin.setDecimals(3 if itm["quantity"] % 1 != 0 else 0)
            spin.valueChanged.connect(self._recalculate_refund)
            self.table.setCellWidget(row, 3, spin)
            self.spinboxes.append(spin)

            self.table.setItem(row, 4, QTableWidgetItem(f"{itm['line_total']:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem("₹ 0.00"))

        layout.addWidget(self.table)

        # Options Box
        opts_frame = QFrame()
        opts_frame.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px;")
        opts_layout = QHBoxLayout(opts_frame)

        # Reason
        opts_layout.addWidget(QLabel("Return Reason:"))
        self.reason_combo = QComboBox()
        self.reason_combo.addItems([
            "Customer Change of Mind",
            "Defective / Damaged Packaging",
            "Expired Product",
            "Wrong Item Billed",
            "Customer Return / Exchange",
        ])
        self.reason_combo.setEditable(True)
        opts_layout.addWidget(self.reason_combo, 2)

        # Refund Method
        opts_layout.addWidget(QLabel("Refund Method:"))
        self.refund_combo = QComboBox()
        self.refund_combo.addItems(["CASH", "UPI", "CARD"])
        opts_layout.addWidget(self.refund_combo, 1)

        # Restock Checkbox
        self.restock_check = QCheckBox("Restock into Saleable Inventory")
        self.restock_check.setChecked(True)
        self.restock_check.setToolTip("Uncheck if goods are damaged or expired so they are not sold to other customers.")
        opts_layout.addWidget(self.restock_check)

        layout.addWidget(opts_frame)

        # Total Refund Card
        total_bar = QHBoxLayout()
        self.total_refund_lbl = QLabel("Total Refund Due: ₹ 0.00")
        self.total_refund_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #DC2626;")
        total_bar.addWidget(self.total_refund_lbl)

        total_bar.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("SecondaryBtn")
        self.cancel_btn.clicked.connect(self.reject)
        total_bar.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("Confirm Return & Refund")
        self.confirm_btn.setObjectName("PrimaryBtn")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._handle_confirm)
        total_bar.addWidget(self.confirm_btn)

        layout.addLayout(total_bar)

    def _recalculate_refund(self):
        items = self.sale.get("items", [])
        total_refund = Decimal("0.00")

        for row, spin in enumerate(self.spinboxes):
            qty = Decimal(str(spin.value()))
            itm = items[row]
            sold_qty = Decimal(str(itm["quantity"]))
            line_tot = Decimal(str(itm["line_total"]))

            if sold_qty > 0 and qty > 0:
                item_refund = (line_tot / sold_qty) * qty
            else:
                item_refund = Decimal("0.00")

            total_refund += item_refund
            self.table.setItem(row, 5, QTableWidgetItem(f"₹ {item_refund:.2f}"))

        self.total_refund_lbl.setText(f"Total Refund Due: ₹ {total_refund:.2f}")
        self.confirm_btn.setEnabled(total_refund > Decimal("0.00"))

    def _handle_confirm(self):
        items = self.sale.get("items", [])
        return_items = []

        for row, spin in enumerate(self.spinboxes):
            qty = Decimal(str(spin.value()))
            if qty > Decimal("0.000"):
                return_items.append((items[row]["id"], qty))

        if not return_items:
            QMessageBox.warning(self, "No Items Selected", "Please select at least one item quantity to return.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Sales Return",
            f"Are you sure you want to process this return?\n"
            f"Restock into Inventory: {'YES' if self.restock_check.isChecked() else 'NO (Marked as Damaged/Expired)'}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        reason = self.reason_combo.currentText().strip() or "Customer Return"
        refund_method = self.refund_combo.currentText()
        restock = self.restock_check.isChecked()

        try:
            ret_no = self.billing_service.process_sales_return(
                current_session=self.current_session,
                invoice_number=self.sale["invoice_number"],
                return_items=return_items,
                reason=reason,
                refund_method=refund_method,
                restock_inventory=restock,
            )
            QMessageBox.information(self, "Return Processed", f"Sales return #{ret_no} successfully processed.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Return Error", str(e))
