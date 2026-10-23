"""
Category and Brand Management Dialog.
Supports adding, renaming, organizing, and archiving/deactivating categories and brands.
"""

from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QWidget, QMessageBox, QInputDialog
)

from src.services.product_service import ProductService
from src.services.auth_service import UserSession


class CategoryBrandManagerDialog(QDialog):
    def __init__(self, product_service: ProductService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.product_service = product_service
        self.current_session = current_session

        self.setWindowTitle("Manage Categories & Brands")
        self.setMinimumSize(750, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self.refresh_categories()
        self.refresh_brands()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        tabs = QTabWidget()

        # ---------------- Tab 1: Categories ----------------
        cat_widget = QWidget()
        cat_layout = QVBoxLayout(cat_widget)
        cat_layout.setContentsMargins(12, 12, 12, 12)
        cat_layout.setSpacing(10)

        cat_btn_bar = QHBoxLayout()
        cat_title = QLabel("Product Categories")
        cat_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #0F172A;")
        cat_btn_bar.addWidget(cat_title)
        cat_btn_bar.addStretch()

        self.add_cat_btn = QPushButton("+ New Category")
        self.add_cat_btn.setObjectName("PrimaryBtn")
        self.add_cat_btn.clicked.connect(self._handle_add_category)
        cat_btn_bar.addWidget(self.add_cat_btn)
        cat_layout.addLayout(cat_btn_bar)

        self.cat_table = QTableWidget()
        self.cat_table.setColumnCount(4)
        self.cat_table.setHorizontalHeaderLabels(["ID", "Category Name", "Code", "Actions"])
        self.cat_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.cat_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.cat_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.cat_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.cat_table.verticalHeader().setDefaultSectionSize(36)
        self.cat_table.verticalHeader().setVisible(False)
        cat_layout.addWidget(self.cat_table)

        tabs.addTab(cat_widget, "📁 Categories")

        # ---------------- Tab 2: Brands ----------------
        brand_widget = QWidget()
        brand_layout = QVBoxLayout(brand_widget)
        brand_layout.setContentsMargins(12, 12, 12, 12)
        brand_layout.setSpacing(10)

        brand_btn_bar = QHBoxLayout()
        brand_title = QLabel("Product Brands & Manufacturers")
        brand_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #0F172A;")
        brand_btn_bar.addWidget(brand_title)
        brand_btn_bar.addStretch()

        self.add_brand_btn = QPushButton("+ New Brand")
        self.add_brand_btn.setObjectName("PrimaryBtn")
        self.add_brand_btn.clicked.connect(self._handle_add_brand)
        brand_btn_bar.addWidget(self.add_brand_btn)
        brand_layout.addLayout(brand_btn_bar)

        self.brand_table = QTableWidget()
        self.brand_table.setColumnCount(4)
        self.brand_table.setHorizontalHeaderLabels(["ID", "Brand Name", "Manufacturer", "Actions"])
        self.brand_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.brand_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.brand_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.brand_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.brand_table.verticalHeader().setDefaultSectionSize(36)
        self.brand_table.verticalHeader().setVisible(False)
        brand_layout.addWidget(self.brand_table)

        tabs.addTab(brand_widget, "🏷️ Brands")

        layout.addWidget(tabs)

        close_btn = QPushButton("Done")
        close_btn.setObjectName("SecondaryBtn")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def refresh_categories(self):
        cats = self.product_service.list_categories()
        self.cat_table.setRowCount(len(cats))
        for row, c in enumerate(cats):
            self.cat_table.setItem(row, 0, QTableWidgetItem(str(c["id"])))
            self.cat_table.setItem(row, 1, QTableWidgetItem(c["name"]))
            self.cat_table.setItem(row, 2, QTableWidgetItem(c.get("code") or "-"))

            rename_btn = QPushButton("Rename")
            rename_btn.setObjectName("TableActionBtn")
            rename_btn.setFixedHeight(28)
            rename_btn.setMinimumWidth(65)
            rename_btn.clicked.connect(lambda _, cid=c["id"], cur=c["name"]: self._handle_rename_category(cid, cur))
            self.cat_table.setCellWidget(row, 3, rename_btn)

    def refresh_brands(self):
        brands = self.product_service.list_brands()
        self.brand_table.setRowCount(len(brands))
        for row, b in enumerate(brands):
            self.brand_table.setItem(row, 0, QTableWidgetItem(str(b["id"])))
            self.brand_table.setItem(row, 1, QTableWidgetItem(b["name"]))
            self.brand_table.setItem(row, 2, QTableWidgetItem(b.get("manufacturer_name") or "-"))

            rename_btn = QPushButton("Rename")
            rename_btn.setObjectName("TableActionBtn")
            rename_btn.setFixedHeight(28)
            rename_btn.setMinimumWidth(65)
            rename_btn.clicked.connect(lambda _, bid=b["id"], cur=b["name"]: self._handle_rename_brand(bid, cur))
            self.brand_table.setCellWidget(row, 3, rename_btn)

    def _handle_add_category(self):
        name, ok = QInputDialog.getText(self, "New Category", "Enter category name:")
        if ok and name.strip():
            self.product_service.get_or_create_category(self.current_session, name.strip())
            self.refresh_categories()

    def _handle_rename_category(self, cat_id: int, current_name: str):
        new_name, ok = QInputDialog.getText(self, "Rename Category", "Edit category name:", QLineEdit.Normal, current_name)
        if ok and new_name.strip() and new_name.strip() != current_name:
            try:
                self.product_service.update_category(self.current_session, cat_id, new_name.strip())
                self.refresh_categories()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _handle_add_brand(self):
        name, ok = QInputDialog.getText(self, "New Brand", "Enter brand name:")
        if ok and name.strip():
            self.product_service.get_or_create_brand(self.current_session, name.strip())
            self.refresh_brands()

    def _handle_rename_brand(self, brand_id: int, current_name: str):
        new_name, ok = QInputDialog.getText(self, "Rename Brand", "Edit brand name:", QLineEdit.Normal, current_name)
        if ok and new_name.strip() and new_name.strip() != current_name:
            try:
                self.product_service.update_brand(self.current_session, brand_id, new_name.strip())
                self.refresh_brands()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
