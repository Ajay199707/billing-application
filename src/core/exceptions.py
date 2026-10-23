"""
Domain and business exceptions for the Multi-Purpose Billing & Shop Management System.
"""

class BillingSystemError(Exception):
    """Base exception for all domain and system errors."""
    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or "SYSTEM_ERROR"
        self.details = details or {}


# Database & Infrastructure Exceptions
class DatabaseError(BillingSystemError):
    """Base error for database-related failures."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="DATABASE_ERROR", details=details)


class DatabaseConnectionError(DatabaseError):
    """Raised when connecting to the database fails or drops."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details=details)
        self.code = "DB_CONNECTION_FAILED"


class MigrationError(DatabaseError):
    """Raised when database schema migrations fail."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details=details)
        self.code = "MIGRATION_ERROR"


# Security & RBAC Exceptions
class SecurityError(BillingSystemError):
    """Base error for authentication and authorization."""
    pass


class ValidationError(BillingSystemError):
    """Raised when data input fails domain validation."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)



class InvalidCredentialsError(SecurityError):
    """Raised when authentication credentials are invalid."""
    def __init__(self, message: str = "Invalid username or password."):
        super().__init__(message, code="INVALID_CREDENTIALS")


class AccountInactiveError(SecurityError):
    """Raised when an inactive user attempts to log in."""
    def __init__(self, message: str = "This user account has been deactivated."):
        super().__init__(message, code="ACCOUNT_INACTIVE")


class PermissionDeniedError(SecurityError):
    """Raised when user lacks the required permission for an operation."""
    def __init__(self, permission_code: str, message: str | None = None):
        msg = message or f"Permission denied. Required privilege: {permission_code}"
        super().__init__(msg, code="PERMISSION_DENIED", details={"permission": permission_code})


# Inventory Exceptions
class InventoryError(BillingSystemError):
    """Base error for inventory operations."""
    pass


class InsufficientStockError(InventoryError):
    """Raised when requested quantity exceeds available quantity on hand."""
    def __init__(self, product_name: str, available: float, requested: float, product_id: int | None = None):
        message = (
            f"Insufficient stock for '{product_name}'. "
            f"Available: {available:.3f}, Requested: {requested:.3f}"
        )
        super().__init__(
            message,
            code="INSUFFICIENT_STOCK",
            details={
                "product_name": product_name,
                "product_id": product_id,
                "available": available,
                "requested": requested,
            },
        )


class NegativeStockNotAllowedError(InventoryError):
    """Raised when an adjustment would drive inventory negative without authorization."""
    def __init__(self, product_name: str, current: float, deduction: float):
        message = f"Deduction of {deduction:.3f} would cause negative stock on '{product_name}' (Current: {current:.3f})."
        super().__init__(message, code="NEGATIVE_STOCK_DISALLOWED")


class BatchExpiredError(InventoryError):
    """Raised when attempting to sell from an expired batch in strict mode."""
    def __init__(self, batch_number: str, expiry_date: str):
        message = f"Batch '{batch_number}' has expired on {expiry_date}."
        super().__init__(message, code="BATCH_EXPIRED", details={"batch": batch_number, "expiry": expiry_date})


# Billing & POS Exceptions
class BillingError(BillingSystemError):
    """Base error for billing and checkout."""
    pass


class PaymentMismatchedError(BillingError):
    """Raised when recorded payments do not equal the invoice grand total."""
    def __init__(self, expected: float, actual: float):
        message = f"Payment mismatch: Total amount payable is ₹{expected:.2f}, but recorded payment is ₹{actual:.2f}."
        super().__init__(message, code="PAYMENT_MISMATCH", details={"expected": expected, "actual": actual})


class EmptyCartError(BillingError):
    """Raised when attempting to checkout an empty invoice."""
    def __init__(self, message: str = "Cannot complete sale with an empty cart."):
        super().__init__(message, code="EMPTY_CART")


class DuplicateInvoiceError(BillingError):
    """Raised when an invoice number collision occurs."""
    def __init__(self, invoice_number: str):
        message = f"Invoice number '{invoice_number}' already exists in database."
        super().__init__(message, code="DUPLICATE_INVOICE", details={"invoice_number": invoice_number})


# Tax Calculation Exceptions
class TaxCalculationError(BillingSystemError):
    """Raised when tax computation encounters invalid state or configuration."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="TAX_CALCULATION_ERROR", details=details)


# Backup & Restore Exceptions
class BackupError(BillingSystemError):
    """Raised when automated or manual backup fails."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="BACKUP_FAILED", details=details)


class RestoreError(BillingSystemError):
    """Raised when database restoration fails verification or execution."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="RESTORE_FAILED", details=details)
