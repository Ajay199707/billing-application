"""
Spreadsheet-Like Bulk Product Entry Dialog.
Allows adding multiple rows, copy-pasting from Excel, cell editing,
validation, duplicate detection, and batch saving.
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QClipboard, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QComboBox
)

from src.services.product_service import ProductService
from src.services.auth_service import UserSession


class BulkProductEntryDialog(QDialog):
    def __init__(self, product_service: ProductService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.product_service = product_service
        self.current_session = current_session

        self.setWindowTitle("Bulk Product Entry (Spreadsheet Grid)")
        self.setMinimumSize(1080, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.uoms = self.product_service.list_uoms()
        self.tax_profiles = self.product_service.list_tax_profiles()

        self._init_ui()
        self._add_empty_rows(5)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QLabel("Bulk Product Entry & Excel Paste")
        header.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        layout.addWidget(header)

        sub = QLabel(
            "Enter products row-by-row or copy-paste columns from Excel (Format: Name | Category | Brand | Unit | Cost | Price | MRP | Stock | Barcode)."
        )
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        layout.addWidget(sub)

        # Toolbar
        tb_layout = QHBoxLayout()
        self.add_row_btn = QPushButton("+ Add Row")
        self.add_row_btn.setObjectName("SecondaryBtn")
        self.add_row_btn.clicked.connect(lambda: self._add_empty_rows(1))
        tb_layout.addWidget(self.add_row_btn)

        self.add_5_btn = QPushButton("+ Add 5 Rows")
        self.add_5_btn.setObjectName("SecondaryBtn")
        self.add_5_btn.clicked.connect(lambda: self._add_empty_rows(5))
        tb_layout.addWidget(self.add_5_btn)

        self.paste_btn = QPushButton("📋 Paste from Excel / Clipboard")
        self.paste_btn.setObjectName("SecondaryBtn")
        self.paste_btn.clicked.connect(self._handle_paste_from_clipboard)
        tb_layout.addWidget(self.paste_btn)

        self.del_row_btn = QPushButton("🗑️ Remove Selected Row")
        self.del_row_btn.setObjectName("SecondaryBtn")
        self.del_row_btn.clicked.connect(self._handle_remove_row)
        tb_layout.addWidget(self.del_row_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setObjectName("SecondaryBtn")
        self.clear_btn.clicked.connect(self._handle_clear_table)
        tb_layout.addWidget(self.clear_btn)

        tb_layout.addStretch()

        self.validate_btn = QPushButton("🔍 Validate All Rows")
        self.validate_btn.setObjectName("SecondaryBtn")
        self.validate_btn.clicked.connect(self.validate_all_rows)
        tb_layout.addWidget(self.validate_btn)

        layout.addLayout(tb_layout)

        # Main Grid Table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Product Name *", "Category", "Brand", "Unit (PCS/KG/L/PACK)",
            "Cost (₹)", "Selling Price (₹) *", "MRP (₹)", "Opening Stock", "Barcode", "Validation Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

        # Footer Actions
        footer = QHBoxLayout()
        self.status_lbl = QLabel("Ready. Fill cells or paste from clipboard.")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #64748B; font-weight: 600;")
        footer.addWidget(self.status_lbl)

        footer.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("SecondaryBtn")
        self.cancel_btn.clicked.connect(self.reject)
        footer.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("💾 Save All Valid Products")
        self.save_btn.setObjectName("PrimaryBtn")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self._handle_save_batch)
        footer.addWidget(self.save_btn)

        layout.addLayout(footer)

    def _add_empty_rows(self, count: int = 1):
        start_row = self.table.rowCount()
        self.table.setRowCount(start_row + count)
        for r in range(start_row, start_row + count):
            self.table.setItem(r, 0, QTableWidgetItem(""))
            self.table.setItem(r, 1, QTableWidgetItem("General Grocery"))
            self.table.setItem(r, 2, QTableWidgetItem("-"))
            self.table.setItem(r, 3, QTableWidgetItem("PCS"))
            self.table.setItem(r, 4, QTableWidgetItem("0.00"))
            self.table.setItem(r, 5, QTableWidgetItem("0.00"))
            self.table.setItem(r, 6, QTableWidgetItem("0.00"))
            self.table.setItem(r, 7, QTableWidgetItem("10.00"))
            self.table.setItem(r, 8, QTableWidgetItem(""))
            status_item = QTableWidgetItem("Draft")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 9, status_item)

    def _handle_remove_row(self):
        curr = self.table.currentRow()
        if curr >= 0:
            self.table.removeRow(curr)

    def _handle_clear_table(self):
        self.table.setRowCount(0)
        self._add_empty_rows(5)
        self.status_lbl.setText("Grid cleared.")

    def _handle_paste_from_clipboard(self):
        clipboard = QGuiApplication.clipboard()
        text = clipboard.text()
        if not text:
            QMessageBox.information(self, "Clipboard Empty", "No tabular text found in clipboard.")
            return

        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        if not lines:
            return

        # Check delimiter: tab (\t) for Excel, or comma
        sep = "\t" if "\t" in lines[0] else ","
        start_row = self.table.rowCount()
        self.table.setRowCount(start_row + len(lines))

        for idx, line in enumerate(lines):
            r = start_row + idx
            parts = [p.strip().strip('"') for p in line.split(sep)]

            name = parts[0] if len(parts) > 0 else ""
            cat = parts[1] if len(parts) > 1 and parts[1] else "General Grocery"
            brand = parts[2] if len(parts) > 2 and parts[2] else "-"
            unit = parts[3] if len(parts) > 3 and parts[3] else "PCS"
            cost = parts[4] if len(parts) > 4 and parts[4] else "0.00"
            price = parts[5] if len(parts) > 5 and parts[5] else "0.00"
            mrp = parts[6] if len(parts) > 6 and parts[6] else price
            stock = parts[7] if len(parts) > 7 and parts[7] else "10.00"
            bc = parts[8] if len(parts) > 8 else ""

            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(cat))
            self.table.setItem(r, 2, QTableWidgetItem(brand))
            self.table.setItem(r, 3, QTableWidgetItem(unit))
            self.table.setItem(r, 4, QTableWidgetItem(cost))
            self.table.setItem(r, 5, QTableWidgetItem(price))
            self.table.setItem(r, 6, QTableWidgetItem(mrp))
            self.table.setItem(r, 7, QTableWidgetItem(stock))
            self.table.setItem(r, 8, QTableWidgetItem(bc))

            status_item = QTableWidgetItem("Pasted")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 9, status_item)

        self.status_lbl.setText(f"Pasted {len(lines)} rows from clipboard. Click 'Validate All Rows' to verify.")

    def validate_all_rows(self) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        Validates all grid rows. Highlights error cells in soft red.
        Returns (valid_rows_data, invalid_row_indices).
        """
        valid_items = []
        invalid_rows = []

        uom_map = {u["code"].upper(): u["id"] for u in self.uoms}
        default_uom_id = self.uoms[0]["id"] if self.uoms else 1
        default_tax_id = self.tax_profiles[0]["id"] if self.tax_profiles else 1

        seen_barcodes = set()

        for r in range(self.table.rowCount()):
            # Clear previous highlighting
            for c in range(10):
                item = self.table.item(r, c)
                if item:
                    item.setBackground(QColor("#FFFFFF"))

            name_item = self.table.item(r, 0)
            name = name_item.text().strip() if name_item else ""
            if not name:
                # If entire row is empty, skip quietly
                if not any(self.table.item(r, col) and self.table.item(r, col).text().strip() for col in range(1, 9)):
                    continue
                name_item.setBackground(QColor("#FEE2E2"))
                self.table.item(r, 9).setText("❌ Missing Name")
                invalid_rows.append(r)
                continue

            # Price
            price_item = self.table.item(r, 5)
            price_str = price_item.text().strip() if price_item else "0"
            try:
                price = Decimal(price_str)
                if price <= Decimal("0.00"):
                    raise ValueError()
            except Exception:
                price_item.setBackground(QColor("#FEE2E2"))
                self.table.item(r, 9).setText("❌ Invalid Price")
                invalid_rows.append(r)
                continue

            # Cost
            cost_item = self.table.item(r, 4)
            cost_str = cost_item.text().strip() if cost_item else "0"
            try:
                cost = Decimal(cost_str)
                if cost < Decimal("0.00"):
                    raise ValueError()
            except Exception:
                cost = Decimal("0.00")

            # MRP
            mrp_item = self.table.item(r, 6)
            mrp_str = mrp_item.text().strip() if mrp_item else price_str
            try:
                mrp = Decimal(mrp_str)
            except Exception:
                mrp = price

            # Stock
            stock_item = self.table.item(r, 7)
            stock_str = stock_item.text().strip() if stock_item else "0"
            try:
                stock = Decimal(stock_str)
            except Exception:
                stock = Decimal("0.000")

            # Unit
            unit_item = self.table.item(r, 3)
            unit_str = unit_item.text().strip().upper() if unit_item else "PCS"
            unit_id = uom_map.get(unit_str, default_uom_id)

            # Barcode
            bc_item = self.table.item(r, 8)
            bc = bc_item.text().strip() if bc_item else None
            if bc:
                if bc in seen_barcodes:
                    bc_item.setBackground(QColor("#FEE2E2"))
                    self.table.item(r, 9).setText("❌ Duplicate Barcode in Table")
                    invalid_rows.append(r)
                    continue
                seen_barcodes.add(bc)

            cat_item = self.table.item(r, 1)
            cat_str = cat_item.text().strip() if cat_item else "General Grocery"

            brand_item = self.table.item(r, 2)
            brand_str = brand_item.text().strip() if brand_item else "-"

            valid_items.append({
                "row_idx": r,
                "name": name,
                "category_name": cat_str,
                "brand_name": brand_str,
                "unit_id": unit_id,
                "tax_profile_id": default_tax_id,
                "purchase_cost": cost,
                "selling_price": price,
                "mrp": mrp,
                "initial_stock": stock,
                "barcode": bc or None,
            })
            self.table.item(r, 9).setText("✅ Valid")
            self.table.item(r, 9).setForeground(Qt.darkGreen)

        if invalid_rows:
            self.status_lbl.setText(f"Validation: {len(valid_items)} valid, {len(invalid_rows)} invalid rows highlighted in red.")
        else:
            self.status_lbl.setText(f"Validation passed: {len(valid_items)} valid rows ready to save.")

        return valid_items, invalid_rows

    def _handle_save_batch(self):
        valid_items, invalid_rows = self.validate_all_rows()
        if not valid_items:
            QMessageBox.warning(self, "No Valid Rows", "No valid product rows to save. Please correct errors.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Batch Save",
            f"Are you sure you want to save {len(valid_items)} valid products to inventory?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        saved_count = 0
        errors = []

        for p in valid_items:
            try:
                # Resolve or auto-create Category and Brand
                cat_id = self.product_service.get_or_create_category(self.current_session, p["category_name"])
                brand_id = self.product_service.get_or_create_brand(self.current_session, p["brand_name"])

                # Auto-generate SKU
                import uuid
                sku = f"SKU-{uuid.uuid4().hex[:8].upper()}"

                self.product_service.create_product(
                    current_session=self.current_session,
                    name=p["name"],
                    sku=sku,
                    barcode=p["barcode"],
                    unit_id=p["unit_id"],
                    tax_profile_id=p["tax_profile_id"],
                    selling_price=p["selling_price"],
                    purchase_cost=p["purchase_cost"],
                    mrp=p["mrp"],
                    reorder_level=Decimal("5.000"),
                    category_id=cat_id,
                    brand_id=brand_id,
                    initial_stock=p["initial_stock"],
                )
                saved_count += 1
            except Exception as e:
                errors.append(f"Row {p['row_idx'] + 1} ({p['name']}): {e}")

        msg = f"Successfully created and stocked {saved_count} products."
        if errors:
            msg += f"\n\nErrors encountered on {len(errors)} rows:\n" + "\n".join(errors[:5])

        QMessageBox.information(self, "Batch Import Completed", msg)

        if saved_count > 0:
            self.accept()
