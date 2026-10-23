"""
Database initialization and seeding service.
Sets up base schema, standard system roles, permissions,
units of measure, GST tax profiles, and default shop configuration.
"""

import logging
from decimal import Decimal
from sqlalchemy.orm import Session

from src.core.database import DatabaseManager
from src.core.security import hash_password
from src.models import (
    Base,
    Shop,
    ShopSettings,
    User,
    Role,
    Permission,
    UnitOfMeasure,
    ProductTaxProfile,
    ExpenseCategory,
    InvoiceSequence,
)

logger = logging.getLogger(__name__)

SYSTEM_PERMISSIONS = [
    # POS & Billing
    ("pos:checkout", "Complete sales and process payments", "POS"),
    ("pos:reprint", "Reprint past receipts and invoices", "POS"),
    ("pos:refund", "Process sales returns and refunds", "POS"),
    ("pos:discount", "Apply line-level or invoice discounts", "POS"),
    # Inventory
    ("inventory:view", "View stock balances and batch status", "Inventory"),
    ("inventory:adjust", "Perform stock corrections and damage write-offs", "Inventory"),
    ("inventory:manage", "Full control over inventory opening balances and locations", "Inventory"),
    # Catalog
    ("products:view", "Browse and search product catalogue", "Products"),
    ("products:manage", "Add, update, deactivate products, variants, and barcodes", "Products"),
    ("products:import_export", "Bulk import/export products via Excel/CSV", "Products"),
    # Purchasing
    ("purchases:view", "View supplier purchases and bills", "Purchases"),
    ("purchases:manage", "Record goods receipts, purchases, and supplier returns", "Purchases"),
    ("suppliers:manage", "Add and edit supplier records", "Purchases"),
    # Customers
    ("customers:view", "View customer directories and purchase history", "Customers"),
    ("customers:manage", "Add and update customer profiles", "Customers"),
    # Reports
    ("reports:view", "Access financial, sales, and inventory analytics", "Reports"),
    ("reports:export", "Export analytics data to Excel and CSV", "Reports"),
    # System Administration
    ("users:manage", "Add, edit, and deactivate user accounts and passwords", "Administration"),
    ("settings:manage", "Configure shop profile, GSTIN, receipt formats, and hardware", "Administration"),
    ("backup:manage", "Generate hot backups and restore databases", "Administration"),
    ("audit:view", "Inspect security audit logs", "Administration"),
]


STANDARD_UOMS = [
    ("PCS", "Pieces", 0, False),
    ("KG", "Kilograms", 3, True),
    ("G", "Grams", 1, True),
    ("L", "Litres", 3, True),
    ("ML", "Millilitres", 1, True),
    ("BOX", "Box", 0, False),
    ("PACK", "Packet", 0, False),
    ("MTR", "Meters", 2, True),
    ("STRIP", "Strip", 0, False),
    ("PAIR", "Pair", 0, False),
    ("SET", "Set", 0, False),
]

STANDARD_GST_PROFILES = [
    ("GST 0% (Exempt / Grains / Milk)", "0000", Decimal("0.00"), Decimal("0.00")),
    ("GST 5% (Essential Food / Staples)", "1001", Decimal("5.00"), Decimal("0.00")),
    ("GST 12% (Processed Goods / Apparel)", "2001", Decimal("12.00"), Decimal("0.00")),
    ("GST 18% (Standard Retail / General)", "8471", Decimal("18.00"), Decimal("0.00")),
    ("GST 28% (Luxury / High-End Electronics)", "8528", Decimal("28.00"), Decimal("0.00")),
]

STANDARD_EXPENSE_CATEGORIES = [
    ("Shop Rent", "Monthly commercial property rental"),
    ("Electricity & Utilities", "Power, water, and shop utilities"),
    ("Staff Salaries", "Employee wages and daily allowance"),
    ("Packaging & Carry Bags", "Billing bags, packaging materials, boxes"),
    ("Freight & Transportation", "Inward stock transport and delivery fees"),
    ("Office & Cleaning Supplies", "Consumables, cleaning items, thermal paper rolls"),
    ("Repairs & Maintenance", "Store fixtures and equipment servicing"),
    ("Miscellaneous", "Other general operational expenses"),
]


