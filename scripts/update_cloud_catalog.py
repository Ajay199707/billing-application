"""
Developer Cloud Catalog Management CLI.
Allows developers to easily view, update, add, or upload price changes
and custom products directly to MongoDB Atlas ('client_catalogs')
for any client shop (SHOP_01, SHOP_02, etc.).

Usage:
  Interactive Mode:
    python scripts/update_cloud_catalog.py

  View Shop Items:
    python scripts/update_cloud_catalog.py --shop SHOP_01 --list

  Update or Add Item Price:
    python scripts/update_cloud_catalog.py --shop SHOP_01 --barcode 8901777011017 --price 65.0 --name "Aachi Chilli Powder 200g"

  Upload JSON File:
    python scripts/update_cloud_catalog.py --upload catalog/shops/SHOP_01_pricing.json
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pymongo
except ImportError:
    print("Error: 'pymongo' is not installed. Run: pip install pymongo dnspython")
    sys.exit(1)

from src.services.mongo_service import DEFAULT_MONGODB_URI, DEFAULT_MONGODB_DB_NAME


def get_mongo_db(uri: str = DEFAULT_MONGODB_URI, db_name: str = DEFAULT_MONGODB_DB_NAME):
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    return client, client[db_name]


def list_shop_items(shop_id: str):
    clean_id = (shop_id or "SHOP_01").strip().upper()
    print(f"\n--- Fetching items for [{clean_id}] from MongoDB Atlas ---")
    try:
        client, db = get_mongo_db()
        doc = db["client_catalogs"].find_one({"$or": [{"client_id": clean_id}, {"shop_id": clean_id}]})
        client.close()

        if not doc:
            print(f"No document found for Shop ID '{clean_id}' in 'client_catalogs'.")
            return

        items = doc.get("price_updates", [])
        print(f"Shop ID: {clean_id}")
        print(f"Description: {doc.get('description', 'N/A')}")
        print(f"Last Synced: {doc.get('synced_at', 'N/A')}")
        print(f"Total Products: {len(items)}\n")

        if not items:
            print("No price updates in this catalog.")
            return

        print(f"{'#':<3} | {'Barcode':<15} | {'SKU':<15} | {'Selling Price':<14} | {'MRP':<10} | {'Name'}")
        print("-" * 80)
        for idx, item in enumerate(items, 1):
            barcode = str(item.get("barcode", "-"))
            sku = str(item.get("sku", "-"))
            price = f"Rs. {float(item.get('selling_price', 0)):.2f}"
            mrp = f"Rs. {float(item.get('mrp', 0)):.2f}"
            name = str(item.get("name", "Unnamed"))
            print(f"{idx:<3} | {barcode:<15} | {sku:<15} | {price:<14} | {mrp:<10} | {name}")
        print("-" * 80)

    except Exception as exc:
        print(f"Failed to fetch catalog: {exc}")


def upload_json_file(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File '{file_path}' does not exist.")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    shop_id = (data.get("shop_id") or data.get("client_id") or path.stem.replace("_pricing", "")).strip().upper()
    data["client_id"] = shop_id
    data["shop_id"] = shop_id
    data["synced_at"] = datetime.now(timezone.utc).isoformat()
    data.pop("_id", None)

    print(f"\nUploading pricing catalog for [{shop_id}] to MongoDB Atlas...")
    try:
        client, db = get_mongo_db()
        db["client_catalogs"].replace_one(
            {"$or": [{"client_id": shop_id}, {"shop_id": shop_id}]},
            data,
            upsert=True,
        )
        client.close()
        items_count = len(data.get("price_updates", []))
        print(f"SUCCESS: Catalog for {shop_id} uploaded with {items_count} products!")
    except Exception as exc:
        print(f"Failed to upload catalog: {exc}")


def update_or_add_item(
    shop_id: str,
    barcode: str,
    selling_price: float,
    name: str = "",
    sku: str = "",
    purchase_cost: float = 0.0,
    mrp: float = 0.0,
    category: str = "General",
    brand: str = "Generic",
):
    clean_id = (shop_id or "SHOP_01").strip().upper()
    clean_barcode = barcode.strip()

    try:
        client, db = get_mongo_db()
        col = db["client_catalogs"]
        doc = col.find_one({"$or": [{"client_id": clean_id}, {"shop_id": clean_id}]})

        if not doc:
            doc = {
                "client_id": clean_id,
                "shop_id": clean_id,
                "description": f"Custom pricing overrides for {clean_id}",
                "price_updates": [],
            }

        updates = doc.get("price_updates", [])
        mrp_val = mrp if mrp > 0 else selling_price
        found = False

        for item in updates:
            if str(item.get("barcode", "")).strip() == clean_barcode or (sku and str(item.get("sku", "")).strip() == sku):
                item["selling_price"] = float(selling_price)
                if purchase_cost > 0:
                    item["purchase_cost"] = float(purchase_cost)
                if mrp_val > 0:
                    item["mrp"] = float(mrp_val)
                if name:
                    item["name"] = name.strip()
                if category and category != "General":
                    item["category"] = category.strip()
                if brand and brand != "Generic":
                    item["brand"] = brand.strip()
                found = True
                print(f"Updated existing item '{item.get('name')}' -> Selling Price: Rs. {selling_price:.2f}")
                break

        if not found:
            new_item = {
                "barcode": clean_barcode,
                "sku": sku or f"SKU-{clean_barcode}",
                "name": name or f"Product {clean_barcode}",
                "selling_price": float(selling_price),
                "purchase_cost": float(purchase_cost),
                "mrp": float(mrp_val),
                "category": category,
                "brand": brand,
            }
            updates.append(new_item)
            print(f"Added new item '{new_item['name']}' -> Selling Price: Rs. {selling_price:.2f}")

        doc["price_updates"] = updates
        doc["synced_at"] = datetime.now(timezone.utc).isoformat()
        doc.pop("_id", None)

        col.replace_one(
            {"$or": [{"client_id": clean_id}, {"shop_id": clean_id}]},
            doc,
            upsert=True,
        )
        client.close()
        print(f"SUCCESS: Changes saved to MongoDB Atlas for [{clean_id}]!")

    except Exception as exc:
        print(f"Failed to update MongoDB item: {exc}")


def interactive_menu():
    print("=" * 60)
    print("      AJ Billing Software - Cloud Catalog Manager")
    print("=" * 60)
    print("1. View products for a Shop")
    print("2. Update or Add a product price")
    print("3. Upload JSON file (e.g. catalog/shops/SHOP_01_pricing.json)")
    print("4. Exit")
    print("-" * 60)

    choice = input("Enter choice (1-4): ").strip()
    if choice == "1":
        shop = input("Enter Shop ID (default: SHOP_01): ").strip() or "SHOP_01"
        list_shop_items(shop)
    elif choice == "2":
        shop = input("Enter Shop ID (default: SHOP_01): ").strip() or "SHOP_01"
        barcode = input("Enter Barcode: ").strip()
        if not barcode:
            print("Barcode cannot be empty.")
            return
        name = input("Enter Product Name (optional, press Enter to keep): ").strip()
        price_str = input("Enter New Selling Price (e.g. 140.00): ").strip()
        try:
            price = float(price_str)
        except ValueError:
            print("Invalid price number.")
            return
        cost_str = input("Enter Purchase Cost (optional, press Enter to skip): ").strip()
        cost = float(cost_str) if cost_str else 0.0
        mrp_str = input("Enter MRP (optional, press Enter to skip): ").strip()
        mrp = float(mrp_str) if mrp_str else 0.0

        update_or_add_item(
            shop_id=shop,
            barcode=barcode,
            selling_price=price,
            name=name,
            purchase_cost=cost,
            mrp=mrp,
        )
    elif choice == "3":
        path = input("Enter path to JSON file (default: catalog/shops/SHOP_01_pricing.json): ").strip()
        if not path:
            path = "catalog/shops/SHOP_01_pricing.json"
        upload_json_file(path)
    elif choice == "4":
        print("Goodbye!")
    else:
        print("Invalid choice.")


def main():
    parser = argparse.ArgumentParser(description="Manage shop catalogs and pricing in MongoDB Atlas.")
    parser.add_argument("--shop", help="Target Shop ID (e.g. SHOP_01)")
    parser.add_argument("--list", action="store_true", help="List all items for the shop")
    parser.add_argument("--upload", help="Upload a pricing JSON file (e.g. catalog/shops/SHOP_01_pricing.json)")
    parser.add_argument("--barcode", help="Product Barcode to update or add")
    parser.add_argument("--name", help="Product Name")
    parser.add_argument("--price", type=float, help="Selling Price")
    parser.add_argument("--cost", type=float, default=0.0, help="Purchase Cost")
    parser.add_argument("--mrp", type=float, default=0.0, help="MRP")
    parser.add_argument("--sku", help="Product SKU")

    args = parser.parse_args()

    if args.upload:
        upload_json_file(args.upload)
    elif args.shop and args.list:
        list_shop_items(args.shop)
    elif args.shop and args.barcode and args.price is not None:
        update_or_add_item(
            shop_id=args.shop,
            barcode=args.barcode,
            selling_price=args.price,
            name=args.name or "",
            sku=args.sku or "",
            purchase_cost=args.cost,
            mrp=args.mrp,
        )
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
