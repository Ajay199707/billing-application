"""
MongoDB Cloud Database Synchronization Service.
Enables central cloud aggregation for multi-shop networks (Shop 1, Shop 2, Shop 3).
- Pushes completed invoices, daily sales, and inventory snapshots to MongoDB Atlas
- Operates asynchronously in background without blocking offline checkout speed
- Idempotent document upserts prevent duplicate bills
- Fetches real-time shop pricing and master catalogs directly from MongoDB Atlas
"""

import json
import logging
import sys
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List

from src.core.database import DatabaseManager
from src.models import ApplicationSettings

logger = logging.getLogger(__name__)

# Production MongoDB Atlas Cloud Credentials & Defaults
DEFAULT_MONGODB_URI = "mongodb+srv://braisonaj_db_user:aaa111@cluster0.6xmc0tb.mongodb.net/"
DEFAULT_MONGODB_DB_NAME = "aj_billing_cloud"


class MongoSyncService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    # ---------------- Configuration ----------------

    def get_config(self) -> Dict[str, Any]:
        """Retrieves active MongoDB connection configuration."""
        try:
            with self.db.session() as session:
                uri_row = session.query(ApplicationSettings).filter_by(key="mongodb_uri").first()
                enabled_row = session.query(ApplicationSettings).filter_by(key="mongodb_enabled").first()
                dbname_row = session.query(ApplicationSettings).filter_by(key="mongodb_db_name").first()

                uri = json.loads(uri_row.value_json) if (uri_row and uri_row.value_json) else DEFAULT_MONGODB_URI
                enabled = json.loads(enabled_row.value_json) if enabled_row else True
                dbname = json.loads(dbname_row.value_json) if (dbname_row and dbname_row.value_json) else DEFAULT_MONGODB_DB_NAME

                return {
                    "uri": uri,
                    "enabled": enabled,
                    "database_name": dbname,
                }
        except Exception as exc:
            logger.debug(f"Could not query MongoDB config from settings table: {exc}")
            return {
                "uri": DEFAULT_MONGODB_URI,
                "enabled": True,
                "database_name": DEFAULT_MONGODB_DB_NAME,
            }

    def save_config(self, uri: str, database_name: str = "aj_billing_cloud", enabled: bool = True) -> None:
        """Saves MongoDB connection parameters."""
        clean_uri = uri.strip()
        clean_db = database_name.strip() or DEFAULT_MONGODB_DB_NAME

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

        target_uri = uri.strip() if uri is not None else self.get_config()["uri"]
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

    # ---------------- Cloud Catalog Retrieval ----------------

    def get_shop_catalog(self, shop_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the latest pricing catalog overrides for a specific shop from MongoDB 'client_catalogs'.
        """
        try:
            import pymongo
        except ImportError:
            return None

        cfg = self.get_config()
        if not cfg.get("enabled") or not cfg.get("uri"):
            return None

        clean_id = (shop_id or "SHOP_01").strip().upper()

        try:
            client = pymongo.MongoClient(cfg["uri"], serverSelectionTimeoutMS=5000)
            db = client[cfg["database_name"]]
            doc = db["client_catalogs"].find_one({
                "$or": [{"client_id": clean_id}, {"shop_id": clean_id}]
            })
            client.close()

            if doc:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                return doc
            return None
        except Exception as exc:
            logger.debug(f"Could not fetch shop catalog from MongoDB for {clean_id}: {exc}")
            return None

    def get_master_catalog(self) -> Optional[Dict[str, Any]]:
        """
        Fetches master catalog from MongoDB 'master_catalog' collection if present.
        """
        try:
            import pymongo
        except ImportError:
            return None

        cfg = self.get_config()
        if not cfg.get("enabled") or not cfg.get("uri"):
            return None

        try:
            client = pymongo.MongoClient(cfg["uri"], serverSelectionTimeoutMS=5000)
            db = client[cfg["database_name"]]
            doc = db["master_catalog"].find_one()
            client.close()

            if doc:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                return doc
            return None
        except Exception as exc:
            logger.debug(f"Could not fetch master catalog from MongoDB: {exc}")
            return None

    def push_master_catalog(self, catalog_data: Dict[str, Any]) -> bool:
        """Uploads or updates the master grocery catalog in MongoDB Atlas."""
        try:
            import pymongo
        except ImportError:
            return False

        cfg = self.get_config()
        if not cfg.get("enabled") or not cfg.get("uri"):
            return False

        try:
            client = pymongo.MongoClient(cfg["uri"], serverSelectionTimeoutMS=6000)
            db = client[cfg["database_name"]]
            clean_copy = dict(catalog_data)
            clean_copy.pop("_id", None)
            clean_copy["synced_at"] = datetime.now(timezone.utc).isoformat()
            db["master_catalog"].replace_one({}, clean_copy, upsert=True)
            client.close()
            return True
        except Exception as exc:
            logger.warning(f"Failed to push master catalog to MongoDB: {exc}")
            return False

    def push_shop_catalog(self, shop_id: str, catalog_data: Dict[str, Any]) -> bool:
        """Uploads or updates custom pricing for a shop in MongoDB Atlas 'client_catalogs'."""
        try:
            import pymongo
        except ImportError:
            return False

        cfg = self.get_config()
        if not cfg.get("enabled") or not cfg.get("uri"):
            return False

        clean_id = (shop_id or "SHOP_01").strip().upper()

        try:
            client = pymongo.MongoClient(cfg["uri"], serverSelectionTimeoutMS=6000)
            db = client[cfg["database_name"]]
            clean_copy = dict(catalog_data)
            clean_copy.pop("_id", None)
            clean_copy["client_id"] = clean_id
            clean_copy["shop_id"] = clean_id
            clean_copy["synced_at"] = datetime.now(timezone.utc).isoformat()
            db["client_catalogs"].replace_one(
                {"$or": [{"client_id": clean_id}, {"shop_id": clean_id}]},
                clean_copy,
                upsert=True,
            )
            client.close()
            return True
        except Exception as exc:
            logger.warning(f"Failed to push shop catalog for {clean_id} to MongoDB: {exc}")
            return False

    # ---------------- Background Sync Operations ----------------

    def sync_sale_async(self, sale_dict: Dict[str, Any], shop_id: str) -> None:
        """Dispatches sale sync to a background daemon thread so POS billing never waits."""
        if "pytest" in sys.modules and not getattr(self, "_force_sync_in_tests", False):
            return

        try:
            cfg = self.get_config()
            if not cfg.get("enabled") or not cfg.get("uri"):
                return
        except Exception:
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
        Uses upsert on (client_id, invoice_number) to prevent duplicates.
        """
        try:
            import pymongo
        except ImportError:
            return False

        try:
            cfg = self.get_config()
            if not cfg.get("enabled") or not cfg.get("uri"):
                return False

            clean_shop_id = (shop_id or "SHOP_01").strip().upper()
            inv_num = sale_dict["invoice_number"]

            # Retrieve shop name for centralized multi-client identification
            shop_name = sale_dict.get("shop_name", "")
            if not shop_name:
                try:
                    from src.models import Shop
                    with self.db.session() as s:
                        s_row = s.query(Shop).first()
                        if s_row:
                            shop_name = s_row.name
                except Exception:
                    shop_name = f"Shop {clean_shop_id}"

            document = {
                "client_id": clean_shop_id,
                "shop_id": clean_shop_id,
                "shop_name": shop_name,
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

            client = pymongo.MongoClient(cfg["uri"], serverSelectionTimeoutMS=6000)
            db = client[cfg["database_name"]]
            collection = db["sales"]
            collection.update_one(
                {"client_id": clean_shop_id, "invoice_number": inv_num},
                {"$set": document},
                upsert=True,
            )
            client.close()
            logger.info(f"Successfully synced Invoice {inv_num} for {clean_shop_id} to MongoDB.")
            return True
        except Exception as exc:
            logger.warning(f"Could not sync invoice {sale_dict.get('invoice_number', 'Unknown')} to MongoDB ({exc}). Local record is safe.")
            return False

    def sync_inventory_async(self, products_list: List[Dict[str, Any]], shop_id: str) -> None:
        """Dispatches inventory snapshot sync to a background daemon thread."""
        if "pytest" in sys.modules and not getattr(self, "_force_sync_in_tests", False):
            return

        try:
            cfg = self.get_config()
            if not cfg.get("enabled") or not cfg.get("uri"):
                return
        except Exception:
            return

        thread = threading.Thread(
            target=self.sync_inventory_snapshot,
            args=(products_list, shop_id),
            daemon=True,
            name=f"MongoSync-Inventory-{shop_id}",
        )
        thread.start()

    def sync_inventory_snapshot(self, products_list: List[Dict[str, Any]], shop_id: str) -> bool:
        """
        Syncs current product stock levels and selling prices for a shop to MongoDB 'inventory' collection.
        """
        try:
            import pymongo
        except ImportError:
            return False

        try:
            cfg = self.get_config()
            if not cfg.get("enabled") or not cfg.get("uri"):
                return False

            clean_shop_id = (shop_id or "SHOP_01").strip().upper()

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
