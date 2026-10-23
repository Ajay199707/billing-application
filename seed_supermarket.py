"""
Full-Fledged Supermarket Database Seeder.
Populates an authentic, production-grade Indian Supermarket / Grocery retail catalog:
- 55+ FMCG Products across Staples, Dals, Edible Oils, Spices, Dairy, Bakery, Beverages, Snacks, Personal Care & Cleaning.
- Loose produce short codes (101, 102, 103, 104, 105) for rapid cashier entry & electronic scale barcodes.
- Realistic EAN-13 barcodes (890...), statutory HSN codes, correct GST rates, wholesale purchase costs, MRPs, and retail prices.
- Initial stock balances & reorder levels.
- Supermarket FMCG Distributors & Suppliers.
- Walk-in, Privilege Loyalty, and B2B Hotel Customers.
"""

import sys
from decimal import Decimal
from typing import List, Dict, Any, Optional

from src.core.database import get_db_manager, DatabaseConfig
from src.core.security import hash_password
from src.models import (
    Base, Shop, User, Role, Permission, Category, Brand,
    UnitOfMeasure, ProductTaxProfile, Product, InventoryBalance,
    ProductBarcode, Supplier, Customer
)
from src.services.auth_service import UserSession
from src.services.product_service import ProductService
from src.services.db_init_service import initialize_database, setup_initial_shop_and_admin


SUPERMARKET_SUPPLIERS = [
    {
        "name": "Hindustan Unilever Ltd (HUL) Distribution",
        "company_name": "HUL C&F Agency",
        "gstin": "33AAACH1234A1Z1",
        "phone": "9840123456",
        "email": "hul.orders@agency.com",
        "address": "Plot 14, Industrial Estate, Guindy, Chennai",
        "state_code": "33",
        "payment_terms_days": 15,
    },
    {
        "name": "ITC Limited Wholesale & Logistics",
        "company_name": "ITC Foods & Personal Care Distributor",
        "gstin": "33AAACI5678B1Z2",
        "phone": "9840234567",
        "email": "itc.dist@fmcgagency.com",
        "address": "Door 82, Mount Road, Chennai",
        "state_code": "33",
        "payment_terms_days": 15,
    },
    {
        "name": "Nestle India Wholesale Agency",
        "company_name": "Nestle Dairy & Confectionery Depot",
        "gstin": "33AAACN9012C1Z3",
        "phone": "9840345678",
        "email": "nestle.supply@fmcg.com",
        "address": "No 45, Ambattur Industrial Estate, Chennai",
        "state_code": "33",
        "payment_terms_days": 7,
    },
    {
        "name": "Amul GCMMF Dairy Agency",
        "company_name": "Gujarat Co-operative Milk Marketing Federation",
        "gstin": "33AAACG3456D1Z4",
        "phone": "9840456789",
        "email": "amul.chennai@gcmmf.coop",
        "address": "Amul Cold Storage Complex, Koyambedu, Chennai",
        "state_code": "33",
        "payment_terms_days": 3,
    },
    {
        "name": "Adani Wilmar & Fortune Depot",
        "company_name": "Adani Wilmar Edible Oil Distributor",
        "gstin": "33AAACA7890E1Z5",
        "phone": "9840567890",
        "email": "fortune.oils@agency.com",
        "address": "Godown 22, Port Trust Road, Chennai",
        "state_code": "33",
        "payment_terms_days": 10,
    },
    {
        "name": "APMC Grain & Pulse Wholesale Mandi",
        "company_name": "APMC Wholesale Merchant Association",
        "gstin": "33AAACP1122F1Z6",
        "phone": "9840678901",
        "email": "apmc.grains@mandi.com",
        "address": "Grain Market Yard, Koyambedu Wholesale Complex, Chennai",
        "state_code": "33",
        "payment_terms_days": 0,
    },
    {
        "name": "Reckitt Benckiser Hygiene Distributors",
        "company_name": "RB Health & Hygiene Agency",
        "gstin": "33AAACR3344G1Z7",
        "phone": "9840789012",
        "email": "rb.chennai@distributors.com",
        "address": "SIDCO Industrial Area, Chennai",
        "state_code": "33",
        "payment_terms_days": 15,
    },
]

