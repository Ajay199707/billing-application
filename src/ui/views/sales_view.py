"""
Sales Invoices History and Returns/Refunds View.
Enables cashiers and admins to browse completed sales, reprint receipts, and process customer refunds.
"""

from decimal import Decimal
from datetime import date, timedelta
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QMessageBox, QDialog, QComboBox, QDoubleSpinBox, QFormLayout, QCheckBox
)

from src.services.billing_service import BillingService
from src.services.reporting_service import ReportingService
from src.services.settings_service import SettingsService
from src.services.invoice_service import InvoicePrintService
from src.services.auth_service import UserSession
from src.ui.dialogs.invoice_preview_dialog import InvoicePreviewDialog


class SalesReturnDialog(QDialog):
    def __init__(self, invoice_data: dict, billing_service: BillingService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.invoice = invoice_data
        self.billing_service = billing_service
        self.current_session = current_session

        self.setWindowTitle(f"Sales Return / Refund - {self.invoice['invoice_number']}")
        self.setFixedSize(560, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Header
        inv_lbl = QLabel(f"Processing return for: <b>{self.invoice['invoice_number']}</b> ({self.invoice['customer_name']})")
        layout.addWidget(inv_lbl)

        # Items Table to select return quantity
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Product Name", "Sold Qty", "Unit Price (₹)", "Return Qty"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        items = self.invoice.get("items", [])
        self.table.setRowCount(len(items))

        self.spin_boxes = []
        for row, itm in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(itm["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"{itm['quantity']:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{itm['unit_price']:.2f}"))

            spin = QDoubleSpinBox()
            spin.setRange(0.0, float(itm["quantity"]))
            spin.setDecimals(2)
            spin.setValue(0.0)
            self.table.setCellWidget(row, 3, spin)
            self.spin_boxes.append((itm["id"], spin))

        layout.addWidget(self.table)

        # Form for reason & refund mode
        form = QFormLayout()
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("e.g. Customer changed mind / wrong size")
        form.addRow("Return Reason *:", self.reason_input)

        self.refund_mode_combo = QComboBox()
        self.refund_mode_combo.addItems(["CASH", "UPI", "CARD"])
        form.addRow("Refund Mode *:", self.refund_mode_combo)

        self.restock_check = QCheckBox("Restock into Saleable Inventory")
        self.restock_check.setChecked(True)
        form.addRow("Inventory Action:", self.restock_check)
        layout.addLayout(form)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        confirm_btn = QPushButton("Process Refund & Restore Stock")
        confirm_btn.setObjectName("DangerBtn")
        confirm_btn.clicked.connect(self._handle_confirm)
        btn_box.addWidget(confirm_btn)

        layout.addLayout(btn_box)

    def _handle_confirm(self):
        reason = self.reason_input.text().strip()
        refund_mode = self.refund_mode_combo.currentText()

        return_items = []
        for item_id, spin in self.spin_boxes:
            qty = Decimal(str(spin.value()))
            if qty > Decimal("0.00"):
                return_items.append((item_id, qty))

        if not return_items:
            QMessageBox.warning(self, "Validation Error", "Please specify return quantity for at least one item.")
            return

        if not reason:
            QMessageBox.warning(self, "Validation Error", "Please provide a reason for the return.")
            self.reason_input.setFocus()
            return

        try:
            ret_no = self.billing_service.process_sales_return(
                current_session=self.current_session,
                invoice_number=self.invoice["invoice_number"],
                return_items=return_items,
                reason=reason,
                refund_method=refund_mode,
                restock_inventory=self.restock_check.isChecked(),
            )
            status_txt = "Stock replenished." if self.restock_check.isChecked() else "Items logged as damaged/expired (stock not added)."
            QMessageBox.information(self, "Return Completed", f"Sales return processed successfully: {ret_no}\n{status_txt}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Return Error", str(e))


class SalesView(QWidget):
    def __init__(
        self,
        billing_service: BillingService,
        reporting_service: ReportingService,
        settings_service: SettingsService,
        print_service: InvoicePrintService,
        current_session: UserSession,
        parent=None,
    ):
        super().__init__(parent)
        self.billing_service = billing_service
        self.reporting_service = reporting_service
        self.settings_service = settings_service
        self.print_service = print_service
        self.current_session = current_session

        self._init_ui()
        self.refresh_sales()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Sales Transactions & Receipt History")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Audit completed retail bills, reprint customer receipts, and manage sales returns")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.refresh_btn = QPushButton("Refresh Sales")
        self.refresh_btn.setObjectName("SecondaryBtn")
        self.refresh_btn.clicked.connect(self.refresh_sales)
        top_bar.addWidget(self.refresh_btn)

        layout.addLayout(top_bar)

        # Date Filters
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("From Date:"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(date.today() - timedelta(days=30))
        self.from_date.dateChanged.connect(self.refresh_sales)
        filter_bar.addWidget(self.from_date)

        filter_bar.addWidget(QLabel("To Date:"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(date.today())
        self.to_date.dateChanged.connect(self.refresh_sales)
        filter_bar.addWidget(self.to_date)

        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # Sales Invoices Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Invoice No", "Date", "Customer", "Subtotal (₹)", "Tax (₹)", "Total (₹)", "Payment", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def refresh_sales(self):
        f_date = self.from_date.date().toPython()
        t_date = self.to_date.date().toPython()

        sales = self.reporting_service.get_sales_report(start_date=f_date, end_date=t_date)
        self.table.setRowCount(len(sales))

        for row, s in enumerate(sales):
            self.table.setItem(row, 0, QTableWidgetItem(s["invoice_number"]))
            self.table.setItem(row, 1, QTableWidgetItem(s["date"]))
            self.table.setItem(row, 2, QTableWidgetItem(s["customer"]))
            self.table.setItem(row, 3, QTableWidgetItem(f"₹ {s['subtotal']:,.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"₹ {s['tax']:,.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"₹ {s['grand_total']:,.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(s["payment_mode"]))

            # Action Buttons: Print & Return
            act_widget = QWidget()
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(6, 4, 6, 4)
            act_layout.setSpacing(6)
            act_layout.setAlignment(Qt.AlignCenter)

            print_btn = QPushButton("Print")
            print_btn.setObjectName("TableActionBtn")
            print_btn.setFixedHeight(28)
            print_btn.setMinimumWidth(55)
            print_btn.clicked.connect(lambda _, inv=s["invoice_number"]: self._open_print_dialog(inv))
            act_layout.addWidget(print_btn)

            ret_btn = QPushButton("Return")
            ret_btn.setObjectName("TableActionDangerBtn")
            ret_btn.setFixedHeight(28)
            ret_btn.setMinimumWidth(55)
            ret_btn.clicked.connect(lambda _, inv=s["invoice_number"]: self._open_return_dialog(inv))
            act_layout.addWidget(ret_btn)

            self.table.setCellWidget(row, 7, act_widget)

    def _open_print_dialog(self, invoice_number: str):
        inv_data = self.billing_service.get_invoice(invoice_number)
        if not inv_data:
            QMessageBox.warning(self, "Error", f"Invoice {invoice_number} not found.")
            return

        dlg = InvoicePreviewDialog(
            invoice_data=inv_data,
            settings_service=self.settings_service,
            print_service=self.print_service,
            parent=self,
        )
        dlg.exec()

    def _open_return_dialog(self, invoice_number: str):
        inv_data = self.billing_service.get_invoice(invoice_number)
        if not inv_data:
            QMessageBox.warning(self, "Error", f"Invoice {invoice_number} not found.")
            return

        dlg = SalesReturnDialog(
            invoice_data=inv_data,
            billing_service=self.billing_service,
            current_session=self.current_session,
            parent=self,
        )
        if dlg.exec():
            self.refresh_sales()
