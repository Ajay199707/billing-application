"""
Indian GST Tax Calculation Engine.
Calculates CGST, SGST, IGST, and cess with strict Decimal precision,
supporting intra-state and inter-state place-of-supply rules,
tax-inclusive and tax-exclusive pricing, and statutory rounding.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any


TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")


def round_currency(val: Decimal) -> Decimal:
    """Rounds decimal to standard 2-place currency."""
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class LineTaxBreakdown:
    product_id: int
    product_name: str
    hsn_sac_code: str
    unit_code: str
    quantity: Decimal
    unit_price: Decimal
    line_discount: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    is_interstate: bool
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    igst_rate: Decimal
    igst_amount: Decimal
    cess_rate: Decimal
    cess_amount: Decimal
    line_total: Decimal


@dataclass
class InvoiceTaxSummary:
    subtotal_gross: Decimal
    item_discounts_total: Decimal
    invoice_discount: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    round_off_amount: Decimal
    grand_total: Decimal
    items: List[LineTaxBreakdown]


class TaxEngine:
    @staticmethod
    def calculate_line_item(
        product_id: int,
        product_name: str,
        hsn_sac_code: str,
        unit_code: str,
        quantity: Decimal,
        unit_price: Decimal,
        gst_rate: Decimal,
        seller_state_code: str,
        buyer_state_code: Optional[str] = None,
        line_discount: Decimal = Decimal("0.00"),
        is_tax_inclusive: bool = False,
        cess_rate: Decimal = Decimal("0.00"),
    ) -> LineTaxBreakdown:
        """
        Computes statutory GST line taxes for a single cart item.
        """
        if quantity <= Decimal("0"):
            raise ValueError("Quantity must be positive.")
        if unit_price < Decimal("0"):
            raise ValueError("Unit price cannot be negative.")

        # Determine place of supply
        # If buyer_state_code is given and differs from seller, it is Inter-State (IGST)
        is_interstate = bool(buyer_state_code and buyer_state_code.strip() and buyer_state_code.strip() != seller_state_code.strip())

        gross_nominal = (quantity * unit_price) - line_discount
        if gross_nominal < Decimal("0"):
            gross_nominal = Decimal("0.00")

        if is_tax_inclusive:
            # Inclusive formula: Taxable = Gross / (1 + GST_Rate / 100)
            denominator = Decimal("1") + (gst_rate / Decimal("100"))
            taxable_val = round_currency(gross_nominal / denominator)
            total_tax = round_currency(gross_nominal - taxable_val)
            line_total = gross_nominal
        else:
            # Exclusive formula: Taxable = Gross, Tax = Taxable * Rate / 100
            taxable_val = round_currency(gross_nominal)
            total_tax = round_currency(taxable_val * (gst_rate / Decimal("100")))
            line_total = taxable_val + total_tax

        # Calculate Cess if applicable
        cess_amount = round_currency(taxable_val * (cess_rate / Decimal("100"))) if cess_rate > 0 else Decimal("0.00")
        line_total += cess_amount

        if is_interstate:
            cgst_rate = Decimal("0.00")
            cgst_amount = Decimal("0.00")
            sgst_rate = Decimal("0.00")
            sgst_amount = Decimal("0.00")
            igst_rate = gst_rate
            igst_amount = total_tax
        else:
            # Intra-state: Split equally between CGST and SGST
            cgst_rate = gst_rate / Decimal("2")
            sgst_rate = gst_rate / Decimal("2")
            cgst_amount = round_currency(total_tax / Decimal("2"))
            sgst_amount = total_tax - cgst_amount  # Avoid 1-paise split rounding discrepancy
            igst_rate = Decimal("0.00")
            igst_amount = Decimal("0.00")

        return LineTaxBreakdown(
            product_id=product_id,
            product_name=product_name,
            hsn_sac_code=hsn_sac_code,
            unit_code=unit_code,
            quantity=quantity,
            unit_price=unit_price,
            line_discount=line_discount,
            taxable_value=taxable_val,
            gst_rate=gst_rate,
            is_interstate=is_interstate,
            cgst_rate=cgst_rate,
            cgst_amount=cgst_amount,
            sgst_rate=sgst_rate,
            sgst_amount=sgst_amount,
            igst_rate=igst_rate,
            igst_amount=igst_amount,
            cess_rate=cess_rate,
            cess_amount=cess_amount,
            line_total=line_total,
        )

    @classmethod
    def calculate_invoice_summary(
        cls,
        line_breakdowns: List[LineTaxBreakdown],
        invoice_discount: Decimal = Decimal("0.00"),
    ) -> InvoiceTaxSummary:
        """Aggregates all lines, applies invoice discount, and calculates final rounded payable total."""
        subtotal_gross = Decimal("0.00")
        item_discounts_total = Decimal("0.00")
        taxable_amount = Decimal("0.00")
        cgst_total = Decimal("0.00")
        sgst_total = Decimal("0.00")
        igst_total = Decimal("0.00")
        cess_total = Decimal("0.00")

        for line in line_breakdowns:
            subtotal_gross += (line.quantity * line.unit_price)
            item_discounts_total += line.line_discount
            taxable_amount += line.taxable_value
            cgst_total += line.cgst_amount
            sgst_total += line.sgst_amount
            igst_total += line.igst_amount
            cess_total += line.cess_amount

        # Calculate exact pre-round total
        pre_round_total = taxable_amount + cgst_total + sgst_total + igst_total + cess_total - invoice_discount

        # Statutory Indian Rupee Half-Up Rounding (Round to nearest integer)
        rounded_total = pre_round_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        round_off = rounded_total - pre_round_total

        return InvoiceTaxSummary(
            subtotal_gross=round_currency(subtotal_gross),
            item_discounts_total=round_currency(item_discounts_total),
            invoice_discount=round_currency(invoice_discount),
            taxable_amount=round_currency(taxable_amount),
            cgst_amount=round_currency(cgst_total),
            sgst_amount=round_currency(sgst_total),
            igst_amount=round_currency(igst_total),
            cess_amount=round_currency(cess_total),
            round_off_amount=round_currency(round_off),
            grand_total=round_currency(rounded_total),
            items=line_breakdowns,
        )