SUPERMARKET_CUSTOMERS = [
    {
        "name": "Walk-in Cash Customer",
        "phone": None,
        "email": None,
        "gstin": None,
        "address": "Counter Customer",
        "state_code": "33",
        "loyalty_points": Decimal("0.00"),
    },
    {
        "name": "Mr. Ramesh Kumar (Privilege Member #1001)",
        "phone": "9876543210",
        "email": "ramesh.k@gmail.com",
        "gstin": None,
        "address": "Flat 3B, Sunshine Apartments, Anna Nagar, Chennai",
        "state_code": "33",
        "loyalty_points": Decimal("45.50"),
    },
    {
        "name": "Mrs. Priya Sundaram",
        "phone": "9876543211",
        "email": "priya.s@yahoo.com",
        "gstin": None,
        "address": "14/2 4th Main Road, T. Nagar, Chennai",
        "state_code": "33",
        "loyalty_points": Decimal("22.00"),
    },
    {
        "name": "Sree Krishna Bhavan Veg Hotel",
        "phone": "9876543212",
        "email": "billing@krishnabhavan.in",
        "gstin": "33AAAAA0000A1Z5",
        "address": "12 Gandhi High Road, Chennai",
        "state_code": "33",
        "loyalty_points": Decimal("150.00"),
    },
]

