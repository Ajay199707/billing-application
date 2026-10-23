"""
Customer records, POS sales invoices, immutable sale items,
immediate payment splits, sales returns, and atomic invoice sequence counters.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String, Text, Boolean, Integer, Numeric, ForeignKey, DateTime, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class PaymentMethod:
    CASH = "CASH"
    UPI = "UPI"
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), default="Walk-in Customer", nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, index=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)  # State code for inter-state tax
    loyalty_points: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)

    sales: Mapped[List["Sale"]] = relationship("Sale", back_populates="customer")


class Sale(Base, TimestampMixin):
    """Authoritative sales invoice record."""
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    sale_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    item_discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    invoice_discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    cess_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    round_off_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    payment_status: Mapped[str] = mapped_column(String(20), default="PAID", nullable=False)  # Immediate payment only
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cashier_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="sales")
    items: Mapped[List["SaleItem"]] = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="sale", cascade="all, delete-orphan")
    returns: Mapped[List["SalesReturn"]] = relationship("SalesReturn", back_populates="sale")


class SaleItem(Base):
    """
    Individual sold item with complete historical snapshot of name,
    HSN/SAC, GST breakdown, and unit price as of the sale timestamp.
    """
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True)

    product_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    hsn_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_name_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)

    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    line_discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_interstate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cgst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    sgst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    igst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    cess_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")
    product: Mapped["Product"] = relationship("Product")  # noqa: F821


class Payment(Base):
    """Immediate payment settlement per sale."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)  # CASH, UPI, CARD, BANK_TRANSFER
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    received_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="payments")


class SalesReturn(Base, TimestampMixin):
    __tablename__ = "sales_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    return_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False)
    return_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    refund_method: Mapped[str] = mapped_column(String(30), default="CASH", nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    cashier_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="returns")
    items: Mapped[List["SalesReturnItem"]] = relationship("SalesReturnItem", back_populates="sales_return", cascade="all, delete-orphan")


class SalesReturnItem(Base):
    __tablename__ = "sales_return_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sales_return_id: Mapped[int] = mapped_column(ForeignKey("sales_returns.id", ondelete="CASCADE"), nullable=False)
    sale_item_id: Mapped[int] = mapped_column(ForeignKey("sale_items.id", ondelete="RESTRICT"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity_returned: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sales_return: Mapped["SalesReturn"] = relationship("SalesReturn", back_populates="items")
    product: Mapped["Product"] = relationship("Product")  # noqa: F821


class InvoiceSequence(Base):
    """Thread-safe and multi-computer sequential counter for invoice generation."""
    __tablename__ = "invoice_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), default="INV-", nullable=False)
    financial_year: Mapped[str] = mapped_column(String(10), default="2026-27", nullable=False)
    current_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("idx_shop_prefix_fy", "shop_id", "prefix", "financial_year", unique=True),
    )


class ParkedBill(Base, TimestampMixin):
    """Temporary held shopping cart for multi-customer fast checkout."""
    __tablename__ = "parked_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    park_reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    cashier_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    counter_id: Mapped[str] = mapped_column(String(50), default="Counter #1", nullable=False)

    customer_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    customer_gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    invoice_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    items_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    cart_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PARKED", nullable=False, index=True)  # PARKED, RECALLED, CANCELLED
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
