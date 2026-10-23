"""
Product Catalogue Service: Categories, Brands, UOMs, Tax Profiles,
Products, Product Variants, Multi-Barcode Resolution, and Excel/CSV Import/Export.
"""

import csv
import io
import logging
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session, joinedload
import openpyxl

from src.core.database import DatabaseManager
from src.core.exceptions import (
    BillingSystemError,
    PermissionDeniedError,
    ValidationError,
)
from src.models import (
    Product,
    ProductVariant,
    ProductBarcode,
    Category,
    Brand,
    UnitOfMeasure,
    ProductTaxProfile,
    InventoryBalance,
    AuditLog,
)
from src.services.auth_service import UserSession

logger = logging.getLogger(__name__)


class ProductService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    # ---------------- Category & Brand Operations ----------------

    def create_category(self, current_session: UserSession, name: str, code: Optional[str] = None, parent_id: Optional[int] = None) -> int:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")
        with self.db.session() as session:
            cat = Category(name=name, code=code, parent_id=parent_id)
            session.add(cat)
            session.flush()
            return cat.id

    def list_categories(self) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            cats = session.query(Category).filter_by(is_active=True).order_by(Category.name).all()
            return [{"id": c.id, "name": c.name, "code": c.code, "parent_id": c.parent_id} for c in cats]

    def get_or_create_category(self, current_session: UserSession, name: str) -> Optional[int]:
        """Looks up an existing category by name (case-insensitive) or automatically creates and saves it."""
        clean = name.strip()
        if not clean or clean.lower() == "none":
            return None
        with self.db.session() as session:
            cat = session.query(Category).filter(func.lower(Category.name) == func.lower(clean)).first()
            if cat:
                return cat.id
            code = clean.upper().replace(" ", "_")[:20]
            cnt = session.query(Category).filter(Category.code.like(f"{code}%")).count()
            if cnt > 0:
                code = f"{code}_{cnt + 1}"
            new_cat = Category(name=clean, code=code, is_active=True)
            session.add(new_cat)
            session.flush()
            logger.info(f"Auto-created and saved new category to memory: '{clean}' (ID: {new_cat.id})")
            return new_cat.id

    def create_brand(self, current_session: UserSession, name: str, manufacturer: Optional[str] = None) -> int:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")
        with self.db.session() as session:
            brand = Brand(name=name, manufacturer_name=manufacturer)
            session.add(brand)
            session.flush()
            return brand.id

    def list_brands(self) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            brands = session.query(Brand).filter_by(is_active=True).order_by(Brand.name).all()
            return [{"id": b.id, "name": b.name, "manufacturer_name": b.manufacturer_name} for b in brands]

    def get_or_create_brand(self, current_session: UserSession, name: str) -> Optional[int]:
        """Looks up an existing brand by name (case-insensitive) or automatically creates and saves it."""
        clean = name.strip()
        if not clean or clean.lower() == "none":
            return None
        with self.db.session() as session:
            brand = session.query(Brand).filter(func.lower(Brand.name) == func.lower(clean)).first()
            if brand:
                return brand.id
            new_brand = Brand(name=clean, is_active=True)
            session.add(new_brand)
            session.flush()
            logger.info(f"Auto-created and saved new brand to memory: '{clean}' (ID: {new_brand.id})")
            return new_brand.id

    def update_category(self, current_session: UserSession, category_id: int, name: str, code: Optional[str] = None) -> None:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")
        with self.db.session() as session:
            cat = session.query(Category).filter_by(id=category_id).first()
            if not cat:
                raise BillingSystemError("Category not found.", code="NOT_FOUND")
            cat.name = name.strip()
            if code:
                cat.code = code.strip()

    def set_category_active(self, current_session: UserSession, category_id: int, is_active: bool) -> None:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")
        with self.db.session() as session:
            cat = session.query(Category).filter_by(id=category_id).first()
            if not cat:
                raise BillingSystemError("Category not found.", code="NOT_FOUND")
            cat.is_active = is_active

    def update_brand(self, current_session: UserSession, brand_id: int, name: str, manufacturer: Optional[str] = None) -> None:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")
        with self.db.session() as session:
            brand = session.query(Brand).filter_by(id=brand_id).first()
            if not brand:
                raise BillingSystemError("Brand not found.", code="NOT_FOUND")
            brand.name = name.strip()
            if manufacturer:
                brand.manufacturer_name = manufacturer.strip()

    def set_brand_active(self, current_session: UserSession, brand_id: int, is_active: bool) -> None:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")
        with self.db.session() as session:
            brand = session.query(Brand).filter_by(id=brand_id).first()
            if not brand:
                raise BillingSystemError("Brand not found.", code="NOT_FOUND")
            brand.is_active = is_active

    def list_uoms(self) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            uoms = session.query(UnitOfMeasure).all()
            return [{"id": u.id, "code": u.code, "name": u.name, "decimal_precision": u.decimal_precision, "is_fractional": u.is_fractional} for u in uoms]

    def list_tax_profiles(self) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            profiles = session.query(ProductTaxProfile).all()
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "hsn_sac_code": p.hsn_sac_code,
                    "gst_rate": float(p.gst_rate),
                    "cess_rate": float(p.cess_rate),
                }
                for p in profiles
            ]

    # ---------------- Product CRUD Operations ----------------

    def create_product(
        self,
        current_session: UserSession,
        name: str,
        sku: str,
        unit_id: int,
        tax_profile_id: int,
        selling_price: Decimal,
        purchase_cost: Decimal = Decimal("0.00"),
        barcode: Optional[str] = None,
        category_id: Optional[int] = None,
        brand_id: Optional[int] = None,
        mrp: Optional[Decimal] = None,
        reorder_level: Decimal = Decimal("5.000"),
        has_variants: bool = False,
        track_batches: bool = False,
        track_serials: bool = False,
        initial_stock: Decimal = Decimal("0.000"),
    ) -> int:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")

        with self.db.session() as session:
            # Check SKU uniqueness
            existing_sku = session.query(Product).filter_by(sku=sku).first()
            if existing_sku:
                raise BillingSystemError(f"Product SKU '{sku}' already exists.", code="DUPLICATE_SKU")

            # Check Barcode uniqueness if provided
            if barcode:
                existing_barcode = session.query(Product).filter_by(barcode=barcode).first()
                if existing_barcode:
                    raise BillingSystemError(f"Barcode '{barcode}' is already assigned to '{existing_barcode.name}'.", code="DUPLICATE_BARCODE")

            product = Product(
                name=name,
                sku=sku,
                barcode=barcode,
                category_id=category_id,
                brand_id=brand_id,
                unit_id=unit_id,
                tax_profile_id=tax_profile_id,
                purchase_cost=purchase_cost,
                selling_price=selling_price,
                mrp=mrp or selling_price,
                reorder_level=reorder_level,
                has_variants=has_variants,
                track_batches=track_batches,
                track_serials=track_serials,
                is_active=True,
            )
            session.add(product)
            session.flush()

            # Initialize Inventory Balance record
            balance = InventoryBalance(
                product_id=product.id,
                variant_id=None,
                quantity_on_hand=initial_stock,
                quantity_reserved=Decimal("0.000"),
            )
            session.add(balance)

            # Record secondary barcode if given
            if barcode:
                p_barcode = ProductBarcode(
                    product_id=product.id,
                    barcode_value=barcode,
                    barcode_type="EAN13" if len(barcode) == 13 else "CODE128",
                )
                session.add(p_barcode)

            session.flush()
            return product.id

    def update_product(
        self,
        current_session: UserSession,
        product_id: int,
        updates: Dict[str, Any],
    ) -> None:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")

        with self.db.session() as session:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise BillingSystemError(f"Product {product_id} not found.", code="PRODUCT_NOT_FOUND")

            if "name" in updates:
                product.name = updates["name"]
            if "selling_price" in updates:
                product.selling_price = Decimal(str(updates["selling_price"]))
            if "purchase_cost" in updates:
                product.purchase_cost = Decimal(str(updates["purchase_cost"]))
            if "mrp" in updates:
                product.mrp = Decimal(str(updates["mrp"])) if updates["mrp"] is not None else None
            if "reorder_level" in updates:
                product.reorder_level = Decimal(str(updates["reorder_level"]))
            if "category_id" in updates:
                product.category_id = updates["category_id"]
            if "brand_id" in updates:
                product.brand_id = updates["brand_id"]
            if "tax_profile_id" in updates:
                product.tax_profile_id = updates["tax_profile_id"]
            if "unit_id" in updates:
                product.unit_id = updates["unit_id"]
            if "is_active" in updates:
                product.is_active = bool(updates["is_active"])

            if "barcode" in updates and updates["barcode"] != product.barcode:
                new_bc = updates["barcode"]
                if new_bc:
                    existing = session.query(Product).filter(Product.barcode == new_bc, Product.id != product_id).first()
                    if existing:
                        raise BillingSystemError(f"Barcode '{new_bc}' is already in use.", code="DUPLICATE_BARCODE")
                product.barcode = new_bc

            session.flush()

    def set_product_active_status(self, current_session: UserSession, product_id: int, is_active: bool) -> None:
        """Deactivates or activates a product."""
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")

        with self.db.session() as session:
            p = session.query(Product).filter_by(id=product_id).first()
            if not p:
                raise BillingSystemError("Product not found", code="NOT_FOUND")
            p.is_active = is_active

    # ---------------- Product Variants ----------------

    def add_product_variant(
        self,
        current_session: UserSession,
        product_id: int,
        variant_sku: str,
        size: Optional[str] = None,
        color: Optional[str] = None,
        style: Optional[str] = None,
        material: Optional[str] = None,
        additional_price: Decimal = Decimal("0.00"),
        additional_cost: Decimal = Decimal("0.00"),
        variant_barcode: Optional[str] = None,
    ) -> int:
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")

        with self.db.session() as session:
            prod = session.query(Product).filter_by(id=product_id).first()
            if not prod:
                raise BillingSystemError("Product not found", code="PRODUCT_NOT_FOUND")
            prod.has_variants = True

            variant = ProductVariant(
                product_id=product_id,
                variant_sku=variant_sku,
                variant_barcode=variant_barcode,
                size=size,
                color=color,
                style=style,
                material=material,
                additional_price=additional_price,
                additional_cost=additional_cost,
                is_active=True,
            )
            session.add(variant)
            session.flush()

            # Create Inventory Balance for this variant
            balance = InventoryBalance(
                product_id=product_id,
                variant_id=variant.id,
                quantity_on_hand=Decimal("0.000"),
                quantity_reserved=Decimal("0.000"),
            )
            session.add(balance)

            if variant_barcode:
                p_bc = ProductBarcode(
                    product_id=product_id,
                    variant_id=variant.id,
                    barcode_value=variant_barcode,
                    barcode_type="CODE128",
                )
                session.add(p_bc)

            return variant.id

    # ---------------- Search & Fast Barcode Resolution ----------------

    def search_products(
        self,
        query: str = "",
        category_id: Optional[int] = None,
        brand_id: Optional[int] = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Fast multi-field product search by name, SKU, or Barcode with pagination.
        Returns (list_of_results, total_count).
        """
        with self.db.session() as session:
            stmt = session.query(Product).options(
                joinedload(Product.category),
                joinedload(Product.brand),
                joinedload(Product.unit),
                joinedload(Product.tax_profile),
                joinedload(Product.inventory_balance),
            )

            if active_only:
                stmt = stmt.filter(Product.is_active == True)  # noqa: E712
            if category_id:
                stmt = stmt.filter(Product.category_id == category_id)
            if brand_id:
                stmt = stmt.filter(Product.brand_id == brand_id)

            if query:
                pattern = f"%{query}%"
                stmt = stmt.filter(
                    or_(
                        Product.name.ilike(pattern),
                        Product.sku.ilike(pattern),
                        Product.barcode.ilike(pattern),
                    )
                )

            total_count = stmt.count()
            products = stmt.order_by(Product.name).limit(limit).offset(offset).all()

            results = []
            for p in products:
                stock_qty = p.inventory_balance.quantity_on_hand if p.inventory_balance else Decimal("0.000")
                results.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "sku": p.sku,
                        "barcode": p.barcode or "",
                        "category_name": p.category.name if p.category else "Uncategorized",
                        "brand_name": p.brand.name if p.brand else "-",
                        "unit_code": p.unit.code if p.unit else "PCS",
                        "decimal_precision": p.unit.decimal_precision if p.unit else 0,
                        "purchase_cost": float(p.purchase_cost),
                        "selling_price": float(p.selling_price),
                        "mrp": float(p.mrp) if p.mrp else float(p.selling_price),
                        "promotional_price": float(p.promotional_price) if p.promotional_price else None,
                        "min_selling_price": float(p.min_selling_price) if p.min_selling_price else None,
                        "package_size": p.package_size or "",
                        "reorder_level": float(p.reorder_level),
                        "quantity_on_hand": float(stock_qty),
                        "hsn_code": p.tax_profile.hsn_sac_code if p.tax_profile else "0000",
                        "gst_rate": float(p.tax_profile.gst_rate) if p.tax_profile else 0.0,
                        "has_variants": p.has_variants,
                        "track_batches": p.track_batches,
                        "track_serials": p.track_serials,
                        "is_active": p.is_active,
                    }
                )
            return results, total_count

    def resolve_barcode(self, barcode_str: str) -> Optional[Dict[str, Any]]:
        """
        Resolves a scanned barcode string against product barcodes, variant barcodes,
        or electronic weight-scale embedded barcodes (EAN-13 in-store 20/21 prefix).
        """
        clean_code = barcode_str.strip()
        if not clean_code:
            return None

        # 0. Check for Supermarket Electronic Weighing Scale Barcode (EAN-13 with prefix 20, 21, or 02)
        # Format: 2 digits prefix (20/21/02) + 5 digits item code + 5 digits weight in grams + 1 check digit
        scale_qty: Optional[float] = None
        target_code = clean_code

        if len(clean_code) == 13 and (clean_code.startswith("20") or clean_code.startswith("21") or clean_code.startswith("02")):
            item_code_part = clean_code[2:7]  # 5 digits
            weight_grams_part = clean_code[7:12]  # 5 digits
            try:
                grams = int(weight_grams_part)
                scale_qty = grams / 1000.0  # e.g. 1250g = 1.250 kg
                target_code = item_code_part.lstrip("0") or item_code_part
            except ValueError:
                pass

        with self.db.session() as session:
            # Check scale barcode match first if applicable
            if scale_qty is not None:
                # Look up product whose SKU or barcode matches the item code part
                scale_prod = (
                    session.query(Product)
                    .options(joinedload(Product.unit), joinedload(Product.tax_profile), joinedload(Product.inventory_balance))
                    .filter(
                        or_(
                            Product.barcode == target_code,
                            Product.sku.ilike(f"%{target_code}%"),
                            Product.id == int(target_code) if target_code.isdigit() else False,
                        ),
                        Product.is_active == True,  # noqa: E712
                    )
                    .first()
                )
                if scale_prod:
                    stock_qty = scale_prod.inventory_balance.quantity_on_hand if scale_prod.inventory_balance else Decimal("0.000")
                    return {
                        "product_id": scale_prod.id,
                        "variant_id": None,
                        "name": scale_prod.name,
                        "sku": scale_prod.sku,
                        "barcode": clean_code,
                        "unit_code": scale_prod.unit.code,
                        "decimal_precision": scale_prod.unit.decimal_precision,
                        "selling_price": float(scale_prod.selling_price),
                        "mrp": float(scale_prod.mrp) if scale_prod.mrp else float(scale_prod.selling_price),
                        "purchase_cost": float(scale_prod.purchase_cost),
                        "hsn_code": scale_prod.tax_profile.hsn_sac_code,
                        "gst_rate": float(scale_prod.tax_profile.gst_rate),
                        "available_qty": float(stock_qty),
                        "scanned_quantity": scale_qty,
                    }

            # 1. Check primary product barcode
            prod = (
                session.query(Product)
                .options(
                    joinedload(Product.unit),
                    joinedload(Product.tax_profile),
                    joinedload(Product.inventory_balance),
                )
                .filter(Product.barcode == clean_code, Product.is_active == True)  # noqa: E712
                .first()
            )
            if prod:
                stock_qty = prod.inventory_balance.quantity_on_hand if prod.inventory_balance else Decimal("0.000")
                return {
                    "product_id": prod.id,
                    "variant_id": None,
                    "name": prod.name,
                    "sku": prod.sku,
                    "barcode": prod.barcode,
                    "unit_code": prod.unit.code,
                    "decimal_precision": prod.unit.decimal_precision,
                    "selling_price": float(prod.selling_price),
                    "mrp": float(prod.mrp) if prod.mrp else float(prod.selling_price),
                    "purchase_cost": float(prod.purchase_cost),
                    "hsn_code": prod.tax_profile.hsn_sac_code,
                    "gst_rate": float(prod.tax_profile.gst_rate),
                    "available_qty": float(stock_qty),
                }

            # 2. Check product_barcodes table
            pb = session.query(ProductBarcode).filter_by(barcode_value=clean_code).first()
            if pb:
                p = session.query(Product).filter_by(id=pb.product_id, is_active=True).first()
                if p:
                    variant_id = pb.variant_id
                    v = session.query(ProductVariant).filter_by(id=variant_id).first() if variant_id else None
                    price = p.selling_price + (v.additional_price if v else Decimal("0.00"))
                    stock_qty = p.inventory_balance.quantity_on_hand if p.inventory_balance else Decimal("0.000")
                    return {
                        "product_id": p.id,
                        "variant_id": variant_id,
                        "name": f"{p.name} ({v.size}/{v.color})" if v else p.name,
                        "sku": v.variant_sku if v else p.sku,
                        "barcode": clean_code,
                        "unit_code": p.unit.code,
                        "decimal_precision": p.unit.decimal_precision,
                        "selling_price": float(price),
                        "mrp": float(p.mrp) if p.mrp else float(price),
                        "purchase_cost": float(p.purchase_cost),
                        "hsn_code": p.tax_profile.hsn_sac_code,
                        "gst_rate": float(p.tax_profile.gst_rate),
                        "available_qty": float(stock_qty),
                    }

            # 3. Check SKU match as fallback
            prod_by_sku = (
                session.query(Product)
                .options(joinedload(Product.unit), joinedload(Product.tax_profile), joinedload(Product.inventory_balance))
                .filter(Product.sku == clean_code, Product.is_active == True)  # noqa: E712
                .first()
            )
            if prod_by_sku:
                stock_qty = prod_by_sku.inventory_balance.quantity_on_hand if prod_by_sku.inventory_balance else Decimal("0.000")
                return {
                    "product_id": prod_by_sku.id,
                    "variant_id": None,
                    "name": prod_by_sku.name,
                    "sku": prod_by_sku.sku,
                    "barcode": prod_by_sku.barcode or "",
                    "unit_code": prod_by_sku.unit.code,
                    "decimal_precision": prod_by_sku.unit.decimal_precision,
                    "selling_price": float(prod_by_sku.selling_price),
                    "mrp": float(prod_by_sku.mrp) if prod_by_sku.mrp else float(prod_by_sku.selling_price),
                    "purchase_cost": float(prod_by_sku.purchase_cost),
                    "hsn_code": prod_by_sku.tax_profile.hsn_sac_code,
                    "gst_rate": float(prod_by_sku.tax_profile.gst_rate),
                    "available_qty": float(stock_qty),
                }

            return None

    # ---------------- CSV / Excel Bulk Import & Export ----------------

    def export_products_to_excel(self, file_path: str) -> None:
        """Exports full product catalogue with stock and tax information to Excel."""
        products, _ = self.search_products(query="", active_only=False, limit=10000)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Products Catalogue"

        headers = [
            "ID", "Name", "SKU", "Barcode", "Category", "Brand", "Unit",
            "Purchase Cost (₹)", "Selling Price (₹)", "MRP (₹)", "Available Stock",
            "Reorder Level", "HSN Code", "GST Rate (%)", "Status"
        ]
        ws.append(headers)

        for p in products:
            ws.append([
                p["id"],
                p["name"],
                p["sku"],
                p["barcode"],
                p["category_name"],
                p["brand_name"],
                p["unit_code"],
                p["purchase_cost"],
                p["selling_price"],
                p["mrp"],
                p["quantity_on_hand"],
                p["reorder_level"],
                p["hsn_code"],
                p["gst_rate"],
                "Active" if p["is_active"] else "Inactive",
            ])

        wb.save(file_path)
        logger.info(f"Exported {len(products)} products to Excel at: {file_path}")

    def import_products_from_csv(
        self, current_session: UserSession, file_path: str
    ) -> Tuple[int, List[str]]:
        """
        Imports products from CSV.
        Expected headers: Name, SKU, Barcode, Unit, SellingPrice, PurchaseCost, GSTRate, OpeningStock
        Returns (success_count, list_of_error_messages).
        """
        if not current_session.has_permission("products:import_export"):
            raise PermissionDeniedError("products:import_export")

        errors: List[str] = []
        imported_count = 0

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        with self.db.session() as session:
            # Map UOMs and Tax Profiles
            uoms = {u.code.upper(): u.id for u in session.query(UnitOfMeasure).all()}
            tax_profiles = {int(p.gst_rate): p.id for p in session.query(ProductTaxProfile).all()}
            default_tax = session.query(ProductTaxProfile).filter_by(gst_rate=Decimal("18.00")).first()
            default_tax_id = default_tax.id if default_tax else 1
            default_unit_id = uoms.get("PCS", 1)

            for idx, row in enumerate(rows, start=2):
                name = row.get("Name", "").strip()
                sku = row.get("SKU", "").strip()
                barcode = row.get("Barcode", "").strip() or None
                unit_str = row.get("Unit", "PCS").strip().upper()
                selling_price_str = row.get("SellingPrice", "0").strip()
                cost_str = row.get("PurchaseCost", "0").strip()
                gst_rate_str = row.get("GSTRate", "18").strip()
                stock_str = row.get("OpeningStock", "0").strip()

                if not name or not sku:
                    errors.append(f"Row {idx}: Name and SKU are required.")
                    continue

                existing = session.query(Product).filter_by(sku=sku).first()
                if existing:
                    errors.append(f"Row {idx}: SKU '{sku}' already exists.")
                    continue

                try:
                    selling_price = Decimal(selling_price_str)
                    purchase_cost = Decimal(cost_str)
                    stock_qty = Decimal(stock_str)
                    rate_int = int(Decimal(gst_rate_str))
                    tax_id = tax_profiles.get(rate_int, default_tax_id)
                    unit_id = uoms.get(unit_str, default_unit_id)

                    prod = Product(
                        name=name,
                        sku=sku,
                        barcode=barcode,
                        unit_id=unit_id,
                        tax_profile_id=tax_id,
                        purchase_cost=purchase_cost,
                        selling_price=selling_price,
                        mrp=selling_price,
                        is_active=True,
                    )
                    session.add(prod)
                    session.flush()

                    balance = InventoryBalance(
                        product_id=prod.id,
                        quantity_on_hand=stock_qty,
                    )
                    session.add(balance)

                    if barcode:
                        session.add(ProductBarcode(product_id=prod.id, barcode_value=barcode))

                    imported_count += 1
                except Exception as exc:
                    errors.append(f"Row {idx}: Invalid data ({exc})")

        return imported_count, errors