# 55+ Full-Fledged Supermarket Products
# Tuple format:
# (Name, SKU, Barcode, Category, Brand, Unit, TaxProfileName, PurchaseCost, SellingPrice, MRP, ReorderLevel, InitialStock)
SUPERMARKET_CATALOG = [
    # --- 1. Grains, Atta & Flours (GST 0% or 5%) ---
    ("Aashirvaad Shudh Chakki Atta 5kg", "AASH-ATTA-5KG", "8901030010011", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "245.00", "280.00", "295.00", "10", "40"),
    ("Aashirvaad Shudh Chakki Atta 10kg", "AASH-ATTA-10KG", "8901030010028", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "470.00", "540.00", "565.00", "10", "35"),
    ("Fortune Chakki Fresh Atta 5kg", "FORT-ATTA-5KG", "8906007280015", "Grains & Flours", "Fortune", "PACK", "GST 5% (Essential Food / Staples)", "230.00", "265.00", "280.00", "8", "30"),
    ("India Gate Basmati Rice Feast Rozzana 1kg", "IG-ROZZANA-1KG", "8901725181014", "Grains & Flours", "India Gate", "PACK", "GST 5% (Essential Food / Staples)", "85.00", "105.00", "120.00", "15", "50"),
    ("India Gate Basmati Rice Feast Rozzana 5kg", "IG-ROZZANA-5KG", "8901725181021", "Grains & Flours", "India Gate", "PACK", "GST 5% (Essential Food / Staples)", "410.00", "495.00", "550.00", "8", "25"),
    ("Daawat Super Basmati Rice 1kg", "DAAW-SUPER-1KG", "8901537001018", "Grains & Flours", "Daawat", "PACK", "GST 5% (Essential Food / Staples)", "125.00", "155.00", "175.00", "10", "40"),
    ("Sona Masoori Raw Rice 5kg Bag", "RICE-SONA-5KG", "8901725181038", "Grains & Flours", "Farm Fresh", "PACK", "GST 5% (Essential Food / Staples)", "270.00", "315.00", "340.00", "10", "30"),
    ("Roasted Rava / Sooji 500g", "RAVA-ROAST-500G", "8901030010035", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "34.00", "42.00", "45.00", "12", "45"),
    ("All Purpose Maida 500g", "MAIDA-500G", "8901030010042", "Grains & Flours", "Aashirvaad", "PACK", "GST 5% (Essential Food / Staples)", "30.00", "38.00", "40.00", "12", "50"),

    # --- 2. Dals & Pulses (GST 0% or 5%) ---
    ("Tata Sampann Unpolished Toor Dal 1kg", "TATA-TOOR-1KG", "8901063141010", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "145.00", "175.00", "190.00", "15", "60"),
    ("Tata Sampann Moong Dal 1kg", "TATA-MOONG-1KG", "8901063141027", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "120.00", "148.00", "165.00", "15", "50"),
    ("Tata Sampann Chana Dal 1kg", "TATA-CHANA-1KG", "8901063141034", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "92.00", "115.00", "125.00", "12", "40"),
    ("Tata Sampann Urad Dal White Whole 1kg", "TATA-URAD-1KG", "8901063141041", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "148.00", "180.00", "198.00", "12", "45"),
    ("Kabuli Chana Premium 500g", "KABULI-500G", "8901063141058", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "65.00", "82.00", "90.00", "10", "35"),
    ("Rajma Red Sharmili 500g", "RAJMA-500G", "8901063141065", "Dals & Pulses", "Tata Sampann", "PACK", "GST 5% (Essential Food / Staples)", "68.00", "85.00", "95.00", "10", "35"),

    # --- 3. Edible Cooking Oils & Ghee (GST 5% & 12%) ---
    ("Fortune Sunlite Refined Sunflower Oil 1L Pouch", "FORT-SUN-1L", "8906007281012", "Edible Oils & Ghee", "Fortune", "PACK", "GST 5% (Essential Food / Staples)", "112.00", "130.00", "145.00", "20", "80"),
    ("Fortune Sunlite Refined Sunflower Oil 5L Jar", "FORT-SUN-5L", "8906007281029", "Edible Oils & Ghee", "Fortune", "PACK", "GST 5% (Essential Food / Staples)", "575.00", "660.00", "720.00", "6", "25"),
    ("Gold Winner Refined Sunflower Oil 1L Pouch", "GOLD-WIN-1L", "8906012431013", "Edible Oils & Ghee", "Gold Winner", "PACK", "GST 5% (Essential Food / Staples)", "114.00", "132.00", "146.00", "20", "75"),
    ("Idhayam Pure Sesame Gingelly Oil 500ml", "IDH-SES-500ML", "8906003251019", "Edible Oils & Ghee", "Idhayam", "PACK", "GST 5% (Essential Food / Staples)", "195.00", "230.00", "250.00", "10", "40"),
    ("Idhayam Pure Sesame Gingelly Oil 1L", "IDH-SES-1L", "8906003251026", "Edible Oils & Ghee", "Idhayam", "PACK", "GST 5% (Essential Food / Staples)", "380.00", "445.00", "485.00", "8", "30"),
    ("Parachute 100% Pure Coconut Oil 250ml", "PARA-COCO-250ML", "8901088011015", "Edible Oils & Ghee", "Parachute", "PACK", "GST 5% (Essential Food / Staples)", "88.00", "105.00", "115.00", "15", "50"),
    ("Parachute 100% Pure Coconut Oil 500ml", "PARA-COCO-500ML", "8901088011022", "Edible Oils & Ghee", "Parachute", "PACK", "GST 5% (Essential Food / Staples)", "165.00", "198.00", "220.00", "12", "45"),
    ("Fortune Kachi Ghani Mustard Oil 1L", "FORT-MUST-1L", "8906007281036", "Edible Oils & Ghee", "Fortune", "PACK", "GST 5% (Essential Food / Staples)", "128.00", "150.00", "165.00", "10", "35"),
    ("Amul Pure Ghee 500ml Refill Pack", "AMUL-GHEE-500ML", "8901262011018", "Edible Oils & Ghee", "Amul", "PACK", "GST 12% (Processed Goods / Apparel)", "290.00", "335.00", "360.00", "10", "40"),
    ("Aashirvaad Svasti Pure Cow Ghee 1L Tin", "AASH-GHEE-1L", "8901030010059", "Edible Oils & Ghee", "Aashirvaad", "PACK", "GST 12% (Processed Goods / Apparel)", "620.00", "710.00", "770.00", "5", "20"),

    # --- 4. Salt, Sugar & Spices (GST 0% & 5%) ---
    ("Tata Salt Vacuum Evaporated Iodised 1kg", "TATA-SALT-1KG", "8901063011016", "Spices, Salt & Sugar", "Tata Salt", "PACK", "GST 5% (Essential Food / Staples)", "22.50", "27.00", "28.00", "25", "120"),
    ("Tata Salt Lite Low Sodium 1kg", "TATA-SALT-LITE-1KG", "8901063011023", "Spices, Salt & Sugar", "Tata Salt", "PACK", "GST 5% (Essential Food / Staples)", "36.00", "45.00", "48.00", "10", "40"),
    ("Madhur Pure & Hygienic Refined Sugar 1kg", "MADH-SUGAR-1KG", "8906014521019", "Spices, Salt & Sugar", "Madhur", "PACK", "GST 5% (Essential Food / Staples)", "46.00", "54.00", "58.00", "20", "80"),
    ("Aachi Chilli Powder 200g", "AACHI-CHILLI-200G", "8901777011017", "Spices, Salt & Sugar", "Aachi", "PACK", "GST 5% (Essential Food / Staples)", "48.00", "60.00", "65.00", "15", "60"),
    ("Everest Turmeric Powder 100g", "EVER-TURM-100G", "8901786011015", "Spices, Salt & Sugar", "Everest", "PACK", "GST 5% (Essential Food / Staples)", "26.00", "34.00", "38.00", "15", "60"),
    ("Everest Coriander Powder 200g", "EVER-CORI-200G", "8901786011022", "Spices, Salt & Sugar", "Everest", "PACK", "GST 5% (Essential Food / Staples)", "44.00", "55.00", "60.00", "15", "50"),
    ("Everest Garam Masala 100g", "EVER-GARAM-100G", "8901786011039", "Spices, Salt & Sugar", "Everest", "PACK", "GST 5% (Essential Food / Staples)", "72.00", "90.00", "98.00", "10", "45"),
    ("Aachi Sambar Powder 200g", "AACHI-SAMBAR-200G", "8901777011024", "Spices, Salt & Sugar", "Aachi", "PACK", "GST 5% (Essential Food / Staples)", "52.00", "65.00", "72.00", "15", "55"),
    ("Mustard Seeds / Kadugu 100g", "MUSTARD-100G", "8901777011031", "Spices, Salt & Sugar", "Farm Fresh", "PACK", "GST 5% (Essential Food / Staples)", "16.00", "22.00", "25.00", "15", "60"),
    ("Cumin Seeds / Jeera 100g", "JEERA-100G", "8901777011048", "Spices, Salt & Sugar", "Farm Fresh", "PACK", "GST 5% (Essential Food / Staples)", "42.00", "55.00", "65.00", "15", "50"),

    # --- 5. Dairy, Bakery & Breakfast (GST 0%, 5%, 12%) ---
    ("Amul Pasteurised Butter 100g", "AMUL-BUTT-100G", "8901262011025", "Dairy & Bakery", "Amul", "PACK", "GST 12% (Processed Goods / Apparel)", "45.00", "54.00", "58.00", "20", "70"),
    ("Amul Pasteurised Butter 500g", "AMUL-BUTT-500G", "8901262011032", "Dairy & Bakery", "Amul", "PACK", "GST 12% (Processed Goods / Apparel)", "220.00", "260.00", "275.00", "10", "40"),
    ("Amul Cheese Slices 200g (10 Slices)", "AMUL-CHEESE-200G", "8901262011049", "Dairy & Bakery", "Amul", "PACK", "GST 12% (Processed Goods / Apparel)", "122.00", "145.00", "155.00", "10", "40"),
    ("Amul Taaza Homogenised Toned Milk 1L Tetra", "AMUL-TAAZA-1L", "8901262011056", "Dairy & Bakery", "Amul", "PACK", "GST 0% (Exempt / Grains / Milk)", "64.00", "72.00", "75.00", "15", "50"),
    ("Britannia 100% Whole Wheat Bread 400g", "BRIT-BREAD-400G", "8901063021015", "Dairy & Bakery", "Britannia", "PACK", "GST 0% (Exempt / Grains / Milk)", "40.00", "48.00", "50.00", "10", "30"),
    ("Kellogg's Corn Flakes Original 500g", "KELL-CORN-500G", "8901499011018", "Dairy & Bakery", "Kellogg's", "PACK", "GST 18% (Standard Retail / General)", "160.00", "195.00", "215.00", "8", "30"),
    ("Quaker Rolled Oats 1kg Pouch", "QUAK-OATS-1KG", "8901491101014", "Dairy & Bakery", "Quaker", "PACK", "GST 18% (Standard Retail / General)", "145.00", "180.00", "199.00", "10", "35"),

    # --- 6. Beverages, Tea & Coffee (GST 5% & 18%) ---
    ("Brooke Bond Red Label Tea 500g", "RED-LABEL-500G", "8901030311019", "Beverages", "Red Label", "PACK", "GST 5% (Essential Food / Staples)", "210.00", "255.00", "280.00", "12", "50"),
    ("Tata Tea Gold 500g", "TATA-GOLD-500G", "8901063031014", "Beverages", "Tata Tea", "PACK", "GST 5% (Essential Food / Staples)", "240.00", "290.00", "320.00", "10", "45"),
    ("Taj Mahal Tea 250g", "TAJ-TEA-250G", "8901030311026", "Beverages", "Taj Mahal", "PACK", "GST 5% (Essential Food / Staples)", "150.00", "185.00", "205.00", "10", "35"),
    ("Nescafe Classic Instant Coffee Jar 50g", "NES-CLASS-50G", "8901058851016", "Beverages", "Nescafe", "PACK", "GST 18% (Standard Retail / General)", "140.00", "175.00", "190.00", "12", "40"),
    ("Bru Instant Coffee 100g Pouch", "BRU-INST-100G", "8901030311033", "Beverages", "Bru", "PACK", "GST 18% (Standard Retail / General)", "165.00", "205.00", "225.00", "12", "40"),
    ("Horlicks Classic Malt Health Drink 500g Pet Jar", "HORLICKS-500G", "8901571011011", "Beverages", "Horlicks", "PACK", "GST 18% (Standard Retail / General)", "220.00", "265.00", "285.00", "8", "30"),
    ("Bournvita Chocolate Health Drink 500g Jar", "BOURN-500G", "8901233011016", "Beverages", "Bournvita", "PACK", "GST 18% (Standard Retail / General)", "215.00", "260.00", "280.00", "8", "30"),

    # --- 7. Biscuits, Snacks & Instant Noodles (GST 12% & 18%) ---
    ("Parle-G Original Glucose Biscuits 250g", "PARLE-G-250G", "8901719101011", "Biscuits & Snacks", "Parle", "PACK", "GST 18% (Standard Retail / General)", "22.00", "28.00", "30.00", "25", "100"),
    ("Britannia Good Day Cashew Cookies 200g", "BRIT-GOOD-200G", "8901063041013", "Biscuits & Snacks", "Britannia", "PACK", "GST 18% (Standard Retail / General)", "36.00", "45.00", "50.00", "20", "80"),
    ("Britannia Marie Gold Biscuits 300g", "BRIT-MARIE-300G", "8901063041020", "Biscuits & Snacks", "Britannia", "PACK", "GST 18% (Standard Retail / General)", "35.00", "44.00", "48.00", "20", "75"),
    ("Sunfeast Dark Fantasy Choco Fills 300g", "SUN-DARK-300G", "8901030411016", "Biscuits & Snacks", "Sunfeast", "PACK", "GST 18% (Standard Retail / General)", "115.00", "145.00", "160.00", "10", "40"),
    ("Maggi 2-Minute Masala Instant Noodles 4-Pack 280g", "MAGGI-4PK-280G", "8901058861015", "Biscuits & Snacks", "Maggi", "PACK", "GST 12% (Processed Goods / Apparel)", "50.00", "60.00", "64.00", "20", "80"),
    ("Maggi 2-Minute Masala Noodles Single 70g", "MAGGI-SGL-70G", "8901058861022", "Biscuits & Snacks", "Maggi", "PACK", "GST 12% (Processed Goods / Apparel)", "12.50", "15.00", "16.00", "30", "120"),
    ("Lay's India's Magic Masala Potato Chips 50g", "LAYS-MAGIC-50G", "8901491111013", "Biscuits & Snacks", "Lay's", "PACK", "GST 12% (Processed Goods / Apparel)", "16.00", "20.00", "20.00", "20", "60"),
    ("Kurkure Masala Munch Crispy Snack 90g", "KURK-MUNCH-90G", "8901491111020", "Biscuits & Snacks", "Kurkure", "PACK", "GST 12% (Processed Goods / Apparel)", "16.00", "20.00", "20.00", "20", "60"),
    ("Haldiram's Nagpur Bhujia Sev 400g", "HALD-BHUJ-400G", "8904004401018", "Biscuits & Snacks", "Haldiram's", "PACK", "GST 12% (Processed Goods / Apparel)", "95.00", "118.00", "130.00", "12", "45"),

    # --- 8. Personal Care, Soaps & Oral Care (GST 18%) ---
    ("Dettol Original Bathing Soap 75g", "DET-SOAP-75G", "8901396300017", "Personal Care & Soaps", "Dettol", "PCS", "GST 18% (Standard Retail / General)", "28.00", "36.00", "40.00", "25", "90"),
    ("Dettol Original Bathing Soap 125g", "DET-SOAP-125G", "8901396300123", "Personal Care & Soaps", "Dettol", "PCS", "GST 18% (Standard Retail / General)", "48.00", "60.00", "65.00", "20", "80"),
    ("Lifebuoy Total Germ Protection Soap 125g", "LIFE-SOAP-125G", "8901030511013", "Personal Care & Soaps", "Lifebuoy", "PCS", "GST 18% (Standard Retail / General)", "32.00", "40.00", "44.00", "20", "70"),
    ("Dove Cream Beauty Bathing Bar 100g", "DOVE-SOAP-100G", "8901030511020", "Personal Care & Soaps", "Dove", "PCS", "GST 18% (Standard Retail / General)", "55.00", "68.00", "75.00", "15", "60"),
    ("Colgate Strong Teeth Dental Paste 150g", "COLG-DENT-150G", "8901314011019", "Personal Care & Soaps", "Colgate", "PCS", "GST 18% (Standard Retail / General)", "78.00", "98.00", "110.00", "15", "65"),
    ("Close Up Everfresh Red Hot Gel 150g", "CLOSE-RED-150G", "8901030511037", "Personal Care & Soaps", "Close Up", "PCS", "GST 18% (Standard Retail / General)", "80.00", "102.00", "115.00", "12", "50"),
    ("Head & Shoulders Anti-Dandruff Shampoo 180ml", "HNS-SHAMP-180ML", "8901030511044", "Personal Care & Soaps", "Head & Shoulders", "PCS", "GST 18% (Standard Retail / General)", "140.00", "175.00", "195.00", "10", "40"),
    ("Clinic Plus Strong & Long Health Shampoo 175ml", "CLINIC-SHAMP-175ML", "8901030511051", "Personal Care & Soaps", "Clinic Plus", "PCS", "GST 18% (Standard Retail / General)", "95.00", "120.00", "135.00", "12", "45"),

    # --- 9. Household, Laundry & Cleaning (GST 18%) ---
    ("Surf Excel Easy Wash Detergent Powder 1kg", "SURF-EASY-1KG", "8901030611010", "Household & Cleaning", "Surf Excel", "PACK", "GST 18% (Standard Retail / General)", "118.00", "142.00", "155.00", "15", "60"),
    ("Ariel Matic Front Load Detergent Powder 1kg", "ARIEL-FL-1KG", "8901030611027", "Household & Cleaning", "Ariel", "PACK", "GST 18% (Standard Retail / General)", "220.00", "265.00", "290.00", "8", "35"),
    ("Rin Advanced Detergent Bar 250g", "RIN-BAR-250G", "8901030611034", "Household & Cleaning", "Rin", "PCS", "GST 18% (Standard Retail / General)", "18.00", "23.00", "25.00", "25", "100"),
    ("Vim Dishwash Bar with Lemon 300g", "VIM-BAR-300G", "8901030611041", "Household & Cleaning", "Vim", "PCS", "GST 18% (Standard Retail / General)", "22.00", "28.00", "30.00", "25", "90"),
    ("Vim Dishwash Gel Liquid Lemon 500ml Bottle", "VIM-GEL-500ML", "8901030611058", "Household & Cleaning", "Vim", "PCS", "GST 18% (Standard Retail / General)", "105.00", "130.00", "145.00", "12", "50"),
    ("Harpic Power Plus Original Toilet Cleaner 500ml", "HARP-TOIL-500ML", "8901396400014", "Household & Cleaning", "Harpic", "PCS", "GST 18% (Standard Retail / General)", "78.00", "96.00", "105.00", "15", "60"),
    ("Lizol Disinfectant Floor Cleaner Citrus 500ml", "LIZ-CITR-500ML", "8901396400021", "Household & Cleaning", "Lizol", "PCS", "GST 18% (Standard Retail / General)", "82.00", "102.00", "112.00", "15", "55"),
    ("Colin Advanced Glass & Surface Cleaner 500ml Spray", "COLIN-SPRAY-500ML", "8901396400038", "Household & Cleaning", "Colin", "PCS", "GST 18% (Standard Retail / General)", "86.00", "108.00", "120.00", "10", "40"),

    # --- 10. Loose / Weighed Items (Scale Barcode & Rapid Cashier Keypad Codes) ---
    # Short codes 101-105 for electronic scale barcode integration (EAN-13 prefix 20) and rapid POS cashiering!
    ("Fresh Onions (Loose)", "VEG-101", "101", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 0% (Exempt / Grains / Milk)", "22.00", "35.00", "40.00", "20", "250"),
    ("Fresh Potatoes (Loose)", "VEG-102", "102", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 0% (Exempt / Grains / Milk)", "18.00", "30.00", "35.00", "20", "200"),
    ("Fresh Country Tomatoes (Loose)", "VEG-103", "103", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 0% (Exempt / Grains / Milk)", "24.00", "40.00", "45.00", "15", "150"),
    ("Loose White Crystal Sugar M-30", "STAP-104", "104", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 5% (Essential Food / Staples)", "36.00", "44.00", "48.00", "30", "300"),
    ("Loose Toor Dal Unpolished Premium", "STAP-105", "105", "Fresh Produce & Loose", "Farm Fresh", "KG", "GST 5% (Essential Food / Staples)", "115.00", "140.00", "155.00", "25", "200"),
]


def seed_supermarket_data() -> None:
    print("=" * 70)
    print("   AJ SUPERMARKET - FULL-FLEDGED PRODUCTION DATABASE SEEDER")
    print("=" * 70)

    db = get_db_manager()

    # 1. Initialize schema and base system data
    initialize_database(db, create_tables=True)

    # 2. Setup shop and admin if not already present
    admin_user_id = None
    with db.session() as session:
        shop = session.query(Shop).first()
        admin = session.query(User).filter_by(username="admin").first()
        if not shop or not admin:
            setup_initial_shop_and_admin(
                db,
                shop_name="Aj Super Market",
                business_category="Grocery / Supermarket",
                currency_symbol="INR",
                admin_username="admin",
                admin_password="admin",
                admin_full_name="Store Administrator",
                tax_number="33AAAAA0000A1Z5",
                phone="9876543210",
                address="100 Commercial Boulevard, Anna Nagar, Chennai",
            )
            admin = session.query(User).filter_by(username="admin").first()
        admin_user_id = admin.id

    admin_session = UserSession(
        user_id=admin_user_id,
        username="admin",
        full_name="Store Administrator",
        is_admin=True,
        permissions={"all"},
        token="supermarket_seed_tok",
    )

    prod_service = ProductService(db)

    # Cache UOMs and Tax Profiles
    uoms_list = prod_service.list_uoms()
    uom_by_code = {u["code"]: u["id"] for u in uoms_list}

    taxes_list = prod_service.list_tax_profiles()
    tax_by_name = {t["name"]: t["id"] for t in taxes_list}

    # 3. Seed FMCG Suppliers
    print("\n[+] Seeding FMCG Supermarket Suppliers...")
    with db.session() as session:
        for s_data in SUPERMARKET_SUPPLIERS:
            existing = session.query(Supplier).filter_by(name=s_data["name"]).first()
            if not existing:
                supplier = Supplier(**s_data)
                session.add(supplier)
                print(f"  [OK] Supplier added: {s_data['name']}")
            else:
                print(f"  [-] Supplier exists: {s_data['name']}")

    # 4. Seed Customers
    print("\n[+] Seeding Supermarket Customers...")
    with db.session() as session:
        for c_data in SUPERMARKET_CUSTOMERS:
            existing = session.query(Customer).filter_by(name=c_data["name"]).first()
            if not existing:
                cust = Customer(**c_data)
                session.add(cust)
                print(f"  [OK] Customer added: {c_data['name']}")
            else:
                print(f"  [-] Customer exists: {c_data['name']}")

    # 5. Seed Catalog Products
    print(f"\n[+] Seeding {len(SUPERMARKET_CATALOG)} Supermarket Catalog Products...")
    seeded_count = 0
    updated_count = 0

    for item in SUPERMARKET_CATALOG:
        (
            name, sku, barcode, cat_name, brand_name,
            uom_code, tax_name, cost_s, price_s, mrp_s,
            reorder_s, stock_s
        ) = item

        # Resolve or create Category and Brand
        cat_id = prod_service.get_or_create_category(admin_session, cat_name)
        brand_id = prod_service.get_or_create_brand(admin_session, brand_name)

        unit_id = uom_by_code.get(uom_code, uom_by_code.get("PCS"))
        tax_profile_id = tax_by_name.get(tax_name, taxes_list[0]["id"])

        purchase_cost = Decimal(cost_s)
        selling_price = Decimal(price_s)
        mrp = Decimal(mrp_s)
        reorder_level = Decimal(reorder_s)
        initial_stock = Decimal(stock_s)

        # Check if already exists
        with db.session() as session:
            existing_prod = session.query(Product).filter((Product.sku == sku) | (Product.barcode == barcode)).first()
            if existing_prod:
                # Update stock and price
                existing_prod.name = name
                existing_prod.selling_price = selling_price
                existing_prod.purchase_cost = purchase_cost
                existing_prod.mrp = mrp
                existing_prod.reorder_level = reorder_level
                existing_prod.category_id = cat_id
                existing_prod.brand_id = brand_id
                existing_prod.unit_id = unit_id
                existing_prod.tax_profile_id = tax_profile_id
                if existing_prod.inventory_balance:
                    if existing_prod.inventory_balance.quantity_on_hand < initial_stock:
                        existing_prod.inventory_balance.quantity_on_hand = initial_stock
                updated_count += 1
                continue

        # Create new product
        prod_id = prod_service.create_product(
            current_session=admin_session,
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
        seeded_count += 1
        print(f"  [OK] Product [{barcode:>13}] {name:<45} | Stock: {initial_stock} {uom_code}")

    print("\n" + "=" * 70)
    print(f"   SUPERMARKET SEEDING COMPLETE: {seeded_count} new products created, {updated_count} refreshed.")
    print("=" * 70)
    print("\nKey Supermarket Features Activated:")
    print("  * Loose Produce Short-Codes: 101 (Onion), 102 (Potato), 103 (Tomato), 104 (Sugar), 105 (Toor Dal)")
    print("  * Scale Barcodes: EAN-13 (20 + 5-digit code + 5-digit weight + check) e.g. '2000101015000' = 1.5kg Onion")
    print("  * Cashier Multiplier Scanning: e.g. '5*8901030010011' adds 5 bags instantly")
    print("  * Complete GST Classification: 0% Grains/Milk, 5% Staples/Oils, 12% Dairy/Processed, 18% Personal/Cleaners")
    print("  * Full FMCG Supply Chain: Suppliers & Walk-in / Loyalty Customers")
    print("\nReady for live production billing!\n")


if __name__ == "__main__":
    seed_supermarket_data()
