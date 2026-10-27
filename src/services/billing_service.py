"""
POS Billing Service: Atomic Checkout, Multi-Computer Collision-Free
Invoice Sequences, Split Payments, Stock Deductions, and Sales Returns.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload

from src.core.database import DatabaseManager
from src.core.exceptions import (
    EmptyCartError,
    PaymentMismatchedError,
    DuplicateInvoiceError,
    InsufficientStockError,
    PermissionDeniedError,
    AccountInactiveError,
    BillingSystemError,
)
from src.models import (
    Shop,
    Customer,
    User,
    Sale,
    SaleItem,
    Payment,
    PaymentMethod,
    InvoiceSequence,
    SalesReturn,
    SalesReturnItem,
    MovementType,
    Product,
    ProductVariant,
    ParkedBill,
)
from src.services.auth_service import UserSession
from src.services.inventory_service import InventoryService
from src.services.tax_service import TaxEngine, LineTaxBreakdown, round_currency

logger = logging.getLogger(__name__)


@dataclass
class CartItemInput:
    product_id: int
    quantity: Decimal
    unit_price: Optional[Decimal] = None
    line_discount: Decimal = Decimal("0.00")
    variant_id: Optional[int] = None
    batch_id: Optional[int] = None
    gst_rate: Optional[Decimal] = None


@dataclass
class PaymentInput:
    payment_method: str  # CASH, UPI, CARD, BANK_TRANSFER
    amount: Decimal
    transaction_reference: Optional[str] = None


class BillingService:
    def __init__(self, db_manager: DatabaseManager, inventory_service: InventoryService):
        self.db = db_manager
        self.inventory = inventory_service

    def _get_next_invoice_number(self, session: Session, shop_id: int) -> str:
        """
        Generates the next sequential invoice number atomically.
        Uses atomic UPDATE ... RETURNING to guarantee unique numbers in multi-computer setups.
        """
        from sqlalchemy import text
        # Ensure sequence row exists
        existing = session.query(InvoiceSequence).filter_by(shop_id=shop_id).first()
        if not existing:
            seq = InvoiceSequence(
                shop_id=shop_id,
                prefix="INV-",
                financial_year="2026-27",
                current_number=0,
            )
            session.add(seq)
            session.flush()

        res = session.execute(
            text("UPDATE invoice_sequences SET current_number = current_number + 1 WHERE shop_id = :sid RETURNING prefix, financial_year, current_number"),
            {"sid": shop_id}
        ).fetchone()

        prefix, fy, curr_num = res[0], res[1], res[2]
        num_str = str(curr_num).zfill(5)
        return f"{prefix}{fy}-{num_str}"

    def complete_sale(
        self,
        current_session: UserSession,
        cart_items: List[CartItemInput],
        payments: List[PaymentInput],
        customer_id: Optional[int] = None,
        invoice_discount: Decimal = Decimal("0.00"),
        idempotency_key: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Completes a retail sale atomically:
        1. Checks idempotency.
        2. Validates cart and items.
        3. Computes GST line-items and invoice summary.
        4. Validates payment amount matches invoice grand total.
        5. Atomically locks and deducts inventory.
        6. Persists Sale, SaleItems, and Payments.
        """
        if not current_session.has_permission("pos:checkout"):
            raise PermissionDeniedError("pos:checkout")

        if not cart_items:
            raise EmptyCartError()

        if not idempotency_key:
            import uuid
            idempotency_key = f"pos_{uuid.uuid4().hex}"

        with self.db.session() as session:
            # Idempotency check: if transaction was already committed, return it
            existing_sale = (
                session.query(Sale)
                .options(joinedload(Sale.items), joinedload(Sale.payments))
                .filter_by(idempotency_key=idempotency_key)
                .first()
            )
            if existing_sale:
                logger.info(f"Idempotent sale detected: returning existing invoice {existing_sale.invoice_number}")
                return self._format_sale_dict(existing_sale)

            # Live check user active status in database
            cashier_user = session.query(User).filter_by(id=current_session.user_id).first()
            if cashier_user and not cashier_user.is_active:
                raise AccountInactiveError("This user account has been deactivated by the administrator. Sale cannot be completed.")

            shop = session.query(Shop).first()
            if not shop:
                raise BillingSystemError("Shop configuration missing.")

            customer = session.query(Customer).filter_by(id=customer_id).first() if customer_id else None
            buyer_state = customer.state_code if customer else None

            # Calculate GST breakdowns for all items
            line_breakdowns: List[LineTaxBreakdown] = []
            for item in cart_items:
                prod = session.query(Product).options(joinedload(Product.unit), joinedload(Product.tax_profile)).filter_by(id=item.product_id).first()
                if not prod or not prod.is_active:
                    raise BillingSystemError(f"Product #{item.product_id} is unavailable or inactive.")

                price = item.unit_price if item.unit_price is not None else prod.selling_price
                gst_rate = item.gst_rate if item.gst_rate is not None else (prod.tax_profile.gst_rate if prod.tax_profile else Decimal("0.00"))
                hsn_code = prod.tax_profile.hsn_sac_code if prod.tax_profile else "0000"
                unit_code = prod.unit.code if prod.unit else "PCS"

                line = TaxEngine.calculate_line_item(
                    product_id=prod.id,
                    product_name=prod.name,
                    hsn_sac_code=hsn_code,
                    unit_code=unit_code,
                    quantity=item.quantity,
                    unit_price=price,
                    gst_rate=gst_rate,
                    seller_state_code=shop.state_code,
                    buyer_state_code=buyer_state,
                    line_discount=item.line_discount,
                    is_tax_inclusive=shop.settings.tax_inclusive_default if shop.settings else False,
                )
                line_breakdowns.append(line)

            summary = TaxEngine.calculate_invoice_summary(line_breakdowns, invoice_discount=invoice_discount)

            # Validate Immediate Payments
            total_paid = sum((p.amount for p in payments), Decimal("0.00"))
            total_paid = round_currency(total_paid)
            if total_paid != summary.grand_total:
                raise PaymentMismatchedError(expected=float(summary.grand_total), actual=float(total_paid))

            # Generate unique sequential invoice number
            invoice_num = self._get_next_invoice_number(session, shop.id)

            # Check negative stock policy
            allow_neg = shop.settings.enable_negative_stock if shop.settings else False

            # Create Sale header
            sale = Sale(
                invoice_number=invoice_num,
                shop_id=shop.id,
                customer_id=customer_id,
                sale_date=datetime.now(timezone.utc),
                subtotal=summary.subtotal_gross,
                item_discount_total=summary.item_discounts_total,
                invoice_discount_amount=summary.invoice_discount,
                taxable_amount=summary.taxable_amount,
                cgst_amount=summary.cgst_amount,
                sgst_amount=summary.sgst_amount,
                igst_amount=summary.igst_amount,
                cess_amount=summary.cess_amount,
                round_off_amount=summary.round_off_amount,
                grand_total=summary.grand_total,
                payment_status="PAID",
                cashier_user_id=current_session.user_id,
                idempotency_key=idempotency_key,
                notes=notes,
            )
            session.add(sale)
            session.flush()

            # Process items and deduct stock atomically
            for cart_item, line in zip(cart_items, line_breakdowns):
                # Lock and deduct stock
                self.inventory.lock_and_deduct_stock(
                    session=session,
                    product_id=cart_item.product_id,
                    variant_id=cart_item.variant_id,
                    quantity=cart_item.quantity,
                    reference_type="SALE",
                    reference_id=invoice_num,
                    user_id=current_session.user_id,
                    batch_id=cart_item.batch_id,
                    allow_negative=allow_neg,
                )

                # Create immutable sale item snapshot
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=cart_item.product_id,
                    variant_id=cart_item.variant_id,
                    batch_id=cart_item.batch_id,
                    product_name_snapshot=line.product_name,
                    hsn_snapshot=line.hsn_sac_code,
                    unit_name_snapshot=line.unit_code,
                    unit_price=line.unit_price,
                    quantity=line.quantity,
                    line_discount_amount=line.line_discount,
                    taxable_value=line.taxable_value,
                    gst_rate=line.gst_rate,
                    is_interstate=line.is_interstate,
                    cgst_rate=line.cgst_rate,
                    cgst_amount=line.cgst_amount,
                    sgst_rate=line.sgst_rate,
                    sgst_amount=line.sgst_amount,
                    igst_rate=line.igst_rate,
                    igst_amount=line.igst_amount,
                    cess_amount=line.cess_amount,
                    line_total=line.line_total,
                )
                session.add(sale_item)

            # Record payments
            for p in payments:
                pay = Payment(
                    sale_id=sale.id,
                    payment_method=p.payment_method,
                    amount=p.amount,
                    transaction_reference=p.transaction_reference,
                    received_by_user_id=current_session.user_id,
                )
                session.add(pay)

            session.flush()
            logger.info(f"Sale completed successfully: Invoice {invoice_num}, Total: ₹{summary.grand_total}")
            sale_dict = self._format_sale_dict(sale)

            # Asynchronously sync to MongoDB Atlas if configured (never blocks local checkout)
            try:
                from src.services.mongo_service import MongoSyncService
                from src.services.settings_service import SettingsService
                mongo_svc = MongoSyncService(self.db)
                shop_id = SettingsService(self.db).get_cloud_shop_id()
                mongo_svc.sync_sale_async(sale_dict, shop_id)
            except Exception as e:
                logger.debug(f"MongoDB background sync trigger error: {e}")

            return sale_dict

    def get_invoice(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        """Retrieves a completed invoice for viewing or printing."""
        with self.db.session() as session:
            sale = (
                session.query(Sale)
                .options(
                    joinedload(Sale.customer),
                    joinedload(Sale.items),
                    joinedload(Sale.payments),
                )
                .filter_by(invoice_number=invoice_number)
                .first()
            )
            if not sale:
                return None
            return self._format_sale_dict(sale)

    def process_sales_return(
        self,
        current_session: UserSession,
        invoice_number: str,
        return_items: List[Tuple[int, Decimal]],  # [(sale_item_id, return_qty)]
        reason: str,
        refund_method: str = "CASH",
        restock_inventory: bool = True,
    ) -> str:
        """
        Processes a full or partial sales return, refunds customer, and replenishes stock if approved for restocking.
        """
        if not current_session.has_permission("pos:refund"):
            raise PermissionDeniedError("pos:refund")

        with self.db.session() as session:
            cashier_user = session.query(User).filter_by(id=current_session.user_id).first()
            if cashier_user and not cashier_user.is_active:
                raise AccountInactiveError("This user account has been deactivated by the administrator.")

            sale = session.query(Sale).options(joinedload(Sale.items)).filter_by(invoice_number=invoice_number).first()
            if not sale:
                raise BillingSystemError(f"Invoice {invoice_number} not found.")

            import uuid
            return_no = f"RET-{uuid.uuid4().hex[:8].upper()}"

            total_refund = Decimal("0.00")
            sr = SalesReturn(
                return_number=return_no,
                sale_id=sale.id,
                return_date=datetime.now(timezone.utc),
                refund_method=refund_method,
                reason=reason,
                cashier_user_id=current_session.user_id,
            )
            session.add(sr)
            session.flush()

            sale_items_by_id = {item.id: item for item in sale.items}

            for item_id, ret_qty in return_items:
                if ret_qty <= Decimal("0.000"):
                    continue
                s_item = sale_items_by_id.get(item_id)
                if not s_item or ret_qty > s_item.quantity:
                    raise BillingSystemError(f"Invalid return quantity for item #{item_id}.")

                # Pro-rata refund amount
                item_refund = (s_item.line_total / s_item.quantity) * ret_qty
                total_refund += item_refund

                sr_item = SalesReturnItem(
                    sales_return_id=sr.id,
                    sale_item_id=item_id,
                    product_id=s_item.product_id,
                    quantity_returned=ret_qty,
                    refund_amount=round_currency(item_refund),
                )
                session.add(sr_item)

                # Replenish stock only if approved for restocking
                if restock_inventory:
                    self.inventory.add_stock(
                        session=session,
                        product_id=s_item.product_id,
                        variant_id=s_item.variant_id,
                        quantity=ret_qty,
                        movement_type=MovementType.SALE_RETURN,
                        reference_type="SALE_RETURN",
                        reference_id=return_no,
                        user_id=current_session.user_id,
                        unit_cost=s_item.unit_price,
                        batch_id=s_item.batch_id,
                        notes=f"Return Restocked for invoice {invoice_number}: {reason}",
                    )
                else:
                    logger.info(
                        f"Returned item #{s_item.product_id} ({ret_qty}) marked as damaged/non-restockable. "
                        f"Saleable stock unchanged."
                    )

            sr.grand_total = round_currency(total_refund)
            sr.subtotal = round_currency(total_refund)
            session.flush()
            logger.info(f"Sales return processed: {return_no}, Refunded: ₹{total_refund}, Restocked: {restock_inventory}")
            return return_no

    def _format_sale_dict(self, sale: Sale) -> Dict[str, Any]:
        """Serializes Sale model into a complete JSON-serializable dictionary."""
        return {
            "id": sale.id,
            "invoice_number": sale.invoice_number,
            "sale_date": sale.sale_date.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": sale.customer.name if sale.customer else "Walk-in Customer",
            "customer_phone": sale.customer.phone if sale.customer else "",
            "customer_gstin": sale.customer.gstin if sale.customer else "",
            "subtotal": float(sale.subtotal),
            "item_discount_total": float(sale.item_discount_total),
            "invoice_discount_amount": float(sale.invoice_discount_amount),
            "taxable_amount": float(sale.taxable_amount),
            "cgst_amount": float(sale.cgst_amount),
            "sgst_amount": float(sale.sgst_amount),
            "igst_amount": float(sale.igst_amount),
            "cess_amount": float(sale.cess_amount),
            "round_off_amount": float(sale.round_off_amount),
            "grand_total": float(sale.grand_total),
            "payment_status": sale.payment_status,
            "is_cancelled": sale.is_cancelled,
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "name": item.product_name_snapshot,
                    "hsn": item.hsn_snapshot,
                    "unit": item.unit_name_snapshot,
                    "unit_price": float(item.unit_price),
                    "quantity": float(item.quantity),
                    "line_discount": float(item.line_discount_amount),
                    "taxable_value": float(item.taxable_value),
                    "gst_rate": float(item.gst_rate),
                    "cgst_amount": float(item.cgst_amount),
                    "sgst_amount": float(item.sgst_amount),
                    "igst_amount": float(item.igst_amount),
                    "line_total": float(item.line_total),
                }
                for item in sale.items
            ],
            "payments": [
                {
                    "method": p.payment_method,
                    "amount": float(p.amount),
                    "reference": p.transaction_reference or "",
                }
                for p in sale.payments
            ],
        }

    # ---------------- Multi-Customer Park & Recall Bills ----------------

    def park_bill(
        self,
        current_session: UserSession,
        cart_data: List[Dict[str, Any]],
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_gstin: Optional[str] = None,
        invoice_discount: Decimal = Decimal("0.00"),
        notes: Optional[str] = None,
        counter_id: str = "Counter #1",
    ) -> Dict[str, Any]:
        """
        Temporarily holds an active shopping cart into the database
        so the cashier can bill another customer immediately.
        """
        if not current_session.has_permission("pos:checkout"):
            raise PermissionDeniedError("pos:checkout")

        if not cart_data:
            raise EmptyCartError()

        import json
        import uuid

        items_count = sum(int(Decimal(str(item.get("quantity", "1")))) for item in cart_data)
        total_amount = Decimal("0.00")
        for item in cart_data:
            qty = Decimal(str(item.get("quantity", "1")))
            price = Decimal(str(item.get("price", "0.00")))
            disc = Decimal(str(item.get("discount", "0.00")))
            total_amount += (qty * price) - disc
        total_amount -= invoice_discount
        if total_amount < Decimal("0.00"):
            total_amount = Decimal("0.00")

        park_ref = f"HOLD-{uuid.uuid4().hex[:6].upper()}"

        with self.db.session() as session:
            cashier_user = session.query(User).filter_by(id=current_session.user_id).first()
            if cashier_user and not cashier_user.is_active:
                raise AccountInactiveError("This user account has been deactivated by the administrator.")

            shop = session.query(Shop).first()
            if not shop:
                raise BillingSystemError("Shop not configured.", code="SHOP_NOT_FOUND")

            parked = ParkedBill(
                park_reference=park_ref,
                shop_id=shop.id,
                cashier_user_id=current_session.user_id,
                counter_id=counter_id,
                customer_name=customer_name or "Walk-in Customer",
                customer_phone=customer_phone,
                customer_gstin=customer_gstin,
                invoice_discount=invoice_discount,
                items_count=items_count,
                total_amount=total_amount,
                cart_data_json=json.dumps(cart_data),
                status="PARKED",
                notes=notes,
            )
            session.add(parked)
            session.flush()

            logger.info(f"Bill parked successfully with reference {park_ref} for {parked.customer_name}")
            return {
                "id": parked.id,
                "park_reference": park_ref,
                "customer_name": parked.customer_name,
                "items_count": items_count,
                "total_amount": float(total_amount),
                "created_at": parked.created_at.strftime("%I:%M %p") if parked.created_at else "",
            }

    def list_parked_bills(self, current_session: UserSession) -> List[Dict[str, Any]]:
        """Lists all active held/parked bills waiting to be recalled."""
        if not current_session.has_permission("pos:checkout"):
            raise PermissionDeniedError("pos:checkout")

        with self.db.session() as session:
            bills = (
                session.query(ParkedBill)
                .filter_by(status="PARKED")
                .order_by(ParkedBill.created_at.desc())
                .all()
            )
            return [
                {
                    "id": b.id,
                    "park_reference": b.park_reference,
                    "customer_name": b.customer_name or "Walk-in",
                    "customer_phone": b.customer_phone or "",
                    "customer_gstin": b.customer_gstin or "",
                    "items_count": b.items_count,
                    "total_amount": float(b.total_amount),
                    "invoice_discount": float(b.invoice_discount),
                    "counter_id": b.counter_id,
                    "created_at": b.created_at.strftime("%I:%M:%S %p") if b.created_at else "",
                }
                for b in bills
            ]

    def get_parked_bills_count(self, current_session: UserSession) -> int:
        """Returns the total number of currently held bills for badging."""
        with self.db.session() as session:
            return session.query(ParkedBill).filter_by(status="PARKED").count()

    def recall_bill(self, current_session: UserSession, parked_id: int) -> Dict[str, Any]:
        """Recalls a held bill, marks it as RECALLED, and returns the full cart data."""
        if not current_session.has_permission("pos:checkout"):
            raise PermissionDeniedError("pos:checkout")

        import json

        with self.db.session() as session:
            cashier_user = session.query(User).filter_by(id=current_session.user_id).first()
            if cashier_user and not cashier_user.is_active:
                raise AccountInactiveError("This user account has been deactivated by the administrator.")

            bill = session.query(ParkedBill).filter_by(id=parked_id, status="PARKED").first()
            if not bill:
                raise BillingSystemError("Held bill not found or already recalled.", code="NOT_FOUND")

            bill.status = "RECALLED"
            session.flush()

            cart_data = json.loads(bill.cart_data_json)
            logger.info(f"Parked bill {bill.park_reference} recalled by cashier {current_session.username}")

            return {
                "id": bill.id,
                "park_reference": bill.park_reference,
                "customer_name": bill.customer_name,
                "customer_phone": bill.customer_phone,
                "customer_gstin": bill.customer_gstin,
                "invoice_discount": float(bill.invoice_discount),
                "cart_data": cart_data,
            }

    def cancel_parked_bill(self, current_session: UserSession, parked_id: int) -> None:
        """Cancels/discards a held bill that will no longer be checked out."""
        if not current_session.has_permission("pos:checkout"):
            raise PermissionDeniedError("pos:checkout")

        with self.db.session() as session:
            bill = session.query(ParkedBill).filter_by(id=parked_id, status="PARKED").first()
            if not bill:
                raise BillingSystemError("Held bill not found.", code="NOT_FOUND")
            bill.status = "CANCELLED"
            logger.info(f"Parked bill {bill.park_reference} cancelled.")
