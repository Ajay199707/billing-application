"""
Reporting & Business Intelligence Service.
Computes real-time dashboard analytics, sales trends, inventory valuations,
GST statutory tax returns, gross/net margins, and Excel/CSV exports.
"""

import csv
import io
import logging
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload
import openpyxl

from src.core.database import DatabaseManager
from src.core.exceptions import PermissionDeniedError
from src.models import (
    Sale,
    SaleItem,
    Payment,
    Product,
    Category,
    InventoryBalance,
    Purchase,
    Expense,
)
from src.services.auth_service import UserSession

logger = logging.getLogger(__name__)


class ReportingService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    # ---------------- Real-Time Dashboard KPI Metrics ----------------

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Fetches high-level executive KPIs for the POS Dashboard."""
        today = date.today()
        start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
        end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)

        with self.db.session() as session:
            # 1. Today's Sales
            sales_today = session.query(Sale).filter(
                Sale.sale_date >= start_of_day,
                Sale.sale_date <= end_of_day,
                Sale.is_cancelled == False,  # noqa: E712
            ).all()

            today_revenue = sum((s.grand_total for s in sales_today), Decimal("0.00"))
            today_bills_count = len(sales_today)

            today_items_sold = (
                session.query(func.coalesce(func.sum(SaleItem.quantity), Decimal("0.000")))
                .join(Sale, SaleItem.sale_id == Sale.id)
                .filter(Sale.sale_date >= start_of_day, Sale.sale_date <= end_of_day, Sale.is_cancelled == False)  # noqa: E712
                .scalar()
            )

            # 2. Payment breakdowns today
            payments_today = (
                session.query(Payment.payment_method, func.sum(Payment.amount))
                .join(Sale, Payment.sale_id == Sale.id)
                .filter(Sale.sale_date >= start_of_day, Sale.sale_date <= end_of_day, Sale.is_cancelled == False)  # noqa: E712
                .group_by(Payment.payment_method)
                .all()
            )
            pay_methods = {pm: float(amt) for pm, amt in payments_today}

            # 3. Low stock and out-of-stock counts
            low_stock_count = (
                session.query(Product)
                .join(InventoryBalance, Product.id == InventoryBalance.product_id)
                .filter(
                    Product.is_active == True,  # noqa: E712
                    InventoryBalance.quantity_on_hand <= Product.reorder_level,
                    InventoryBalance.quantity_on_hand > Decimal("0.000"),
                )
                .count()
            )

            out_of_stock_count = (
                session.query(Product)
                .join(InventoryBalance, Product.id == InventoryBalance.product_id)
                .filter(
                    Product.is_active == True,  # noqa: E712
                    InventoryBalance.quantity_on_hand <= Decimal("0.000"),
                )
                .count()
            )

            # 4. Total Products
            total_products = session.query(Product).filter_by(is_active=True).count()

            # 5. Recent transactions
            recent_sales = (
                session.query(Sale)
                .options(joinedload(Sale.customer))
                .order_by(Sale.sale_date.desc())
                .limit(10)
                .all()
            )

            recent_txns = [
                {
                    "invoice_number": s.invoice_number,
                    "date": s.sale_date.strftime("%H:%M:%S"),
                    "customer": s.customer.name if s.customer else "Walk-in",
                    "grand_total": float(s.grand_total),
                }
                for s in recent_sales
            ]

            return {
                "today_revenue": float(today_revenue),
                "today_bills_count": today_bills_count,
                "today_items_sold": float(today_items_sold),
                "payment_methods": pay_methods,
                "low_stock_count": low_stock_count,
                "out_of_stock_count": out_of_stock_count,
                "total_products": total_products,
                "recent_transactions": recent_txns,
            }

    # ---------------- Sales Reports ----------------

    def get_sales_report(
        self,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Retrieves sales invoices within date range."""
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)

        with self.db.session() as session:
            sales = (
                session.query(Sale)
                .options(joinedload(Sale.customer), joinedload(Sale.payments))
                .filter(
                    Sale.sale_date >= start_dt,
                    Sale.sale_date <= end_dt,
                    Sale.is_cancelled == False,  # noqa: E712
                )
                .order_by(Sale.sale_date.desc())
                .all()
            )

            results = []
            for s in sales:
                pay_mode = ", ".join([p.payment_method for p in s.payments]) if s.payments else "CASH"
                results.append({
                    "invoice_number": s.invoice_number,
                    "date": s.sale_date.strftime("%Y-%m-%d %H:%M"),
                    "customer": s.customer.name if s.customer else "Walk-in",
                    "subtotal": float(s.subtotal),
                    "discount": float(s.invoice_discount_amount + s.item_discount_total),
                    "taxable": float(s.taxable_amount),
                    "tax": float(s.cgst_amount + s.sgst_amount + s.igst_amount),
                    "grand_total": float(s.grand_total),
                    "payment_mode": pay_mode,
                })
            return results

    # ---------------- Product-Wise & Category-Wise Sales ----------------

    def get_product_sales_summary(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)

        with self.db.session() as session:
            rows = (
                session.query(
                    SaleItem.product_name_snapshot,
                    SaleItem.hsn_snapshot,
                    func.sum(SaleItem.quantity).label("total_qty"),
                    func.sum(SaleItem.taxable_value).label("total_taxable"),
                    func.sum(SaleItem.line_total).label("total_revenue"),
                )
                .join(Sale, SaleItem.sale_id == Sale.id)
                .filter(Sale.sale_date >= start_dt, Sale.sale_date <= end_dt, Sale.is_cancelled == False)  # noqa: E712
                .group_by(SaleItem.product_name_snapshot, SaleItem.hsn_snapshot)
                .order_by(func.sum(SaleItem.line_total).desc())
                .all()
            )

            return [
                {
                    "product_name": r[0],
                    "hsn": r[1],
                    "quantity": float(r[2]),
                    "taxable": float(r[3]),
                    "revenue": float(r[4]),
                }
                for r in rows
            ]

    # ---------------- GST Statutory Tax Summary (GSTR-1 Preparation) ----------------

    def get_gst_tax_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Aggregates GST tax components grouped by GST tax rate."""
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)

        with self.db.session() as session:
            rows = (
                session.query(
                    SaleItem.gst_rate,
                    func.sum(SaleItem.taxable_value).label("taxable"),
                    func.sum(SaleItem.cgst_amount).label("cgst"),
                    func.sum(SaleItem.sgst_amount).label("sgst"),
                    func.sum(SaleItem.igst_amount).label("igst"),
                    func.sum(SaleItem.line_total).label("total"),
                )
                .join(Sale, SaleItem.sale_id == Sale.id)
                .filter(Sale.sale_date >= start_dt, Sale.sale_date <= end_dt, Sale.is_cancelled == False)  # noqa: E712
                .group_by(SaleItem.gst_rate)
                .order_by(SaleItem.gst_rate)
                .all()
            )

            breakdown = [
                {
                    "gst_rate": float(r[0]),
                    "taxable": float(r[1]),
                    "cgst": float(r[2]),
                    "sgst": float(r[3]),
                    "igst": float(r[4]),
                    "total_tax": float(r[2] + r[3] + r[4]),
                    "total_gross": float(r[5]),
                }
                for r in rows
            ]

            total_taxable = sum((b["taxable"] for b in breakdown), 0.0)
            total_cgst = sum((b["cgst"] for b in breakdown), 0.0)
            total_sgst = sum((b["sgst"] for b in breakdown), 0.0)
            total_igst = sum((b["igst"] for b in breakdown), 0.0)
            total_tax = sum((b["total_tax"] for b in breakdown), 0.0)

            return {
                "breakdown": breakdown,
                "total_taxable": total_taxable,
                "total_cgst": total_cgst,
                "total_sgst": total_sgst,
                "total_igst": total_igst,
                "total_tax": total_tax,
            }

    # ---------------- Inventory Valuation ----------------

    def get_inventory_valuation(self) -> Dict[str, Any]:
        """Calculates total inventory holding value at cost price and estimated retail value."""
        with self.db.session() as session:
            rows = (
                session.query(Product, InventoryBalance)
                .join(InventoryBalance, Product.id == InventoryBalance.product_id)
                .filter(Product.is_active == True)  # noqa: E712
                .all()
            )

            total_items = len(rows)
            total_units = Decimal("0.000")
            total_cost_val = Decimal("0.00")
            total_retail_val = Decimal("0.00")

            item_details = []
            for prod, bal in rows:
                qty = bal.quantity_on_hand
                cost_val = qty * prod.purchase_cost
                retail_val = qty * prod.selling_price
                total_units += qty
                total_cost_val += cost_val
                total_retail_val += retail_val

                item_details.append({
                    "product_name": prod.name,
                    "sku": prod.sku,
                    "quantity": float(qty),
                    "unit_cost": float(prod.purchase_cost),
                    "selling_price": float(prod.selling_price),
                    "cost_value": float(cost_val),
                    "retail_value": float(retail_val),
                })

            gross_margin_est = total_retail_val - total_cost_val

            return {
                "total_items": total_items,
                "total_quantity": float(total_units),
                "total_cost_value": float(total_cost_val),
                "total_retail_value": float(total_retail_val),
                "estimated_gross_profit": float(gross_margin_est),
                "items": item_details,
            }

    # ---------------- Financial Profit & Loss Estimation ----------------

    def get_profit_and_loss(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Calculates Estimated Gross and Net Profit:
        Revenue (Taxable) - Cost of Goods Sold = Gross Profit
        Gross Profit - Operating Expenses = Net Operating Profit
        """
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)

        with self.db.session() as session:
            # Sales taxable total
            taxable_sales = (
                session.query(func.coalesce(func.sum(Sale.taxable_amount), Decimal("0.00")))
                .filter(Sale.sale_date >= start_dt, Sale.sale_date <= end_dt, Sale.is_cancelled == False)  # noqa: E712
                .scalar()
            )

            # Cost of Goods Sold (quantity sold * product purchase cost)
            cogs = (
                session.query(func.coalesce(func.sum(SaleItem.quantity * Product.purchase_cost), Decimal("0.00")))
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Product, SaleItem.product_id == Product.id)
                .filter(Sale.sale_date >= start_dt, Sale.sale_date <= end_dt, Sale.is_cancelled == False)  # noqa: E712
                .scalar()
            )

            # Expenses
            expenses = (
                session.query(func.coalesce(func.sum(Expense.amount), Decimal("0.00")))
                .filter(Expense.expense_date >= start_date, Expense.expense_date <= end_date)
                .scalar()
            )

            gross_profit = taxable_sales - cogs
            net_profit = gross_profit - expenses

            return {
                "taxable_sales_revenue": float(taxable_sales),
                "cost_of_goods_sold": float(cogs),
                "estimated_gross_profit": float(gross_profit),
                "operating_expenses": float(expenses),
                "estimated_net_profit": float(net_profit),
            }

    def get_7_day_sales_trend(self, days: int = 7) -> List[Dict[str, Any]]:
        """Computes daily revenue trends for the last N days."""
        today = date.today()
        results = []
        with self.db.session() as session:
            for i in range(days - 1, -1, -1):
                cur_date = today - timedelta(days=i)
                start_dt = datetime(cur_date.year, cur_date.month, cur_date.day, 0, 0, 0, tzinfo=timezone.utc)
                end_dt = datetime(cur_date.year, cur_date.month, cur_date.day, 23, 59, 59, tzinfo=timezone.utc)

                rev = (
                    session.query(func.coalesce(func.sum(Sale.grand_total), Decimal("0.00")))
                    .filter(Sale.sale_date >= start_dt, Sale.sale_date <= end_dt, Sale.is_cancelled == False)  # noqa: E712
                    .scalar()
                )
                results.append({
                    "date": cur_date.strftime("%d-%b"),
                    "revenue": float(rev),
                })
        return results

    def get_category_sales_breakdown(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Aggregates revenue grouped by product category."""
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)

        with self.db.session() as session:
            rows = (
                session.query(
                    func.coalesce(Category.name, "Uncategorized").label("category_name"),
                    func.sum(SaleItem.line_total).label("total_rev"),
                )
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Product, SaleItem.product_id == Product.id)
                .outerjoin(Category, Product.category_id == Category.id)
                .filter(Sale.sale_date >= start_dt, Sale.sale_date <= end_dt, Sale.is_cancelled == False)  # noqa: E712
                .group_by(Category.name)
                .order_by(func.sum(SaleItem.line_total).desc())
                .all()
            )
            return [{"category": r[0], "revenue": float(r[1])} for r in rows]

    # ---------------- Excel Export Engine ----------------

    def export_report_to_excel(
        self,
        headers: List[str],
        data_rows: List[List[Any]],
        sheet_title: str,
        output_file_path: str,
    ) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_title[:30]  # Excel max sheet title is 31 chars

        ws.append(headers)
        for row in data_rows:
            ws.append(row)

        wb.save(output_file_path)
        logger.info(f"Report exported to Excel: {output_file_path}")
