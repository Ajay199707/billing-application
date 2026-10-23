"""
Invoice Preview and Document Printing Dialog.
Allows cashiers to view bill breakdowns, generate PDFs, and trigger direct printing.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)

from src.services.invoice_service import InvoicePrintService
from src.services.settings_service import SettingsService


class InvoicePreviewDialog(QDialog):
    def __init__(
        self,
        invoice_data: Dict[str, Any],
        settings_service: SettingsService,
        print_service: InvoicePrintService,
        parent=None,
    ):
        super().__init__(parent)
        self.invoice = invoice_data
        self.settings_service = settings_service
        self.print_service = print_service
        self.shop_info = self.settings_service.get_shop_info()

        self.setWindowTitle(f"Invoice Preview - {self.invoice['invoice_number']}")
        self.setFixedSize(650, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header Info Card
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        h_box = QVBoxLayout(hdr_frame)

        shop_lbl = QLabel(self.shop_info.get("name", "Store").upper())
        shop_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        h_box.addWidget(shop_lbl)

        meta_lbl = QLabel(
            f"Invoice: <b>{self.invoice['invoice_number']}</b> | Date: {self.invoice['sale_date']} | "
            f"Customer: <b>{self.invoice.get('customer_name', 'Walk-in')}</b>"
        )
        meta_lbl.setStyleSheet("font-size: 12px; color: #475569;")
        h_box.addWidget(meta_lbl)
        layout.addWidget(hdr_frame)

        # Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Name", "HSN", "Qty", "Rate (₹)", "Total (₹)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        items = self.invoice.get("items", [])
        self.table.setRowCount(len(items))

        for row, itm in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(itm["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(itm["hsn"]))
            self.table.setItem(row, 2, QTableWidgetItem(f"{itm['quantity']:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{itm['unit_price']:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{itm['line_total']:.2f}"))

        layout.addWidget(self.table)

        # Totals Summary Card
        tot_frame = QFrame()
        tot_frame.setStyleSheet("background-color: #F8FAFC; border: 1px solid #D1FAE5; border-radius: 6px; padding: 10px;")
        t_box = QHBoxLayout(tot_frame)

        # Payment Mode Badge
        payments = self.invoice.get("payments", [])
        if payments:
            pay_str = ", ".join([f"{p['method']}: ₹{p['amount']:.2f}" for p in payments])
        else:
            pay_str = "CASH"

        pay_badge = QLabel(f"💳 Payment: <b>{pay_str}</b>")
        pay_badge.setStyleSheet("font-size: 12px; font-weight: 700; color: #064E3B; background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 4px; padding: 4px 10px;")
        t_box.addWidget(pay_badge)
        t_box.addSpacing(10)

        tax_breakdown = (
            f"Taxable: ₹{self.invoice['taxable_amount']:.2f} | "
            f"CGST: ₹{self.invoice['cgst_amount']:.2f} | "
            f"SGST: ₹{self.invoice['sgst_amount']:.2f}"
        )
        if self.invoice.get("igst_amount", 0) > 0:
            tax_breakdown += f" | IGST: ₹{self.invoice['igst_amount']:.2f}"

        t_lbl = QLabel(tax_breakdown)
        t_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        t_box.addWidget(t_lbl)
        t_box.addStretch()

        grand_lbl = QLabel(f"GRAND TOTAL: ₹ {self.invoice['grand_total']:.2f}")
        grand_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #059669;")
        t_box.addWidget(grand_lbl)
        layout.addWidget(tot_frame)

        # Print Format Buttons
        p_box = QHBoxLayout()

        self.btn_58 = QPushButton("Print 58mm Thermal")
        self.btn_58.setObjectName("SecondaryBtn")
        self.btn_58.clicked.connect(lambda: self._generate_and_open("58mm"))
        p_box.addWidget(self.btn_58)

        self.btn_80 = QPushButton("Print 80mm Thermal")
        self.btn_80.setObjectName("SecondaryBtn")
        self.btn_80.clicked.connect(lambda: self._generate_and_open("80mm"))
        p_box.addWidget(self.btn_80)

        self.btn_a4 = QPushButton("Print A4 GST Invoice")
        self.btn_a4.setObjectName("PrimaryBtn")
        self.btn_a4.clicked.connect(lambda: self._generate_and_open("A4"))
        p_box.addWidget(self.btn_a4)

        layout.addLayout(p_box)

        # Close
        btn_close = QPushButton("Close")
        btn_close.setObjectName("SecondaryBtn")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _generate_and_open(self, format_type: str):
        try:
            pdf_path = self.print_service.generate_pdf(
                invoice_data=self.invoice,
                shop_info=self.shop_info,
                format_type=format_type,
            )
            # Open PDF with default Windows viewer
            os.startfile(str(pdf_path))
        except Exception as exc:
            QMessageBox.critical(self, "Printing Error", f"Failed to generate invoice document:\n{exc}")
