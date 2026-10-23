# Grocery Store & Supermarket Billing System - Deployment & Architecture Guide

## 1. Operating Modes Overview

The application supports two production deployment architectures:

```
[Mode A: Single-Computer Standalone]
+-------------------------------------------------------+
|  Windows POS Terminal (Shop Billing App)              |
|   +-----------------------------------------------+   |
|   |  Embedded SQLite (WAL Mode + 64MB Cache)      |   |
|   |  Path: %LOCALAPPDATA%\AJBillingSoftware\      |   |
|   +-----------------------------------------------+   |
+-------------------------------------------------------+

[Mode B: Multi-Computer Local Network (LAN)]
+------------------------+      +------------------------+
| Cashier 1 Terminal     |      | Cashier 2 Terminal     |
| (PySide6 Desktop App)  |      | (PySide6 Desktop App)  |
+-----------+------------+      +-----------+------------+
            |                               |
            +---------------+---------------+
                            |
                   (Local Shop LAN)
                            |
            +---------------v---------------+
            | Central Server / Main Counter |
            | PostgreSQL 15+ Server         |
            | - Row-level Locking (SELECT   |
            |   FOR UPDATE)                 |
            | - Collision-free RETURNING    |
            |   invoice counters            |
            +-------------------------------+
```

---

## 2. Mode A: Single-Computer Installation

### Prerequisites
- Windows 10 or Windows 11 (64-bit).
- Python 3.12+ (or pre-compiled `.exe` standalone package).
- Thermal Receipt Printer (58mm or 80mm ESC/POS or standard Windows Spooler driver).
- USB Barcode Scanner (configured in standard HID Keyboard Wedge mode).

### Step-by-Step Setup
1. Clone or extract the application files to `C:\GroceryBilling\`.
2. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
3. Run the application:
   ```cmd
   python main.py
   ```
4. On first launch, the **Initial Setup Wizard** guides you through:
   - Entering Shop Name, Address, Phone, and GSTIN.
   - Selecting Business Category: **Grocery / Supermarket**.
   - Creating Administrator credentials.
5. Populating Grocery Catalog:
   - Run `python seed_supermarket.py` to seed 79 authentic grocery products, categories, brands, UOMs, and tax rates.

---

## 3. Mode B: Multi-Computer Shared Shop Network

In this mode, multiple billing computers share a single inventory and billing database over the shop's local Wi-Fi or Ethernet network.

### Server Machine Configuration
1. Install PostgreSQL 15 or 16 on the primary computer (or designated server).
2. Create database and user:
   ```sql
   CREATE USER shop_user WITH ENCRYPTED PASSWORD 'StrongShopPassword123';
   CREATE DATABASE grocery_db OWNER shop_user;
   GRANT ALL PRIVILEGES ON DATABASE grocery_db TO shop_user;
   ```
3. Allow LAN connections in `postgresql.conf`:
   ```
   listen_addresses = '*'
   ```
4. Authorize local subnet in `pg_hba.conf` (e.g. `192.168.1.0/24`):
   ```
   host    grocery_db    shop_user    192.168.1.0/24    scram-sha-256
   ```
5. In Windows Defender Firewall on the server, open port **5432** for Inbound TCP connections.

### Client Terminal Configuration
1. Install the application on Cashier Terminal 1, 2, etc.
2. In the Setup Wizard or **⚙️ Shop Settings** -> **Database Configuration**:
   - **Mode**: Multiple Computers (PostgreSQL)
   - **Host**: Local IP of server (e.g. `192.168.1.50`)
   - **Port**: `5432`
   - **Database Name**: `grocery_db`
   - **Username**: `shop_user`
   - **Password**: `StrongShopPassword123`
3. Click **Test Database Connection** -> verify success -> Save.

### Concurrency Guarantees in Mode B
- **Overselling Prevention**: During checkout, inventory rows are locked using `SELECT ... FOR UPDATE`. If Cashier 1 and Cashier 2 scan the last packet of milk simultaneously, the first transaction commits and the second is immediately alerted with `InsufficientStockError`.
- **Sequential Invoices**: Numbering uses atomic `UPDATE invoice_sequences ... RETURNING current_number`, preventing duplicate invoice numbers across concurrent billing counters.

---

## 4. Reset & Maintenance Utilities

- **Reset Administrator Password**:
  ```cmd
  python reset_data.py
  ```
- **Wipe and Re-run Setup Wizard**:
  ```cmd
  python reset_data.py --full
  ```
- **Refresh Supermarket Catalog**:
  ```cmd
  python seed_supermarket.py
  ```
- **Run Automated Test Suite**:
  ```cmd
  python -m pytest tests/ -v
  ```
