"""
Barcode Generation and Printable Label Sheet Service.
Generates EAN-13, CODE128, and CODE39 barcodes using python-barcode and Pillow.
Supports generating single barcode images and multi-label printable PDF sheets.
"""

import io
import logging
from typing import Optional, List, Dict, Any
import barcode
from barcode.writer import ImageWriter
from PIL import Image

logger = logging.getLogger(__name__)


class BarcodeService:
    @staticmethod
    def generate_barcode_image_bytes(code_value: str, code_type: str = "code128") -> bytes:
        """
        Generates barcode as PNG image bytes.
        Supports 'code128', 'ean13', 'code39'.
        """
        clean_code = code_value.strip()
        writer = ImageWriter()
        writer.font_size = 8
        writer.text_distance = 3

        # EAN13 requires exactly 12 or 13 digits
        target_type = code_type.lower()
        if target_type == "ean13" and (len(clean_code) not in (12, 13) or not clean_code.isdigit()):
            # Fallback to code128 for non-standard numbers/alphanumeric
            target_type = "code128"

        try:
            barcode_class = barcode.get_barcode_class(target_type)
            # For 12 digits, EAN13 will compute check digit automatically
            bc = barcode_class(clean_code[:12] if target_type == "ean13" and len(clean_code) >= 12 else clean_code, writer=writer)
            buf = io.BytesIO()
            bc.write(buf)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to generate {target_type} barcode for '{code_value}', fallback to code128: {e}")
            bc_fallback = barcode.get_barcode_class("code128")(clean_code, writer=writer)
            buf = io.BytesIO()
            bc_fallback.write(buf)
            buf.seek(0)
            return buf.getvalue()

    @staticmethod
    def format_sticker_label_sheet_pdf(
        products: List[Dict[str, Any]],
        shop_name: str = "Supermarket",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generates a 3x8 or 4x10 grid of product barcode price stickers in standard A4 PDF format.
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        path = output_path or "barcode_labels.pdf"
        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
        elements = []
        styles = getSampleStyleSheet()

        label_style = ParagraphStyle(
            "BarcodeLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            alignment=1,  # Center
            leading=8,
        )

        sub_style = ParagraphStyle(
            "BarcodeSub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=6,
            alignment=1,
            leading=7,
        )

        cells = []
        current_row = []

        for p in products:
            bc_code = p.get("barcode") or p.get("sku") or "0000"
            bc_bytes = BarcodeService.generate_barcode_image_bytes(bc_code, "code128")
            img_buf = io.BytesIO(bc_bytes)
            rl_img = RLImage(img_buf, width=120, height=40)

            name = p.get("name", "Product")[:28]
            price = p.get("selling_price", 0.0)

            cell_content = [
                Paragraph(f"<b>{shop_name[:24]}</b>", label_style),
                Paragraph(name, sub_style),
                rl_img,
                Paragraph(f"<b>MRP: ₹ {price:.2f}</b> (Incl. GST)", label_style),
            ]
            current_row.append(cell_content)

            if len(current_row) == 3:  # 3 columns per row on A4
                cells.append(current_row)
                current_row = []

        if current_row:
            while len(current_row) < 3:
                current_row.append([])
            cells.append(current_row)

        if not cells:
            cells = [[Paragraph("No products provided for barcode printing", styles["Normal"])]]

        table = Table(cells, colWidths=[180, 180, 180])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(table)
        doc.build(elements)
        logger.info(f"Barcode sticker label sheet generated at: {path}")
        return path
