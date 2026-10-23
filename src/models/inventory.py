"""
Inventory models: balances, batches, serial/IMEI tracking,
auditable stock movement ledger, and stock adjustments.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String, Text, Boolean, Integer, Numeric, ForeignKey, DateTime, Date, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class MovementType:
    OPENING_STOCK = "OPENING_STOCK"
    PURCHASE_IN = "PURCHASE_IN"
    SALE_OUT = "SALE_OUT"
    SALE_RETURN = "SALE_RETURN"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    ADJUSTMENT_DAMAGE = "ADJUSTMENT_DAMAGE"
    ADJUSTMENT_EXPIRY = "ADJUSTMENT_EXPIRY"
    ADJUSTMENT_CORRECTION = "ADJUSTMENT_CORRECTION"


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True, index=True)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.000"), nullable=False)
    quantity_reserved: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.000"), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    product: Mapped["Product"] = relationship("Product", back_populates="inventory_balance")  # noqa: F821
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant")  # noqa: F821

    __table_args__ = (
        Index("idx_product_variant_balance", "product_id", "variant_id", unique=True),
    )


class InventoryBatch(Base, TimestampMixin):
    __tablename__ = "inventory_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    manufacturing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.000"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped["Product"] = relationship("Product")  # noqa: F821


class InventorySerial(Base, TimestampMixin):
    __tablename__ = "inventory_serials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    imei_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="IN_STOCK", nullable=False)  # IN_STOCK, SOLD, RETURNED, DEFECTIVE
    purchase_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sale_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    product: Mapped["Product"] = relationship("Product")  # noqa: F821


class StockMovement(Base):
    """Immutable ledger of every inventory mutation."""
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True)
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # SALE, PURCHASE, ADJUSTMENT
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adjustment_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    adjustment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(100), nullable=False)  # DAMAGE, EXPIRY, CORRECTION, PHYSICAL_COUNT
    authorized_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    items: Mapped[List["StockAdjustmentItem"]] = relationship(
        "StockAdjustmentItem", back_populates="adjustment", cascade="all, delete-orphan"
    )


class StockAdjustmentItem(Base):
    __tablename__ = "stock_adjustment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adjustment_id: Mapped[int] = mapped_column(ForeignKey("stock_adjustments.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True)
    previous_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    new_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    adjustment_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    adjustment: Mapped["StockAdjustment"] = relationship("StockAdjustment", back_populates="items")
    product: Mapped["Product"] = relationship("Product")  # noqa: F821
