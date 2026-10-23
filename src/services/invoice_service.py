"""
Invoice and Receipt Generation Service using ReportLab.
Renders professional 58mm Thermal, 80mm Thermal, and standard A4 GST Invoices to PDF.
"""

import os
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm


def number_to_words_inr(amount: float) -> str:
    """Converts a monetary figure to Indian English Words (Rupees and Paise)."""
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
             "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def _convert_below_thousand(n: int) -> str:
        res = ""
        if n >= 100:
            res += units[n // 100] + " Hundred "
            n %= 100
        if n >= 20:
            res += tens[n // 10] + " "
            n %= 10
        if n > 0:
            res += units[n] + " "
        return res.strip()

    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))

    if rupees == 0:
        words = "Zero Rupees"
    else:
        crores = rupees // 10000000
        rupees %= 10000000
        lakhs = rupees // 100000
        rupees %= 100000
        thousands = rupees // 1000
        rupees %= 1000
        rem = rupees

        parts = []
        if crores > 0:
            parts.append(f"{_convert_below_thousand(crores)} Crore")
        if lakhs > 0:
            parts.append(f"{_convert_below_thousand(lakhs)} Lakh")
        if thousands > 0:
            parts.append(f"{_convert_below_thousand(thousands)} Thousand")
        if rem > 0:
            parts.append(_convert_below_thousand(rem))
        words = " ".join(parts).strip() + " Rupees"

    if paise > 0:
        words += f" and {_convert_below_thousand(paise)} Paise"
    return words + " Only"


