"""
Cloud Master Catalog Sync Service.
Connects to the central cloud catalog (hosted on GitHub raw CDN)
to fetch new products, updated barcodes, and tax classifications
without overwriting a shop's private selling prices or stock balances.
"""

import json
import logging
import urllib.request
import urllib.error
from decimal import Decimal
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
) -> Dict[str, Any]:
    """
    Downloads the master catalog JSON from the cloud repository.
    Raises CloudSyncError if network connection fails.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AJBillingSoftware-POS/1.0 (Windows; CloudSync)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                raise CloudSyncError(f"Cloud server returned HTTP status {response.status}")
            raw_data = response.read().decode("utf-8")
            return json.loads(raw_data)
    except urllib.error.URLError as err:
        logger.error(f"Failed to reach cloud catalog at {url}: {err}")
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
        cloud_data = fetch_cloud_catalog(url=url)

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
