"""
UI dialog windows and modal wizards.
"""

from src.ui.dialogs.bulk_price_update_dialog import BulkPriceUpdateDialog
from src.ui.dialogs.bulk_product_entry_dialog import BulkProductEntryDialog
from src.ui.dialogs.category_brand_manager_dialog import CategoryBrandManagerDialog
from src.ui.dialogs.invoice_preview_dialog import InvoicePreviewDialog
from src.ui.dialogs.login_dialog import LoginDialog
from src.ui.dialogs.onboarding_dialog import OnboardingDialog
from src.ui.dialogs.payment_dialog import PaymentDialog
from src.ui.dialogs.price_history_dialog import PriceHistoryDialog
from src.ui.dialogs.product_dialog import ProductDialog
from src.ui.dialogs.recall_bill_dialog import RecallParkedBillDialog
from src.ui.dialogs.sales_return_dialog import SalesReturnDialog

# Backwards compatibility alias
RecallBillDialog = RecallParkedBillDialog

__all__ = [
    "BulkPriceUpdateDialog",
    "BulkProductEntryDialog",
    "CategoryBrandManagerDialog",
    "InvoicePreviewDialog",
    "LoginDialog",
    "OnboardingDialog",
    "PaymentDialog",
    "PriceHistoryDialog",
    "ProductDialog",
    "RecallParkedBillDialog",
    "RecallBillDialog",
    "SalesReturnDialog",
]
