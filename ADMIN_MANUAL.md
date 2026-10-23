# Antigravity Billing & Shop Management System
## Administrator Manual

---

### 1. Introduction & Initial Onboarding

When launching the application for the very first time on a fresh installation, the **Setup Wizard** appears automatically.

#### Setup Wizard Steps:
1. **Shop Trade Name**: Enter the primary business name displayed on receipts (e.g. *Sri Murugan Super Stores*).
2. **Legal Entity Name**: Registered business name (e.g. *Sri Murugan Retail Pvt Ltd*).
3. **Shop GSTIN**: 15-character Indian Goods & Services Tax Identification Number (e.g. `33ABCDE1234F1Z5`).
4. **Home State (POS)**: Select your state (e.g. `Tamil Nadu (33)`). This serves as the statutory place-of-supply anchor for CGST/SGST vs IGST calculation.
5. **Business Category**: Select your primary store category.
6. **Administrator Credentials**: Set your root admin username and secure password (minimum 6 characters).

---

### 2. Business Category Profiles

You can change or adjust the active profile anytime under **Settings > Shop & Business Profile**:

| Profile | Key Adaptations |
| :--- | :--- |
| **Grocery / Supermarket** | Kilograms (kg), Grams (g), Litres (L), Millilitres (mL), Packets. Supports 3-decimal fractional sales (e.g. 1.250 kg rice), batch numbers, and expiry alerts. |
| **Electrical / Hardware** | Units, Packs, Meters, Boxes. Manufacturer brand filter, technical specifications, model numbers, warranty durations. |
| **Clothing / Textile** | Product variant matrix (Size, Colour, Fit, Fabric). Each variant maintains independent stock balance and barcode. |
| **Mobile & Electronics** | Serial numbers, Dual IMEI tracking, device warranty period, purchase invoice cross-referencing. |
| **Medical / Pharmacy** | Batch numbers, Expiry dates, FEFO (First-Expiry-First-Out) dispensing, Schedule H drug prescription alerts. |
| **General Retail** | Flexible multi-category store supporting mixed goods and services. |

---

### 3. User Accounts and Role-Based Permissions

Under **User Management**, administrators can provision user accounts and configure privileges:

#### Default Roles:
- **Administrator**: Full privileges over settings, user creation, reports, inventory adjustments, and backups.
- **Cashier**: Restricted to POS billing, processing payments, reprinting receipts, and looking up customers/products. Cannot modify product prices, adjust stock arbitrarily, or view sensitive gross-profit reports.
- **Inventory Manager**: Can add/edit products, import catalogs, record supplier purchase bills, and perform physical stock reconciliation.

---

### 4. Product Catalogue Management

Under **Products**:
- **Adding Products**: Click `+ Add New Product`. Enter Name, SKU (must be unique), Barcode (scan or auto-generated), UOM, Selling Price, Purchase Cost, and GST tax profile.
- **Bulk Import**: Click `Import CSV`. CSV format:
  ```csv
  Name,SKU,Barcode,Unit,SellingPrice,PurchaseCost,GSTRate,OpeningStock
  Aashirvaad Atta 5kg,ATTA-5KG,890103001,PACK,265.00,210.00,5,25
  Tata Salt 1kg,SALT-1KG,890103002,PACK,28.00,20.00,0,100
  ```
- **Exporting**: Click `Export to Excel` to download the entire merchandise catalog with current stock quantities and costs.

---

### 5. Inventory Auditing & Physical Stock Adjustments

Under **Inventory**:
- **Stock Balances**: Shows quantity on hand, reorder levels, and stock alert status (`IN STOCK`, `LOW STOCK`, `OUT OF STOCK`).
- **Auditable Ledger**: Every sale, purchase, customer return, or correction creates an immutable `StockMovement` row with timestamp, user ID, and quantity delta.
- **Manual Stock Correction**: Click `Adjust Stock / Physical Count`. Select the product, input the verified physical count, select the reason (`PHYSICAL_COUNT`, `DAMAGE`, `EXPIRY`, `CORRECTION`), and provide audit notes.

---

### 6. Purchasing & Supplier Procurement

Under **Purchases**:
1. Click `+ Record Purchase Bill`.
2. Select or create the Supplier (with their GSTIN and contact details).
3. Enter the Supplier's tax invoice number and bill date.
4. Add items, quantities, and inward cost prices.
5. Click `Confirm Purchase & Receive Stock`.
6. Inventory balances are atomically increased, and a `PURCHASE_IN` movement is appended to the ledger.

---

### 7. GST Statutory Compliance & Tax Summaries

The system computes statutory Indian GST in compliance with CGST/SGST/IGST rules:
- **Intra-State Supplies** (Customer in same state or walk-in): Tax is split equally between **CGST** and **SGST**.
- **Inter-State Supplies** (Customer provides out-of-state GSTIN / state code): Full rate applied as **IGST**.
- **GSTR-1 Preparation**: Open **Reports & Tax > GST Tax Breakdown**. View and export taxable value, CGST, SGST, and IGST totals grouped by statutory rate (0%, 5%, 12%, 18%, 28%).

---

### 8. Backup & Disaster Recovery

Under **Backup & Restore**:
- **Creating Hot Backups**: Click `Create Database Backup Now`. The system takes a non-blocking hot snapshot of the database, computes its SHA-256 checksum, and records the event in the history log.
- **Integrity Verification**: Click `Verify` next to any backup in the list. The system validates the file size, checksum, and executes `PRAGMA integrity_check` to verify database consistency.
- **Restoration**: Click `Restore`. The system automatically creates a pre-restoration safety snapshot of your current database before restoring from the chosen backup file.
