"""
Master Grocery and Supermarket Catalog Service.
Provides barcode auto-fill lookup for the product entry dialog
and a 1-click starter catalog seeder for grocery stores.
"""

from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from src.core.database import DatabaseManager
from src.models import (
    Product,
    Category,
    Brand,
    UnitOfMeasure,
    ProductTaxProfile,
)
from src.services.auth_service import UserSession
from src.services.product_service import ProductService

# Master Catalog: 80+ Pre-Configured Fast-Moving Grocery & FMCG Products
# Tuple: (Name, SKU, Barcode, Category, Brand, Unit, TaxProfileName, PurchaseCost, SellingPrice, MRP, ReorderLevel, InitialStock)
MASTER_GROCERY_CATALOG = [
    # --- 1. Grains, Atta & Flours (GST 5%) ---
    ("Aashirvaad Shudh Chakki Atta 1kg", "AASH-ATTA-1KG", "8901030010004", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "52.00", "62.00", "68.00", "15", "50"),
    ("Aashirvaad Shudh Chakki Atta 5kg", "AASH-ATTA-5KG", "8901030010011", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "245.00", "280.00", "295.00", "10", "40"),
    ("Aashirvaad Shudh Chakki Atta 10kg", "AASH-ATTA-10KG", "8901030010028", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "470.00", "540.00", "565.00", "10", "35"),
    ("Fortune Chakki Fresh Atta 5kg", "FORT-ATTA-5KG", "8906007280015", "Grains & Flours", "Fortune", "PACK", "GST 5% (Essential Food / Staples)", "230.00", "265.00", "280.00", "8", "30"),
    ("India Gate Basmati Rice Feast Rozzana 1kg", "IG-ROZZANA-1KG", "8901725181014", "Grains & Flours", "India Gate", "PACK", "GST 5% (Essential Food / Staples)", "85.00", "105.00", "120.00", "15", "50"),
    ("India Gate Basmati Rice Feast Rozzana 5kg", "IG-ROZZANA-5KG", "8901725181021", "Grains & Flours", "India Gate", "PACK", "GST 5% (Essential Food / Staples)", "410.00", "495.00", "550.00", "8", "25"),
    ("Daawat Super Basmati Rice 1kg", "DAAW-SUPER-1KG", "8901537001018", "Grains & Flours", "Daawat", "PACK", "GST 5% (Essential Food / Staples)", "125.00", "155.00", "175.00", "10", "40"),
    ("Sona Masoori Raw Rice 5kg Bag", "RICE-SONA-5KG", "8901725181038", "Grains & Flours", "Farm Fresh", "PACK", "GST 5% (Essential Food / Staples)", "270.00", "315.00", "340.00", "10", "30"),
    ("Roasted Rava / Sooji 500g", "RAVA-ROAST-500G", "8901030010035", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "34.00", "42.00", "45.00", "12", "45"),
    ("All Purpose Maida 500g", "MAIDA-500G", "8901030010042", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "30.00", "38.00", "40.00", "12", "50"),

    # --- 2. Dals & Pulses (GST 5%) ---
    ("Tata Sampann Toor Dal 500g", "TATA-TOOR-500G", "8901063141003", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "75.00", "90.00", "98.00", "15", "50"),
    ("Tata Sampann Unpolished Toor Dal 1kg", "TATA-TOOR-1KG", "8901063141010", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "145.00", "175.00", "190.00", "15", "60"),
    ("Tata Sampann Moong Dal 1kg", "TATA-MOONG-1KG", "8901063141027", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "120.00", "148.00", "165.00", "15", "50"),
    ("Tata Sampann Chana Dal 1kg", "TATA-CHANA-1KG", "8901063141034", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "92.00", "115.00", "125.00", "12", "40"),
    ("Tata Sampann Urad Dal White Whole 1kg", "TATA-URAD-1KG", "8901063141041", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "148.00", "180.00", "198.00", "12", "45"),
    ("Kabuli Chana Premium 500g", "KABULI-500G", "8901063141058", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "65.00", "82.00", "90.00", "10", "35"),

    # --- 3. Edible Cooking Oils & Pure Ghee (GST 5% & 12%) ---
    ("Fortune Sunlite Refined Sunflower Oil 1L Pouch", "FORT-SUN-1L", "8906007281012", "Edible Oils & Ghee", "Fortune", "POUCH", "GST 5% (Essential Food / Staples)", "115.00", "132.00", "145.00", "20", "80"),
    ("Fortune Sunlite Refined Sunflower Oil 5L Can", "FORT-SUN-5L", "8906007281029", "Edible Oils & Ghee", "Fortune", "CAN", "GST 5% (Essential Food / Staples)", "560.00", "640.00", "695.00", "5", "20"),
    ("Gold Winner Refined Sunflower Oil 1L Pouch", "GW-SUN-1L", "8906014640017", "Edible Oils & Ghee", "Gold Winner", "POUCH", "GST 5% (Essential Food / Staples)", "118.00", "135.00", "148.00", "20", "90"),
    ("Saffola Gold Pro Healthy Lifestyle Oil 1L Pouch", "SAFF-GOLD-1L", "8901088001016", "Edible Oils & Ghee", "Saffola", "POUCH", "GST 5% (Essential Food / Staples)", "148.00", "172.00", "190.00", "15", "60"),
    ("Gemini Pure Groundnut Oil 1L Pouch", "GEM-GNUT-1L", "8906007281036", "Edible Oils & Ghee", "Gemini", "POUCH", "GST 5% (Essential Food / Staples)", "165.00", "190.00", "210.00", "10", "40"),
    ("Fortune Kachi Ghani Mustard Oil 1L Pet Bottle", "FORT-MUST-1L", "8906007281043", "Edible Oils & Ghee", "Fortune", "BOTTLE", "GST 5% (Essential Food / Staples)", "130.00", "150.00", "165.00", "10", "40"),
    ("Idhayam Sesame Gingelly Oil 500ml Pouch", "IDH-GING-500ML", "8901396001012", "Edible Oils & Ghee", "Idhayam", "POUCH", "GST 5% (Essential Food / Staples)", "145.00", "170.00", "185.00", "12", "50"),
    ("Idhayam Sesame Gingelly Oil 1L Bottle", "IDH-GING-1L", "8901396001029", "Edible Oils & Ghee", "Idhayam", "BOTTLE", "GST 5% (Essential Food / Staples)", "285.00", "330.00", "360.00", "10", "40"),
    ("Amul Pure Ghee 500ml Refill Pack", "AMUL-GHEE-500ML", "8901262010014", "Edible Oils & Ghee", "Amul", "PACK", "GST 12% (Standard Food / Concessional)", "270.00", "310.00", "335.00", "12", "45"),
    ("Aashirvaad Svasti Pure Cow Ghee 1L Tin", "AASH-GHEE-1L", "8901030010059", "Edible Oils & Ghee", "Aashirvaad", "TIN", "GST 12% (Standard Food / Concessional)", "580.00", "665.00", "720.00", "6", "25"),

    # --- 4. Spices, Salt & Sugar (GST 5%) ---
    ("Tata Salt Iodized Vacuum Evaporated 1kg", "TATA-SALT-1KG", "8901063010019", "Spices, Salt & Sugar", "Tata Salt", "PACK", "GST 5% (Essential Food / Staples)", "22.50", "27.00", "28.00", "30", "150"),
    ("Tata Salt Lite Low Sodium 1kg", "TATA-SALT-LITE", "8901063010026", "Spices, Salt & Sugar", "Tata Salt", "PACK", "GST 5% (Essential Food / Staples)", "36.00", "44.00", "48.00", "15", "50"),
    ("Madhur Pure & Hygienic Sugar 500g", "MADH-SUGAR-500G", "8906007282026", "Spices, Salt & Sugar", "Madhur", "PACK", "GST 5% (Essential Food / Staples)", "22.00", "26.00", "28.00", "15", "40"),
    ("Madhur Pure & Hygienic Sugar 1kg", "MADH-SUGAR-1KG", "8906007282019", "Spices, Salt & Sugar", "Madhur", "PACK", "GST 5% (Essential Food / Staples)", "42.00", "48.00", "52.00", "20", "60"),
    ("Madhur Pure & Hygienic Sugar 5kg", "MADH-SUGAR-5KG", "8906007282033", "Spices, Salt & Sugar", "Madhur", "PACK", "GST 5% (Essential Food / Staples)", "205.00", "235.00", "250.00", "10", "40"),
    ("Aashirvaad Chilli Powder 200g Pouch", "AASH-CHILLI-200G", "8901030010066", "Spices, Salt & Sugar", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "62.00", "76.00", "84.00", "15", "60"),
    ("Aashirvaad Turmeric Haldi Powder 200g", "AASH-HALDI-200G", "8901030010073", "Spices, Salt & Sugar", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "48.00", "58.00", "65.00", "15", "60"),
    ("Aashirvaad Coriander Dhania Powder 200g", "AASH-DHANIA-200G", "8901030010080", "Spices, Salt & Sugar", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "46.00", "56.00", "62.00", "15", "50"),
    ("Everest Garam Masala 100g Carton", "EVER-GMAS-100G", "8901786101013", "Spices, Salt & Sugar", "Everest", "BOX", "GST 5% (Essential Food / Staples)", "70.00", "85.00", "94.00", "12", "45"),
    ("MTR Sambar Powder 200g Pouch", "MTR-SAMBAR-200G", "8901042961011", "Spices, Salt & Sugar", "MTR", "PACK", "GST 5% (Essential Food / Staples)", "74.00", "90.00", "99.00", "15", "55"),

    # --- 5. Dairy & Bakery (GST 0%, 12%, 18%) ---
    ("Amul Taaza Homogenised Toned Milk 1L Tetra", "AMUL-TAAZA-1L", "8901262020013", "Dairy & Bakery", "Amul", "PACK", "GST 0% (Exempt / Nil Rated)", "68.00", "74.00", "75.00", "20", "100"),
    ("Britannia 100% Whole Wheat Bread 400g", "BRIT-BREAD-400G", "8901063020018", "Dairy & Bakery", "Britannia", "PACK", "GST 0% (Exempt / Nil Rated)", "38.00", "44.00", "45.00", "10", "30"),
    ("Amul Pasteurised Butter 100g", "AMUL-BUTTER-100G", "8901262030012", "Dairy & Bakery", "Amul", "PACK", "GST 12% (Standard Food / Concessional)", "48.00", "56.00", "58.00", "15", "60"),
    ("Amul Pasteurised Butter 500g", "AMUL-BUTTER-500G", "8901262030029", "Dairy & Bakery", "Amul", "PACK", "GST 12% (Standard Food / Concessional)", "235.00", "272.00", "285.00", "10", "40"),
    ("Amul Cheese Slices 200g (10 Slices)", "AMUL-CHEESE-200G", "8901262040011", "Dairy & Bakery", "Amul", "PACK", "GST 12% (Standard Food / Concessional)", "128.00", "148.00", "155.00", "10", "35"),
    ("Milky Mist Fresh Paneer 200g Vacuum Pack", "MM-PANEER-200G", "8904082700018", "Dairy & Bakery", "Milky Mist", "PACK", "GST 5% (Essential Food / Staples)", "82.00", "98.00", "105.00", "15", "40"),
    ("Kellogg's Corn Flakes Original 500g", "KELL-CORN-500G", "8901499010011", "Dairy & Bakery", "Kellogg's", "BOX", "GST 18% (Standard Goods & Services)", "160.00", "190.00", "210.00", "8", "30"),
    ("Quaker Rolled Oats 1kg Pouch", "QUAK-OATS-1KG", "8901491101014", "Dairy & Bakery", "Quaker", "PACK", "GST 18% (Standard Goods & Services)", "155.00", "185.00", "205.00", "10", "35"),

    # --- 6. Beverages & Hot Drinks (GST 5% & 18%) ---
    ("Brooke Bond Red Label Tea 500g Carton", "RED-LABEL-500G", "8901030020010", "Beverages", "Red Label", "BOX", "GST 5% (Essential Food / Staples)", "175.00", "210.00", "230.00", "15", "60"),
    ("Tata Tea Gold Rich Taste 500g", "TATA-GOLD-500G", "8901063030017", "Beverages", "Tata Tea", "PACK", "GST 5% (Essential Food / Staples)", "210.00", "255.00", "275.00", "15", "50"),
    ("Bru Instant Coffee 100g Pouch", "BRU-INST-100G", "8901030030019", "Beverages", "Bru", "POUCH", "GST 18% (Standard Goods & Services)", "155.00", "185.00", "200.00", "12", "50"),
    ("Nescafe Classic Instant Coffee Jar 50g", "NESC-CLASS-50G", "8901058850015", "Beverages", "Nescafe", "BOTTLE", "GST 18% (Standard Goods & Services)", "130.00", "155.00", "170.00", "10", "40"),
    ("Horlicks Classic Malt Health Drink 500g Pet Jar", "HORL-MALT-500G", "8901571001012", "Beverages", "Horlicks", "BOTTLE", "GST 18% (Standard Goods & Services)", "215.00", "255.00", "275.00", "10", "40"),
    ("Boost Energy & Stamina Drink 500g Jar", "BOOST-JAR-500G", "8901571002019", "Beverages", "Boost", "BOTTLE", "GST 18% (Standard Goods & Services)", "220.00", "260.00", "285.00", "10", "40"),
    ("Coca Cola Original Taste 750ml Pet Bottle", "COKE-750ML", "8901764012014", "Beverages", "Coca Cola", "BOTTLE", "GST 18% (Standard Goods & Services)", "32.00", "38.00", "40.00", "24", "96"),

    # --- 7. Biscuits, Snacks & Instant Food (GST 12% & 18%) ---
    ("Parle-G Gold Gluco Biscuits 1kg Family Pack", "PARLE-G-1KG", "8901719101011", "Biscuits & Snacks", "Parle", "PACK", "GST 18% (Standard Goods & Services)", "78.00", "92.00", "100.00", "20", "80"),
    ("Britannia Good Day Butter Cookies 600g Value Pack", "BRIT-GDAY-600G", "8901063040016", "Biscuits & Snacks", "Britannia", "PACK", "GST 18% (Standard Goods & Services)", "105.00", "125.00", "140.00", "15", "60"),
    ("Britannia Marie Gold Biscuits 1kg Jumbo Pack", "BRIT-MARIE-1KG", "8901063040023", "Biscuits & Snacks", "Britannia", "PACK", "GST 18% (Standard Goods & Services)", "112.00", "135.00", "150.00", "15", "60"),
    ("Sunfeast Dark Fantasy Choco Fills 300g", "DARK-FANT-300G", "8901030040018", "Biscuits & Snacks", "Sunfeast", "BOX", "GST 18% (Standard Goods & Services)", "115.00", "138.00", "150.00", "10", "45"),
    ("Maggi 2-Minute Masala Instant Noodles 420g (6-Pack)", "MAGGI-6PACK", "8901058852019", "Biscuits & Snacks", "Maggi", "PACK", "GST 12% (Standard Food / Concessional)", "78.00", "92.00", "96.00", "20", "80"),
    ("Lay's India's Magic Masala Potato Chips 50g", "LAYS-MASALA-50G", "8901491102011", "Biscuits & Snacks", "Lay's", "PACK", "GST 18% (Standard Goods & Services)", "16.50", "19.00", "20.00", "30", "120"),
    ("Kurkure Masala Munch Crispy Snacks 90g", "KURK-MUNCH-90G", "8901491103018", "Biscuits & Snacks", "Kurkure", "PACK", "GST 18% (Standard Goods & Services)", "16.50", "19.00", "20.00", "30", "120"),
    ("Kissan Fresh Tomato Ketchup 1kg Squeezo Pouch", "KISSAN-KETCH-1KG", "8901030050017", "Biscuits & Snacks", "Kissan", "POUCH", "GST 12% (Standard Food / Concessional)", "110.00", "132.00", "145.00", "10", "40"),

    # --- 8. Personal Care & Soaps (GST 18%) ---
    ("Dettol Original Germ Protection Soap 125g (Buy 3 Get 1)", "DETT-SOAP-4X125", "8901396112014", "Personal Care & Soaps", "Dettol", "PACK", "GST 18% (Standard Goods & Services)", "165.00", "195.00", "220.00", "15", "60"),
    ("Lifebuoy Total Germ Protection Soap 125g (Pack of 4)", "LIFE-SOAP-4X125", "8901030060016", "Personal Care & Soaps", "Lifebuoy", "PACK", "GST 18% (Standard Goods & Services)", "125.00", "148.00", "165.00", "15", "60"),
    ("Dove Cream Beauty Bathing Bar 100g (Pack of 3)", "DOVE-SOAP-3X100", "8901030060023", "Personal Care & Soaps", "Dove", "PACK", "GST 18% (Standard Goods & Services)", "195.00", "230.00", "255.00", "10", "40"),
    ("Clinic Plus Strong & Long Shampoo 650ml Bottle", "CLINIC-SHAMP-650", "8901030070015", "Personal Care & Soaps", "Clinic Plus", "BOTTLE", "GST 18% (Standard Goods & Services)", "310.00", "365.00", "410.00", "8", "30"),
    ("Head & Shoulders Anti-Dandruff Smooth & Silky 650ml", "HS-SHAMP-650ML", "8901314010019", "Personal Care & Soaps", "Head & Shoulders", "BOTTLE", "GST 18% (Standard Goods & Services)", "420.00", "495.00", "550.00", "6", "25"),
    ("Colgate Strong Teeth Dental Cream Toothpaste 500g Saver", "COLG-DENT-500G", "8901314020018", "Personal Care & Soaps", "Colgate", "PACK", "GST 18% (Standard Goods & Services)", "190.00", "225.00", "250.00", "15", "50"),
    ("Close Up Everfresh Red Hot Gel Toothpaste 300g (Pack of 2)", "CLOSEUP-RED-300G", "8901030080014", "Personal Care & Soaps", "Close Up", "PACK", "GST 18% (Standard Goods & Services)", "145.00", "172.00", "190.00", "12", "45"),
    ("Parachute 100% Pure Coconut Hair Oil 500ml Bottle", "PARA-OIL-500ML", "8901088010018", "Personal Care & Soaps", "Parachute", "BOTTLE", "GST 18% (Standard Goods & Services)", "185.00", "215.00", "235.00", "12", "50"),

    # --- 9. Household & Cleaning (GST 18%) ---
    ("Surf Excel Quick Wash Detergent Powder 1kg Pouch", "SURF-QW-1KG", "8901030090013", "Household & Cleaning", "Surf Excel", "PACK", "GST 18% (Standard Goods & Services)", "125.00", "148.00", "160.00", "20", "80"),
    ("Surf Excel Easy Wash Detergent Powder 5kg Bag", "SURF-EW-5KG", "8901030090020", "Household & Cleaning", "Surf Excel", "PACK", "GST 18% (Standard Goods & Services)", "580.00", "680.00", "740.00", "6", "25"),
    ("Rin Detergent Bar 250g (Pack of 4)", "RIN-BAR-4X250G", "8901030090037", "Household & Cleaning", "Rin", "PACK", "GST 18% (Standard Goods & Services)", "68.00", "80.00", "88.00", "20", "90"),
    ("Vim Dishwash Gel Lemon 750ml Refill Pouch", "VIM-GEL-750ML", "8901030100019", "Household & Cleaning", "Vim", "POUCH", "GST 18% (Standard Goods & Services)", "130.00", "155.00", "170.00", "15", "60"),
    ("Vim Dishwash Bar 300g", "VIM-BAR-300G", "8901030100026", "Household & Cleaning", "Vim", "PACK", "GST 18% (Standard Goods & Services)", "24.00", "29.00", "32.00", "25", "100"),
    ("Harpic Power Plus Disinfectant Toilet Cleaner 1L", "HARPIC-1L", "8901396120019", "Household & Cleaning", "Harpic", "BOTTLE", "GST 18% (Standard Goods & Services)", "160.00", "190.00", "215.00", "12", "50"),
    ("Lizol Disinfectant Surface & Floor Cleaner Citrus 1L", "LIZOL-CITRUS-1L", "8901396130018", "Household & Cleaning", "Lizol", "BOTTLE", "GST 18% (Standard Goods & Services)", "170.00", "200.00", "225.00", "12", "50"),
    ("Colin Glass & Household Surface Cleaner Spray 500ml", "COLIN-SPRAY-500", "8901396140017", "Household & Cleaning", "Colin", "BOTTLE", "GST 18% (Standard Goods & Services)", "85.00", "102.00", "115.00", "10", "40"),

    # --- 10. Fresh Produce & Loose Staples (GST 0% - Scale & Cashier Short-Codes) ---
    ("Fresh Onions (Loose)", "VEG-ONION-KG", "101", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 0% (Exempt / Nil Rated)", "24.00", "32.00", "35.00", "50", "200"),
    ("Fresh Potatoes (Loose)", "VEG-POTATO-KG", "102", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 0% (Exempt / Nil Rated)", "28.00", "36.00", "40.00", "50", "200"),
    ("Fresh Country Tomatoes (Loose)", "VEG-TOMATO-KG", "103", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 0% (Exempt / Nil Rated)", "18.00", "26.00", "30.00", "40", "150"),
    ("Fresh Royal Gala Apples (Loose)", "FRUIT-APPLE-KG", "104", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 0% (Exempt / Nil Rated)", "120.00", "165.00", "180.00", "20", "80"),
    ("Fresh Robusta Bananas (Loose)", "FRUIT-BANANA-KG", "105", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 0% (Exempt / Nil Rated)", "32.00", "45.00", "50.00", "25", "100"),
]

# Fast in-memory lookup dictionary indexed by barcode string
_CATALOG_INDEX: Dict[str, Dict[str, Any]] = {}
for _item in MASTER_GROCERY_CATALOG:
    _name, _sku, _barcode, _cat, _brand, _unit, _tax, _cost, _price, _mrp, _reorder, _stock = _item
    _CATALOG_INDEX[str(_barcode).strip()] = {
        "name": _name,
        "sku": _sku,
        "barcode": str(_barcode).strip(),
        "category": _cat,
        "brand": _brand,
        "unit": _unit,
        "tax_name": _tax,
        "purchase_cost": Decimal(_cost),
        "selling_price": Decimal(_price),
        "mrp": Decimal(_mrp),
        "reorder_level": Decimal(_reorder),
        "initial_stock": Decimal(_stock),
    }


def lookup_barcode(barcode: str) -> Optional[Dict[str, Any]]:
    """
    Looks up a barcode in the master grocery catalog.
    Returns matched item dictionary if found, else None.
    """
    clean_code = str(barcode).strip()
    return _CATALOG_INDEX.get(clean_code)


def seed_starter_catalog(db_manager: DatabaseManager, current_session: UserSession) -> Tuple[int, int]:
    """
    Populates the starter grocery catalog into the database.
    Returns (created_count, updated_count).
    """
    prod_service = ProductService(db_manager)

    # Cache UOMs and Tax profiles
    uoms_list = prod_service.list_uoms()
    uom_by_code = {u["code"]: u["id"] for u in uoms_list}
    taxes_list = prod_service.list_tax_profiles()
    tax_by_name = {t["name"]: t["id"] for t in taxes_list}

    created_count = 0
    updated_count = 0

    for item in MASTER_GROCERY_CATALOG:
        (
            name, sku, barcode, cat_name, brand_name,
            uom_code, tax_name, cost_s, price_s, mrp_s,
            reorder_s, stock_s
        ) = item

        cat_id = prod_service.get_or_create_category(current_session, cat_name)
        brand_id = prod_service.get_or_create_brand(current_session, brand_name)

        unit_id = uom_by_code.get(uom_code, uom_by_code.get("PCS", 1))
        tax_profile_id = tax_by_name.get(tax_name, taxes_list[0]["id"] if taxes_list else 1)

        purchase_cost = Decimal(cost_s)
        selling_price = Decimal(price_s)
        mrp = Decimal(mrp_s)
        reorder_level = Decimal(reorder_s)
        initial_stock = Decimal(stock_s)

        with db_manager.session() as session:
            existing = session.query(Product).filter((Product.sku == sku) | (Product.barcode == barcode)).first()
            if existing:
                existing.name = name
                existing.selling_price = selling_price
                existing.purchase_cost = purchase_cost
                existing.mrp = mrp
                existing.reorder_level = reorder_level
                existing.category_id = cat_id
                existing.brand_id = brand_id
                existing.unit_id = unit_id
                existing.tax_profile_id = tax_profile_id
                if existing.inventory_balance and existing.inventory_balance.quantity_on_hand < initial_stock:
                    existing.inventory_balance.quantity_on_hand = initial_stock
                updated_count += 1
                continue

        # Create fresh product
        prod_service.create_product(
            current_session=current_session,
            name=name,
            sku=sku,
            barcode=barcode,
            unit_id=unit_id,
            tax_profile_id=tax_profile_id,
            selling_price=selling_price,
            purchase_cost=purchase_cost,
            mrp=mrp,
            reorder_level=reorder_level,
            category_id=cat_id,
            brand_id=brand_id,
            initial_stock=initial_stock,
        )
        created_count += 1

    return created_count, updated_count
