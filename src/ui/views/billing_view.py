"""
Fast, Keyboard-Friendly Point-of-Sale (POS) Billing Interface.
Supports hardware barcode scanner wedge input, live product lookup,
line/invoice discounts, split payment settlement, and instant receipt generation.
"""

import re
from decimal import Decimal
from typing import Dict, Any, List, Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QDoubleSpinBox, QCompleter, QDialog
)

from src.core.exceptions import (
    InsufficientStockError,
    PaymentMismatchedError,
    EmptyCartError,
    AccountInactiveError,
)
from src.services.auth_service import UserSession
from src.services.billing_service import BillingService, CartItemInput, PaymentInput
from src.services.product_service import ProductService
from src.services.settings_service import SettingsService
from src.services.invoice_service import InvoicePrintService
from src.services.tax_service import TaxEngine, LineTaxBreakdown, round_currency
from src.ui.dialogs.payment_dialog import PaymentDialog
from src.ui.dialogs.invoice_preview_dialog import InvoicePreviewDialog


class POSCartItem:
    def __init__(
        self,
        product_id: int,
        name: str,
        sku: str,
        barcode: str,
        unit: str,
        price: Decimal,
        gst_rate: Decimal,
        hsn: str,
        quantity: Decimal = Decimal("1.000"),
        discount: Decimal = Decimal("0.00"),
        decimal_precision: int = 0,
        available_qty: Decimal = Decimal("0.000"),
        variant_id: Optional[int] = None,
    ):
        self.product_id = product_id
        self.name = name
        self.sku = sku
        self.barcode = barcode
        self.unit = unit
        self.price = price
        self.gst_rate = gst_rate
        self.hsn = hsn
        self.quantity = quantity
        self.discount = discount
        self.decimal_precision = decimal_precision
        self.available_qty = available_qty
        self.variant_id = variant_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "sku": self.sku,
            "barcode": self.barcode,
            "unit": self.unit,
            "price": str(self.price),
            "gst_rate": str(self.gst_rate),
            "hsn": self.hsn,
            "quantity": str(self.quantity),
            "discount": str(self.discount),
            "decimal_precision": self.decimal_precision,
            "available_qty": str(self.available_qty),
            "variant_id": self.variant_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "POSCartItem":
        return cls(
            product_id=d["product_id"],
            name=d["name"],
            sku=d["sku"],
            barcode=d.get("barcode", ""),
            unit=d["unit"],
            price=Decimal(str(d["price"])),
            gst_rate=Decimal(str(d["gst_rate"])),
            hsn=d.get("hsn", ""),
            quantity=Decimal(str(d["quantity"])),
            discount=Decimal(str(d.get("discount", "0.00"))),
            decimal_precision=d.get("decimal_precision", 0),
            available_qty=Decimal(str(d.get("available_qty", "0.000"))),
            variant_id=d.get("variant_id"),
        )


