# AJ Billing Software
## Cashier POS Quick-Start Manual

---

### 1. POS Keyboard Shortcuts Reference

The Billing screen is designed for high-speed operation without requiring mouse interaction:

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| **`F2`** | Focus Barcode Scanner | Immediately highlights the barcode input box for scanning. |
| **`F3`** | Search Product | Highlights the name search box to quickly look up items without barcodes. |
| **`F4`** | Clear Cart | Clears the current cart for a new walk-in customer. |
| **`F8`** | Reprint Last Bill | Re-opens and prints the most recently completed invoice. |
| **`F12`** | Complete Sale | Opens the Payment Settlement dialog to conclude checkout. |
| **`Enter`** | Add Scanned Item | Triggers barcode lookup and adds product to the active bill. |
| **`Esc`** | Cancel Dialog | Closes any open modal dialog. |

---

### 2. Standard Billing Workflow

#### Step 1: Scan Merchandise
1. Ensure the cursor is in the **Scan Barcode** input (or press `F2`).
2. Point your USB / Bluetooth barcode scanner at the product barcode.
3. The scanner simulates typing the barcode followed by `Enter`.
4. The product is added to the cart table with quantity `1`.
5. If the same barcode is scanned again, the quantity increments automatically.

#### Step 2: Manual Search for Unbarcoded Goods
1. Press `F3` to jump to **Search Product by Name**.
2. Type 2 or 3 letters (e.g. `ric` for rice, or `dal`).
3. A dropdown shows matching items with current price and available stock.
4. Double-click the item or press `Enter` to add it to the cart.

#### Step 3: Adjust Quantities and Line Discounts
- In the cart table, use the **Qty** spin box to adjust quantities (e.g. `2.500` kg).
- Enter any authorized item-level discount in the **Disc (₹)** column.
- To remove an item accidentally scanned, click the red **✕** button.

#### Step 4: Optional Customer Details
- For ordinary retail sales, customer details are optional (*Walk-in Customer*).
- For registered customers or B2B bills, enter their **Phone Number** and **Customer GSTIN**.

---

### 3. Payment Settlement & Change Calculation

Press **`F12`** (or click the green **COMPLETE SALE** button).

The Payment Dialog appears:
1. **Total Amount Payable** is displayed in large green numbers (e.g. `₹ 708.00`).
2. **Single Cash Payment**:
   - Enter cash received from customer in **Cash Received** (or click a Quick Cash button: `₹100`, `₹200`, `₹500`, `₹2000`).
   - The **Change Due to Customer** is calculated automatically.
3. **Split Payment** (e.g. part Cash, part UPI):
   - In **Cash Amount**, enter `₹ 500.00`.
   - In **UPI / QR Code**, enter `₹ 208.00` and optionally type the UPI transaction reference / UTR.
   - The system validates that the combined payment matches the grand total exactly.
4. Click **Confirm Payment & Print** (or press `Enter`).

---

### 4. Printing & Receipts

Once the sale completes:
1. The **Invoice Preview Dialog** opens automatically.
2. Select your desired format:
   - **Print 58mm Thermal**: For compact thermal receipt printers.
   - **Print 80mm Thermal**: Standard 3-inch roll receipt with complete GST breakdown.
   - **Print A4 GST Invoice**: Formal full-page tax invoice for B2B supplies.
3. The bill opens in your default printer viewer ready to print.
4. The cart resets automatically for the next customer in queue.

---

### 5. Sales Returns & Customer Refunds

If a customer returns an item:
1. Open **Sales History** in the left navigation.
2. Find the customer's invoice using the invoice number or date filter.
3. Click the **Return** button on the invoice row.
4. In the dialog, enter the quantity of each item being returned.
5. Provide a return reason (e.g. *Defective item* or *Size exchange*).
6. Select refund mode (**CASH**, **UPI**, or **CARD**).
7. Click **Process Refund & Restore Stock**.
8. The refunded amount is recorded and the stock is returned to inventory.
