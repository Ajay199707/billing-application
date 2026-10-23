"""
Price History Audit Log Dialog.
Displays chronological timeline of purchase cost, MRP, and selling price revisions.
"""

from typing import List, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
)

from src.services.price_service import PriceService


class PriceHistoryDialog(QDialog):
    def __init__(self, price_service: PriceService, product_id: int, product_name: str, parent=None):
        super().__init__(parent)
        self.price_service = price_service
        self.product_id = product_id
        self.product_name = product_name

        self.setWindowTitle(f"Price History - {self.product_name}")
        self.setMinimumSize(780, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._load_history()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel(f"Price Modification Audit Trail: {self.product_name}")
        header.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        layout.addWidget(header)

        sub = QLabel("Complete record of who adjusted prices, when the change occurred, and reason for change.")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        layout.addWidget(sub)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Old Price (₹)", "New Price (₹)", "Old Cost (₹)", "New Cost (₹)", "Changed By", "Reason"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)

        layout.addWidget(self.table)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("SecondaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def _load_history(self):
        records = self.price_service.get_price_history(self.product_id)
        self.table.setRowCount(len(records))

        if not records:
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("No historical price changes recorded."))
            self.table.setSpan(0, 0, 1, 7)
            return

        for row, r in enumerate(records):
            self.table.setItem(row, 0, QTableWidgetItem(r["date"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"₹ {r['old_price']:.2f}"))

            new_price_item = QTableWidgetItem(f"₹ {r['new_price']:.2f}")
            new_price_item.setForeground(Qt.darkGreen if r['new_price'] >= r['old_price'] else Qt.darkRed)
            self.table.setItem(row, 2, new_price_item)

            self.table.setItem(row, 3, QTableWidgetItem(f"₹ {r['old_cost']:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"₹ {r['new_cost']:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(r["changed_by"]))
            self.table.setItem(row, 6, QTableWidgetItem(r["reason"]))