class InvoicePrintService:
    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path.home() / ".aj_billing_software" / "invoices"
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_pdf(
        self,
        invoice_data: Dict[str, Any],
        shop_info: Dict[str, Any],
        format_type: str = "80mm",  # "58mm", "80mm", "A4"
    ) -> Path:
        """
        Generates a PDF document for the given invoice in the specified receipt format.
        Returns the absolute Path of the created PDF.
        """
        inv_num = invoice_data["invoice_number"].replace("/", "_").replace("\\", "_")
        file_name = f"{inv_num}_{format_type}.pdf"
        file_path = self.output_dir / file_name

        if format_type == "58mm":
            return self._build_thermal_pdf(file_path, invoice_data, shop_info, width_mm=58)
        elif format_type == "80mm":
            return self._build_thermal_pdf(file_path, invoice_data, shop_info, width_mm=80)
        else:
            return self._build_a4_pdf(file_path, invoice_data, shop_info)

    def _build_thermal_pdf(
        self,
        file_path: Path,
        inv: Dict[str, Any],
        shop: Dict[str, Any],
        width_mm: float,
    ) -> Path:
        """Builds compact thermal roll receipt (58mm or 80mm)."""
        width = width_mm * mm
        # Dynamic height estimated based on line items
        num_items = len(inv["items"])
        height = max(160 * mm, (120 + (num_items * 10)) * mm)

        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=(width, height),
            leftMargin=2 * mm,
            rightMargin=2 * mm,
            topMargin=4 * mm,
            bottomMargin=4 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("TTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, alignment=1, leading=13)
        center_style = ParagraphStyle("TCenter", parent=styles["Normal"], fontName="Helvetica", fontSize=8, alignment=1, leading=10)
        bold_left = ParagraphStyle("TBoldL", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10)
        norm_left = ParagraphStyle("TNormL", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=9)
        norm_right = ParagraphStyle("TNormR", parent=styles["Normal"], fontName="Helvetica", fontSize=7, alignment=2, leading=9)

        story = []

        # Header
        story.append(Paragraph(shop.get("name", "RETAIL SHOP"), title_style))
        if shop.get("address_line1"):
            story.append(Paragraph(shop["address_line1"], center_style))
        if shop.get("gstin"):
            story.append(Paragraph(f"GSTIN: {shop['gstin']}", center_style))
        if shop.get("phone"):
            story.append(Paragraph(f"Ph: {shop['phone']}", center_style))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceBefore=3, spaceAfter=3))

        # Invoice Metadata
        story.append(Paragraph(f"Invoice: {inv['invoice_number']}", bold_left))
        story.append(Paragraph(f"Date: {inv['sale_date']}", norm_left))
        story.append(Paragraph(f"Cust: {inv.get('customer_name', 'Walk-in')}", norm_left))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceBefore=2, spaceAfter=2))

        # Items Table
        item_data = [["Item", "Qty", "Rate", "Total"]]
        col_widths = [width * 0.45, width * 0.16, width * 0.18, width * 0.21]

        for itm in inv["items"]:
            item_data.append([
                Paragraph(itm["name"], norm_left),
                f"{itm['quantity']:.2f}",
                f"{itm['unit_price']:.2f}",
                f"{itm['line_total']:.2f}",
            ])

        t = Table(item_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
        ]))
        story.append(t)

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceBefore=2, spaceAfter=2))

        # Totals
        tot_data = [
            ["Taxable:", f"₹{inv['taxable_amount']:.2f}"],
            ["CGST:", f"₹{inv['cgst_amount']:.2f}"],
            ["SGST:", f"₹{inv['sgst_amount']:.2f}"],
        ]
        if inv.get("igst_amount", 0) > 0:
            tot_data.append(["IGST:", f"₹{inv['igst_amount']:.2f}"])
        if inv.get("round_off_amount", 0) != 0:
            tot_data.append(["Round Off:", f"₹{inv['round_off_amount']:.2f}"])
        tot_data.append(["GRAND TOTAL:", f"₹{inv['grand_total']:.2f}"])

        t_tot = Table(tot_data, colWidths=[width * 0.55, width * 0.45])
        t_tot.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -2), 7),
            ("FONTSIZE", (0, -1), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        story.append(t_tot)

        # Prominent Payment Mode Block
        payments = inv.get("payments", [])
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceBefore=2, spaceAfter=2))

        pay_data = []
        if payments:
            if len(payments) == 1:
                p = payments[0]
                m = p['method'].upper()
                method_display = "UPI (GPay/Paytm)" if m == "UPI" else m
                ref_txt = f" [{p['reference']}]" if p.get('reference') else ""
                pay_data.append(["PAYMENT MODE:", f"{method_display}{ref_txt}"])
                pay_data.append(["AMOUNT PAID:", f"₹{p['amount']:.2f}"])
                pay_data.append(["PAYMENT STATUS:", "PAID"])
            else:
                pay_data.append(["PAYMENT MODE:", "SPLIT PAYMENT"])
                for p in payments:
                    m = p['method'].upper()
                    method_display = "UPI" if m == "UPI" else m
                    pay_data.append([f"  • {method_display}:", f"₹{p['amount']:.2f}"])
                pay_data.append(["PAYMENT STATUS:", "PAID"])
        else:
            pay_data.append(["PAYMENT MODE:", "CASH"])
            pay_data.append(["PAYMENT STATUS:", "PAID"])

        t_pay = Table(pay_data, colWidths=[width * 0.45, width * 0.55])
        t_pay.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        story.append(t_pay)

        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(shop.get("invoice_footer_text", "Thank you! Visit Again!"), center_style))

        doc.build(story)
        return file_path

    def _build_a4_pdf(
        self,
        file_path: Path,
        inv: Dict[str, Any],
        shop: Dict[str, Any],
    ) -> Path:
        """Builds standard Indian A4 GST Tax Invoice."""
        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )

        styles = getSampleStyleSheet()
        header_title = ParagraphStyle("A4Title", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16, alignment=1, leading=18, textColor=colors.HexColor("#1A365D"))
        sub_title = ParagraphStyle("A4Sub", parent=styles["Normal"], fontName="Helvetica", fontSize=9, alignment=1, leading=12)
        tax_inv_badge = ParagraphStyle("Badge", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, alignment=1, leading=14, textColor=colors.HexColor("#2B6CB0"))
        bold_label = ParagraphStyle("BLabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=11)
        val_label = ParagraphStyle("VLabel", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=11)

        story = []

        # Store Title & Tax Invoice Heading
        story.append(Paragraph(shop.get("name", "RETAIL STORE").upper(), header_title))
        addr = f"{shop.get('address_line1', '')}, {shop.get('city', '')} - {shop.get('pincode', '')}"
        story.append(Paragraph(addr, sub_title))
        gst_phone = f"GSTIN: <b>{shop.get('gstin', 'N/A')}</b> | State: {shop.get('state_name', 'Tamil Nadu')} (Code: {shop.get('state_code', '33')}) | Ph: {shop.get('phone', '-')}"
        story.append(Paragraph(gst_phone, sub_title))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("TAX INVOICE", tax_inv_badge))
        story.append(Spacer(1, 3 * mm))

        # Invoice & Customer Details 2-Column Table
        meta_data = [
            [
                Paragraph(f"<b>Invoice No:</b> {inv['invoice_number']}", val_label),
                Paragraph(f"<b>Bill To:</b> {inv.get('customer_name', 'Walk-in Customer')}", val_label),
            ],
            [
                Paragraph(f"<b>Invoice Date:</b> {inv['sale_date']}", val_label),
                Paragraph(f"<b>Phone:</b> {inv.get('customer_phone') or 'N/A'}", val_label),
            ],
            [
                Paragraph(f"<b>Place of Supply:</b> {shop.get('state_name')} ({shop.get('state_code')})", val_label),
                Paragraph(f"<b>Customer GSTIN:</b> {inv.get('customer_gstin') or 'Unregistered'}", val_label),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[90 * mm, 95 * mm])
        meta_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 4 * mm))

        # Items Table
        headers = ["#", "Item Description", "HSN/SAC", "Qty", "Unit", "Rate (₹)", "Taxable (₹)", "GST %", "Total (₹)"]
        items_table_data = [headers]

        for idx, itm in enumerate(inv["items"], start=1):
            items_table_data.append([
                str(idx),
                Paragraph(itm["name"], val_label),
                itm["hsn"],
                f"{itm['quantity']:.2f}",
                itm["unit"],
                f"{itm['unit_price']:.2f}",
                f"{itm['taxable_value']:.2f}",
                f"{itm['gst_rate']:.1f}%",
                f"{itm['line_total']:.2f}",
            ])

        col_w = [8 * mm, 54 * mm, 18 * mm, 16 * mm, 14 * mm, 20 * mm, 23 * mm, 14 * mm, 21 * mm]
        items_table = Table(items_table_data, colWidths=col_w)
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 3 * mm))

        # GST Breakdown & Grand Total Table
        tax_rows = [
            ["Taxable Amount:", f"₹ {inv['taxable_amount']:.2f}"],
            ["CGST:", f"₹ {inv['cgst_amount']:.2f}"],
            ["SGST:", f"₹ {inv['sgst_amount']:.2f}"],
        ]
        if inv.get("igst_amount", 0) > 0:
            tax_rows.append(["IGST:", f"₹ {inv['igst_amount']:.2f}"])
        if inv.get("round_off_amount", 0) != 0:
            tax_rows.append(["Round Off:", f"₹ {inv['round_off_amount']:.2f}"])
        tax_rows.append(["Invoice Grand Total:", f"₹ {inv['grand_total']:.2f}"])

        tax_table = Table(tax_rows, colWidths=[50 * mm, 35 * mm])
        tax_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTSIZE", (0, -1), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        # Amount in Words & Payment Mode Layout
        payments = inv.get("payments", [])
        if payments:
            if len(payments) == 1:
                p = payments[0]
                m_name = "UPI (GPay / PhonePe / Paytm)" if p['method'] == "UPI" else p['method']
                ref_str = f" | Ref/UTR: {p['reference']}" if p.get('reference') else ""
                pay_summary = f"<b>Payment Mode:</b> <font color='#059669'><b>{m_name}</b></font> (₹ {p['amount']:.2f}){ref_str}"
            else:
                splits = ", ".join([f"{p['method']}: ₹{p['amount']:.2f}" for p in payments])
                pay_summary = f"<b>Payment Mode:</b> <font color='#059669'><b>SPLIT</b></font> ({splits})"
        else:
            pay_summary = "<b>Payment Mode:</b> <font color='#059669'><b>CASH</b></font>"

        words_content = f"<b>Amount in Words:</b><br/>{number_to_words_inr(inv['grand_total'])}<br/><br/>{pay_summary}"
        words_paragraph = Paragraph(words_content, val_label)
        bottom_composite = Table([[words_paragraph, tax_table]], colWidths=[103 * mm, 85 * mm])
        bottom_composite.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(bottom_composite)

        story.append(Spacer(1, 8 * mm))
        sign_table = Table([
            [Paragraph("Customer Signature", val_label), Paragraph(f"For {shop.get('name', 'Store')}<br/><br/>Authorised Signatory", ParagraphStyle("SignR", parent=val_label, alignment=2))]
        ], colWidths=[94 * mm, 94 * mm])
        story.append(sign_table)

        doc.build(story)
        return file_path
