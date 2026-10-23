# Complete Grocery Store & Supermarket Billing System - User Manual

## 1. Quick Cashier Billing (POS)
The billing interface is optimized for speed and single-keystroke operations.

### Keyboard Shortcuts
- **F2**: Focus Barcode Scanner wedge input.
- **F3**: Focus Search Box (search by Name or SKU).
- **F4**: Clear Cart (cancels draft bill without altering stock).
- **F8**: Reprint Last Bill (instant 80mm/58mm thermal or A4 invoice).
- **F12**: Complete Sale & Settle Payment.
- **Esc**: Dismiss dialogs / return to billing.

### Barcode & Multiplier Scanning
1. **Direct Scan**: Aim USB scanner at product barcode; item is added to cart with quantity `1`. Scanning again increments quantity to `2`.
2. **Multiplier Wedge**: To ring up multiples without repeated scanning:
   - Type `5*` and scan barcode: adds **5 units** instantly.
   - Type `2.5*101` and press Enter: rings up **2.500 kg** of loose onions.
3. **Electronic Weighing Scale Barcodes**:
   - In-store scales print labels with prefix `20` or `21` (e.g. `2000101015000` = item 101, 1.500 kg).
   - Scanner decodes weight automatically and populates decimal quantity.
4. **Loose Produce Short-Codes**:
   - `101`: Fresh Onions (Loose)
   - `102`: Fresh Potatoes (Loose)
   - `103`: Fresh Country Tomatoes (Loose)
   - `104`: Loose Sugar M-30
   - `105`: Loose Toor Dal

### Payment Settlement (F12)
- **Cash**: Enter amount received in *Cash Tendered*. Change due to customer is calculated automatically. Quick cash buttons (`₹100`, `₹200`, `₹500`, `₹2000`) populate denominations with one click.
- **UPI / QR Code**: Settle via UPI; enter optional Bank UTR / Transaction Reference.
- **Card**: Enter debit or credit card settlement.
- **Split Payment**: Split total across multiple modes (e.g. ₹500 Cash + ₹700 UPI). The system verifies that exact payment matches payable total before enabling the confirmation button.
- **No Customer Credit**: Customer credit sales are strictly prohibited; every transaction is settled immediately.

---

## 2. Product & Inventory Management

### Adding Products
1. **Quick Add**: Navigate to **Products** -> Click **+ Add New Product**.
   - Type Category and Brand directly in the box: if it's new, it automatically saves to memory and autocompletes for subsequent products.
   - Enter Cost, Selling Price, MRP, Tax profile (0%, 5%, 12%, 18%), and Opening Stock.
2. **Spreadsheet Bulk Entry**:
   - Click **📑 Bulk Entry Grid** on the Products screen.
   - Type rows or copy-paste columns directly from Excel.
   - Click **🔍 Validate All Rows**: error cells are highlighted in soft red.
   - Click **💾 Save All Valid Products** to commit.
3. **Excel / CSV Import**:
   - Use the sample template in `templates/sample_product_import.csv`.
   - Click **Import CSV** to batch import large vendor catalogs.

### Barcode Sticker Printing
- On the **Products** screen, click **🏷️ Barcode Labels**.
- Generates an A4 PDF sheet of printable barcode stickers with shop name, barcode graphic, and MRP (Incl. GST).

---

## 3. Dedicated Price & Margin Management
Accessible via **💰 Price Management** in the sidebar.

1. **Inline Price Adjustment**:
   - Search by product name, SKU, or filter by category/brand.
   - Shows wholesale cost, MRP, selling price, and real-time **Gross Margin %** (green >25%, red <5%).
   - Click **Edit** to update selling price and enter a mandatory reason for audit history.
2. **Price History Audit Trail**:
   - Click **History** on any product to review the full timeline of price changes, old vs new values, user who changed it, and reason.
3. **Bulk Price Revision**:
   - Click **⚡ Bulk Price Revision**.
   - Choose Target (Selling Price, MRP, or Cost), select Category or Brand, and enter a % change or flat ₹ adjustment.
   - Click **🔍 Calculate Safety Preview**: displays affected product count and exact old vs proposed prices before applying.
   - Click **Confirm & Apply Price Revisions** to atomically commit and record Price History.

---

## 4. Controlled Sales Returns
1. Navigate to **🧾 Sales History**.
2. Select the completed invoice and click **Process Return**.
3. Specify returned quantity for eligible items.
4. Select **Return Reason** and **Refund Method** (Cash / UPI / Card).
5. **Restock Decision**:
   - If goods are in resalable condition: leave **Restock into Saleable Inventory** checked (inventory balance increments).
   - If goods are damaged or expired: **uncheck** the box (customer is refunded, but damaged goods are not returned to saleable stock).

---

## 5. Daily Reports & Analytics
- **📊 Dashboard**: Real-time sales KPIs, completed bill counter, low-stock count, payment splits, recent transactions, and an embedded **7-Day Sales Trend Matplotlib chart**.
- **📑 Reports & Tax**:
  - Detailed Sales Register.
  - Product-wise & Category-wise sales volume.
  - **GSTR-1 Statutory Tax Summary**: Taxable value, CGST, SGST, IGST broken down by GST slab (0%, 5%, 12%, 18%, 28%).
  - Inventory Stock Valuation at Cost and Retail.
  - Profit & Loss Statement (Taxable Revenue - COGS = Gross Profit).
  - One-click **Export to Excel** for accounting and filing.

---

## 6. Zero-Downtime Backup & Restore
- Navigate to **💾 Backup & Restore**.
- Click **Create Immediate Backup**: performs an atomic online backup without interrupting billing.
- Every backup generates a cryptographic SHA-256 integrity checksum.
- Automated daily backups can be configured in **⚙️ Shop Settings**.
