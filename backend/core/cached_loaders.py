# backend/core/cached_loaders.py
# Branch-safe cached wrappers around db_adapter loaders.
# - Every wrapper resolves the current branch and passes it EXPLICITLY,
#   so Streamlit's cache key always includes the branch.
# - TTL is short (60s) so the UI is never more than a minute stale.
# - Saver functions are NOT cached — they always hit the DB.

import streamlit as st
from backend.core import db_adapter as _db

CACHE_TTL = 60  # seconds


def _branch():
    return _db.get_current_branch()


# ---- read-only loaders (cached) ----

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_branches():
    return _db.load_branches()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_products(branch_id: str):
    return _db.load_products(branch_id)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_sales(branch_id: str, date_from=None, date_to=None):
    return _db.load_sales(branch_id, date_from, date_to)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_customers(branch_id: str):
    return _db.load_customers(branch_id)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_debtors(branch_id: str):
    return _db.load_debtors(branch_id)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_expenses(branch_id: str, date_from=None, date_to=None):
    return _db.load_expenses(branch_id, date_from, date_to)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_purchases(branch_id: str):
    return _db.load_purchases(branch_id)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_cash(branch_id: str, shift_id=None):
    return _db.load_cash(branch_id, shift_id)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_shifts(branch_id: str, status=None):
    return _db.load_shifts(branch_id, status)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_suppliers(branch_id: str):
    return _db.load_suppliers(branch_id)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_loyalty(branch_id: str):
    return _db.load_loyalty(branch_id)


# ---- convenience no-arg wrappers (resolve branch for you) ----

def products():
    return load_products(_branch())

def sales(date_from=None, date_to=None):
    return load_sales(_branch(), date_from, date_to)

def customers():
    return load_customers(_branch())

def debtors():
    return load_debtors(_branch())

def expenses(date_from=None, date_to=None):
    return load_expenses(_branch(), date_from, date_to)

def purchases():
    return load_purchases(_branch())

def cash(shift_id=None):
    return load_cash(_branch(), shift_id)

def shifts(status=None):
    return load_shifts(_branch(), status)

def suppliers():
    return load_suppliers(_branch())

def loyalty():
    return load_loyalty(_branch())


# ---- cache busting helper (call after any save) ----

def invalidate_all():
    """Clear the data cache. Call this after save_products / save_sales / etc."""
    st.cache_data.clear()