"""
Recall Parked / Held Shopping Baskets Dialog.
Allows cashiers to quickly search, inspect, and restore held customer carts.
"""

from typing import Optional, Dict, Any, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QMessageBox, QWidget
)

from src.services.auth_service import UserSession
from src.services.billing_service import BillingService


class RecallParkedBillDialog(QDialog):
    def __init__(
        self,
        billing_service: BillingService,
        current_session: UserSession,
        parent=None,
    ):
        super().__init__(parent)
        self.billing_service = billing_service
        self.current_session = current_session
        self.recalled_cart_data: Optional[Dict[str, Any]] = None

        self.setWindowTitle("📂 Recall Held Customer Basket")
        self.setMinimumSize(860, 480)
        self.resize(920, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self.refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Parked / Held Customer Baskets")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Select a customer's basket to restore to your active register counter.")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setObjectName("SecondaryBtn")
        refresh_btn.setFixedHeight(32)
        refresh_btn.clicked.connect(self.refresh_table)
        top_bar.addWidget(refresh_btn)

        layout.addLayout(top_bar)

        # Held Bills Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Hold Ref", "Time", "Customer Name", "Items", "Total (₹)", "Counter", "Action"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 190)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        # Bottom Buttons
        bottom_bar = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #64748B; font-weight: 600;")
        bottom_bar.addWidget(self.status_lbl)

        bottom_bar.addStretch()

        close_btn = QPushButton("Close (Esc)")
        close_btn.setObjectName("SecondaryBtn")
        close_btn.clicked.connect(self.reject)
        bottom_bar.addWidget(close_btn)

        layout.addLayout(bottom_bar)

    def refresh_table(self):
        try:
            bills = self.billing_service.list_parked_bills(self.current_session)
            self.table.setRowCount(len(bills))
            self.status_lbl.setText(f"{len(bills)} held customer basket(s) waiting")

            for row, b in enumerate(bills):
                ref_item = QTableWidgetItem(b["park_reference"])
                ref_item.setData(Qt.UserRole, b["id"])
                self.table.setItem(row, 0, ref_item)
                self.table.setItem(row, 1, QTableWidgetItem(b["created_at"]))
                self.table.setItem(row, 2, QTableWidgetItem(b["customer_name"]))
                self.table.setItem(row, 3, QTableWidgetItem(str(b["items_count"])))
                self.table.setItem(row, 4, QTableWidgetItem(f"₹ {b['total_amount']:,.2f}"))
                self.table.setItem(row, 5, QTableWidgetItem(b["counter_id"]))

                # Action Container
                act_widget = QWidget()
                act_layout = QHBoxLayout(act_widget)
                act_layout.setContentsMargins(4, 2, 4, 2)
                act_layout.setSpacing(8)
                act_layout.setAlignment(Qt.AlignCenter)

                recall_btn = QPushButton("Restore Cart")
                recall_btn.setFixedHeight(30)
                recall_btn.setMinimumWidth(105)
                recall_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2563EB;
                        color: #FFFFFF;
                        font-weight: 700;
                        font-size: 12px;
                        border-radius: 5px;
                        padding: 0 10px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #1D4ED8;
                    }
                    QPushButton:pressed {
                        background-color: #1E40AF;
                    }
                """)
                recall_btn.clicked.connect(lambda _, pid=b["id"]: self._recall_single(pid))
                act_layout.addWidget(recall_btn)

                cancel_btn = QPushButton("✕ Discard")
                cancel_btn.setFixedHeight(30)
                cancel_btn.setMinimumWidth(68)
                cancel_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FEE2E2;
                        color: #DC2626;
                        font-weight: 700;
                        font-size: 11px;
                        border-radius: 5px;
                        padding: 0 6px;
                        border: 1px solid #FECACA;
                    }
                    QPushButton:hover {
                        background-color: #DC2626;
                        color: #FFFFFF;
                        border-color: #DC2626;
                    }
                """)
                cancel_btn.setToolTip("Discard this held bill")
                cancel_btn.clicked.connect(lambda _, pid=b["id"]: self._cancel_single(pid))
                act_layout.addWidget(cancel_btn)

                self.table.setCellWidget(row, 6, act_widget)

        except Exception as e:
            QMessageBox.critical(self, "Error Loading Held Bills", str(e))

    def _recall_single(self, parked_id: int):
        try:
            recalled = self.billing_service.recall_bill(self.current_session, parked_id)
            self.recalled_cart_data = recalled
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Recall Failed", str(e))

    def _on_row_double_clicked(self, row, col):
        item = self.table.item(row, 0)
        if item:
            pid = item.data(Qt.UserRole)
            self._recall_single(pid)

    def _cancel_single(self, parked_id: int):
        reply = QMessageBox.question(
            self,
            "Discard Held Bill",
            "Are you sure you want to discard this held customer basket?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.billing_service.cancel_parked_bill(self.current_session, parked_id)
                self.refresh_table()
            except Exception as e:
                QMessageBox.critical(self, "Discard Failed", str(e))
