"""
Unit tests for MongoDB Cloud Database Synchronization and Multi-Shop Partitioning.
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from src.services.mongo_service import MongoSyncService, DEFAULT_MONGODB_URI
from src.services.settings_service import SettingsService
from src.services.cloud_sync_service import fetch_shop_pricing


def test_mongo_config_save_and_retrieve(db_manager):
    """Verify default production MongoDB configuration and updating settings."""
    mongo = MongoSyncService(db_manager)

    # Initial state: enabled by default with production MongoDB cluster URI
    cfg = mongo.get_config()
    assert cfg["enabled"] is True
    assert "mongodb+srv://" in cfg["uri"]
    assert cfg["database_name"] == "aj_billing_cloud"

    # Save custom configuration
    test_uri = "mongodb+srv://admin:secret@cluster0.mongodb.net/"
    mongo.save_config(uri=test_uri, database_name="shop_network_db", enabled=False)

    updated = mongo.get_config()
    assert updated["enabled"] is False
    assert updated["uri"] == test_uri
    assert updated["database_name"] == "shop_network_db"


def test_mongo_test_connection_empty_uri(db_manager):
    """Verify validation when testing empty MongoDB URI."""
    mongo = MongoSyncService(db_manager)
    ok, msg = mongo.test_connection(uri="")
    assert ok is False
    assert "cannot be empty" in msg.lower()


def test_mongo_sale_sync_mock(db_manager):
    """Verify sale synchronization document structure and shop_id tagging."""
    mongo = MongoSyncService(db_manager)
    mongo.save_config(uri="mongodb://localhost:27017", database_name="test_cloud", enabled=True)

    sample_sale = {
        "invoice_number": "INV-2026-0001",
        "sale_date": "2026-10-27 14:00:00",
        "customer_name": "Walk-in Customer",
        "subtotal": 120.0,
        "taxable_amount": 114.28,
        "cgst_amount": 2.86,
        "sgst_amount": 2.86,
        "grand_total": 120.0,
        "items": [
            {"name": "Tata Salt 1kg", "quantity": 2.0, "unit_price": 28.0, "line_total": 56.0}
        ],
        "payments": [{"method": "UPI", "amount": 120.0}],
    }

    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

    with patch("pymongo.MongoClient", return_value=mock_client):
        res = mongo.sync_sale_now(sample_sale, shop_id="SHOP_02")
        assert res is True

        # Verify update_one was called with shop_id partition and upsert
        mock_collection.update_one.assert_called_once()
        filter_arg, update_arg = mock_collection.update_one.call_args[0]
        kwargs = mock_collection.update_one.call_args[1]

        assert filter_arg == {"client_id": "SHOP_02", "invoice_number": "INV-2026-0001"}
        assert update_arg["$set"]["client_id"] == "SHOP_02"
        assert update_arg["$set"]["shop_id"] == "SHOP_02"
        assert update_arg["$set"]["grand_total"] == 120.0
        assert kwargs.get("upsert") is True


def test_mongo_get_shop_catalog_mock(db_manager):
    """Verify retrieval of shop catalog from MongoDB Atlas."""
    mongo = MongoSyncService(db_manager)
    mock_doc = {
        "client_id": "SHOP_01",
        "shop_id": "SHOP_01",
        "price_updates": [
            {"sku": "FORT-SUN-1L", "selling_price": 135.0, "mrp": 145.0}
        ],
    }

    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_coll = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_coll
    mock_coll.find_one.return_value = mock_doc

    with patch("pymongo.MongoClient", return_value=mock_client):
        result = mongo.get_shop_catalog("SHOP_01")
        assert result is not None
        assert result["client_id"] == "SHOP_01"
        assert len(result["price_updates"]) == 1


def test_cloud_sync_service_prefers_mongo_catalog(db_manager):
    """Verify that fetch_shop_pricing pulls from MongoDB when available."""
    mock_doc = {
        "client_id": "SHOP_03",
        "shop_id": "SHOP_03",
        "price_updates": [
            {"sku": "BRU-100G", "selling_price": 195.0, "mrp": 210.0}
        ],
    }

    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_coll = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_coll
    mock_coll.find_one.return_value = mock_doc

    with patch("pymongo.MongoClient", return_value=mock_client):
        catalog = fetch_shop_pricing("SHOP_03", db_manager=db_manager)
        assert catalog is not None
        assert catalog["client_id"] == "SHOP_03"
        assert catalog["price_updates"][0]["sku"] == "BRU-100G"


def test_multi_shop_id_persistence(db_manager):
    """Verify that multiple shops can independently persist their shop_id."""
    sett = SettingsService(db_manager)

    # Defaults to SHOP_01
    assert sett.get_cloud_shop_id() == "SHOP_01"

    # Configure as SHOP_03
    sett.set_cloud_shop_id("SHOP_03")
    assert sett.get_cloud_shop_id() == "SHOP_03"
