"""
Immediate POS Payment Settlement Dialog.
Streamlined for fast counter cashier checkout:
- 1-Click Payment Mode Switcher: Cash (F1 / 1), UPI Stand (F2 / 2), Card (F3 / 3), Split (F4 / 4)
- UPI Mode for Counter Stand QR: 100% allocated to UPI in 1 keystroke, check soundbox & complete
- Cash Mode with Tendered and Change calculation
- Clear payment breakdown and single Enter key confirmation
"""

from decimal import Decimal
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QKeyEvent
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QDoubleSpinBox, QGridLayout,
    QStackedWidget, QWidget
)

from src.services.billing_service import PaymentInput
from src.services.tax_service import round_currency


class PaymentDialog(QDialog):
    def __init__(self, grand_total: Decimal, parent=None):
        super().__init__(parent)
        self.grand_total = grand_total
        self.confirmed_payments: List[PaymentInput] = []
        self.current_mode = "CASH"  # "CASH", "UPI", "CARD", "SPLIT"

        self.setWindowTitle("Settle Payment - POS Checkout")
        self.setFixedSize(520, 540)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._setup_shortcuts()
        self.set_mode("CASH")

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        # 1. Header: Total Amount Card
        total_card = QFrame()
        total_card.setStyleSheet("background-color: #064E3B; border-radius: 8px; padding: 10px;")
        t_box = QVBoxLayout(total_card)
        t_box.setContentsMargins(6, 6, 6, 6)
        t_box.setSpacing(2)

        t_lbl = QLabel("TOTAL AMOUNT PAYABLE")
        t_lbl.setStyleSheet("color: #A7F3D0; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        t_lbl.setAlignment(Qt.AlignCenter)
        t_box.addWidget(t_lbl)

        self.amount_lbl = QLabel(f"₹ {self.grand_total:.2f}")
        self.amount_lbl.setStyleSheet("color: #34D399; font-size: 32px; font-weight: 900;")
        self.amount_lbl.setAlignment(Qt.AlignCenter)
        t_box.addWidget(self.amount_lbl)

        root_layout.addWidget(total_card)

        # 2. Ask Customer: Payment Mode Selection Tabs
        ask_lbl = QLabel("Select Customer Payment Method:")
        ask_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #065F46; text-transform: uppercase;")
        root_layout.addWidget(ask_lbl)

        mode_bar = QHBoxLayout()
        mode_bar.setSpacing(8)

        self.btn_cash = QPushButton("💵 Cash (F1)")
        self.btn_cash.setFixedHeight(38)
        self.btn_cash.clicked.connect(lambda: self.set_mode("CASH"))
        mode_bar.addWidget(self.btn_cash)

        self.btn_upi = QPushButton("📱 UPI / Stand (F2)")
        self.btn_upi.setFixedHeight(38)
        self.btn_upi.clicked.connect(lambda: self.set_mode("UPI"))
        mode_bar.addWidget(self.btn_upi)

        self.btn_card = QPushButton("💳 Card (F3)")
        self.btn_card.setFixedHeight(38)
        self.btn_card.clicked.connect(lambda: self.set_mode("CARD"))
        mode_bar.addWidget(self.btn_card)

        self.btn_split = QPushButton("🔀 Split (F4)")
        self.btn_split.setFixedHeight(38)
        self.btn_split.clicked.connect(lambda: self.set_mode("SPLIT"))
        mode_bar.addWidget(self.btn_split)

        root_layout.addLayout(mode_bar)

        # 3. Stacked View for Each Payment Mode
        self.stack = QStackedWidget()

        # --- View 0: Cash Mode ---
        self.cash_view = QWidget()
        cv_layout = QVBoxLayout(self.cash_view)
        cv_layout.setContentsMargins(12, 12, 12, 12)
        cv_layout.setSpacing(10)

        c_grid = QGridLayout()
        c_grid.setHorizontalSpacing(12)
        c_grid.setVerticalSpacing(10)

        c_grid.addWidget(QLabel("Cash Due:"), 0, 0)
        self.cash_bill_amt = QLabel(f"₹ {self.grand_total:.2f}")
        self.cash_bill_amt.setStyleSheet("font-size: 15px; font-weight: 700; color: #064E3B;")
        c_grid.addWidget(self.cash_bill_amt, 0, 1)

        c_grid.addWidget(QLabel("Cash Received:"), 1, 0)
        self.tendered_spin = QDoubleSpinBox()
        self.tendered_spin.setRange(0, 1000000)
        self.tendered_spin.setValue(float(self.grand_total))
        self.tendered_spin.setPrefix("₹ ")
        self.tendered_spin.setDecimals(2)
        self.tendered_spin.setFixedHeight(36)
        self.tendered_spin.setStyleSheet("font-size: 15px; font-weight: 700; color: #064E3B;")
        self.tendered_spin.valueChanged.connect(self._recalculate_change)
        c_grid.addWidget(self.tendered_spin, 1, 1)

        c_grid.addWidget(QLabel("Change to Return:"), 2, 0)
        self.change_lbl = QLabel("₹ 0.00")
        self.change_lbl.setStyleSheet("font-weight: 800; color: #2563EB; font-size: 18px;")
        c_grid.addWidget(self.change_lbl, 2, 1)

        cv_layout.addLayout(c_grid)

        cash_tip = QLabel("💡 Tip: Enter cash tendered to calculate change, then press Enter to complete.")
        cash_tip.setStyleSheet("font-size: 11px; color: #64748B; font-style: italic;")
        cv_layout.addWidget(cash_tip)
        cv_layout.addStretch()
        self.stack.addWidget(self.cash_view)

        # --- View 1: UPI Mode (Stand QR) ---
        self.upi_view = QWidget()
        uv_layout = QVBoxLayout(self.upi_view)
        uv_layout.setContentsMargins(12, 12, 12, 12)
        uv_layout.setSpacing(10)

        upi_banner = QFrame()
        upi_banner.setStyleSheet("""
            QFrame {
                background-color: #ECFDF5;
                border: 1px solid #A7F3D0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        ub_layout = QVBoxLayout(upi_banner)
        ub_layout.setSpacing(6)

        upi_title = QLabel("📱 UPI Stand Payment (GPay / PhonePe / Paytm)")
        upi_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #064E3B; border: none; background: transparent;")
        ub_layout.addWidget(upi_title)

        self.upi_collect_lbl = QLabel(f"Amount to Collect: ₹ {self.grand_total:.2f}")
        self.upi_collect_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #059669; border: none; background: transparent;")
        ub_layout.addWidget(self.upi_collect_lbl)

        step1 = QLabel("1. Customer scans the shop QR code on the counter stand.")
        step1.setStyleSheet("font-size: 12px; color: #065F46; border: none; background: transparent;")
        ub_layout.addWidget(step1)

        step2 = QLabel("2. Check Paytm / PhonePe Soundbox voice alert or phone notification.")
        step2.setStyleSheet("font-size: 12px; color: #065F46; font-weight: 600; border: none; background: transparent;")
        ub_layout.addWidget(step2)

        step3 = QLabel("3. Press Enter to confirm payment and print bill.")
        step3.setStyleSheet("font-size: 12px; color: #065F46; border: none; background: transparent;")
        ub_layout.addWidget(step3)

        uv_layout.addWidget(upi_banner)

        # Optional UTR / Reference
        ref_box = QHBoxLayout()
        ref_lbl = QLabel("UPI Ref / UTR:")
        ref_lbl.setStyleSheet("font-size: 12px; color: #475569;")
        ref_box.addWidget(ref_lbl)

        self.upi_ref_input = QLineEdit()
        self.upi_ref_input.setPlaceholderText("Last 4 digits or UTR (Optional)")
        self.upi_ref_input.setFixedHeight(34)
        ref_box.addWidget(self.upi_ref_input)
        uv_layout.addLayout(ref_box)

        uv_layout.addStretch()
        self.stack.addWidget(self.upi_view)

        # --- View 2: Card Mode ---
        self.card_view = QWidget()
        card_layout = QVBoxLayout(self.card_view)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        card_banner = QFrame()
        card_banner.setStyleSheet("background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 10px;")
        cb_layout = QVBoxLayout(card_banner)
        cb_layout.setSpacing(6)

        card_title = QLabel("💳 Card Payment (Debit / Credit)")
        card_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #1E3A8A; border: none; background: transparent;")
        cb_layout.addWidget(card_title)

        self.card_amt_lbl = QLabel(f"Amount to Charge: ₹ {self.grand_total:.2f}")
        self.card_amt_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #2563EB; border: none; background: transparent;")
        cb_layout.addWidget(self.card_amt_lbl)

        card_step = QLabel("Swipe / Tap customer card on POS terminal, then confirm.")
        card_step.setStyleSheet("font-size: 12px; color: #1E40AF; border: none; background: transparent;")
        cb_layout.addWidget(card_step)

        card_layout.addWidget(card_banner)

        card_ref_box = QHBoxLayout()
        card_ref_lbl = QLabel("Approval Code:")
        card_ref_lbl.setStyleSheet("font-size: 12px; color: #475569;")
        card_ref_box.addWidget(card_ref_lbl)

        self.card_ref_input = QLineEdit()
        self.card_ref_input.setPlaceholderText("Auth Code or Card digits (Optional)")
        self.card_ref_input.setFixedHeight(34)
        card_ref_box.addWidget(self.card_ref_input)
        card_layout.addLayout(card_ref_box)

        card_layout.addStretch()
        self.stack.addWidget(self.card_view)

        # --- View 3: Split Mode ---
        self.split_view = QWidget()
        sv_layout = QVBoxLayout(self.split_view)
        sv_layout.setContentsMargins(12, 12, 12, 12)
        sv_layout.setSpacing(8)

        s_grid = QGridLayout()
        s_grid.setHorizontalSpacing(10)
        s_grid.setVerticalSpacing(8)

        s_grid.addWidget(QLabel("Cash Portion:"), 0, 0)
        self.split_cash_spin = QDoubleSpinBox()
        self.split_cash_spin.setRange(0, 1000000)
        self.split_cash_spin.setPrefix("₹ ")
        self.split_cash_spin.setDecimals(2)
        self.split_cash_spin.valueChanged.connect(self._recalculate_split)
        s_grid.addWidget(self.split_cash_spin, 0, 1)

        s_grid.addWidget(QLabel("UPI Portion:"), 1, 0)
        self.split_upi_spin = QDoubleSpinBox()
        self.split_upi_spin.setRange(0, 1000000)
        self.split_upi_spin.setPrefix("₹ ")
        self.split_upi_spin.setDecimals(2)
        self.split_upi_spin.valueChanged.connect(self._recalculate_split)
        s_grid.addWidget(self.split_upi_spin, 1, 1)

        s_grid.addWidget(QLabel("Card Portion:"), 2, 0)
        self.split_card_spin = QDoubleSpinBox()
        self.split_card_spin.setRange(0, 1000000)
        self.split_card_spin.setPrefix("₹ ")
        self.split_card_spin.setDecimals(2)
        self.split_card_spin.valueChanged.connect(self._recalculate_split)
        s_grid.addWidget(self.split_card_spin, 2, 1)

        sv_layout.addLayout(s_grid)

        self.split_status_lbl = QLabel()
        self.split_status_lbl.setAlignment(Qt.AlignCenter)
        self.split_status_lbl.setStyleSheet("font-weight: 600; padding: 4px;")
        sv_layout.addWidget(self.split_status_lbl)

        sv_layout.addStretch()
        self.stack.addWidget(self.split_view)

        root_layout.addWidget(self.stack)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel (Esc)")
        self.cancel_btn.setObjectName("SecondaryBtn")
        self.cancel_btn.setFixedHeight(44)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn, 1)

        self.confirm_btn = QPushButton("Confirm Payment && Print (Enter)")
        self.confirm_btn.setObjectName("SuccessBtn")
        self.confirm_btn.setFixedHeight(44)
        self.confirm_btn.setStyleSheet("""
            QPushButton#SuccessBtn {
                background-color: #059669;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 800;
                border-radius: 6px;
                border: 1px solid #047857;
            }
            QPushButton#SuccessBtn:hover {
                background-color: #047857;
            }
        """)
        self.confirm_btn.clicked.connect(self._handle_confirm)
        btn_layout.addWidget(self.confirm_btn, 2)

        root_layout.addLayout(btn_layout)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F1"), self, lambda: self.set_mode("CASH"))
        QShortcut(QKeySequence("F2"), self, lambda: self.set_mode("UPI"))
        QShortcut(QKeySequence("F3"), self, lambda: self.set_mode("CARD"))
        QShortcut(QKeySequence("F4"), self, lambda: self.set_mode("SPLIT"))
        QShortcut(QKeySequence("Alt+1"), self, lambda: self.set_mode("CASH"))
        QShortcut(QKeySequence("Alt+2"), self, lambda: self.set_mode("UPI"))
        QShortcut(QKeySequence("Alt+3"), self, lambda: self.set_mode("CARD"))
        QShortcut(QKeySequence("Alt+4"), self, lambda: self.set_mode("SPLIT"))

    def keyPressEvent(self, event: QKeyEvent):
        # Allow instant numeric switching (1=Cash, 2=UPI, 3=Card, 4=Split) when not actively typing inside a spinbox or line edit
        focused = self.focusWidget()
        is_editing = isinstance(focused, (QLineEdit, QDoubleSpinBox))

        if not is_editing:
            if event.key() == Qt.Key_1:
                self.set_mode("CASH")
                event.accept()
                return
            elif event.key() == Qt.Key_2:
                self.set_mode("UPI")
                event.accept()
                return
            elif event.key() == Qt.Key_3:
                self.set_mode("CARD")
                event.accept()
                return
            elif event.key() == Qt.Key_4:
                self.set_mode("SPLIT")
                event.accept()
                return

        super().keyPressEvent(event)

    def set_mode(self, mode: str):
        self.current_mode = mode

        # Update mode button highlights
        active_style = "background-color: #059669; color: #FFFFFF; font-weight: 700; border-radius: 6px; border: 1px solid #047857;"
        idle_style = "background-color: #E6F7EF; color: #065F46; font-weight: 600; border-radius: 6px; border: 1px solid #A7F3D0;"

        self.btn_cash.setStyleSheet(active_style if mode == "CASH" else idle_style)
        self.btn_upi.setStyleSheet(active_style if mode == "UPI" else idle_style)
        self.btn_card.setStyleSheet(active_style if mode == "CARD" else idle_style)
        self.btn_split.setStyleSheet(active_style if mode == "SPLIT" else idle_style)

        if mode == "CASH":
            self.stack.setCurrentIndex(0)
            self.confirm_btn.setText("Confirm Cash Payment && Print (Enter)")
            self.confirm_btn.setEnabled(True)
            self.tendered_spin.setFocus()
            self.tendered_spin.selectAll()
            self._recalculate_change()
        elif mode == "UPI":
            self.stack.setCurrentIndex(1)
            self.confirm_btn.setText("Confirm UPI Payment && Print (Enter)")
            self.confirm_btn.setEnabled(True)
            self.confirm_btn.setFocus()
        elif mode == "CARD":
            self.stack.setCurrentIndex(2)
            self.confirm_btn.setText("Confirm Card Payment && Print (Enter)")
            self.confirm_btn.setEnabled(True)
            self.confirm_btn.setFocus()
        elif mode == "SPLIT":
            self.stack.setCurrentIndex(3)
            self.confirm_btn.setText("Confirm Split Payment && Print (Enter)")
            if self.split_cash_spin.value() == 0 and self.split_upi_spin.value() == 0:
                self.split_cash_spin.setValue(float(self.grand_total))
            self._recalculate_split()
            self.split_cash_spin.setFocus()

    def _recalculate_change(self):
        tendered = Decimal(str(self.tendered_spin.value()))
        cash_due = self.grand_total
        change = tendered - cash_due if tendered >= cash_due else Decimal("0.00")
        self.change_lbl.setText(f"₹ {change:.2f}")

    def _recalculate_split(self):
        c = Decimal(str(self.split_cash_spin.value()))
        u = Decimal(str(self.split_upi_spin.value()))
        cd = Decimal(str(self.split_card_spin.value()))
        total_rec = c + u + cd
        diff = self.grand_total - total_rec

        if diff == Decimal("0.00"):
            self.split_status_lbl.setText("✓ Exact split payment allocated.")
            self.split_status_lbl.setStyleSheet("color: #16A34A; font-weight: 600;")
            self.confirm_btn.setEnabled(True)
        elif diff > Decimal("0.00"):
            self.split_status_lbl.setText(f"Remaining to allocate: ₹ {diff:.2f}")
            self.split_status_lbl.setStyleSheet("color: #DC2626; font-weight: 600;")
            self.confirm_btn.setEnabled(False)
        else:
            self.split_status_lbl.setText(f"Overallocated by: ₹ {-diff:.2f}")
            self.split_status_lbl.setStyleSheet("color: #D97706; font-weight: 600;")
            self.confirm_btn.setEnabled(False)

    def _handle_confirm(self):
        payments: List[PaymentInput] = []

        if self.current_mode == "CASH":
            payments.append(PaymentInput(payment_method="CASH", amount=self.grand_total))
        elif self.current_mode == "UPI":
            ref = self.upi_ref_input.text().strip()
            payments.append(PaymentInput(payment_method="UPI", amount=self.grand_total, transaction_reference=ref if ref else None))
        elif self.current_mode == "CARD":
            ref = self.card_ref_input.text().strip()
            payments.append(PaymentInput(payment_method="CARD", amount=self.grand_total, transaction_reference=ref if ref else None))
        elif self.current_mode == "SPLIT":
            c = Decimal(str(self.split_cash_spin.value()))
            u = Decimal(str(self.split_upi_spin.value()))
            cd = Decimal(str(self.split_card_spin.value()))
            if c > Decimal("0.00"):
                payments.append(PaymentInput(payment_method="CASH", amount=c))
            if u > Decimal("0.00"):
                payments.append(PaymentInput(payment_method="UPI", amount=u))
            if cd > Decimal("0.00"):
                payments.append(PaymentInput(payment_method="CARD", amount=cd))

            total_rec = sum((p.amount for p in payments), Decimal("0.00"))
            if round_currency(total_rec) != round_currency(self.grand_total):
                QMessageBox.warning(self, "Payment Allocation Mismatch", "Recorded payment must equal total amount payable.")
                return

        self.confirmed_payments = payments
        self.accept()
