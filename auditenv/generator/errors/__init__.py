"""Error types. Importing this package registers all of them in REGISTRY."""

from . import duplicate_invoice, fx_rate, payment_allocation, period_cutoff  # noqa: F401
from .base import ORDER, REGISTRY, Injected, register  # noqa: F401
