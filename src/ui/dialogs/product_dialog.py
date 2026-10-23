"""
Product Creation and Modification Dialog.
Adapts to business profiles with UOMs, Tax brackets, and variant settings.
Supports typing manual categories and brands with auto-save to memory and live auto-complete suggestions.
"""

from decimal import Decimal
from typing import Optional, Dict, Any, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QDoubleSpinBox, QCheckBox, QMessageBox,
    QGroupBox, QFormLayout, QCompleter
)

from src.services.product_service import ProductService
from src.services.auth_service import UserSession


class ProductDialog(QDialog):
    def __init__(
        self,
        product_service: ProductService,
        current_session: UserSession,
        product_id: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.product_service = product_service
        self.current_session = current_session
        self.product_id = product_id

        self.setWindowTitle("Edit Product" if product_id else "Add New Product")
        self.setFixedSize(540, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._load_metadata()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Basic Info
        grp1 = QGroupBox("Product Identification")
        form1 = QFormLayout(grp1)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Aashirvaad Whole Wheat Flour 5kg")
        form1.addRow("Product Name *:", self.name_input)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("e.g. WHEAT-AASH-5KG")
        form1.addRow("SKU / Code *:", self.sku_input)

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Scan barcode or leave empty to auto-generate")
        form1.addRow("Barcode:", self.barcode_input)

        # Editable Category ComboBox with Live Suggestion
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setInsertPolicy(QComboBox.NoInsert)
        if self.category_combo.completer():
            self.category_combo.completer().setCompletionMode(QCompleter.PopupCompletion)
            self.category_combo.completer().setFilterMode(Qt.MatchContains)
        self.category_combo.lineEdit().setPlaceholderText("Type or select category...")
        form1.addRow("Category (Type or Select):", self.category_combo)

        # Editable Brand ComboBox with Live Suggestion
        self.brand_combo = QComboBox()
        self.brand_combo.setEditable(True)
        self.brand_combo.setInsertPolicy(QComboBox.NoInsert)
        if self.brand_combo.completer():
            self.brand_combo.completer().setCompletionMode(QCompleter.PopupCompletion)
            self.brand_combo.completer().setFilterMode(Qt.MatchContains)
        self.brand_combo.lineEdit().setPlaceholderText("Type or select brand...")
        form1.addRow("Brand (Type or Select):", self.brand_combo)

        layout.addWidget(grp1)

        # Pricing & Taxes
        grp2 = QGroupBox("Pricing & Tax Classification")
        form2 = QFormLayout(grp2)

        self.unit_combo = QComboBox()
        form2.addRow("Unit of Measure *:", self.unit_combo)

        self.tax_combo = QComboBox()
        form2.addRow("GST Tax Rate *:", self.tax_combo)

        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0, 1000000)
        self.cost_spin.setDecimals(2)
        self.cost_spin.setPrefix("₹ ")
        form2.addRow("Purchase Cost:", self.cost_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 1000000)
        self.price_spin.setDecimals(2)
        self.price_spin.setPrefix("₹ ")
        form2.addRow("Selling Price *:", self.price_spin)

        self.mrp_spin = QDoubleSpinBox()
        self.mrp_spin.setRange(0, 1000000)
        self.mrp_spin.setDecimals(2)
        self.mrp_spin.setPrefix("₹ ")
        form2.addRow("MRP:", self.mrp_spin)

        self.stock_spin = QDoubleSpinBox()
        self.stock_spin.setRange(0, 100000)
        self.stock_spin.setDecimals(3)
        stock_label_str = "Stock Quantity:" if self.product_id else "Initial Stock Qty:"
        form2.addRow(stock_label_str, self.stock_spin)

        layout.addWidget(grp2)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("SecondaryBtn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Product")
        self.save_btn.setObjectName("PrimaryBtn")
        self.save_btn.clicked.connect(self._handle_save)
        btn_box.addWidget(self.save_btn)

        layout.addLayout(btn_box)

    def _load_metadata(self):
        # 1. Load Categories with memory and popular suggestions
        cats = self.product_service.list_categories()
        existing_cat_names = [c["name"] for c in cats]
        common_cats = [
            "Grains & Rice", "Flours & Atta", "Pulses & Dals", "Edible Oils & Ghee",
            "Spices & Masalas", "Snacks & Biscuits", "Beverages & Tea",
            "Dairy & Bakery", "Personal Care & Soaps", "Cleaning & Household",
            "Fruits & Vegetables", "Hardware & Tools", "Electrical Items"
        ]
        all_cats = ["None"]
        for cn in existing_cat_names:
            if cn not in all_cats:
                all_cats.append(cn)
        for cc in common_cats:
            if cc not in all_cats:
                all_cats.append(cc)

        self.category_combo.clear()
        self.category_combo.addItems(all_cats)
        if self.category_combo.completer():
            self.category_combo.completer().setFilterMode(Qt.MatchContains)

        # 2. Load Brands with memory and popular suggestions
        brands = self.product_service.list_brands()
        existing_brand_names = [b["name"] for b in brands]
        common_brands = [
            "Aashirvaad", "India Gate", "Tata", "Fortune", "Amul", "Nestle",
            "Britannia", "Parle", "Dabur", "Hindustan Unilever", "ITC", "Patanjali",
            "Cadbury", "Bru", "Surf Excel", "Philips", "Havells"
        ]
        all_brands = ["None"]
        for bn in existing_brand_names:
            if bn not in all_brands:
                all_brands.append(bn)
        for cb in common_brands:
            if cb not in all_brands:
                all_brands.append(cb)

        self.brand_combo.clear()
        self.brand_combo.addItems(all_brands)
        if self.brand_combo.completer():
            self.brand_combo.completer().setFilterMode(Qt.MatchContains)

        # 3. Load Units
        uoms = self.product_service.list_uoms()
        for u in uoms:
            self.unit_combo.addItem(f"{u['name']} ({u['code']})", u["id"])

        # 4. Load Tax Profiles
        taxes = self.product_service.list_tax_profiles()
        for t in taxes:
            self.tax_combo.addItem(f"{t['name']} - HSN {t['hsn_sac_code']}", t["id"])

        # 5. If editing existing product, populate current fields
        if self.product_id:
            with self.product_service.db.session() as session:
                from sqlalchemy.orm import joinedload
                from src.models import Product, InventoryBalance
                prod = (
                    session.query(Product)
                    .options(joinedload(Product.inventory_balance))
                    .filter_by(id=self.product_id)
                    .first()
                )
                if prod:
                    self.name_input.setText(prod.name)
                    self.sku_input.setText(prod.sku)
                    self.sku_input.setEnabled(False)
                    self.barcode_input.setText(prod.barcode or "")
                    if prod.category:
                        self.category_combo.setEditText(prod.category.name)
                    if prod.brand:
                        self.brand_combo.setEditText(prod.brand.name)
                    self.price_spin.setValue(float(prod.selling_price))
                    self.cost_spin.setValue(float(prod.purchase_cost))
                    self.mrp_spin.setValue(float(prod.mrp or prod.selling_price))

                    # Current Stock Quantity - enabled and editable
                    current_stock = prod.inventory_balance.quantity_on_hand if prod.inventory_balance else Decimal("0.000")
                    self.original_stock = Decimal(str(current_stock))
                    self.stock_spin.setValue(float(current_stock))
                    self.stock_spin.setEnabled(True)
                    self.stock_spin.setToolTip("Update physical stock count for this item")

    def _handle_save(self):
        name = self.name_input.text().strip()
        sku = self.sku_input.text().strip()
        barcode = self.barcode_input.text().strip() or None
        unit_id = self.unit_combo.currentData()
        tax_id = self.tax_combo.currentData()
        cost = Decimal(str(self.cost_spin.value()))
        price = Decimal(str(self.price_spin.value()))
        mrp = Decimal(str(self.mrp_spin.value())) or price
        stock = Decimal(str(self.stock_spin.value()))

        # Read typed manual text for category and brand
        cat_text = self.category_combo.currentText().strip()
        brand_text = self.brand_combo.currentText().strip()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Product Name is required.")
            self.name_input.setFocus()
            return

        if not sku:
            QMessageBox.warning(self, "Validation Error", "SKU / Product Code is required.")
            self.sku_input.setFocus()
            return

        if price <= Decimal("0.00"):
            QMessageBox.warning(self, "Validation Error", "Selling price must be greater than zero.")
            self.price_spin.setFocus()
            return

        try:
            # Auto-save typed category and brand to memory/database
            cat_id = self.product_service.get_or_create_category(self.current_session, cat_text)
            brand_id = self.product_service.get_or_create_brand(self.current_session, brand_text)

            if self.product_id is None:
                self.product_service.create_product(
                    current_session=self.current_session,
                    name=name,
                    sku=sku,
                    barcode=barcode,
                    unit_id=unit_id,
                    tax_profile_id=tax_id,
                    purchase_cost=cost,
                    selling_price=price,
                    mrp=mrp,
                    category_id=cat_id,
                    brand_id=brand_id,
                    initial_stock=stock,
                )
            else:
                self.product_service.update_product(
                    current_session=self.current_session,
                    product_id=self.product_id,
                    updates={
                        "name": name,
                        "barcode": barcode,
                        "purchase_cost": cost,
                        "selling_price": price,
                        "mrp": mrp,
                        "unit_id": unit_id,
                        "tax_profile_id": tax_id,
                        "category_id": cat_id,
                        "brand_id": brand_id,
                    },
                )

                # Update stock balance if changed by user
                orig_stock = getattr(self, "original_stock", Decimal("0.000"))
                if stock != orig_stock:
                    from src.services.inventory_service import InventoryService
                    inv_svc = InventoryService(self.product_service.db)
                    inv_svc.perform_stock_adjustment(
                        current_session=self.current_session,
                        product_id=self.product_id,
                        new_quantity=stock,
                        reason="PHYSICAL_COUNT",
                        notes="Stock updated via Edit Product dialog",
                    )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error Saving Product", str(exc))
