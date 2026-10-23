"""
Shop identity, business configuration, and application-level settings models.
"""

from typing import Optional, List
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, index=True)
    trade_license: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state_code: Mapped[str] = mapped_column(String(2), default="33", nullable=False)  # 33 = Tamil Nadu
    state_name: Mapped[str] = mapped_column(String(100), default="Tamil Nadu", nullable=False)
    pincode: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    currency_symbol: Mapped[str] = mapped_column(String(5), default="₹", nullable=False)

    settings: Mapped[Optional["ShopSettings"]] = relationship(
        "ShopSettings", back_populates="shop", uselist=False, cascade="all, delete-orphan"
    )
    users: Mapped[List["User"]] = relationship("User", back_populates="shop")  # noqa: F821


class ShopSettings(Base, TimestampMixin):
    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), unique=True, nullable=False)
    business_profile: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    invoice_prefix: Mapped[str] = mapped_column(String(20), default="INV-", nullable=False)
    receipt_format: Mapped[str] = mapped_column(String(20), default="80mm", nullable=False)
    thermal_printer_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    enable_negative_stock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    low_stock_threshold_default: Mapped[float] = mapped_column(default=5.0, nullable=False)
    tax_inclusive_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invoice_footer_text: Mapped[Optional[str]] = mapped_column(Text, default="Thank you for your visit!", nullable=True)

    shop: Mapped["Shop"] = relationship("Shop", back_populates="settings")


class ApplicationSettings(Base, TimestampMixin):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
