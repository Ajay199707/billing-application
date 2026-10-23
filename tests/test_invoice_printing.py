"""
Tests for ReportLab Invoice Generation (58mm, 80mm, and A4 PDF).
"""

from decimal import Decimal
from pathlib import Path
from src.services.invoice_service import InvoicePrintService, number_to_words_inr


def test_number_to_words_inr():
    assert number_to_words_inr(0.0) == "Zero Rupees Only"
    assert number_to_words_inr(500.0) == "Five Hundred Rupees Only"
    assert number_to_words_inr(1250.50) == "One Thousand Two Hundred Fifty Rupees and Fifty Paise Only"
    assert number_to_words_inr(100000.0) == "One Lakh Rupees Only"


def test_generate_invoices(tmp_path):
    print_service = InvoicePrintService(output_dir=tmp_path)

    sample_invoice = {
        "invoice_number": "INV-2026-00042",
        "sale_date": "2026-10-23 11:30:00",
        "customer_name": "Ramesh Kumar",
        "customer_phone": "9876543210",
        "customer_gstin": "33AABCR1234F1Z1",
        "subtotal": 1000.0,
        "item_discount_total": 0.0,
        "invoice_discount_amount": 0.0,
        "taxable_amount": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "igst_amount": 0.0,
        "round_off_amount": 0.0,
        "grand_total": 1180.0,
        "payments": [{"method": "UPI", "amount": 1180.0, "reference": "UPI998877"}],
        "items": [
            {
                "id": 1,
                "name": "Bluetooth Wireless Headphones",
                "hsn": "8518",
                "unit": "PCS",
                "quantity": 1.0,
                "unit_price": 1000.0,
                "line_discount": 0.0,
                "taxable_value": 1000.0,
                "gst_rate": 18.0,
                "cgst_amount": 90.0,
                "sgst_amount": 90.0,
                "igst_amount": 0.0,
                "line_total": 1180.0,
            }
        ],
    }

    sample_shop = {
        "name": "Sri Murugan Super Stores",
        "legal_name": "Sri Murugan Super Stores Pvt Ltd",
        "address_line1": "123 Anna Salai, T Nagar",
        "city": "Chennai",
        "pincode": "600017",
        "state_name": "Tamil Nadu",
        "state_code": "33",
        "gstin": "33AAACS1234F1Z9",
        "phone": "+91 94441 23456",
        "invoice_footer_text": "Goods once sold cannot be taken back without bill.",
    }

    # 1. 58mm Thermal
    p58 = print_service.generate_pdf(sample_invoice, sample_shop, format_type="58mm")
    assert p58.exists()
    assert p58.stat().st_size > 1000

    # 2. 80mm Thermal
    p80 = print_service.generate_pdf(sample_invoice, sample_shop, format_type="80mm")
    assert p80.exists()
    assert p80.stat().st_size > 1000

    # 3. A4 Full GST Invoice
    pa4 = print_service.generate_pdf(sample_invoice, sample_shop, format_type="A4")
    assert pa4.exists()
    assert pa4.stat().st_size > 1000