class BillingView(QWidget):
    def __init__(
        self,
        billing_service: BillingService,
        product_service: ProductService,
        settings_service: SettingsService,
        print_service: InvoicePrintService,
        current_session: UserSession,
        parent=None,
    ):
        super().__init__(parent)
        self.billing_service = billing_service
        self.product_service = product_service
        self.settings_service = settings_service
        self.print_service = print_service
        self.current_session = current_session

        self.cart_items: List[POSCartItem] = []
        self.last_completed_invoice: Optional[Dict[str, Any]] = None

        self._init_ui()
        self._setup_shortcuts()
        self.update_totals()
        self._update_parked_badge()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ---------------- Left Panel: POS Input & Cart Table ----------------
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        # Top Barcode & Search Controls
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        # Barcode Wedge Input
        bc_box = QVBoxLayout()
        bc_box.setSpacing(2)
        bc_lbl = QLabel("Scan Barcode (F2)")
        bc_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        bc_box.addWidget(bc_lbl)

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Scan barcode or enter SKU & press Enter...")
        self.barcode_input.setFixedHeight(38)
        self.barcode_input.setStyleSheet("font-size: 14px; font-weight: 600; color: #1E293B;")
        self.barcode_input.returnPressed.connect(self._handle_barcode_scan)
        bc_box.addWidget(self.barcode_input)
        top_bar.addLayout(bc_box, 3)

        # Product Search by Name
        search_box = QVBoxLayout()
        search_box.setSpacing(2)
        search_lbl = QLabel("Search Product by Name (F3)")
        search_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        search_box.addWidget(search_lbl)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type product name...")
        self.search_input.setFixedHeight(38)
        self.search_input.textChanged.connect(self._handle_live_search)
        self.search_input.returnPressed.connect(self._add_first_search_result)
        search_box.addWidget(self.search_input)
        top_bar.addLayout(search_box, 3)

        left_layout.addLayout(top_bar)

        # Search Results Dropdown / Floating Preview Table
        self.search_results_table = QTableWidget()
        self.search_results_table.setColumnCount(4)
        self.search_results_table.setHorizontalHeaderLabels(["Product Name", "SKU / Barcode", "Price (₹)", "Stock"])
        self.search_results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.search_results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.search_results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.search_results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.search_results_table.setFixedHeight(120)
        self.search_results_table.setVisible(False)
        self.search_results_table.cellDoubleClicked.connect(self._on_search_result_double_clicked)
        left_layout.addWidget(self.search_results_table)

        # Main Cart Table
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(8)
        self.cart_table.setHorizontalHeaderLabels([
            "#", "Item Description", "Qty", "Unit", "Price (₹)", "Disc (₹)", "Total (₹)", "Action"
        ])
        self.cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.cart_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.cart_table.verticalHeader().setDefaultSectionSize(40)
        self.cart_table.verticalHeader().setVisible(False)
        left_layout.addWidget(self.cart_table, 1)

        # Action Buttons below Cart - High-Contrast and Crystal Clear
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 4, 0, 4)
        btn_bar.setSpacing(10)

        self.clear_btn = QPushButton("🗑️ Clear Cart (F4)")
        self.clear_btn.setObjectName("SecondaryBtn")
        self.clear_btn.setFixedHeight(38)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFC;
                color: #0F172A;
                font-weight: 700;
                font-size: 13px;
                border: 1.5px solid #94A3B8;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #000000;
                border-color: #64748B;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_cart)
        btn_bar.addWidget(self.clear_btn)

        self.reprint_btn = QPushButton("🖨️ Reprint Bill (F8)")
        self.reprint_btn.setObjectName("SecondaryBtn")
        self.reprint_btn.setFixedHeight(38)
        self.reprint_btn.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFC;
                color: #0F172A;
                font-weight: 700;
                font-size: 13px;
                border: 1.5px solid #94A3B8;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #000000;
                border-color: #64748B;
            }
        """)
        self.reprint_btn.clicked.connect(self.reprint_last_bill)
        btn_bar.addWidget(self.reprint_btn)

        # Multi-Customer Fast Checkout: Hold & Recall
        self.hold_btn = QPushButton("⏸️ Hold Bill (F9)")
        self.hold_btn.setFixedHeight(38)
        self.hold_btn.setToolTip("Temporarily park this customer's cart so you can bill the next customer (F9)")
        self.hold_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEF3C7;
                color: #78350F;
                font-weight: 700;
                font-size: 13px;
                border: 1.5px solid #F59E0B;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #FDE68A;
                color: #451A03;
                border-color: #D97706;
            }
        """)
        self.hold_btn.clicked.connect(self._handle_hold_bill)
        btn_bar.addWidget(self.hold_btn)

        self.recall_btn = QPushButton("📂 Recall Bill (F10)")
        self.recall_btn.setFixedHeight(38)
        self.recall_btn.setToolTip("View and restore held customer baskets (F10)")
        self.recall_btn.setStyleSheet("""
            QPushButton {
                background-color: #EFF6FF;
                color: #1E40AF;
                font-weight: 700;
                font-size: 13px;
                border: 1.5px solid #3B82F6;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #DBEAFE;
                color: #172554;
                border-color: #2563EB;
            }
        """)
        self.recall_btn.clicked.connect(self._handle_recall_bill)
        btn_bar.addWidget(self.recall_btn)

        btn_bar.addStretch()
        left_layout.addLayout(btn_bar)

        main_layout.addLayout(left_layout, 7)

        # ---------------- Right Panel: Customer & Bill Totals ----------------
        right_panel = QFrame()
        right_panel.setObjectName("BillingRightPanel")
        right_panel.setStyleSheet("""
            QFrame#BillingRightPanel {
                background-color: #FFFFFF;
                border: 1px solid #D1FAE5;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 12, 14, 12)
        right_layout.setSpacing(6)

        # Customer Details
        cust_title = QLabel("CUSTOMER DETAILS (OPTIONAL)")
        cust_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #065F46;")
        right_layout.addWidget(cust_title)

        self.cust_name_input = QLineEdit()
        self.cust_name_input.setFixedHeight(30)
        self.cust_name_input.setPlaceholderText("Customer Name (Walk-in)")
        right_layout.addWidget(self.cust_name_input)

        self.cust_phone_input = QLineEdit()
        self.cust_phone_input.setFixedHeight(30)
        self.cust_phone_input.setPlaceholderText("Phone Number")
        right_layout.addWidget(self.cust_phone_input)

        self.cust_gstin_input = QLineEdit()
        self.cust_gstin_input.setFixedHeight(30)
        self.cust_gstin_input.setPlaceholderText("Customer GSTIN (B2B)")
        self.cust_gstin_input.setMaxLength(15)
        right_layout.addWidget(self.cust_gstin_input)

        right_layout.addSpacing(2)

        # Invoice Discount Box
        disc_box = QHBoxLayout()
        disc_lbl = QLabel("Invoice Discount:")
        disc_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #334155;")
        disc_box.addWidget(disc_lbl)

        self.inv_disc_spin = QDoubleSpinBox()
        self.inv_disc_spin.setFixedHeight(30)
        self.inv_disc_spin.setRange(0, 100000)
        self.inv_disc_spin.setPrefix("₹ ")
        self.inv_disc_spin.setDecimals(2)
        self.inv_disc_spin.valueChanged.connect(self.update_totals)
        disc_box.addWidget(self.inv_disc_spin)
        right_layout.addLayout(disc_box)

        right_layout.addSpacing(4)

        # Summary Breakdown Box
        self.subtotal_lbl = QLabel("Subtotal Gross: ₹ 0.00")
        self.subtotal_lbl.setStyleSheet("font-size: 12px; color: #334155; font-weight: 600;")
        right_layout.addWidget(self.subtotal_lbl)

        self.taxable_lbl = QLabel("Taxable Amount: ₹ 0.00")
        self.taxable_lbl.setStyleSheet("font-size: 12px; color: #334155; font-weight: 600;")
        right_layout.addWidget(self.taxable_lbl)

        self.cgst_lbl = QLabel("CGST: ₹ 0.00")
        self.cgst_lbl.setStyleSheet("font-size: 12px; color: #334155; font-weight: 600;")
        right_layout.addWidget(self.cgst_lbl)

        self.sgst_lbl = QLabel("SGST: ₹ 0.00")
        self.sgst_lbl.setStyleSheet("font-size: 12px; color: #334155; font-weight: 600;")
        right_layout.addWidget(self.sgst_lbl)

        self.round_off_lbl = QLabel("Round Off: ₹ 0.00")
        self.round_off_lbl.setStyleSheet("font-size: 12px; color: #334155; font-weight: 600;")
        right_layout.addWidget(self.round_off_lbl)

        right_layout.addSpacing(4)

        # Large Payable Amount Card
        amt_card = QFrame()
        amt_card.setObjectName("AmountPayableCard")
        amt_card.setStyleSheet("""
            QFrame#AmountPayableCard {
                background-color: #064E3B;
                border-radius: 8px;
                border: none;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        amt_box = QVBoxLayout(amt_card)
        amt_box.setContentsMargins(10, 8, 10, 8)
        amt_box.setSpacing(2)

        payable_header = QLabel("AMOUNT PAYABLE")
        payable_header.setStyleSheet("color: #A7F3D0; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        payable_header.setAlignment(Qt.AlignCenter)
        amt_box.addWidget(payable_header)

        self.grand_total_lbl = QLabel("₹ 0.00")
        self.grand_total_lbl.setStyleSheet("color: #34D399; font-size: 28px; font-weight: 800;")
        self.grand_total_lbl.setAlignment(Qt.AlignCenter)
        amt_box.addWidget(self.grand_total_lbl)
        right_layout.addWidget(amt_card)

        right_layout.addStretch()

        # Checkout Button - Vibrant High-Contrast Green with Bold Title
        self.checkout_btn = QPushButton("COMPLETE SALE (F12)")
        self.checkout_btn.setObjectName("CheckoutBtn")
        self.checkout_btn.setFixedHeight(48)
        self.checkout_btn.setStyleSheet("""
            QPushButton#CheckoutBtn {
                background-color: #059669;
                color: #FFFFFF;
                font-size: 16px;
                font-weight: 800;
                letter-spacing: 0.5px;
                border-radius: 8px;
                border: 1px solid #047857;
            }
            QPushButton#CheckoutBtn:hover {
                background-color: #047857;
            }
            QPushButton#CheckoutBtn:pressed {
                background-color: #064E3B;
            }
        """)
        self.checkout_btn.clicked.connect(self._handle_checkout)
        right_layout.addWidget(self.checkout_btn)

        main_layout.addWidget(right_panel, 3)

        # Initially set focus to Barcode scanner
        self.barcode_input.setFocus()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F2"), self, lambda: self.barcode_input.setFocus())
        QShortcut(QKeySequence("F3"), self, lambda: self.search_input.setFocus())
        QShortcut(QKeySequence("F4"), self, self.clear_cart)
        QShortcut(QKeySequence("F8"), self, self.reprint_last_bill)
        QShortcut(QKeySequence("F9"), self, self._handle_hold_bill)
        QShortcut(QKeySequence("F10"), self, self._handle_recall_bill)
        QShortcut(QKeySequence("F12"), self, self._handle_checkout)

    # ---------------- Barcode & Search Handlers ----------------

    def _handle_barcode_scan(self):
        raw_text = self.barcode_input.text().strip()
        if not raw_text:
            return

        multiplier = Decimal("1.000")
        code = raw_text

        # Check for multiplier format (e.g. "5*8901030" or "2.5*101" or "3x8901030")
        if "*" in raw_text:
            parts = raw_text.split("*", 1)
            try:
                multiplier = Decimal(parts[0].strip())
                code = parts[1].strip()
            except Exception:
                code = raw_text
                multiplier = Decimal("1.000")
        elif "x" in raw_text.lower() and not raw_text.startswith("0x"):
            parts = re.split(r"[xX]", raw_text, maxsplit=1)
            try:
                multiplier = Decimal(parts[0].strip())
                code = parts[1].strip()
            except Exception:
                code = raw_text
                multiplier = Decimal("1.000")

        if not code:
            return

        resolved = self.product_service.resolve_barcode(code)
        if not resolved:
            QMessageBox.warning(self, "Item Not Found", f"No product matched barcode or SKU: '{code}'")
            self.barcode_input.clear()
            return

        # Handle weighing scale barcode with pre-encoded weight
        if resolved.get("scanned_quantity") is not None:
            qty = Decimal(str(resolved["scanned_quantity"])) * multiplier
        else:
            qty = multiplier

        self._add_product_to_cart(resolved, quantity=qty)
        self.barcode_input.clear()
        self.barcode_input.setFocus()

    def _handle_live_search(self, text: str):
        query = text.strip()
        if len(query) < 2:
            self.search_results_table.setVisible(False)
            return

        products, _ = self.product_service.search_products(query=query, limit=5)
        if not products:
            self.search_results_table.setVisible(False)
            return

        self.search_results_table.setRowCount(len(products))
        for row, p in enumerate(products):
            self.search_results_table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.search_results_table.setItem(row, 1, QTableWidgetItem(p["barcode"] or p["sku"]))
            self.search_results_table.setItem(row, 2, QTableWidgetItem(f"{p['selling_price']:.2f}"))
            self.search_results_table.setItem(row, 3, QTableWidgetItem(f"{p['quantity_on_hand']:.2f}"))
            # Store ID in hidden data
            self.search_results_table.item(row, 0).setData(Qt.UserRole, p)

        self.search_results_table.setVisible(True)

    def _on_search_result_double_clicked(self, row, col):
        item = self.search_results_table.item(row, 0)
        p = item.data(Qt.UserRole)
        if p:
            resolved = {
                "product_id": p["id"],
                "variant_id": None,
                "name": p["name"],
                "sku": p["sku"],
                "barcode": p["barcode"],
                "unit_code": p["unit_code"],
                "decimal_precision": p["decimal_precision"],
                "selling_price": p["selling_price"],
                "purchase_cost": p["purchase_cost"],
                "hsn_code": p["hsn_code"],
                "gst_rate": p["gst_rate"],
                "available_qty": p["quantity_on_hand"],
            }
            self._add_product_to_cart(resolved, quantity=Decimal("1.000"))
            self.search_input.clear()
            self.search_results_table.setVisible(False)
            self.barcode_input.setFocus()

    def _add_first_search_result(self):
        if self.search_results_table.isVisible() and self.search_results_table.rowCount() > 0:
            self._on_search_result_double_clicked(0, 0)

    def _add_product_to_cart(self, prod_dict: Dict[str, Any], quantity: Decimal = Decimal("1.000")):
        # Check if already in cart
        pid = prod_dict["product_id"]
        vid = prod_dict.get("variant_id")

        for item in self.cart_items:
            if item.product_id == pid and item.variant_id == vid:
                item.quantity += quantity
                self._refresh_cart_table()
                self.update_totals()
                return

        # Add new row
        cart_item = POSCartItem(
            product_id=pid,
            name=prod_dict["name"],
            sku=prod_dict["sku"],
            barcode=prod_dict.get("barcode", ""),
            unit=prod_dict["unit_code"],
            price=Decimal(str(prod_dict["selling_price"])),
            gst_rate=Decimal(str(prod_dict["gst_rate"])),
            hsn=prod_dict["hsn_code"],
            quantity=quantity,
            decimal_precision=prod_dict.get("decimal_precision", 0),
            available_qty=Decimal(str(prod_dict.get("available_qty", 0.0))),
            variant_id=vid,
        )
        self.cart_items.append(cart_item)
        self._refresh_cart_table()
        self.update_totals()

    # ---------------- Cart Table UI Refresh ----------------

    def _refresh_cart_table(self):
        self.cart_table.setRowCount(len(self.cart_items))

        for row, item in enumerate(self.cart_items):
            # 0. Index
            self.cart_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

            # 1. Name & SKU
            self.cart_table.setItem(row, 1, QTableWidgetItem(item.name))

            # 2. Quantity SpinBox
            q_spin = QDoubleSpinBox()
            q_spin.setRange(0.001, 10000)
            q_spin.setDecimals(item.decimal_precision)
            q_spin.setValue(float(item.quantity))
            q_spin.valueChanged.connect(lambda val, idx=row: self._on_qty_changed(idx, val))
            self.cart_table.setCellWidget(row, 2, q_spin)

            # 3. Unit
            self.cart_table.setItem(row, 3, QTableWidgetItem(item.unit))

            # 4. Price
            self.cart_table.setItem(row, 4, QTableWidgetItem(f"{item.price:.2f}"))

            # 5. Discount
            d_spin = QDoubleSpinBox()
            d_spin.setRange(0, 10000)
            d_spin.setDecimals(2)
            d_spin.setValue(float(item.discount))
            d_spin.valueChanged.connect(lambda val, idx=row: self._on_discount_changed(idx, val))
            self.cart_table.setCellWidget(row, 5, d_spin)

            # 6. Line Total
            line_tot = (item.quantity * item.price) - item.discount
            self.cart_table.setItem(row, 6, QTableWidgetItem(f"{line_tot:.2f}"))

            # 7. Delete Button
            del_btn = QPushButton("✕")
            del_btn.setObjectName("TableActionDangerBtn")
            del_btn.setFixedSize(32, 28)
            del_btn.clicked.connect(lambda _, idx=row: self._remove_item(idx))
            self.cart_table.setCellWidget(row, 7, del_btn)

    def _on_qty_changed(self, row_idx: int, new_val: float):
        if 0 <= row_idx < len(self.cart_items):
            self.cart_items[row_idx].quantity = Decimal(str(new_val))
            # Update line total cell
            item = self.cart_items[row_idx]
            line_tot = (item.quantity * item.price) - item.discount
            self.cart_table.setItem(row_idx, 6, QTableWidgetItem(f"{line_tot:.2f}"))
            self.update_totals()

    def _on_discount_changed(self, row_idx: int, new_val: float):
        if 0 <= row_idx < len(self.cart_items):
            self.cart_items[row_idx].discount = Decimal(str(new_val))
            item = self.cart_items[row_idx]
            line_tot = (item.quantity * item.price) - item.discount
            self.cart_table.setItem(row_idx, 6, QTableWidgetItem(f"{line_tot:.2f}"))
            self.update_totals()

    def _remove_item(self, row_idx: int):
        if 0 <= row_idx < len(self.cart_items):
            self.cart_items.pop(row_idx)
            self._refresh_cart_table()
            self.update_totals()

    def clear_cart(self):
        self.cart_items.clear()
        self.cart_table.setRowCount(0)
        self.cust_name_input.clear()
        self.cust_phone_input.clear()
        self.cust_gstin_input.clear()
        self.inv_disc_spin.setValue(0.0)
        self.update_totals()
        self.barcode_input.setFocus()

    # ---------------- Tax & Totals Computation ----------------

    def update_totals(self):
        if not self.cart_items:
            self.subtotal_lbl.setText("Subtotal Gross: ₹ 0.00")
            self.taxable_lbl.setText("Taxable Amount: ₹ 0.00")
            self.cgst_lbl.setText("CGST: ₹ 0.00")
            self.sgst_lbl.setText("SGST: ₹ 0.00")
            self.round_off_lbl.setText("Round Off: ₹ 0.00")
            self.grand_total_lbl.setText("₹ 0.00")
            self.current_summary = None
            return

        shop = self.settings_service.get_shop_info()
        seller_state = shop.get("state_code", "33")
        buyer_gstin = self.cust_gstin_input.text().strip()
        buyer_state = buyer_gstin[:2] if len(buyer_gstin) >= 2 and buyer_gstin[:2].isdigit() else seller_state

        line_breakdowns: List[LineTaxBreakdown] = []
        for itm in self.cart_items:
            line = TaxEngine.calculate_line_item(
                product_id=itm.product_id,
                product_name=itm.name,
                hsn_sac_code=itm.hsn,
                unit_code=itm.unit,
                quantity=itm.quantity,
                unit_price=itm.price,
                gst_rate=itm.gst_rate,
                seller_state_code=seller_state,
                buyer_state_code=buyer_state,
                line_discount=itm.discount,
                is_tax_inclusive=shop.get("tax_inclusive_default", False),
            )
            line_breakdowns.append(line)

        inv_disc = Decimal(str(self.inv_disc_spin.value()))
        summary = TaxEngine.calculate_invoice_summary(line_breakdowns, invoice_discount=inv_disc)
        self.current_summary = summary

        self.subtotal_lbl.setText(f"Subtotal Gross: ₹ {summary.subtotal_gross:.2f}")
        self.taxable_lbl.setText(f"Taxable Amount: ₹ {summary.taxable_amount:.2f}")
        self.cgst_lbl.setText(f"CGST: ₹ {summary.cgst_amount:.2f}")
        self.sgst_lbl.setText(f"SGST: ₹ {summary.sgst_amount:.2f}")
        self.round_off_lbl.setText(f"Round Off: ₹ {summary.round_off_amount:.2f}")
        self.grand_total_lbl.setText(f"₹ {summary.grand_total:.2f}")

    # ---------------- Checkout & Immediate Payment ----------------

    def _handle_checkout(self):
        if not self.cart_items or not self.current_summary:
            QMessageBox.warning(self, "Empty Cart", "Cannot checkout an empty cart. Please scan products first.")
            self.barcode_input.setFocus()
            return

        grand_total = self.current_summary.grand_total

        # Open Payment Settlement Dialog
        pay_dlg = PaymentDialog(grand_total=grand_total, parent=self)
        if pay_dlg.exec() != QDialog.Accepted:
            return

        payments = pay_dlg.confirmed_payments

        cart_inputs = [
            CartItemInput(
                product_id=i.product_id,
                quantity=i.quantity,
                unit_price=i.price,
                line_discount=i.discount,
                variant_id=i.variant_id,
                gst_rate=i.gst_rate,
            )
            for i in self.cart_items
        ]

        try:
            sale_dict = self.billing_service.complete_sale(
                current_session=self.current_session,
                cart_items=cart_inputs,
                payments=payments,
                invoice_discount=Decimal(str(self.inv_disc_spin.value())),
            )
            self.last_completed_invoice = sale_dict

            # Open Invoice Preview / Print Dialog
            preview = InvoicePreviewDialog(
                invoice_data=sale_dict,
                settings_service=self.settings_service,
                print_service=self.print_service,
                parent=self,
            )
            preview.exec()

            # Clear cart for next customer
            self.clear_cart()

        except AccountInactiveError as exc:
            QMessageBox.critical(self, "Account Deactivated", f"{exc}\nPlease contact your administrator.")
            self.checkout_btn.setEnabled(False)
        except InsufficientStockError as exc:
            QMessageBox.critical(self, "Insufficient Stock", str(exc))
        except PaymentMismatchedError as exc:
            QMessageBox.critical(self, "Payment Error", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Checkout Failed", f"An error occurred while saving invoice:\n{exc}")

    def reprint_last_bill(self):
        if not self.last_completed_invoice:
            QMessageBox.information(self, "No Recent Sale", "No recent invoice found in this session to reprint.")
            return

        preview = InvoicePreviewDialog(
            invoice_data=self.last_completed_invoice,
            settings_service=self.settings_service,
            print_service=self.print_service,
            parent=self,
        )
        preview.exec()

    # ---------------- Multi-Customer Hold & Recall Handlers ----------------

    def _handle_hold_bill(self):
        if not self.cart_items:
            QMessageBox.information(self, "Hold Bill", "The active cart is empty. There are no items to hold.")
            return

        cust_name = self.cust_name_input.text().strip() or "Walk-in Customer"
        cust_phone = self.cust_phone_input.text().strip()
        cust_gstin = self.cust_gstin_input.text().strip()
        inv_disc = Decimal(str(self.inv_disc_spin.value()))

        cart_data = [item.to_dict() for item in self.cart_items]

        try:
            parked = self.billing_service.park_bill(
                current_session=self.current_session,
                cart_data=cart_data,
                customer_name=cust_name,
                customer_phone=cust_phone,
                customer_gstin=cust_gstin,
                invoice_discount=inv_disc,
            )
            self.clear_cart()
            self._update_parked_badge()
            QMessageBox.information(
                self,
                "Bill Held / Parked",
                f"Customer basket saved as {parked['park_reference']} ({parked['items_count']} items, ₹ {parked['total_amount']:,.2f}).\n\nScreen cleared for the next customer. Press [F10] to recall anytime."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error Holding Bill", str(e))

    def _handle_recall_bill(self):
        from src.ui.dialogs.recall_bill_dialog import RecallParkedBillDialog
        dlg = RecallParkedBillDialog(self.billing_service, self.current_session, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.recalled_cart_data:
            data = dlg.recalled_cart_data

            if self.cart_items:
                reply = QMessageBox.question(
                    self,
                    "Active Cart Not Empty",
                    "You already have items in your current cart.\nWould you like to hold the current cart before loading the recalled basket?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes,
                )
                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:
                    c_data = [item.to_dict() for item in self.cart_items]
                    self.billing_service.park_bill(
                        current_session=self.current_session,
                        cart_data=c_data,
                        customer_name=self.cust_name_input.text().strip() or "Walk-in Customer",
                        customer_phone=self.cust_phone_input.text().strip(),
                        customer_gstin=self.cust_gstin_input.text().strip(),
                        invoice_discount=Decimal(str(self.inv_disc_spin.value())),
                    )

            # Load recalled cart
            self.cart_items = [POSCartItem.from_dict(d) for d in data["cart_data"]]
            self.cust_name_input.setText(data.get("customer_name") or "")
            self.cust_phone_input.setText(data.get("customer_phone") or "")
            self.cust_gstin_input.setText(data.get("customer_gstin") or "")
            self.inv_disc_spin.setValue(float(data.get("invoice_discount", 0.0)))

            self._refresh_cart_table()
            self.update_totals()
            self._update_parked_badge()
            self.barcode_input.setFocus()
            QMessageBox.information(
                self,
                "Basket Restored",
                f"Restored held basket {data['park_reference']} for {data.get('customer_name') or 'Customer'}."
            )
        else:
            self._update_parked_badge()

    def _update_parked_badge(self):
        try:
            count = self.billing_service.get_parked_bills_count(self.current_session)
            if count > 0:
                self.recall_btn.setText(f"📂 Recall Bill ({count}) (F10)")
                self.recall_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2563EB;
                        color: #FFFFFF;
                        font-weight: 700;
                        border: 1px solid #1D4ED8;
                        border-radius: 6px;
                        padding: 4px 14px;
                    }
                    QPushButton:hover {
                        background-color: #1D4ED8;
                    }
                """)
            else:
                self.recall_btn.setText("📂 Recall Bill (F10)")
                self.recall_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #EFF6FF;
                        color: #1D4ED8;
                        font-weight: 600;
                        border: 1px solid #BFDBFE;
                        border-radius: 6px;
                        padding: 4px 14px;
                    }
                    QPushButton:hover {
                        background-color: #DBEAFE;
                    }
                """)
        except Exception:
            pass