def initialize_database(db_manager: DatabaseManager, create_tables: bool = True) -> None:
    """
    Creates tables if required, upgrades schema columns, and seeds default system data
    (Permissions, Roles, UOMs, Tax Profiles, Expense Categories).
    """
    if create_tables:
        db_manager.create_all_tables(Base)
        _upgrade_schema(db_manager.engine)

    with db_manager.session() as session:
        _seed_permissions(session)
        _seed_roles(session)
        _seed_uoms(session)
        _seed_tax_profiles(session)
        _seed_expense_categories(session)
        _ensure_default_cashier(session)

    logger.info("Database initialized and base catalogs seeded.")


def _upgrade_schema(engine) -> None:
    """
    Performs non-destructive schema migrations on startup.
    Adds any newly introduced columns to existing tables if missing.
    """
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        # 1. products table columns
        if "products" in table_names:
            prod_cols = {c["name"] for c in inspector.get_columns("products")}
            with engine.connect() as conn:
                if "promotional_price" not in prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN promotional_price NUMERIC(12, 2)"))
                    logger.info("Migrated schema: added 'promotional_price' to 'products'")
                if "min_selling_price" not in prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN min_selling_price NUMERIC(12, 2)"))
                    logger.info("Migrated schema: added 'min_selling_price' to 'products'")
                if "package_size" not in prod_cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN package_size VARCHAR(50)"))
                    logger.info("Migrated schema: added 'package_size' to 'products'")
                conn.commit()

        # 2. product_variants table columns
        if "product_variants" in table_names:
            var_cols = {c["name"] for c in inspector.get_columns("product_variants")}
            with engine.connect() as conn:
                if "package_size" not in var_cols:
                    conn.execute(text("ALTER TABLE product_variants ADD COLUMN package_size VARCHAR(50)"))
                    logger.info("Migrated schema: added 'package_size' to 'product_variants'")
                conn.commit()

        # 3. parked_bills table for multi-customer park & resume
        if "parked_bills" not in table_names:
            Base.metadata.tables["parked_bills"].create(engine)
            logger.info("Migrated schema: created table 'parked_bills'")

    except Exception as e:
        logger.warning(f"Schema upgrade check encountered error: {e}")


def _seed_permissions(session: Session) -> None:
    for code, name, category in SYSTEM_PERMISSIONS:
        existing = session.query(Permission).filter_by(code=code).first()
        if not existing:
            perm = Permission(code=code, name=name, category=category)
            session.add(perm)
    session.flush()


def _seed_roles(session: Session) -> None:
    all_perms = session.query(Permission).all()
    perms_by_code = {p.code: p for p in all_perms}

    # 1. Administrator
    admin_role = session.query(Role).filter_by(name="Administrator").first()
    if not admin_role:
        admin_role = Role(name="Administrator", description="Full system access", is_system_role=True)
        admin_role.permissions = all_perms
        session.add(admin_role)

    # 2. Cashier
    cashier_role = session.query(Role).filter_by(name="Cashier").first()
    cashier_perm_codes = [
        "pos:checkout", "pos:reprint", "pos:refund", "pos:discount",
        "products:view", "customers:view", "customers:manage",
    ]
    if not cashier_role:
        cashier_role = Role(name="Cashier", description="POS billing, receipt reprinting, customer lookup", is_system_role=True)
        cashier_role.permissions = [perms_by_code[c] for c in cashier_perm_codes if c in perms_by_code]
        session.add(cashier_role)

    # 3. Inventory Manager
    inv_role = session.query(Role).filter_by(name="Inventory Manager").first()
    inv_perm_codes = [
        "products:view", "products:manage", "products:import_export",
        "inventory:view", "inventory:adjust", "inventory:manage",
        "purchases:view", "purchases:manage", "suppliers:manage",
        "reports:view", "reports:export",
    ]
    if not inv_role:
        inv_role = Role(name="Inventory Manager", description="Product catalog, inventory control, purchase receipts", is_system_role=True)
        inv_role.permissions = [perms_by_code[c] for c in inv_perm_codes if c in perms_by_code]
        session.add(inv_role)

    session.flush()


