"""
Unit tests for MongoDB Cloud Database Synchronization and Multi-Shop Partitioning.
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from src.services.mongo_service import MongoSyncService
from src.services.settings_service import SettingsService


def test_mongo_config_save_and_retrieve(db_manager):
    """Verify saving and retrieving MongoDB configuration."""
    mongo = MongoSyncService(db_manager)

    # Initial state: disabled
    cfg = mongo.get_config()
    assert cfg["enabled"] is False

    # Save new configuration
    test_uri = "mongodb+srv://admin:secret@cluster0.mongodb.net/"
    mongo.save_config(uri=test_uri, database_name="shop_network_db", enabled=True)

    updated = mongo.get_config()
    assert updated["enabled"] is True
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


def test_multi_shop_id_persistence(db_manager):
    """Verify that multiple shops can independently persist their shop_id."""
    sett = SettingsService(db_manager)

    # Defaults to SHOP_01
    assert sett.get_cloud_shop_id() == "SHOP_01"

    # Configure as SHOP_03
    sett.set_cloud_shop_id("SHOP_03")
    assert sett.get_cloud_shop_id() == "SHOP_03"
