"""
Supplier and Purchasing Management Service.
Manages supplier master records, procurement bills, goods receipts, and purchase returns.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload

from src.core.database import DatabaseManager
from src.core.exceptions import (
    BillingSystemError,
    PermissionDeniedError,
)
from src.models import (
    Supplier,
    Purchase,
    PurchaseItem,
    PurchaseReturn,
    Product,
    ProductVariant,
    MovementType,
    InventoryBatch,
)
from src.services.auth_service import UserSession
from src.services.inventory_service import InventoryService
from src.services.tax_service import round_currency

logger = logging.getLogger(__name__)


@dataclass
class PurchaseItemInput:
    product_id: int
    quantity: Decimal
    unit_cost: Decimal
    gst_rate: Decimal
    variant_id: Optional[int] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    hsn_code: Optional[str] = None


class PurchaseService:
    def __init__(self, db_manager: DatabaseManager, inventory_service: InventoryService):
        self.db = db_manager
        self.inventory = inventory_service

    # ---------------- Supplier Management ----------------

    def create_supplier(
        self,
        current_session: UserSession,
        name: str,
        company_name: Optional[str] = None,
        gstin: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        state_code: str = "33",
        payment_terms_days: int = 0,
    ) -> int:
        if not current_session.has_permission("suppliers:manage"):
            raise PermissionDeniedError("suppliers:manage")

        with self.db.session() as session:
            supplier = Supplier(
                name=name,
                company_name=company_name,
                gstin=gstin,
                phone=phone,
                email=email,
                address=address,
                state_code=state_code,
                payment_terms_days=payment_terms_days,
                is_active=True,
            )
            session.add(supplier)
            session.flush()
            return supplier.id

    def list_suppliers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            stmt = session.query(Supplier)
            if active_only:
                stmt = stmt.filter_by(is_active=True)
            suppliers = stmt.order_by(Supplier.name).all()
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "company_name": s.company_name or "",
                    "gstin": s.gstin or "",
                    "phone": s.phone or "",
                    "email": s.email or "",
                    "state_code": s.state_code,
                    "payment_terms_days": s.payment_terms_days,
                    "is_active": s.is_active,
                }
                for s in suppliers
            ]

    # ---------------- Purchase Orders & Goods Receipt ----------------

    def record_purchase(
        self,
        current_session: UserSession,
        supplier_id: int,
        supplier_invoice_no: str,
        items: List[PurchaseItemInput],
        purchase_date: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> str:
        """
        Records a purchase order and increases inventory stock atomically.
        """
        if not current_session.has_permission("purchases:manage"):
            raise PermissionDeniedError("purchases:manage")

        if not items:
            raise BillingSystemError("Cannot record purchase without items.")

        with self.db.session() as session:
            supplier = session.query(Supplier).filter_by(id=supplier_id).first()
            if not supplier:
                raise BillingSystemError(f"Supplier #{supplier_id} not found.")

            import uuid
            purchase_no = f"PO-{uuid.uuid4().hex[:8].upper()}"

            subtotal = Decimal("0.00")
            tax_total = Decimal("0.00")
            grand_total = Decimal("0.00")

            purchase = Purchase(
                purchase_number=purchase_no,
                supplier_id=supplier_id,
                supplier_invoice_no=supplier_invoice_no,
                purchase_date=purchase_date or date.today(),
                status="RECEIVED",
                payment_status="PAID",
                received_by_user_id=current_session.user_id,
                notes=notes,
            )
            session.add(purchase)
            session.flush()

            for item_in in items:
                prod = session.query(Product).filter_by(id=item_in.product_id).first()
                if not prod:
                    raise BillingSystemError(f"Product #{item_in.product_id} not found.")

                item_taxable = round_currency(item_in.quantity * item_in.unit_cost)
                item_tax = round_currency(item_taxable * (item_in.gst_rate / Decimal("100")))
                item_line_total = item_taxable + item_tax

                subtotal += item_taxable
                tax_total += item_tax
                grand_total += item_line_total

                batch_id = None
                if item_in.batch_number:
                    # Create or find batch
                    batch = session.query(InventoryBatch).filter_by(
                        product_id=item_in.product_id, batch_number=item_in.batch_number
                    ).first()
                    if not batch:
                        batch = InventoryBatch(
                            product_id=item_in.product_id,
                            batch_number=item_in.batch_number,
                            expiry_date=item_in.expiry_date,
                            purchase_cost=item_in.unit_cost,
                            selling_price=prod.selling_price,
                            quantity_on_hand=Decimal("0.000"),
                        )
                        session.add(batch)
                        session.flush()
                    batch_id = batch.id

                p_item = PurchaseItem(
                    purchase_id=purchase.id,
                    product_id=item_in.product_id,
                    variant_id=item_in.variant_id,
                    batch_number=item_in.batch_number,
                    expiry_date=item_in.expiry_date,
                    quantity=item_in.quantity,
                    unit_cost=item_in.unit_cost,
                    hsn_code=item_in.hsn_code or (prod.tax_profile.hsn_sac_code if prod.tax_profile else "0000"),
                    gst_rate=item_in.gst_rate,
                    tax_amount=item_tax,
                    line_total=item_line_total,
                )
                session.add(p_item)

                # Atomically increase inventory stock
                self.inventory.add_stock(
                    session=session,
                    product_id=item_in.product_id,
                    variant_id=item_in.variant_id,
                    quantity=item_in.quantity,
                    movement_type=MovementType.PURCHASE_IN,
                    reference_type="PURCHASE",
                    reference_id=purchase_no,
                    user_id=current_session.user_id,
                    unit_cost=item_in.unit_cost,
                    batch_id=batch_id,
                    notes=f"Purchase from {supplier.name} (Inv: {supplier_invoice_no})",
                )

                # Optionally update latest purchase cost on product
                prod.purchase_cost = item_in.unit_cost

            purchase.subtotal = round_currency(subtotal)
            purchase.tax_total = round_currency(tax_total)
            purchase.grand_total = round_currency(grand_total)

            session.flush()
            logger.info(f"Purchase order {purchase_no} recorded: Total: ₹{grand_total}")
            return purchase_no

    def list_purchases(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            purchases = (
                session.query(Purchase)
                .options(joinedload(Purchase.supplier), joinedload(Purchase.items))
                .order_by(Purchase.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [
                {
                    "id": p.id,
                    "purchase_number": p.purchase_number,
                    "supplier_name": p.supplier.name if p.supplier else "Unknown",
                    "supplier_invoice_no": p.supplier_invoice_no or "",
                    "purchase_date": p.purchase_date.strftime("%Y-%m-%d"),
                    "status": p.status,
                    "subtotal": float(p.subtotal),
                    "tax_total": float(p.tax_total),
                    "grand_total": float(p.grand_total),
                    "items_count": len(p.items),
                }
                for p in purchases
            ]
