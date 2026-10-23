"""
Quick Price & Stock Checker View for Cashiers.
Allows cashiers to rapidly scan any barcode or search products to check
the retail selling price, MRP, and available stock without exposing wholesale costs.
"""

from typing import Optional, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
)

from src.services.product_service import ProductService


class PriceCheckerView(QWidget):
    def __init__(self, product_service: ProductService, parent=None):
        super().__init__(parent)
        self.product_service = product_service

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(18)

        # Header
        header = QLabel("🔍 Price & Stock Checker")
        header.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")
        layout.addWidget(header)

        sub = QLabel("Scan product barcode or type product name/SKU to check selling price and store availability.")
        sub.setStyleSheet("font-size: 13px; color: #64748B;")
        layout.addWidget(sub)

        # Search / Scan Input
        input_bar = QHBoxLayout()
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Scan barcode or type product name / SKU (e.g. 8901030010011, 101, Atta)...")
        self.code_input.setFixedHeight(44)
        self.code_input.setStyleSheet("font-size: 15px; font-weight: 500; padding: 0 14px;")
        self.code_input.returnPressed.connect(self._handle_lookup)
        input_bar.addWidget(self.code_input, 4)

        self.lookup_btn = QPushButton("Check Price")
        self.lookup_btn.setObjectName("PrimaryBtn")
        self.lookup_btn.setFixedHeight(44)
        self.lookup_btn.clicked.connect(self._handle_lookup)
        input_bar.addWidget(self.lookup_btn, 1)

        layout.addLayout(input_bar)

        # Large Result Card
        self.result_card = QFrame()
        self.result_card.setStyleSheet("QFrame { background-color: #FFFFFF; border: 2px solid #D1FAE5; border-radius: 12px; } QLabel { border: none; background: transparent; }")
        res_layout = QVBoxLayout(self.result_card)
        res_layout.setContentsMargins(24, 24, 24, 24)
        res_layout.setSpacing(14)

        self.item_name_lbl = QLabel("Ready for Scan")
        self.item_name_lbl.setStyleSheet("font-size: 24px; font-weight: 800; color: #064E3B;")
        res_layout.addWidget(self.item_name_lbl)

        self.item_meta_lbl = QLabel("Scan an item or enter barcode above to view pricing.")
        self.item_meta_lbl.setStyleSheet("font-size: 14px; color: #64748B;")
        res_layout.addWidget(self.item_meta_lbl)

        res_layout.addSpacing(10)

        # Big Price Display
        price_row = QHBoxLayout()
        price_row.setSpacing(20)

        # Selling Price Card
        sp_frame = QFrame()
        sp_frame.setStyleSheet("QFrame { background-color: #064E3B; border-radius: 8px; border: none; } QLabel { border: none; background: transparent; }")
        sp_layout = QVBoxLayout(sp_frame)
        sp_layout.setContentsMargins(20, 14, 20, 14)
        sp_hdr = QLabel("RETAIL SELLING PRICE")
        sp_hdr.setStyleSheet("color: #A7F3D0; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        sp_layout.addWidget(sp_hdr)
        self.selling_price_lbl = QLabel("₹ 0.00")
        self.selling_price_lbl.setStyleSheet("color: #34D399; font-size: 36px; font-weight: 900;")
        sp_layout.addWidget(self.selling_price_lbl)
        price_row.addWidget(sp_frame)

        # MRP Card
        mrp_frame = QFrame()
        mrp_frame.setStyleSheet("QFrame { background-color: #F4FBF7; border: 1px solid #D1FAE5; border-radius: 8px; } QLabel { border: none; background: transparent; }")
        mrp_layout = QVBoxLayout(mrp_frame)
        mrp_layout.setContentsMargins(20, 14, 20, 14)
        mrp_hdr = QLabel("MAX RETAIL PRICE (MRP)")
        mrp_hdr.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        mrp_layout.addWidget(mrp_hdr)
        self.mrp_lbl = QLabel("₹ 0.00")
        self.mrp_lbl.setStyleSheet("color: #0F172A; font-size: 32px; font-weight: 800;")
        mrp_layout.addWidget(self.mrp_lbl)
        price_row.addWidget(mrp_frame)

        # Stock Balance Card
        stock_frame = QFrame()
        stock_frame.setStyleSheet("QFrame { background-color: #F4FBF7; border: 1px solid #D1FAE5; border-radius: 8px; } QLabel { border: none; background: transparent; }")
        stock_layout = QVBoxLayout(stock_frame)
        stock_layout.setContentsMargins(20, 14, 20, 14)
        stock_hdr = QLabel("AVAILABLE STOCK IN STORE")
        stock_hdr.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        stock_layout.addWidget(stock_hdr)
        self.stock_lbl = QLabel("0.00 Units")
        self.stock_lbl.setStyleSheet("color: #059669; font-size: 32px; font-weight: 800;")
        stock_layout.addWidget(self.stock_lbl)
        price_row.addWidget(stock_frame)

        res_layout.addLayout(price_row)

        layout.addWidget(self.result_card)

        # Alternative matches table if multiple results
        self.matches_table = QTableWidget()
        self.matches_table.setColumnCount(5)
        self.matches_table.setHorizontalHeaderLabels(["Product Name", "SKU / Barcode", "Unit", "Price (₹)", "Stock Available"])
        self.matches_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.matches_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.matches_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.matches_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.matches_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.matches_table.verticalHeader().setDefaultSectionSize(36)
        self.matches_table.verticalHeader().setVisible(False)
        self.matches_table.cellDoubleClicked.connect(self._on_match_selected)
        self.matches_table.setVisible(False)
        layout.addWidget(self.matches_table)

        layout.addStretch()

    def set_focus_input(self):
        self.code_input.setFocus()
        self.code_input.selectAll()

    def _handle_lookup(self):
        query = self.code_input.text().strip()
        if not query:
            return

        # 1. First attempt exact barcode resolution
        resolved = self.product_service.resolve_barcode(query)
        if resolved:
            self._display_single_item(resolved)
            self.matches_table.setVisible(False)
            return

        # 2. If not exact barcode, search by name or SKU
        products, _ = self.product_service.search_products(query=query, limit=10)
        if not products:
            self.item_name_lbl.setText("❌ Item Not Found")
            self.item_meta_lbl.setText(f"No grocery product matched '{query}'. Please check barcode or spelling.")
            self.selling_price_lbl.setText("₹ --")
            self.mrp_lbl.setText("₹ --")
            self.stock_lbl.setText("--")
            self.matches_table.setVisible(False)
            return

        if len(products) == 1:
            p = products[0]
            resolved_dict = {
                "name": p["name"],
                "sku": p["sku"],
                "barcode": p["barcode"],
                "category_name": p["category_name"],
                "brand_name": p["brand_name"],
                "unit_code": p["unit_code"],
                "selling_price": p["selling_price"],
                "mrp": p["mrp"],
                "available_qty": p["quantity_on_hand"],
                "gst_rate": p["gst_rate"],
            }
            self._display_single_item(resolved_dict)
            self.matches_table.setVisible(False)
        else:
            # Display best match on card and list all candidates in table
            p0 = products[0]
            self._display_single_item({
                "name": p0["name"],
                "sku": p0["sku"],
                "barcode": p0["barcode"],
                "category_name": p0["category_name"],
                "brand_name": p0["brand_name"],
                "unit_code": p0["unit_code"],
                "selling_price": p0["selling_price"],
                "mrp": p0["mrp"],
                "available_qty": p0["quantity_on_hand"],
                "gst_rate": p0["gst_rate"],
            })
            self._populate_matches(products)

    def _display_single_item(self, item: Dict[str, Any]):
        self.item_name_lbl.setText(item["name"])
        cat = item.get("category_name", "General")
        brand = item.get("brand_name", "-")
        sku = item.get("sku", "")
        bc = item.get("barcode", "-")
        gst = item.get("gst_rate", 0.0)

        self.item_meta_lbl.setText(f"Category: {cat} | Brand: {brand} | SKU: {sku} | Barcode: {bc} | GST: {gst:.0f}%")
        self.selling_price_lbl.setText(f"₹ {item['selling_price']:.2f}")
        mrp = item.get("mrp", item["selling_price"])
        self.mrp_lbl.setText(f"₹ {mrp:.2f}")
        unit = item.get("unit_code", "PCS")
        qty = item.get("available_qty", 0.0)
        self.stock_lbl.setText(f"{qty:.2f} {unit}")

        if qty <= 0:
            self.stock_lbl.setStyleSheet("color: #DC2626; font-size: 32px; font-weight: 800;")
        else:
            self.stock_lbl.setStyleSheet("color: #2563EB; font-size: 32px; font-weight: 800;")

    def _populate_matches(self, products):
        self.matches_table.setRowCount(len(products))
        for row, p in enumerate(products):
            self.matches_table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.matches_table.setItem(row, 1, QTableWidgetItem(p["barcode"] or p["sku"]))
            self.matches_table.setItem(row, 2, QTableWidgetItem(p["unit_code"]))
            self.matches_table.setItem(row, 3, QTableWidgetItem(f"₹ {p['selling_price']:.2f}"))
            self.matches_table.setItem(row, 4, QTableWidgetItem(f"{p['quantity_on_hand']:.2f} {p['unit_code']}"))
            self.matches_table.item(row, 0).setData(Qt.UserRole, p)
        self.matches_table.setVisible(True)

    def _on_match_selected(self, row, col):
        p = self.matches_table.item(row, 0).data(Qt.UserRole)
        if p:
            self._display_single_item({
                "name": p["name"],
                "sku": p["sku"],
                "barcode": p["barcode"],
                "category_name": p["category_name"],
                "brand_name": p["brand_name"],
                "unit_code": p["unit_code"],
                "selling_price": p["selling_price"],
                "mrp": p["mrp"],
                "available_qty": p["quantity_on_hand"],
                "gst_rate": p["gst_rate"],
            })
