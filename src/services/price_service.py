"""
Price Management and Auditable Price History Service.
Supports independent pricing across product variants, package sizes, brands,
promotional prices, discount thresholds, price history logging, and bulk price revisions.
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import or_, and_, desc
from sqlalchemy.orm import Session, joinedload

from src.core.database import DatabaseManager
from src.core.exceptions import PermissionDeniedError, BillingSystemError
from src.models import Product, ProductVariant, PriceHistory, Category, Brand, User
from src.services.auth_service import UserSession

logger = logging.getLogger(__name__)


class PriceService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def update_product_price(
        self,
        current_session: UserSession,
        product_id: int,
        new_selling_price: Decimal,
        new_purchase_cost: Optional[Decimal] = None,
        new_mrp: Optional[Decimal] = None,
        promotional_price: Optional[Decimal] = None,
        min_selling_price: Optional[Decimal] = None,
        change_reason: str = "Manual Price Update",
        effective_date: Optional[datetime] = None,
    ) -> None:
        """
        Updates product price fields and logs an auditable entry in PriceHistory.
        """
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")

        if new_selling_price < Decimal("0.00"):
            raise BillingSystemError("Selling price cannot be negative.", code="INVALID_PRICE")

        with self.db.session() as session:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise BillingSystemError(f"Product ID {product_id} not found.", code="PRODUCT_NOT_FOUND")

            old_cost = product.purchase_cost
            old_price = product.selling_price
            old_mrp = product.mrp

            target_cost = new_purchase_cost if new_purchase_cost is not None else old_cost
            target_mrp = new_mrp if new_mrp is not None else old_mrp

            # Record Price History
            history_entry = PriceHistory(
                product_id=product.id,
                variant_id=None,
                old_purchase_cost=old_cost,
                new_purchase_cost=target_cost,
                old_selling_price=old_price,
                new_selling_price=new_selling_price,
                old_mrp=old_mrp,
                new_mrp=target_mrp,
                changed_by_user_id=current_session.user_id,
                change_reason=change_reason,
                effective_date=effective_date or datetime.now(timezone.utc),
            )
            session.add(history_entry)

            # Apply updates
            product.selling_price = new_selling_price
            product.purchase_cost = target_cost
            product.mrp = target_mrp
            product.promotional_price = promotional_price
            product.min_selling_price = min_selling_price

            session.flush()
            logger.info(
                f"Price updated for product '{product.name}' (ID {product.id}): "
                f"₹{old_price:.2f} -> ₹{new_selling_price:.2f} by user {current_session.username}"
            )

    def preview_bulk_updates(
        self,
        category_id: Optional[int] = None,
        brand_id: Optional[int] = None,
        product_ids: Optional[List[int]] = None,
        percent_change: Decimal = Decimal("0.00"),
        flat_change: Decimal = Decimal("0.00"),
        target_field: str = "selling_price",
    ) -> List[Dict[str, Any]]:
        """
        Calculates proposed price changes without modifying the database.
        Allows UI confirmation preview showing old vs new prices.
        """
        with self.db.session() as session:
            stmt = session.query(Product).options(joinedload(Product.category), joinedload(Product.brand))

            if product_ids:
                stmt = stmt.filter(Product.id.in_(product_ids))
            else:
                filters = []
                if category_id:
                    filters.append(Product.category_id == category_id)
                if brand_id:
                    filters.append(Product.brand_id == brand_id)
                if filters:
                    stmt = stmt.filter(and_(*filters))

            products = stmt.filter(Product.is_active == True).all()  # noqa: E712
            previews = []

            for p in products:
                current_val = getattr(p, target_field, Decimal("0.00")) or Decimal("0.00")

                # Formula: current * (1 + pct / 100) + flat
                mult = Decimal("1.00") + (percent_change / Decimal("100.00"))
                new_val = (current_val * mult) + flat_change
                if new_val < Decimal("0.00"):
                    new_val = Decimal("0.00")
                new_val = new_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                previews.append({
                    "product_id": p.id,
                    "name": p.name,
                    "sku": p.sku,
                    "category": p.category.name if p.category else "Uncategorized",
                    "brand": p.brand.name if p.brand else "-",
                    "old_val": float(current_val),
                    "new_val": float(new_val),
                    "difference": float(new_val - current_val),
                })

            return previews

    def apply_bulk_updates(
        self,
        current_session: UserSession,
        category_id: Optional[int] = None,
        brand_id: Optional[int] = None,
        product_ids: Optional[List[int]] = None,
        percent_change: Decimal = Decimal("0.00"),
        flat_change: Decimal = Decimal("0.00"),
        target_field: str = "selling_price",
        change_reason: str = "Bulk Price Revision",
    ) -> int:
        """
        Atomically applies bulk price revisions and creates individual auditable PriceHistory rows.
        """
        if not current_session.has_permission("products:manage"):
            raise PermissionDeniedError("products:manage")

        previews = self.preview_bulk_updates(
            category_id=category_id,
            brand_id=brand_id,
            product_ids=product_ids,
            percent_change=percent_change,
            flat_change=flat_change,
            target_field=target_field,
        )

        if not previews:
            return 0

        now = datetime.now(timezone.utc)
        with self.db.session() as session:
            for item in previews:
                prod = session.query(Product).filter_by(id=item["product_id"]).first()
                if not prod:
                    continue

                old_cost = prod.purchase_cost
                old_price = prod.selling_price
                old_mrp = prod.mrp

                new_cost = old_cost
                new_price = old_price
                new_mrp = old_mrp

                new_decimal = Decimal(str(item["new_val"]))
                if target_field == "selling_price":
                    new_price = new_decimal
                    prod.selling_price = new_decimal
                elif target_field == "purchase_cost":
                    new_cost = new_decimal
                    prod.purchase_cost = new_decimal
                elif target_field == "mrp":
                    new_mrp = new_decimal
                    prod.mrp = new_decimal

                history = PriceHistory(
                    product_id=prod.id,
                    variant_id=None,
                    old_purchase_cost=old_cost,
                    new_purchase_cost=new_cost,
                    old_selling_price=old_price,
                    new_selling_price=new_price,
                    old_mrp=old_mrp,
                    new_mrp=new_mrp,
                    changed_by_user_id=current_session.user_id,
                    change_reason=change_reason,
                    effective_date=now,
                )
                session.add(history)

            session.flush()

        logger.info(f"Bulk price revision applied to {len(previews)} products by user {current_session.username}")
        return len(previews)

    def get_price_history(self, product_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves complete chronological price change audit log for a product.
        """
        with self.db.session() as session:
            rows = (
                session.query(PriceHistory)
                .options(joinedload(PriceHistory.product))
                .filter(PriceHistory.product_id == product_id)
                .order_by(desc(PriceHistory.created_at))
                .all()
            )

            # Map user names
            user_ids = {r.changed_by_user_id for r in rows if r.changed_by_user_id}
            users = session.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
            user_name_map = {u.id: u.full_name or u.username for u in users}

            results = []
            for r in rows:
                user_label = user_name_map.get(r.changed_by_user_id, "System")
                results.append({
                    "id": r.id,
                    "date": r.created_at.strftime("%Y-%m-%d %H:%M"),
                    "old_cost": float(r.old_purchase_cost),
                    "new_cost": float(r.new_purchase_cost),
                    "old_price": float(r.old_selling_price),
                    "new_price": float(r.new_selling_price),
                    "old_mrp": float(r.old_mrp) if r.old_mrp else None,
                    "new_mrp": float(r.new_mrp) if r.new_mrp else None,
                    "changed_by": user_label,
                    "reason": r.change_reason or "N/A",
                })
            return results
