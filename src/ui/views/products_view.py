"""
Product Catalogue Management View.
Enables product listing, search, filtering, add/edit dialog, Excel export, and CSV import.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox, QFileDialog
)

from src.services.product_service import ProductService
from src.services.auth_service import UserSession
from src.ui.dialogs.product_dialog import ProductDialog


class ProductsView(QWidget):
    def __init__(self, product_service: ProductService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.product_service = product_service
        self.current_session = current_session

        self._init_ui()
        self._refresh_category_filter()
        self.refresh_products()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title and Action Buttons
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Product Catalogue & Stock")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Manage merchandise, barcodes, retail pricing, and tax classifications")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.cat_brand_btn = QPushButton("📁 Categories & Brands")
        self.cat_brand_btn.setObjectName("SecondaryBtn")
        self.cat_brand_btn.clicked.connect(self._handle_manage_categories_brands)
        top_bar.addWidget(self.cat_brand_btn)

        self.bulk_entry_btn = QPushButton("📑 Bulk Entry Grid")
        self.bulk_entry_btn.setObjectName("SecondaryBtn")
        self.bulk_entry_btn.clicked.connect(self._handle_bulk_entry)
        top_bar.addWidget(self.bulk_entry_btn)

        self.print_barcodes_btn = QPushButton("🏷️ Barcode Labels")
        self.print_barcodes_btn.setObjectName("SecondaryBtn")
        self.print_barcodes_btn.clicked.connect(self._handle_print_barcode_labels)
        top_bar.addWidget(self.print_barcodes_btn)

        self.import_btn = QPushButton("Import CSV")
        self.import_btn.setObjectName("SecondaryBtn")
        self.import_btn.clicked.connect(self._handle_import_csv)
        top_bar.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export to Excel")
        self.export_btn.setObjectName("SecondaryBtn")
        self.export_btn.clicked.connect(self._handle_export_excel)
        top_bar.addWidget(self.export_btn)

        self.add_btn = QPushButton("+ Add New Product")
        self.add_btn.setObjectName("PrimaryBtn")
        self.add_btn.clicked.connect(self._handle_add_product)
        top_bar.addWidget(self.add_btn)

        layout.addLayout(top_bar)

        # Filter & Search Controls Bar
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by product name, SKU, or barcode...")
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.refresh_products)
        filter_bar.addWidget(self.search_input, 3)

        self.category_filter = QComboBox()
        self.category_filter.setFixedHeight(36)
        self.category_filter.addItem("All Categories", None)
        self.category_filter.currentIndexChanged.connect(self.refresh_products)
        filter_bar.addWidget(self.category_filter, 2)

        layout.addLayout(filter_bar)

        # Main Products Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Product Name", "SKU", "Barcode", "Price (₹)", "Cost (₹)", "Stock", "Unit", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table)

        # Bottom Count
        self.count_lbl = QLabel("Showing 0 products")
        self.count_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(self.count_lbl)

    def _refresh_category_filter(self):
        curr = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories", None)
        cats = self.product_service.list_categories()
        for c in cats:
            self.category_filter.addItem(c["name"], c["id"])
        idx = self.category_filter.findData(curr)
        if idx >= 0:
            self.category_filter.setCurrentIndex(idx)
        self.category_filter.blockSignals(False)

    def refresh_products(self):
        query = self.search_input.text().strip()
        cat_id = self.category_filter.currentData()

        products, total = self.product_service.search_products(
            query=query,
            category_id=cat_id,
            active_only=False,
            limit=500,
        )

        self.table.setRowCount(len(products))
        for row, p in enumerate(products):
            self.table.setItem(row, 0, QTableWidgetItem(str(p["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(p["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(p["sku"]))
            self.table.setItem(row, 3, QTableWidgetItem(p["barcode"] or "-"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{p['selling_price']:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{p['purchase_cost']:.2f}"))

            # Stock with low-stock warning color
            stock_item = QTableWidgetItem(f"{p['quantity_on_hand']:.2f}")
            if p["quantity_on_hand"] <= 0:
                stock_item.setForeground(Qt.red)
            elif p["quantity_on_hand"] <= p["reorder_level"]:
                stock_item.setForeground(Qt.darkYellow)
            self.table.setItem(row, 6, stock_item)

            self.table.setItem(row, 7, QTableWidgetItem(p["unit_code"]))

            # Action button
            edit_btn = QPushButton("Edit")
            edit_btn.setObjectName("TableActionBtn")
            edit_btn.setFixedHeight(28)
            edit_btn.setMinimumWidth(55)
            edit_btn.clicked.connect(lambda _, pid=p["id"]: self._handle_edit_product(pid))
            self.table.setCellWidget(row, 8, edit_btn)

        self.count_lbl.setText(f"Showing {len(products)} of {total} products")

    def _handle_add_product(self):
        dlg = ProductDialog(self.product_service, self.current_session, parent=self)
        if dlg.exec():
            self._refresh_category_filter()
            self.refresh_products()

    def _handle_edit_product(self, product_id: int):
        dlg = ProductDialog(self.product_service, self.current_session, product_id=product_id, parent=self)
        if dlg.exec():
            self._refresh_category_filter()
            self.refresh_products()

    def _handle_export_excel(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Product Catalogue", "products_export.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                self.product_service.export_products_to_excel(file_path)
                QMessageBox.information(self, "Export Successful", f"Product catalogue exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _handle_manage_categories_brands(self):
        from src.ui.dialogs.category_brand_manager_dialog import CategoryBrandManagerDialog
        dlg = CategoryBrandManagerDialog(self.product_service, self.current_session, parent=self)
        if dlg.exec():
            self._refresh_category_filter()
            self.refresh_products()

    def _handle_bulk_entry(self):
        from src.ui.dialogs.bulk_product_entry_dialog import BulkProductEntryDialog
        dlg = BulkProductEntryDialog(self.product_service, self.current_session, parent=self)
        if dlg.exec():
            self._refresh_category_filter()
            self.refresh_products()

    def _handle_print_barcode_labels(self):
        from src.services.barcode_service import BarcodeService
        products, _ = self.product_service.search_products(limit=50)
        if not products:
            QMessageBox.information(self, "No Products", "No products available for barcode printing.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Barcode Labels PDF", "barcode_labels.pdf", "PDF Files (*.pdf)")
        if file_path:
            try:
                BarcodeService.format_sticker_label_sheet_pdf(products[:48], shop_name="Aj Super Market", output_path=file_path)
                QMessageBox.information(self, "Labels Ready", f"Printable barcode label sheet saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Print Error", f"Failed to generate barcode labels: {e}")

    def _handle_import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Products from CSV", "", "CSV Files (*.csv)")
        if file_path:
            try:
                count, errs = self.product_service.import_products_from_csv(self.current_session, file_path)
                msg = f"Successfully imported {count} products."
                if errs:
                    msg += f"\n\nWarnings/Errors ({len(errs)}):\n" + "\n".join(errs[:5])
                QMessageBox.information(self, "Import Complete", msg)
                self.refresh_products()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))
