"""
Product catalogue, categories, brands, units of measure, tax profiles,
and variant/barcode structures supporting adaptive business profiles.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String, Text, Boolean, Integer, Numeric, ForeignKey, Index, DateTime
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    children: Mapped[List["Category"]] = relationship("Category", back_populates="parent")
    parent: Mapped[Optional["Category"]] = relationship("Category", back_populates="children", remote_side=[id])
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")


class Brand(Base, TimestampMixin):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    manufacturer_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    products: Mapped[List["Product"]] = relationship("Product", back_populates="brand")


class UnitOfMeasure(Base, TimestampMixin):
    __tablename__ = "units_of_measure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # e.g., PCS, KG, G, L, ML, MTR
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    decimal_precision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 for PCS, 3 for KG
    is_fractional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    products: Mapped[List["Product"]] = relationship("Product", back_populates="unit")


class UnitConversion(Base):
    __tablename__ = "unit_conversions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="CASCADE"), nullable=False)
    to_unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="CASCADE"), nullable=False)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)  # e.g., 1 KG = 1000 G (multiplier=1000)


class ProductTaxProfile(Base, TimestampMixin):
    __tablename__ = "product_tax_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "GST 5% (Food grains)", "GST 18% (Apparel)"
    hsn_sac_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)  # e.g. 5.00, 18.00
    cess_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    products: Mapped[List["Product"]] = relationship("Product", back_populates="tax_profile")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    brand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False)
    tax_profile_id: Mapped[int] = mapped_column(ForeignKey("product_tax_profiles.id", ondelete="RESTRICT"), nullable=False)

    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    mrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    promotional_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    min_selling_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    package_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("5.000"), nullable=False)

    has_variants: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    track_batches: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    track_serials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products")
    brand: Mapped[Optional["Brand"]] = relationship("Brand", back_populates="products")
    unit: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure", back_populates="products")
    tax_profile: Mapped["ProductTaxProfile"] = relationship("ProductTaxProfile", back_populates="products")

    variants: Mapped[List["ProductVariant"]] = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    barcodes: Mapped[List["ProductBarcode"]] = relationship("ProductBarcode", back_populates="product", cascade="all, delete-orphan")
    price_history: Mapped[List["PriceHistory"]] = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    inventory_balance: Mapped[Optional["InventoryBalance"]] = relationship("InventoryBalance", back_populates="product", uselist=False)  # noqa: F821


class ProductVariant(Base, TimestampMixin):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    variant_sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    variant_barcode: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    package_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    material: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    additional_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    additional_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")


class ProductBarcode(Base):
    __tablename__ = "product_barcodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True)
    barcode_value: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    barcode_type: Mapped[str] = mapped_column(String(30), default="EAN13", nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="barcodes")


class PriceHistory(Base, TimestampMixin):
    """Auditable historical record of price changes for products and variants."""
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True)

    old_purchase_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    new_purchase_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    old_selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    new_selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    old_mrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    new_mrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    changed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="price_history")
