"""
MongoDB Cloud Database Synchronization Service.
Enables central cloud aggregation for multi-shop networks (Shop 1, Shop 2, Shop 3).
- Pushes completed invoices, daily sales, and inventory snapshots to MongoDB Atlas
- Operates asynchronously in background without blocking offline checkout speed
- Idempotent document upserts prevent duplicate bills
"""

import json
import logging
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List

from src.core.database import DatabaseManager
from src.models import ApplicationSettings

logger = logging.getLogger(__name__)


class MongoSyncService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    # ---------------- Configuration ----------------

    def get_config(self) -> Dict[str, Any]:
        """Retrieves active MongoDB connection configuration."""
        with self.db.session() as session:
            uri_row = session.query(ApplicationSettings).filter_by(key="mongodb_uri").first()
            enabled_row = session.query(ApplicationSettings).filter_by(key="mongodb_enabled").first()
            dbname_row = session.query(ApplicationSettings).filter_by(key="mongodb_db_name").first()

            uri = json.loads(uri_row.value_json) if uri_row else ""
            enabled = json.loads(enabled_row.value_json) if enabled_row else False
            dbname = json.loads(dbname_row.value_json) if dbname_row else "aj_billing_cloud"

            return {
                "uri": uri,
                "enabled": enabled,
                "database_name": dbname,
            }

    def save_config(self, uri: str, database_name: str = "aj_billing_cloud", enabled: bool = True) -> None:
        """Saves MongoDB connection parameters."""
        clean_uri = uri.strip()
        clean_db = database_name.strip() or "aj_billing_cloud"

        with self.db.session() as session:
            for key, val, desc in [
                ("mongodb_uri", clean_uri, "MongoDB Atlas Connection URI"),
                ("mongodb_db_name", clean_db, "MongoDB Database Name"),
                ("mongodb_enabled", enabled, "Enable MongoDB Cloud Sync"),
            ]:
                row = session.query(ApplicationSettings).filter_by(key=key).first()
                if not row:
                    row = ApplicationSettings(key=key, value_json=json.dumps(val), description=desc)
                    session.add(row)
                else:
                    row.value_json = json.dumps(val)

    def test_connection(self, uri: Optional[str] = None) -> Tuple[bool, str]:
        """Validates connection to MongoDB cluster by pinging."""
        try:
            import pymongo
        except ImportError:
            return False, "pymongo driver is not installed."

        target_uri = uri.strip() if uri else self.get_config()["uri"]
        if not target_uri:
            return False, "MongoDB connection URI cannot be empty."

        try:
            client = pymongo.MongoClient(target_uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            client.close()
            return True, "MongoDB connection successful! Cluster reachable."
        except Exception as exc:
            logger.warning(f"MongoDB connection test failed: {exc}")
            return False, f"Connection failed: {exc}"

    # ---------------- Background Sync Operations ----------------

    def sync_sale_async(self, sale_dict: Dict[str, Any], shop_id: str) -> None:
        """Dispatches sale sync to a background daemon thread so POS billing never waits."""
        cfg = self.get_config()
        if not cfg.get("enabled") or not cfg.get("uri"):
            return

        thread = threading.Thread(
            target=self.sync_sale_now,
            args=(sale_dict, shop_id),
            daemon=True,
            name=f"MongoSync-{sale_dict.get('invoice_number', 'Sale')}",
        )
        thread.start()

    def sync_sale_now(self, sale_dict: Dict[str, Any], shop_id: str) -> bool:
        """
        Idempotently inserts or updates an invoice in MongoDB collection 'sales'.
        Uses upsert on (shop_id, invoice_number) to prevent duplicates.
        """
        try:
            import pymongo
        except ImportError:
            return False

        cfg = self.get_config()
        if not cfg.get("enabled") or not cfg.get("uri"):
            return False

        clean_shop_id = (shop_id or "SHOP_01").strip().upper()
        inv_num = sale_dict["invoice_number"]

        document = {
            "shop_id": clean_shop_id,
            "invoice_number": inv_num,
            "sale_date": sale_dict.get("sale_date"),
            "customer_name": sale_dict.get("customer_name", "Walk-in Customer"),
            "customer_phone": sale_dict.get("customer_phone", ""),
            "customer_gstin": sale_dict.get("customer_gstin", ""),
            "subtotal": float(sale_dict.get("subtotal", 0.0)),
            "taxable_amount": float(sale_dict.get("taxable_amount", 0.0)),
            "cgst_amount": float(sale_dict.get("cgst_amount", 0.0)),
            "sgst_amount": float(sale_dict.get("sgst_amount", 0.0)),
            "igst_amount": float(sale_dict.get("igst_amount", 0.0)),
            "round_off_amount": float(sale_dict.get("round_off_amount", 0.0)),
            "grand_total": float(sale_dict.get("grand_total", 0.0)),
            "payment_status": sale_dict.get("payment_status", "PAID"),
            "items": sale_dict.get("items", []),
            "payments": sale_dict.get("payments", []),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            client = pymongo.MongoClient(cfg["uri"], serverSelectionTimeoutMS=6000)
            db = client[cfg["database_name"]]
            collection = db["sales"]
            collection.update_one(
                {"shop_id": clean_shop_id, "invoice_number": inv_num},
                {"$set": document},
                upsert=True,
            )
            client.close()
            logger.info(f"Successfully synced Invoice {inv_num} for {clean_shop_id} to MongoDB.")
            return True
        except Exception as exc:
            logger.warning(f"Could not sync invoice {inv_num} to MongoDB ({exc}). Local record is safe.")
            return False

    def sync_inventory_snapshot(self, products_list: List[Dict[str, Any]], shop_id: str) -> bool:
        """
        Syncs current product stock levels and selling prices for a shop to MongoDB 'inventory' collection.
        """
        try:
            import pymongo
        except ImportError:
            return False

        cfg = self.get_config()
        if not cfg.get("enabled") or not cfg.get("uri"):
            return False

        clean_shop_id = (shop_id or "SHOP_01").strip().upper()

        try:
            client = pymongo.MongoClient(cfg["uri"], serverSelectionTimeoutMS=6000)
            db = client[cfg["database_name"]]
            collection = db["inventory"]

            for p in products_list:
                doc = {
                    "shop_id": clean_shop_id,
                    "product_id": p.get("id"),
                    "name": p.get("name"),
                    "sku": p.get("sku"),
                    "barcode": p.get("barcode"),
                    "selling_price": float(p.get("selling_price", 0.0)),
                    "mrp": float(p.get("mrp", 0.0)),
                    "quantity_on_hand": float(p.get("quantity_on_hand", 0.0)),
                    "last_synced": datetime.now(timezone.utc).isoformat(),
                }
                collection.update_one(
                    {"shop_id": clean_shop_id, "sku": p.get("sku")},
                    {"$set": doc},
                    upsert=True,
                )

            client.close()
            logger.info(f"Synced {len(products_list)} inventory items for {clean_shop_id} to MongoDB.")
            return True
        except Exception as exc:
            logger.warning(f"Failed to sync inventory to MongoDB: {exc}")
            return False
