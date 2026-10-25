"""
Application business service layer.
"""

from src.services.auth_service import AuthService, UserSession
from src.services.backup_service import BackupService
from src.services.barcode_service import BarcodeService
from src.services.billing_service import BillingService
from src.services.db_init_service import initialize_database, setup_initial_shop_and_admin
from src.services.inventory_service import InventoryService
from src.services.invoice_service import InvoicePrintService
from src.services.price_service import PriceService
from src.services.product_service import ProductService
from src.services.purchase_service import PurchaseService
from src.services.reporting_service import ReportingService
from src.services.settings_service import SettingsService
from src.services.tax_service import TaxEngine, round_currency
from src.services.master_catalog_service import lookup_barcode, seed_starter_catalog
from src.services.cloud_sync_service import (
    fetch_cloud_catalog,
    sync_catalog_from_cloud,
    CloudSyncError,
    DEFAULT_CLOUD_CATALOG_URL,
)

# Alias for backwards compatibility
TaxService = TaxEngine

__all__ = [
    "AuthService",
    "UserSession",
    "BackupService",
    "BarcodeService",
    "BillingService",
    "initialize_database",
    "setup_initial_shop_and_admin",
    "InventoryService",
    "InvoicePrintService",
    "PriceService",
    "ProductService",
    "PurchaseService",
    "ReportingService",
    "SettingsService",
    "TaxEngine",
    "TaxService",
    "round_currency",
    "lookup_barcode",
    "seed_starter_catalog",
    "fetch_cloud_catalog",
    "sync_catalog_from_cloud",
    "CloudSyncError",
    "DEFAULT_CLOUD_CATALOG_URL",
]
