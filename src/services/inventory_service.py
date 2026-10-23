"""
Inventory Management Service: Auditable Stock Ledger, Atomic Deductions,
Batch and Expiry Tracking, Stock Corrections, and Stock Reconciliation.
"""

import logging
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import DatabaseManager
from src.core.exceptions import (
    InsufficientStockError,
    NegativeStockNotAllowedError,
    PermissionDeniedError,
    BillingSystemError,
)
from src.models import (
    Product,
    ProductVariant,
    InventoryBalance,
    InventoryBatch,
    StockMovement,
    StockAdjustment,
    StockAdjustmentItem,
    MovementType,
    ShopSettings,
)
from src.services.auth_service import UserSession

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def lock_and_deduct_stock(
        self,
        session: Session,
        product_id: int,
        variant_id: Optional[int],
        quantity: Decimal,
        reference_type: str,
        reference_id: str,
        user_id: Optional[int],
        batch_id: Optional[int] = None,
        allow_negative: bool = False,
    ) -> Decimal:
        """
        Atomically locks the inventory record (using FOR UPDATE on PostgreSQL),
        validates quantity availability, deducts the stock, and appends an immutable
        StockMovement ledger row.

        Must be called within an active transaction session.
        """
        if quantity <= Decimal("0.000"):
            raise BillingSystemError("Deduction quantity must be strictly positive.")

        # Dialect-aware locking query:
        # SQLite doesn't support SELECT ... FOR UPDATE, but SQLite transactions with WAL
        # provide isolation. On PostgreSQL, with_for_update() provides explicit row locking.
        is_postgres = session.bind.dialect.name == "postgresql"

        query = session.query(InventoryBalance).filter(
            InventoryBalance.product_id == product_id,
            InventoryBalance.variant_id == variant_id,
        )
        if is_postgres:
            query = query.with_for_update()

        balance = query.first()
        prod = session.query(Product).filter_by(id=product_id).first()
        prod_name = prod.name if prod else f"Product #{product_id}"

        if not balance:
            # Create a balance row if missing
            balance = InventoryBalance(
                product_id=product_id,
                variant_id=variant_id,
                quantity_on_hand=Decimal("0.000"),
                quantity_reserved=Decimal("0.000"),
            )
            session.add(balance)
            session.flush()

        current_qty = balance.quantity_on_hand

        if not allow_negative and current_qty < quantity:
            raise InsufficientStockError(
                product_name=prod_name,
                available=float(current_qty),
                requested=float(quantity),
                product_id=product_id,
            )

        new_balance = current_qty - quantity
        balance.quantity_on_hand = new_balance

        # If batch_id provided, deduct from batch as well
        if batch_id:
            batch = session.query(InventoryBatch).filter_by(id=batch_id).first()
            if batch:
                batch.quantity_on_hand -= quantity

        # Record immutable stock ledger movement
        movement = StockMovement(
            product_id=product_id,
            variant_id=variant_id,
            batch_id=batch_id,
            movement_type=MovementType.SALE_OUT,
            quantity=-quantity,
            unit_cost=prod.purchase_cost if prod else Decimal("0.00"),
            balance_after=new_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by_user_id=user_id,
            notes=f"POS Sale deduction for invoice {reference_id}",
        )
        session.add(movement)
        return new_balance

    def add_stock(
        self,
        session: Session,
        product_id: int,
        variant_id: Optional[int],
        quantity: Decimal,
        movement_type: str,
        reference_type: str,
        reference_id: str,
        user_id: Optional[int],
        unit_cost: Decimal = Decimal("0.00"),
        batch_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Decimal:
        """
        Adds inventory quantity (from purchase receipt, opening stock, or return)
        and logs a StockMovement.
        """
        if quantity <= Decimal("0.000"):
            raise BillingSystemError("Quantity added must be strictly positive.")

        is_postgres = session.bind.dialect.name == "postgresql"
        query = session.query(InventoryBalance).filter(
            InventoryBalance.product_id == product_id,
            InventoryBalance.variant_id == variant_id,
        )
        if is_postgres:
            query = query.with_for_update()

        balance = query.first()
        if not balance:
            balance = InventoryBalance(
                product_id=product_id,
                variant_id=variant_id,
                quantity_on_hand=Decimal("0.000"),
                quantity_reserved=Decimal("0.000"),
            )
            session.add(balance)
            session.flush()

        new_balance = balance.quantity_on_hand + quantity
        balance.quantity_on_hand = new_balance

        if batch_id:
            batch = session.query(InventoryBatch).filter_by(id=batch_id).first()
            if batch:
                batch.quantity_on_hand += quantity

        movement = StockMovement(
            product_id=product_id,
            variant_id=variant_id,
            batch_id=batch_id,
            movement_type=movement_type,
            quantity=quantity,
            unit_cost=unit_cost,
            balance_after=new_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by_user_id=user_id,
            notes=notes,
        )
        session.add(movement)
        return new_balance

    def perform_stock_adjustment(
        self,
        current_session: UserSession,
        product_id: int,
        new_quantity: Decimal,
        reason: str,  # "CORRECTION", "DAMAGE", "EXPIRY", "PHYSICAL_COUNT"
        notes: Optional[str] = None,
        variant_id: Optional[int] = None,
        batch_id: Optional[int] = None,
    ) -> int:
        """Performs an authorized manual stock adjustment and logs both adjustment item and stock movement."""
        if not current_session.has_permission("inventory:adjust"):
            raise PermissionDeniedError("inventory:adjust")

        with self.db.session() as session:
            balance = session.query(InventoryBalance).filter_by(
                product_id=product_id, variant_id=variant_id
            ).first()

            prev_qty = balance.quantity_on_hand if balance else Decimal("0.000")
            delta = new_quantity - prev_qty

            if delta == Decimal("0.000"):
                return 0

            import uuid
            adj_number = f"ADJ-{uuid.uuid4().hex[:8].upper()}"

            adjustment = StockAdjustment(
                adjustment_number=adj_number,
                reason=reason,
                authorized_by_user_id=current_session.user_id,
                notes=notes,
            )
            session.add(adjustment)
            session.flush()

            adj_item = StockAdjustmentItem(
                adjustment_id=adjustment.id,
                product_id=product_id,
                batch_id=batch_id,
                previous_quantity=prev_qty,
                new_quantity=new_quantity,
                adjustment_quantity=delta,
            )
            session.add(adj_item)

            if not balance:
                balance = InventoryBalance(product_id=product_id, variant_id=variant_id, quantity_on_hand=new_quantity)
                session.add(balance)
            else:
                balance.quantity_on_hand = new_quantity

            mv_type = {
                "DAMAGE": MovementType.ADJUSTMENT_DAMAGE,
                "EXPIRY": MovementType.ADJUSTMENT_EXPIRY,
            }.get(reason, MovementType.ADJUSTMENT_CORRECTION)

            prod = session.query(Product).filter_by(id=product_id).first()
            movement = StockMovement(
                product_id=product_id,
                variant_id=variant_id,
                batch_id=batch_id,
                movement_type=mv_type,
                quantity=delta,
                unit_cost=prod.purchase_cost if prod else Decimal("0.00"),
                balance_after=new_quantity,
                reference_type="ADJUSTMENT",
                reference_id=adj_number,
                created_by_user_id=current_session.user_id,
                notes=notes or f"Manual adjustment: {reason}",
            )
            session.add(movement)
            return adjustment.id

    def get_stock_ledger(
        self,
        product_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieves historical stock movements for auditing."""
        with self.db.session() as session:
            stmt = session.query(StockMovement).join(Product, StockMovement.product_id == Product.id)
            if product_id:
                stmt = stmt.filter(StockMovement.product_id == product_id)

            movements = stmt.order_by(StockMovement.created_at.desc()).limit(limit).offset(offset).all()

            results = []
            for m in movements:
                prod = session.query(Product).filter_by(id=m.product_id).first()
                results.append(
                    {
                        "id": m.id,
                        "product_name": prod.name if prod else "Unknown",
                        "movement_type": m.movement_type,
                        "quantity": float(m.quantity),
                        "unit_cost": float(m.unit_cost),
                        "balance_after": float(m.balance_after),
                        "reference_type": m.reference_type or "",
                        "reference_id": m.reference_id or "",
                        "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "notes": m.notes or "",
                    }
                )
            return results

    def get_low_stock_products(self) -> List[Dict[str, Any]]:
        """Finds all products where quantity on hand is at or below the reorder level."""
        with self.db.session() as session:
            results = (
                session.query(Product, InventoryBalance)
                .join(InventoryBalance, Product.id == InventoryBalance.product_id)
                .filter(
                    Product.is_active == True,  # noqa: E712
                    InventoryBalance.quantity_on_hand <= Product.reorder_level,
                )
                .all()
            )
            return [
                {
                    "product_id": p.id,
                    "name": p.name,
                    "sku": p.sku,
                    "available_qty": float(b.quantity_on_hand),
                    "reorder_level": float(p.reorder_level),
                    "unit": p.unit.code if p.unit else "PCS",
                }
                for p, b in results
            ]

    def reconcile_product_stock(self, product_id: int) -> Tuple[Decimal, Decimal, bool]:
        """
        Reconciles stored inventory balance against the exact sum of all stock movements.
        Returns (balance_on_hand, sum_of_movements, is_matching).
        """
        with self.db.session() as session:
            balance = session.query(InventoryBalance).filter_by(product_id=product_id, variant_id=None).first()
            current_qty = balance.quantity_on_hand if balance else Decimal("0.000")

            from sqlalchemy import func
            total_sum = session.query(func.coalesce(func.sum(StockMovement.quantity), Decimal("0.000"))).filter(
                StockMovement.product_id == product_id,
                StockMovement.variant_id == None,  # noqa: E711
            ).scalar()

            is_match = (current_qty == total_sum)
            return current_qty, total_sum, is_match
