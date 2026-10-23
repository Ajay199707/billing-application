# Multi-Purpose Windows Billing, Inventory, GST and Shop Management System

A production-ready, offline-capable Windows desktop application for retail billing, point-of-sale (POS), auditable inventory control, supplier procurement, GST tax calculations, and shop administration.

Designed to operate seamlessly on a **single computer** (with zero-configuration SQLite WAL) or across **multiple computers sharing one shop database** on a local network (powered by PostgreSQL with atomic concurrency controls).

---

## 1. Supported Business Profiles

A single unified codebase dynamically adapts to different retail categories:

1. **Grocery & Supermarkets**: Kilograms, grams, litres, millilitres, packets, pieces, weighted decimal quantities, batch numbers, and expiry tracking.
2. **Electrical & Hardware Shops**: Units, packs, meters, manufacturer brands, model numbers, technical specifications, and optional serial tracking.
3. **Clothing & Textile Shops**: Product variants (Size, Colour, Fit, Fabric, Style) with unique SKU/barcode and variant-level inventory.
4. **Mobile & Electronics Shops**: Serial numbers, dual IMEI tracking, device warranty tracking, and purchase references.
5. **Medical & Pharmacy Shops**: Strict batch numbers, expiry dates, FEFO dispensing, schedule drug alerts, and pack conversions.
6. **General Retail**: Standard products, services, barcode scanning, and multi-category retail inventory.

---

## 2. Technology Stack

- **Desktop Framework**: Python 3.14 + PySide6 (Qt 6.11)
- **Database Engine**: PostgreSQL 15+ (Authoritative for Multi-PC mode) & SQLite WAL (Single-PC mode)
- **ORM & Migrations**: SQLAlchemy 2.0 & Alembic
- **Document Generation**: ReportLab (58mm/80mm Thermal Receipts & A4 GST Tax Invoices)
- **Data Exchange**: OpenPyXL (Excel) & Python standard CSV
- **Security**: Argon2id password hashing & Windows Credential storage
- **Packaging**: PyInstaller & Inno Setup
- **Quality Assurance**: pytest test suite

---

## 3. Architecture & Directory Layout

```
billing_software/
├── alembic/                  # Schema migration scripts
├── src/
│   ├── core/
│   │   ├── config.py         # AppConfig, DatabaseConfig, ProfileConfig
│   │   ├── database.py       # Dialect adapters (PostgreSQL + SQLite WAL)
│   │   ├── security.py       # Argon2id password hashing & tokens
│   │   ├── exceptions.py     # Domain and business exceptions
│   │   └── logging.py        # Structured logging setup
│   ├── models/               # SQLAlchemy 2.0 ORM models (38 entities)
│   ├── services/
│   │   ├── auth_service.py      # Authentication, RBAC, user management
│   │   ├── settings_service.py  # Shop profile & business categories
│   │   ├── product_service.py   # Catalog, barcodes, variants, Excel/CSV
│   │   ├── inventory_service.py # Auditable movement ledger, atomic locks
│   │   ├── tax_service.py       # Indian GST engine (CGST/SGST/IGST)
│   │   ├── billing_service.py   # POS checkout, split payment, sequence locks
│   │   ├── invoice_service.py   # ReportLab PDF thermal & A4 invoices
│   │   ├── purchase_service.py  # Supplier procurement & goods receipt
│   │   ├── reporting_service.py # Analytics, valuations, P&L, exports
│   │   └── backup_service.py    # Hot backups, SHA-256 verify, restoration
│   └── ui/
│       ├── app.py            # Lifecycle bootstrap & onboarding check
│       ├── main_window.py    # Desktop shell & sidebar drawer
│       ├── styles.py         # Modern QSS desktop styling
│       ├── views/            # Dashboard, POS, Products, Inventory, Reports...
│       └── dialogs/          # Login, Onboarding, Payment, Product Dialogs...
├── tests/                    # 17+ comprehensive automated tests
├── main.py                   # Desktop application entry point
├── build_exe.py              # PyInstaller executable builder
├── installer.iss             # Inno Setup Windows installer script
└── requirements.txt          # Python dependencies
```

---

## 4. Single-Computer vs Multi-Computer Operation

### Mode A: Single Computer (Offline Standalone)
- Runs out of the box with zero external dependencies.
- Uses an embedded SQLite database in **WAL mode** (`PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=5000;`, `PRAGMA foreign_keys=ON;`).
- All business records persist locally under `%LOCALAPPDATA%\AntigravityBilling\shop_billing.db`.
- Supports hot online backups using `sqlite3.backup()` without locking or stopping billing.

### Mode B: Multiple Computers in One Shop (Shared Local Network)
1. **Designate One Machine as the Shop Database Server**:
   - Install PostgreSQL 15+ on the designated server computer.
   - Create a database: `CREATE DATABASE billing_db;`
   - In `pg_hba.conf`, allow connections from the shop's local network subnet (e.g. `192.168.1.0/24`).
2. **Configure Cashier Workstations**:
   - In the application's **Settings > Database & Multi-Workstation** tab:
     - Set Deployment Mode to `Multi-Computer - Shared Network PostgreSQL Server`.
     - Host: `192.168.1.50` (Server local IP)
     - Port: `5432`
     - Database: `billing_db`
     - Username & Password.
   - Click **Test Database Connection** to verify reachability.
3. **Concurrency Controls**:
   - All checkouts acquire row-level locks on stock (`with_for_update()`).
   - If stock is 5 units and two cashiers sell 4 units simultaneously, exactly one completes; the second receives an `InsufficientStockError`.
   - Invoice numbers are generated using atomic `UPDATE ... RETURNING` sequences, guaranteeing zero collisions across counters.

---

## 5. Running the Application

### Prerequisites
- Windows 10 / 11 (64-bit)
- Python 3.10 to 3.14

### Installation
```powershell
# Clone or enter workspace
cd "c:\Users\KF0052\New folder\billing software"

# Install dependencies
pip install -r requirements.txt
```

### Launch
```powershell
python main.py
```
*On first launch, the Setup Wizard prompts you to enter shop details, GSTIN, business category, and set up your Administrator account.*

---

## 6. Running Automated Tests

Run the complete test suite:
```powershell
python -m pytest tests/ -v
```

Tests verify:
- Argon2id password security & RBAC privilege resolution
- Database schema initialization & base catalog seeding
- GST intra-state (CGST/SGST) & inter-state (IGST) calculations
- Immediate split payment reconciliation
- Atomic stock deduction and prevention of overselling
- Collision-free multi-workstation sequential invoice numbering
- PDF generation for 58mm Thermal, 80mm Thermal, and A4 GST Tax Invoices
- Procurement orders, goods receipt, and stock valuation
- Zero-downtime hot backups, SHA-256 checksums, and database restoration

---

## 7. Building Windows Distribution Executable & Installer

### Build Standalone Executable
```powershell
python build_exe.py
```
Generates a standalone directory in `dist/AntigravityBilling/`.

### Compile Windows Setup Installer
Open `installer.iss` in [Inno Setup Compiler](https://jrsoftware.org/isdl.php) and click **Compile** (or run `ISCC.exe installer.iss`).
This generates `output/AntigravityBilling_Setup_v1.0.0.exe` with desktop shortcuts, start menu entries, and uninstaller.
