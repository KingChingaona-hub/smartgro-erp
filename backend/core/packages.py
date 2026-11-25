# backend/core/packages.py
# Single source of truth: which sidebar modules each subscription package unlocks.
#
# Tiers are cumulative: each tier lists ONLY what it adds to the tier below,
# so a module is never copy-pasted into four lists again.
#
# Final visibility for a user = (modules allowed by the branch package)
#                               ∩ (modules allowed by the user's role)
# The role half lives in auth.can_access_feature(); the combining logic
# lives in role_based_menu.get_visible_modules().

from __future__ import annotations

PACKAGE_ORDER = ["Bronze", "Silver", "Gold", "Platinum"]
DEFAULT_PACKAGE = "Bronze"

# ------------------------------------------------------------
# What each tier ADDS on top of the previous one
# ------------------------------------------------------------
_TIER_ADDITIONS = {
    "Bronze": [
        "POS", "Sales History",
        "Stock Dashboard", "Inventory", "Barcode Generator", "Barcode Scanner",
        "Purchases", "Purchases Dashboard", "Expenses", "Expenses Dashboard",
        "Income", "Income Dashboard", "Cash Dashboard",
        "Debtors", "Debtors Dashboard",
        "Shift Management", "Documents",
        "User Management",
    ],
    "Silver": [
        "Customer Dashboard", "Retention Dashboard", "Segmentation Dashboard",
        "Lifecycle Dashboard", "Reports Dashboard", "Floating Financials",
        "P&L", "Duplicate Products", "Mobile Dashboard", "PWA Setup",
        "Offline Mode", "Language Management",
        # Previously in NO package (so only owners ever saw them). Placed in
        # Silver here -- move them if you want a different tier.
        "Sales Dashboard", "Returns & Refunds",
    ],
    "Gold": [
        "Customer 360 View", "Customer Insights 360",
        "Supplier Bidding", "Supplier Bidding Portal",
        "Smart Replenishment", "Inventory Optimizer",
        "Financial Closing", "Profit Center Analysis",
        "Automated Follow-up", "Workflow Approvals",
        "Live Dashboard", "Payment Gateway", "SMS Gateway", "E-commerce Sync",
    ],
    "Platinum": [
        "Predictive Analytics", "Demand Forecasting", "Churn Prediction",
        "Recommendation Engine", "Anomaly Detection", "Automated Insights",
        "Competitor Price Monitoring", "Business Advisor",
        "Accounting Sync", "API Developer", "Multi-Tenant", "White Label",
        "Voice Commands", "Branch Management", "Branch Performance",
        "Security Dashboard", "Settings",
    ],
}


def _build_cumulative() -> dict[str, frozenset[str]]:
    result, running = {}, set()
    for tier in PACKAGE_ORDER:
        running |= set(_TIER_ADDITIONS[tier])
        result[tier] = frozenset(running)
    return result


PACKAGE_MODULES: dict[str, frozenset[str]] = _build_cumulative()

# Cashier is a restricted role: these are the ONLY modules a cashier can ever
# see, and only if the branch package also includes them.
CASHIER_MODULES = (
    "POS", "Sales History", "Barcode Scanner", "Customer Dashboard",
    "Floating Financials", "Debtors", "Debtors Dashboard",
    "Shift Management", "Documents",
)

# Owner of a NON head-office branch still needs these to administer their
# own branch, even if the package doesn't include them.
OWNER_ALWAYS_MODULES = frozenset({"User Management", "Settings"})

# Branch code of the head office / system owner. That owner sees everything
# (needed to manage branches and packages).
HEAD_OFFICE_CODE = "HO"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def normalize_package(package) -> str:
    """'gold' / ' GOLD ' -> 'Gold'. None / unknown / NaN -> 'Bronze' (fail closed)."""
    if not isinstance(package, str):
        return DEFAULT_PACKAGE
    key = package.strip().title()
    return key if key in PACKAGE_MODULES else DEFAULT_PACKAGE


def package_modules(package) -> frozenset[str]:
    return PACKAGE_MODULES[normalize_package(package)]


def package_allows(package, module: str) -> bool:
    """Does this package include the sidebar module? Unknown modules -> False."""
    return module in package_modules(package)


def min_package_for(module: str) -> str | None:
    """Lowest tier that includes the module (for 'Upgrade to Gold' messages)."""
    for tier in PACKAGE_ORDER:
        if module in PACKAGE_MODULES[tier]:
            return tier
    return None


def is_head_office(branch_id) -> bool:
    return str(branch_id or "").strip().upper() == HEAD_OFFICE_CODE