def _seed_uoms(session: Session) -> None:
    for code, name, precision, is_frac in STANDARD_UOMS:
        existing = session.query(UnitOfMeasure).filter_by(code=code).first()
        if not existing:
            uom = UnitOfMeasure(code=code, name=name, decimal_precision=precision, is_fractional=is_frac)
            session.add(uom)
    session.flush()


def _seed_tax_profiles(session: Session) -> None:
    for name, hsn, rate, cess in STANDARD_GST_PROFILES:
        existing = session.query(ProductTaxProfile).filter_by(name=name).first()
        if not existing:
            profile = ProductTaxProfile(name=name, hsn_sac_code=hsn, gst_rate=rate, cess_rate=cess)
            session.add(profile)
    session.flush()


def _seed_expense_categories(session: Session) -> None:
    for name, desc in STANDARD_EXPENSE_CATEGORIES:
        existing = session.query(ExpenseCategory).filter_by(name=name).first()
        if not existing:
            cat = ExpenseCategory(name=name, description=desc)
            session.add(cat)
    session.flush()


def _ensure_default_cashier(session: Session) -> None:
    shop = session.query(Shop).first()
    if not shop:
        return
    cashier = session.query(User).filter_by(username="cashier").first()
    if not cashier:
        cashier_role = session.query(Role).filter_by(name="Cashier").first()
        cashier = User(
            shop_id=shop.id,
            username="cashier",
            password_hash=hash_password("cashier123"),
            full_name="Counter Cashier 1",
            is_active=True,
            is_admin=False,
        )
        if cashier_role:
            cashier.roles.append(cashier_role)
        session.add(cashier)
        session.flush()
        logger.info("Default cashier account 'cashier' provisioned.")


def setup_initial_shop_and_admin(
    db_manager: DatabaseManager,
    shop_name: str,
    legal_name: str,
    gstin: str,
    state_code: str,
    state_name: str,
    admin_username: str,
    admin_password: str,
    admin_full_name: str,
    business_profile: str = "general",
) -> tuple[Shop, User]:
    """
    Initializes a new shop profile and provisions the root Administrator account.
    """
    initialize_database(db_manager, create_tables=True)

    with db_manager.session() as session:
        shop = session.query(Shop).first()
        if not shop:
            shop = Shop(
                name=shop_name,
                legal_name=legal_name,
                gstin=gstin,
                state_code=state_code,
                state_name=state_name,
                currency_symbol="₹",
            )
            session.add(shop)
            session.flush()

            settings = ShopSettings(
                shop_id=shop.id,
                business_profile=business_profile,
                invoice_prefix="INV-",
                receipt_format="80mm",
                enable_negative_stock=False,
                low_stock_threshold_default=5.0,
                tax_inclusive_default=False,
            )
            session.add(settings)

            # Initialize Invoice Sequence
            seq = InvoiceSequence(
                shop_id=shop.id,
                prefix="INV-",
                financial_year="2026-27",
                current_number=0,
            )
            session.add(seq)

        admin_user = session.query(User).filter_by(username=admin_username).first()
        if not admin_user:
            admin_role = session.query(Role).filter_by(name="Administrator").first()
            admin_user = User(
                shop_id=shop.id,
                username=admin_username,
                password_hash=hash_password(admin_password),
                full_name=admin_full_name,
                is_active=True,
                is_admin=True,
            )
            if admin_role:
                admin_user.roles.append(admin_role)
            session.add(admin_user)

        _ensure_default_cashier(session)

        session.commit()
        # Refresh to load detached values
        session.refresh(shop)
        session.refresh(admin_user)
        logger.info(f"Shop '{shop.name}' and Administrator '{admin_user.username}' provisioned.")
        return shop, admin_user
