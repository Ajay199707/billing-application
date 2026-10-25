"""
Shop settings, configuration, and business profile management service.
"""

import json
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from src.core.database import DatabaseManager
from src.core.exceptions import BillingSystemError, PermissionDeniedError
from src.models import Shop, ShopSettings, AuditLog, ApplicationSettings
from src.services.auth_service import UserSession

logger = logging.getLogger(__name__)

# Profile-specific metadata and defaults
BUSINESS_PROFILES_METADATA = {
    "grocery": {
        "display_name": "Grocery & Supermarkets",
        "description": "FMCG, staples, grains, fruits & vegetables, weighted goods.",
        "default_units": ["KG", "G", "L", "ML", "PACK", "PCS"],
        "supports_fractional_qty": True,
        "features": ["expiry_tracking", "batch_tracking", "scale_barcodes", "reorder_alerts"],
        "tax_defaults": {"grains": "0%", "essentials": "5%", "processed": "12%"},
    },
    "hardware": {
        "display_name": "Electrical & Hardware",
        "description": "Electrical components, tools, sanitary ware, wires, pipes.",
        "default_units": ["PCS", "BOX", "MTR", "PACK", "SET"],
        "supports_fractional_qty": True,
        "features": ["model_number", "technical_specs", "warranty_months", "serial_tracking"],
        "tax_defaults": {"general": "18%", "fittings": "18%"},
    },
    "textile": {
        "display_name": "Clothing & Textile",
        "description": "Garments, fabrics, footwear, accessories with sizes and colors.",
        "default_units": ["PCS", "MTR", "PAIR", "SET"],
        "supports_fractional_qty": True,
        "features": ["variant_matrix", "size_attribute", "color_attribute", "fabric_type"],
        "tax_defaults": {"apparel_under_1000": "5%", "apparel_above_1000": "12%"},
    },
    "electronics": {
        "display_name": "Mobile & Electronics",
        "description": "Smartphones, laptops, accessories, consumer appliances.",
        "default_units": ["PCS", "BOX", "SET"],
        "supports_fractional_qty": False,
        "features": ["serial_imei_tracking", "warranty_tracking", "brand_model_filter"],
        "tax_defaults": {"mobile_phones": "18%", "accessories": "18%", "luxury": "28%"},
    },
    "pharmacy": {
        "display_name": "Medical & Pharmacy",
        "description": "Prescription medicines, OTC drugs, medical supplies, surgicals.",
        "default_units": ["STRIP", "PCS", "BOX", "BOTTLE"],
        "supports_fractional_qty": False,
        "features": ["strict_batch_expiry", "generic_name_search", "fefo_dispensing", "schedule_h_alert"],
        "tax_defaults": {"lifesaving": "5%", "medicines": "12%"},
    },
    "general": {
        "display_name": "General Retail",
        "description": "Versatile retail store accommodating mixed merchandise.",
        "default_units": ["PCS", "PACK", "BOX", "KG"],
        "supports_fractional_qty": True,
        "features": ["flexible_attributes", "standard_pos", "barcode_lookup"],
        "tax_defaults": {"standard": "18%"},
    },
}


