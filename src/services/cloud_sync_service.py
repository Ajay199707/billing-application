"""
Cloud Master Catalog Sync Service.
Connects to MongoDB Atlas cloud database (and GitHub Raw CDN fallback)
to fetch new products, updated barcodes, and statutory tax classifications
as well as shop-specific developer pricing overrides without overwriting
a shop's private selling prices or stock balances.
"""

import json
import logging
import time
import urllib.request
import urllib.error
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from src.core.database import DatabaseManager
from src.core.exceptions import BillingSystemError
from src.models import (
    Product,
    Category,
    Brand,
    UnitOfMeasure,
    ProductTaxProfile,
)
from src.services.auth_service import UserSession
from src.services.product_service import ProductService

logger = logging.getLogger(__name__)

# Default Cloud Catalog Endpoint (GitHub Raw CDN)
DEFAULT_CLOUD_CATALOG_URL = (
    "https://raw.githubusercontent.com/Ajay199707/billing-application/main/catalog/master_catalog.json"
)


class CloudSyncError(BillingSystemError):
    """Raised when connecting or fetching the cloud catalog fails."""
    pass


def fetch_cloud_catalog(
    url: str = DEFAULT_CLOUD_CATALOG_URL,
    timeout: int = 12,
    db_manager: Optional[DatabaseManager] = None,
) -> Dict[str, Any]:
    """
    Downloads the master catalog JSON.
    First checks MongoDB Atlas 'master_catalog' collection if db_manager is provided.
    Falls back to GitHub Raw CDN, and finally to local repository copy.
    """
    if db_manager:
        try:
            from src.services.mongo_service import MongoSyncService
            mongo_doc = MongoSyncService(db_manager).get_master_catalog()
            if mongo_doc and "products" in mongo_doc:
                logger.info("Loaded master catalog from MongoDB Atlas cloud database.")
                return mongo_doc
        except Exception as e:
            logger.debug(f"MongoDB master catalog check bypassed: {e}")

    clean_url = f"{url}?_cb={int(time.time())}" if "?" not in url else url
    req = urllib.request.Request(
        clean_url,
        headers={
            "User-Agent": "AJBillingSoftware-POS/1.0 (Windows; CloudSync)",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                raise CloudSyncError(f"Cloud server returned HTTP status {response.status}")
            raw_data = response.read().decode("utf-8")
            return json.loads(raw_data)
    except urllib.error.URLError as err:
        logger.error(f"Failed to reach cloud catalog at {url}: {err}")
        # Local fallback if master_catalog.json exists on disk
        local_path = Path("catalog") / "master_catalog.json"
        if local_path.exists():
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    logger.info("Loaded master catalog from local repository fallback.")
                    return json.load(f)
            except Exception:
                pass
        raise CloudSyncError(
            f"Unable to connect to the cloud server. Please check your internet connection.\n\nDetails: {err.reason}"
        )
    except json.JSONDecodeError as err:
        logger.error(f"Invalid JSON received from cloud catalog: {err}")
        raise CloudSyncError("Cloud catalog file format is invalid or corrupted.")
    except Exception as exc:
        logger.error(f"Unexpected error fetching cloud catalog: {exc}")
        raise CloudSyncError(f"Cloud sync failed: {exc}")


def sync_catalog_from_cloud(
    db_manager: DatabaseManager,
    current_session: UserSession,
    cloud_data: Optional[Dict[str, Any]] = None,
    url: str = DEFAULT_CLOUD_CATALOG_URL,
    preserve_shop_prices: bool = True,
) -> Dict[str, Any]:
    """
    Synchronizes local store database with the Cloud Master Catalog.
    - Adds new products that the shop doesn't have yet.
    - Updates names, categories, brands, and statutory GST profiles.
    - If preserve_shop_prices is True, NEVER overwrites the shopkeeper's custom selling price or stock!
    """
    if cloud_data is None:
        cloud_data = fetch_cloud_catalog(url=url, db_manager=db_manager)

    products_list = cloud_data.get("products", [])
    if not products_list:
        return {"status": "success", "created": 0, "updated": 0, "total": 0}

    prod_service = ProductService(db_manager)

    # Cache UOMs and Tax profiles
    uoms_list = prod_service.list_uoms()
    uom_by_code = {u["code"]: u["id"] for u in uoms_list}
    taxes_list = prod_service.list_tax_profiles()
    tax_by_name = {t["name"]: t["id"] for t in taxes_list}

    created_count = 0
    updated_count = 0

    for item in products_list:
        name = item.get("name")
        sku = item.get("sku")
        barcode = str(item.get("barcode", "")).strip()
        cat_name = item.get("category", "General")
        brand_name = item.get("brand", "Generic")
        uom_code = item.get("unit", "PCS")
        tax_name = item.get("tax_name", "")
        cost = Decimal(str(item.get("purchase_cost", "0.00")))
        price = Decimal(str(item.get("selling_price", "0.00")))
        mrp = Decimal(str(item.get("mrp", "0.00")))
        reorder = Decimal(str(item.get("reorder_level", "5")))
        initial_stock = Decimal(str(item.get("initial_stock", "0")))

        cat_id = prod_service.get_or_create_category(current_session, cat_name)
        brand_id = prod_service.get_or_create_brand(current_session, brand_name)

        unit_id = uom_by_code.get(uom_code, uom_by_code.get("PCS", 1))
        tax_profile_id = tax_by_name.get(tax_name, taxes_list[0]["id"] if taxes_list else 1)

        # Check existing product by barcode or SKU
        with db_manager.session() as session:
            existing = session.query(Product).filter(
                (Product.barcode == barcode) | (Product.sku == sku)
            ).first()

            if existing:
                # Update metadata only; protect shop's private pricing & stock
                existing.name = name
                existing.category_id = cat_id
                existing.brand_id = brand_id
                existing.unit_id = unit_id
                existing.tax_profile_id = tax_profile_id
                existing.mrp = mrp  # Standard manufacturer MRP

                if not preserve_shop_prices:
                    existing.selling_price = price
                    existing.purchase_cost = cost

                updated_count += 1
                continue

        # Brand new product from cloud: create it with default prices
        prod_service.create_product(
            current_session=current_session,
            name=name,
            sku=sku,
            barcode=barcode,
            unit_id=unit_id,
            tax_profile_id=tax_profile_id,
            selling_price=price,
            purchase_cost=cost,
            mrp=mrp,
            reorder_level=reorder,
            category_id=cat_id,
            brand_id=brand_id,
            initial_stock=initial_stock,
        )
        created_count += 1

    return {
        "status": "success",
        "created": created_count,
        "updated": updated_count,
        "total_cloud": len(products_list),
        "version": cloud_data.get("catalog_version", "1.0.0"),
        "last_updated": cloud_data.get("last_updated", ""),
    }


# Template for per-shop custom pricing hosted on GitHub Raw CDN
DEFAULT_SHOP_PRICING_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/Ajay199707/billing-application/main/catalog/shops/{shop_id}_pricing.json"
)


def fetch_shop_pricing(
    shop_id: str,
    base_url_template: str = DEFAULT_SHOP_PRICING_URL_TEMPLATE,
    timeout: int = 10,
    db_manager: Optional[DatabaseManager] = None,
) -> Optional[Dict[str, Any]]:
    """
    Downloads shop-specific pricing overrides.
    First checks MongoDB Atlas 'client_catalogs' collection if db_manager is provided.
    Falls back to GitHub raw CDN, and finally to local file if available.
    """
    clean_id = (shop_id or "SHOP_01").strip().upper()

    # 1. MongoDB Atlas Cloud Check
    if db_manager:
        try:
            from src.services.mongo_service import MongoSyncService
            mongo_doc = MongoSyncService(db_manager).get_shop_catalog(clean_id)
            if mongo_doc and "price_updates" in mongo_doc:
                logger.info(f"Loaded pricing overrides for {clean_id} from MongoDB Atlas collection 'client_catalogs'.")
                return mongo_doc
        except Exception as exc:
            logger.debug(f"MongoDB shop pricing fetch bypassed for {clean_id}: {exc}")

    # 2. GitHub Raw CDN Check
    url = f"{base_url_template.format(shop_id=clean_id)}?_cb={int(time.time())}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AJBillingSoftware-POS/1.0 (Windows; ShopPricingSync)",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                raw_bytes = response.read().decode("utf-8")
                return json.loads(raw_bytes)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            logger.info(f"No custom pricing file found for shop {clean_id} (HTTP 404).")
        else:
            logger.warning(f"HTTP error fetching shop pricing for {clean_id}: {err}")
    except Exception as exc:
        logger.warning(f"Could not connect to fetch shop pricing for {clean_id}: {exc}")

    # 3. Fallback to local catalog file if present on disk
    local_path = Path("catalog") / "shops" / f"{clean_id}_pricing.json"
    if local_path.exists():
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                logger.info(f"Loaded shop pricing from local fallback file: {local_path}")
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read local fallback {local_path}: {e}")

    return None


def sync_shop_pricing_from_cloud(
    db_manager: DatabaseManager,
    current_session: UserSession,
    shop_id: str,
    pricing_data: Optional[Dict[str, Any]] = None,
    base_url_template: str = DEFAULT_SHOP_PRICING_URL_TEMPLATE,
) -> Dict[str, Any]:
    """
    Applies developer-managed custom pricing and shop-specific products for a specific shop.
    - If product exists: updates selling_price, purchase_cost, mrp, and name.
    - If product is brand new: automatically creates the product in the local store catalog!
    Leaves existing stock balances untouched.
    """
    clean_id = (shop_id or "SHOP_01").strip().upper()
    if pricing_data is None:
        pricing_data = fetch_shop_pricing(
            shop_id=clean_id,
            base_url_template=base_url_template,
            db_manager=db_manager,
        )

    if not pricing_data:
        return {"status": "skipped", "updated": 0, "created": 0, "shop_id": clean_id, "reason": "No pricing file"}

    price_updates = pricing_data.get("price_updates", [])
    updated_count = 0
    created_count = 0

    prod_service = ProductService(db_manager)
    uoms_list = prod_service.list_uoms()
    uom_by_code = {u["code"]: u["id"] for u in uoms_list}
    taxes_list = prod_service.list_tax_profiles()
    tax_by_name = {t["name"]: t["id"] for t in taxes_list}
    default_unit_id = uom_by_code.get("PCS", next(iter(uom_by_code.values()), 1) if uom_by_code else 1)
    default_tax_id = taxes_list[0]["id"] if taxes_list else 1

    for item in price_updates:
        barcode = str(item.get("barcode", "")).strip() if item.get("barcode") else None
        sku = str(item.get("sku", "")).strip() if item.get("sku") else None
        if not barcode and not sku:
            continue

        item_name = item.get("name") or sku or f"Product {barcode}"
        selling_price = Decimal(str(item.get("selling_price", 0.0)))
        purchase_cost = Decimal(str(item.get("purchase_cost", 0.0)))
        mrp_val = Decimal(str(item.get("mrp", selling_price)))

        with db_manager.session() as session:
            prod = None
            if barcode:
                prod = session.query(Product).filter_by(barcode=barcode).first()
            if not prod and sku:
                prod = session.query(Product).filter_by(sku=sku).first()

            if prod:
                if "selling_price" in item:
                    prod.selling_price = selling_price
                if "purchase_cost" in item:
                    prod.purchase_cost = purchase_cost
                if "mrp" in item:
                    prod.mrp = mrp_val
                if "name" in item and item["name"]:
                    prod.name = item["name"].strip()
                updated_count += 1
                continue

        # If product does NOT exist in store yet, create it as a new product!
        try:
            unit_id = uom_by_code.get(item.get("unit", "PCS"), default_unit_id)
            tax_id = tax_by_name.get(item.get("tax_name", ""), default_tax_id)

            cat_id = None
            if item.get("category"):
                cat_id = prod_service.get_or_create_category(current_session, item["category"])
            brand_id = None
            if item.get("brand"):
                brand_id = prod_service.get_or_create_brand(current_session, item["brand"])

            prod_service.create_product(
                current_session=current_session,
                name=item_name,
                sku=sku or f"SKU-{barcode}",
                barcode=barcode,
                unit_id=unit_id,
                tax_profile_id=tax_id,
                selling_price=selling_price,
                purchase_cost=purchase_cost,
                mrp=mrp_val,
                category_id=cat_id,
                brand_id=brand_id,
                initial_stock=Decimal(str(item.get("initial_stock", "0.000"))),
            )
            created_count += 1
            logger.info(f"Created new product from shop pricing for {clean_id}: '{item_name}' (Barcode: {barcode}, Price: {selling_price})")
        except Exception as err:
            logger.warning(f"Could not create product '{item_name}' from shop pricing: {err}")

    return {
        "status": "success",
        "updated": updated_count,
        "created": created_count,
        "shop_id": clean_id,
        "version": pricing_data.get("version", "1.0.0"),
    }


def run_auto_sync_on_startup(
    db_manager: DatabaseManager,
    current_session: UserSession,
    shop_id: str = "SHOP_01",
) -> Dict[str, Any]:
    """
    Executed silently in background on application startup.
    1. Downloads any brand-new grocery items added by developer to master catalog (from MongoDB or CDN)
    2. Downloads and updates developer-managed retail prices and custom products for this specific shop
    Never throws uncaught exceptions or blocks offline store operations.
    """
    clean_id = (shop_id or "SHOP_01").strip().upper()
    result = {
        "success": False,
        "shop_id": clean_id,
        "new_products": 0,
        "master_refreshed": 0,
        "shop_prices_updated": 0,
        "shop_products_created": 0,
        "message": "",
    }

    # 1. Sync Master Catalog
    try:
        master_res = sync_catalog_from_cloud(
            db_manager=db_manager,
            current_session=current_session,
            preserve_shop_prices=True,
        )
        result["new_products"] = master_res.get("created", 0)
        result["master_refreshed"] = master_res.get("updated", 0)
    except Exception as exc:
        logger.info(f"Startup master catalog sync skipped: {exc}")

    # 2. Sync Shop-Specific Pricing & Custom Products
    try:
        shop_res = sync_shop_pricing_from_cloud(
            db_manager=db_manager,
            current_session=current_session,
            shop_id=clean_id,
        )
        result["shop_prices_updated"] = shop_res.get("updated", 0)
        result["shop_products_created"] = shop_res.get("created", 0)
        result["success"] = True
    except Exception as exc:
        logger.info(f"Startup shop pricing sync skipped: {exc}")

    parts = []
    if result["new_products"] > 0:
        parts.append(f"{result['new_products']} master products added")
    if result["shop_products_created"] > 0:
        parts.append(f"{result['shop_products_created']} custom products added for {clean_id}")
    if result["shop_prices_updated"] > 0:
        parts.append(f"{result['shop_prices_updated']} prices updated for {clean_id}")

    if parts:
        result["message"] = f"Cloud Sync ({clean_id}): " + ", ".join(parts)
    else:
        result["message"] = f"Cloud Sync ({clean_id}): Up to date"

    return result
