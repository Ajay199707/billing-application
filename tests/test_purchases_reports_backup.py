"""
Unit and integration tests for Purchases, Reports, and Backup/Restore workflows.
"""

from datetime import date
from decimal import Decimal
import pytest

from src.core.config import DatabaseConfig, DatabaseMode
from src.core.database import DatabaseManager
from src.models import Base, Product, InventoryBalance
from src.services.auth_service import UserSession
from src.services.db_init_service import initialize_database, setup_initial_shop_and_admin
from src.services.product_service import ProductService
from src.services.inventory_service import InventoryService
from src.services.purchase_service import PurchaseService, PurchaseItemInput
from src.services.reporting_service import ReportingService
from src.services.backup_service import BackupService


@pytest.fixture
def admin_session():
    return UserSession(
        user_id=1,
        username="admin",
        full_name="Admin",
        is_admin=True,
        permissions={"all"},
        token="tok",
    )


def test_purchase_procurement_workflow(db_manager, test_shop_and_admin, admin_session):
    prod_service = ProductService(db_manager)
    inv_service = InventoryService(db_manager)
    purchase_service = PurchaseService(db_manager, inv_service)

    # 1. Create Product
    prod_id = prod_service.create_product(
        current_session=admin_session,
        name="LED Tube Light 20W",
        sku="LED-TUBE-20W",
        unit_id=1,
        tax_profile_id=4,  # 18%
        selling_price=Decimal("350.00"),
        purchase_cost=Decimal("200.00"),
        initial_stock=Decimal("5.000"),
    )

    # 2. Create Supplier
    sup_id = purchase_service.create_supplier(
        current_session=admin_session,
        name="Philips Electrical Distributors",
        gstin="33ABCDE9999F1Z1",
    )

    # 3. Record Purchase of 20 units @ ₹180
    items = [
        PurchaseItemInput(
            product_id=prod_id,
            quantity=Decimal("20.000"),
            unit_cost=Decimal("180.00"),
            gst_rate=Decimal("18.00"),
        )
    ]

    po_num = purchase_service.record_purchase(
        current_session=admin_session,
        supplier_id=sup_id,
        supplier_invoice_no="SUP-INV-8821",
        items=items,
    )

    assert po_num.startswith("PO-")

    # 4. Verify inventory increased from 5 to 25
    balance, total_mv, is_match = inv_service.reconcile_product_stock(prod_id)
    assert balance == Decimal("25.000")


def test_reporting_valuation_and_kpis(db_manager, test_shop_and_admin, admin_session):
    prod_service = ProductService(db_manager)
    reporting_service = ReportingService(db_manager)

    prod_service.create_product(
        current_session=admin_session,
        name="Cotton Shirt",
        sku="SHIRT-COT-01",
        unit_id=1,
        tax_profile_id=3,
        selling_price=Decimal("800.00"),
        purchase_cost=Decimal("400.00"),
        initial_stock=Decimal("10.000"),
    )

    valuation = reporting_service.get_inventory_valuation()
    assert valuation["total_items"] >= 1
    assert valuation["total_quantity"] >= 10.0
    assert valuation["total_cost_value"] >= 4000.0
    assert valuation["total_retail_value"] >= 8000.0

    kpi = reporting_service.get_dashboard_summary()
    assert "today_revenue" in kpi
    assert "low_stock_count" in kpi


def test_backup_and_verification(tmp_path, admin_session):
    # Setup on-disk SQLite DB for hot backup testing
    db_file = tmp_path / "live_shop.db"
    backup_folder = tmp_path / "backups"

    cfg = DatabaseConfig(mode=DatabaseMode.SINGLE_SQLITE, sqlite_file=str(db_file))
    mgr = DatabaseManager(cfg)
    mgr.initialize()
    mgr.create_all_tables(Base)
    initialize_database(mgr, create_tables=False)

    setup_initial_shop_and_admin(
        db_manager=mgr,
        shop_name="Backup Test Shop",
        legal_name="Backup Test Shop Pvt Ltd",
        gstin="33ABCDE1234F1Z5",
        state_code="33",
        state_name="Tamil Nadu",
        admin_username="admin",
        admin_password="Password123!",
        admin_full_name="Admin",
    )

    backup_service = BackupService(mgr, backup_dir=backup_folder)

    # 1. Create Backup
    backup_result = backup_service.create_backup(admin_session, backup_type="MANUAL")
    assert backup_result["status"] == "SUCCESS"
    assert backup_result["file_size"] > 0

    # 2. Verify Backup
    is_valid, msg = backup_service.verify_backup(backup_result["file_path"])
    assert is_valid is True
    assert "ok" in msg

    # 3. List Backups
    backups = backup_service.list_backups()
    assert len(backups) == 1

    # 4. Test Restore
    restore_ok = backup_service.restore_backup(admin_session, backup_result["file_path"])
    assert restore_ok is True

    mgr.close()
