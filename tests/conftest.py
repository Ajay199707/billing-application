"""
Pytest configuration and common fixtures for testing billing software.
"""

import pytest
from sqlalchemy.orm import Session

from src.core.config import DatabaseConfig, DatabaseMode
from src.core.database import DatabaseManager
from src.models import Base
from src.services.db_init_service import initialize_database, setup_initial_shop_and_admin


@pytest.fixture(scope="function")
def db_manager():
    """Provides an isolated in-memory SQLite database for test execution."""
    cfg = DatabaseConfig(mode=DatabaseMode.SINGLE_SQLITE, sqlite_file=":memory:")
    manager = DatabaseManager(cfg)
    manager.initialize()
    manager.create_all_tables(Base)
    initialize_database(manager, create_tables=False)
    yield manager
    manager.close()


@pytest.fixture(scope="function")
def db_session(db_manager) -> Session:
    """Provides a database session for testing."""
    with db_manager.session() as session:
        yield session


@pytest.fixture(scope="function")
def test_shop_and_admin(db_manager):
    """Provisions a test shop and admin user."""
    shop, admin = setup_initial_shop_and_admin(
        db_manager=db_manager,
        shop_name="SuperMart Retail",
        legal_name="SuperMart Retail Pvt Ltd",
        gstin="33ABCDE1234F1Z5",
        state_code="33",
        state_name="Tamil Nadu",
        admin_username="admin",
        admin_password="AdminPassword123!",
        admin_full_name="System Administrator",
        business_profile="grocery",
    )
    return shop, admin