class SettingsService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_shop_info(self) -> Dict[str, Any]:
        """Retrieves active shop metadata and settings."""
        with self.db.session() as session:
            shop = session.query(Shop).first()
            if not shop:
                raise BillingSystemError("No shop profile configured. Please run setup.", code="SHOP_NOT_FOUND")

            settings = shop.settings
            return {
                "id": shop.id,
                "name": shop.name,
                "legal_name": shop.legal_name or "",
                "gstin": shop.gstin or "",
                "address_line1": shop.address_line1 or "",
                "address_line2": shop.address_line2 or "",
                "city": shop.city or "",
                "state_code": shop.state_code,
                "state_name": shop.state_name,
                "pincode": shop.pincode or "",
                "phone": shop.phone or "",
                "email": shop.email or "",
                "currency_symbol": shop.currency_symbol,
                "business_profile": settings.business_profile if settings else "general",
                "invoice_prefix": settings.invoice_prefix if settings else "INV-",
                "receipt_format": settings.receipt_format if settings else "80mm",
                "thermal_printer_name": settings.thermal_printer_name if settings else "",
                "enable_negative_stock": settings.enable_negative_stock if settings else False,
                "low_stock_threshold_default": float(settings.low_stock_threshold_default) if settings else 5.0,
                "tax_inclusive_default": settings.tax_inclusive_default if settings else False,
                "invoice_footer_text": settings.invoice_footer_text if settings else "",
            }

    def update_shop_details(self, current_session: UserSession, details: Dict[str, Any]) -> None:
        """Updates shop contact and legal details."""
        if not current_session.has_permission("settings:manage"):
            raise PermissionDeniedError("settings:manage")

        with self.db.session() as session:
            shop = session.query(Shop).first()
            if not shop:
                shop = Shop(name=details.get("name", "New Shop"), state_code="33", state_name="Tamil Nadu")
                session.add(shop)

            shop.name = details.get("name", shop.name)
            shop.legal_name = details.get("legal_name", shop.legal_name)
            shop.gstin = details.get("gstin", shop.gstin)
            shop.address_line1 = details.get("address_line1", shop.address_line1)
            shop.address_line2 = details.get("address_line2", shop.address_line2)
            shop.city = details.get("city", shop.city)
            shop.state_code = details.get("state_code", shop.state_code)
            shop.state_name = details.get("state_name", shop.state_name)
            shop.pincode = details.get("pincode", shop.pincode)
            shop.phone = details.get("phone", shop.phone)
            shop.email = details.get("email", shop.email)

            if not shop.settings:
                shop.settings = ShopSettings(shop_id=shop.id)

            if "business_profile" in details:
                shop.settings.business_profile = details["business_profile"]
            if "invoice_prefix" in details:
                shop.settings.invoice_prefix = details["invoice_prefix"]
            if "receipt_format" in details:
                shop.settings.receipt_format = details["receipt_format"]
            if "thermal_printer_name" in details:
                shop.settings.thermal_printer_name = details["thermal_printer_name"]
            if "enable_negative_stock" in details:
                shop.settings.enable_negative_stock = bool(details["enable_negative_stock"])
            if "low_stock_threshold_default" in details:
                shop.settings.low_stock_threshold_default = float(details["low_stock_threshold_default"])
            if "tax_inclusive_default" in details:
                shop.settings.tax_inclusive_default = bool(details["tax_inclusive_default"])
            if "invoice_footer_text" in details:
                shop.settings.invoice_footer_text = details["invoice_footer_text"]

            audit = AuditLog(
                user_id=current_session.user_id,
                action="SETTINGS_UPDATED",
                entity_name="ShopSettings",
                entity_id=str(shop.id),
                details_json=json.dumps(details),
            )
            session.add(audit)

    def get_available_profiles(self) -> Dict[str, Any]:
        """Returns the dictionary of all supported business profiles and metadata."""
        return BUSINESS_PROFILES_METADATA

    def get_cloud_shop_id(self) -> str:
        """Returns the configured Cloud Shop ID (e.g. SHOP_01) used for remote price updates."""
        with self.db.session() as session:
            row = session.query(ApplicationSettings).filter_by(key="cloud_shop_id").first()
            if row:
                try:
                    return str(json.loads(row.value_json))
                except Exception:
                    return str(row.value_json).strip('"')
            return "SHOP_01"

    def set_cloud_shop_id(self, shop_id: str) -> None:
        """Sets the Cloud Shop ID for automatic remote pricing sync."""
        clean_id = (shop_id or "SHOP_01").strip().upper()
        with self.db.session() as session:
            row = session.query(ApplicationSettings).filter_by(key="cloud_shop_id").first()
            if not row:
                row = ApplicationSettings(
                    key="cloud_shop_id",
                    value_json=json.dumps(clean_id),
                    description="Cloud Sync Shop Identifier",
                )
                session.add(row)
            else:
                row.value_json = json.dumps(clean_id)
