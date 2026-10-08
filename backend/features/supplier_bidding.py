# backend/features/supplier_bidding.py
# Supplier Bidding — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate view (owner only)
#
# Storage (branch-isolated directories, zero DB migration required):
#     data/supplier_bidding/<BRANCH>/suppliers.csv
#     data/supplier_bidding/<BRANCH>/bids.csv
#     data/supplier_bidding/settings.json     (global — shared vocabulary)

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import hashlib
import re

from backend.core.db_adapter import (
    load_purchases,
    load_products,
    load_branches,
    save_purchases,
)


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
BIDDING_ROOT = DATA_DIR / "supplier_bidding"
BIDDING_SETTINGS_FILE = BIDDING_ROOT / "settings.json"


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_all_branches(branch_id):
    return isinstance(branch_id, str) and branch_id.upper() == ALL_BRANCHES


def _load_scoped(loader, branch_id, **kwargs):
    if _is_all_branches(branch_id):
        try:
            bdf = load_branches()
        except Exception:
            bdf = pd.DataFrame()
        if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
            try:
                return loader(**kwargs)
            except Exception:
                return pd.DataFrame()
        frames = []
        for bid in bdf["branch_id"].astype(str).tolist():
            try:
                df = loader(branch_id=bid, **kwargs)
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    try:
        return loader(branch_id=branch_id, **kwargs)
    except TypeError:
        try:
            return loader(**kwargs)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _branch_label(branch_id):
    if _is_all_branches(branch_id):
        return "All Branches"
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                return f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()
    except Exception:
        pass
    return str(branch_id)


def _branch_slug(branch_id):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_").upper() or "HO"


def _branch_scope_selector(branches_df):
    role = st.session_state.get("role", "cashier")
    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})"
            for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            options,
            key="bidding_branch_scope",
            help="Owners may manage bids for any branch or view all at once.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Supplier bidding locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# PATHS PER BRANCH
# ==============================
def _branch_dir(branch_id):
    d = BIDDING_ROOT / _branch_slug(branch_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _suppliers_file(branch_id):
    return _branch_dir(branch_id) / "suppliers.csv"


def _bids_file(branch_id):
    return _branch_dir(branch_id) / "bids.csv"


SUPPLIER_COLUMNS = [
    "supplier_id", "branch_id", "supplier_name", "contact_person", "email",
    "phone", "address", "payment_terms", "lead_time_days", "rating",
    "active", "created_date",
]

BID_COLUMNS = [
    "bid_id", "branch_id", "po_number", "supplier_id", "supplier_name",
    "bid_amount", "original_amount", "bid_date", "delivery_days",
    "warranty_months", "payment_terms", "status", "notes",
    "evaluated_by", "evaluated_date",
]


# ==============================
# INITIALIZATION
# ==============================
def init_bidding_files():
    """Create the root directory and global settings file."""
    BIDDING_ROOT.mkdir(parents=True, exist_ok=True)

    if not BIDDING_SETTINGS_FILE.exists():
        settings = {
            "auto_accept_lowest_bid": True,
            "bidding_duration_days": 7,
            "require_minimum_bids": 2,
            "auto_reject_after_days": 14,
            "notify_suppliers": True,
            "preferred_supplier_bonus": 5,
            "minimum_bid_reduction": 5,
            "last_updated": datetime.now().isoformat(),
        }
        with open(BIDDING_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)


def _ensure_branch_files(branch_id):
    init_bidding_files()
    sf = _suppliers_file(branch_id)
    bf = _bids_file(branch_id)
    if not sf.exists():
        pd.DataFrame(columns=SUPPLIER_COLUMNS).to_csv(sf, index=False)
    if not bf.exists():
        pd.DataFrame(columns=BID_COLUMNS).to_csv(bf, index=False)


# ==============================
# LOADERS / SAVERS
# ==============================
def load_suppliers(branch_id=None):
    """
    Load suppliers for a branch (or aggregated across all when __ALL__).
    Legacy per-branch files that lack `branch_id` are auto-patched.
    """
    branch_id = _resolve_branch(branch_id)

    if _is_all_branches(branch_id):
        try:
            bdf = load_branches()
        except Exception:
            bdf = pd.DataFrame()
        if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
            return pd.DataFrame(columns=SUPPLIER_COLUMNS)
        frames = []
        for bid in bdf["branch_id"].astype(str).tolist():
            _ensure_branch_files(bid)
            try:
                df = pd.read_csv(_suppliers_file(bid))
                if "branch_id" not in df.columns:
                    df["branch_id"] = str(bid).upper()
                frames.append(df)
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=SUPPLIER_COLUMNS)

    _ensure_branch_files(branch_id)
    try:
        df = pd.read_csv(_suppliers_file(branch_id))
        if "branch_id" not in df.columns:
            df["branch_id"] = _branch_slug(branch_id)
        return df
    except Exception:
        return pd.DataFrame(columns=SUPPLIER_COLUMNS)


def save_suppliers(df, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        # Refuse to write to "all" — must target one branch.
        raise ValueError("save_suppliers requires a single branch, not __ALL__")
    _ensure_branch_files(branch_id)
    df.to_csv(_suppliers_file(branch_id), index=False)


def load_bids(branch_id=None):
    branch_id = _resolve_branch(branch_id)

    if _is_all_branches(branch_id):
        try:
            bdf = load_branches()
        except Exception:
            bdf = pd.DataFrame()
        if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
            return pd.DataFrame(columns=BID_COLUMNS)
        frames = []
        for bid in bdf["branch_id"].astype(str).tolist():
            _ensure_branch_files(bid)
            try:
                df = pd.read_csv(_bids_file(bid))
                if "branch_id" not in df.columns:
                    df["branch_id"] = str(bid).upper()
                frames.append(df)
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=BID_COLUMNS)

    _ensure_branch_files(branch_id)
    try:
        df = pd.read_csv(_bids_file(branch_id))
        if "branch_id" not in df.columns:
            df["branch_id"] = _branch_slug(branch_id)
        return df
    except Exception:
        return pd.DataFrame(columns=BID_COLUMNS)


def save_bids(df, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        raise ValueError("save_bids requires a single branch, not __ALL__")
    _ensure_branch_files(branch_id)
    df.to_csv(_bids_file(branch_id), index=False)


def load_bidding_settings():
    init_bidding_files()
    with open(BIDDING_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_bidding_settings(settings):
    with open(BIDDING_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# ==============================
# SUPPLIER SYNC FROM PURCHASES
# ==============================
def _get_supplier_col(df):
    for c in ["supplier", "supplier_name", "vendor", "provider"]:
        if c in df.columns:
            return c
    return None


def get_suppliers_from_purchases(branch_id=None):
    """Extract unique suppliers from the branch's purchases only."""
    branch_id = _resolve_branch(branch_id)
    purchases_df = _load_scoped(load_purchases, branch_id)

    if purchases_df is None or purchases_df.empty:
        return pd.DataFrame()

    supplier_col = _get_supplier_col(purchases_df)
    if supplier_col is None:
        return pd.DataFrame()

    suppliers = purchases_df[supplier_col].dropna().unique().tolist()
    suppliers = [
        str(s).strip() for s in suppliers
        if str(s).strip() and str(s).strip().lower() != "unknown"
    ]
    if not suppliers:
        return pd.DataFrame()

    branch_key = _branch_slug(branch_id)
    supplier_records = []
    for idx, name in enumerate(suppliers):
        supplier_records.append({
            "supplier_id": f"SUP{idx+1:03d}",
            "branch_id": branch_key,
            "supplier_name": name,
            "contact_person": "",
            "email": "",
            "phone": "",
            "address": "",
            "payment_terms": "NET30",
            "lead_time_days": 7,
            "rating": 0,
            "active": True,
            "created_date": datetime.now().isoformat(),
        })
    return pd.DataFrame(supplier_records)


def sync_suppliers_from_purchases(branch_id=None):
    """Add any new suppliers seen in this branch's purchases."""
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return
    purchases_suppliers = get_suppliers_from_purchases(branch_id=branch_id)
    existing = load_suppliers(branch_id=branch_id)

    if purchases_suppliers.empty:
        return
    if existing.empty:
        save_suppliers(purchases_suppliers, branch_id=branch_id)
        return

    existing_names = existing["supplier_name"].str.lower().tolist()
    new_rows = [
        row.to_dict() for _, row in purchases_suppliers.iterrows()
        if row["supplier_name"].lower() not in existing_names
    ]
    if new_rows:
        combined = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
        save_suppliers(combined, branch_id=branch_id)


def get_supplier_suggestions(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    purchases_df = _load_scoped(load_purchases, branch_id)
    if purchases_df is None or purchases_df.empty:
        return []
    supplier_col = _get_supplier_col(purchases_df)
    if supplier_col is None:
        return []
    suppliers = purchases_df[supplier_col].dropna().unique().tolist()
    suppliers = [
        str(s).strip() for s in suppliers
        if str(s).strip() and str(s).strip().lower() != "unknown"
    ]
    return sorted(set(suppliers))


# ==============================
# SUPPLIER CRUD
# ==============================
def generate_supplier_id(branch_id):
    suppliers_df = load_suppliers(branch_id=branch_id)
    if suppliers_df.empty:
        return "SUP001"
    existing_ids = suppliers_df["supplier_id"].tolist()
    numbers = []
    for s in existing_ids:
        if isinstance(s, str) and s.startswith("SUP"):
            try:
                numbers.append(int(s.replace("SUP", "")))
            except ValueError:
                pass
    next_num = max(numbers) + 1 if numbers else 1
    return f"SUP{next_num:03d}"


def add_supplier(supplier_name, contact_person, email, phone, address="",
                 payment_terms="NET30", lead_time_days=7, branch_id=None):
    """Add a supplier to the current branch only."""
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return None, "Please select a specific branch to add a supplier."

    suppliers_df = load_suppliers(branch_id=branch_id)

    if not suppliers_df.empty:
        existing = suppliers_df[
            suppliers_df["supplier_name"].str.lower() == supplier_name.lower()
        ]
        if not existing.empty:
            return None, f"Supplier '{supplier_name}' already exists in {_branch_label(branch_id)}"

    supplier_id = generate_supplier_id(branch_id)

    new_supplier = pd.DataFrame([{
        "supplier_id": supplier_id,
        "branch_id": _branch_slug(branch_id),
        "supplier_name": supplier_name,
        "contact_person": contact_person,
        "email": email,
        "phone": phone,
        "address": address,
        "payment_terms": payment_terms,
        "lead_time_days": lead_time_days,
        "rating": 0,
        "active": True,
        "created_date": datetime.now().isoformat(),
    }])

    suppliers_df = pd.concat([suppliers_df, new_supplier], ignore_index=True)
    save_suppliers(suppliers_df, branch_id=branch_id)
    return supplier_id, None


def delete_supplier(supplier_id, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return False, "Please select a specific branch to delete a supplier."

    suppliers_df = load_suppliers(branch_id=branch_id)
    bids_df = load_bids(branch_id=branch_id)

    if suppliers_df[suppliers_df["supplier_id"] == supplier_id].empty:
        return False, "Supplier not found"

    supplier_bids = bids_df[bids_df["supplier_id"] == supplier_id]
    accepted_bids = supplier_bids[supplier_bids["status"] == "ACCEPTED"]
    if not accepted_bids.empty:
        return False, f"Cannot delete supplier with {len(accepted_bids)} accepted bids. Reject bids first."

    suppliers_df = suppliers_df[suppliers_df["supplier_id"] != supplier_id]
    save_suppliers(suppliers_df, branch_id=branch_id)

    if not supplier_bids.empty:
        bids_df = bids_df[bids_df["supplier_id"] != supplier_id]
        save_bids(bids_df, branch_id=branch_id)

    return True, "Supplier deleted successfully"


def toggle_supplier_active(supplier_id, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return False
    suppliers_df = load_suppliers(branch_id=branch_id)
    idx = suppliers_df[suppliers_df["supplier_id"] == supplier_id].index
    if len(idx) == 0:
        return False
    suppliers_df.loc[idx[0], "active"] = not suppliers_df.loc[idx[0], "active"]
    save_suppliers(suppliers_df, branch_id=branch_id)
    return True


# ==============================
# BIDDING FLOW
# ==============================
def _get_po_col(df):
    for c in ["po_number", "po", "order_number"]:
        if c in df.columns:
            return c
    return None


def _get_total_col(df):
    for c in ["total_cost", "total", "amount"]:
        if c in df.columns:
            return c
    return None


def create_bidding_opportunity(po_number, total_amount, supplier_ids=None, branch_id=None):
    """Create bid records for the given PO, for this branch's suppliers only."""
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return 0, "Please select a specific branch to create a bidding opportunity."

    sync_suppliers_from_purchases(branch_id=branch_id)
    bids_df = load_bids(branch_id=branch_id)
    suppliers_df = load_suppliers(branch_id=branch_id)

    existing = bids_df[bids_df["po_number"] == po_number]
    if not existing.empty:
        return 0, "Bidding opportunity already exists for this PO"

    if supplier_ids:
        eligible = suppliers_df[suppliers_df["supplier_id"].isin(supplier_ids)]
    else:
        eligible = suppliers_df[suppliers_df["active"] == True]  # noqa: E712

    if eligible.empty:
        return 0, "No eligible suppliers found. Please add suppliers first."

    branch_key = _branch_slug(branch_id)
    new_bids = []
    for _, supplier in eligible.iterrows():
        bid_id = hashlib.md5(
            f"{po_number}{supplier['supplier_id']}{datetime.now().isoformat()}{branch_key}".encode()
        ).hexdigest()[:16]
        new_bids.append({
            "bid_id": bid_id,
            "branch_id": branch_key,
            "po_number": po_number,
            "supplier_id": supplier["supplier_id"],
            "supplier_name": supplier["supplier_name"],
            "bid_amount": total_amount,
            "original_amount": total_amount,
            "bid_date": datetime.now().isoformat(),
            "delivery_days": supplier.get("lead_time_days", 7),
            "warranty_months": 12,
            "payment_terms": supplier.get("payment_terms", "NET30"),
            "status": "PENDING",
            "notes": "",
            "evaluated_by": "",
            "evaluated_date": "",
        })

    bids_df = pd.concat([bids_df, pd.DataFrame(new_bids)], ignore_index=True)
    save_bids(bids_df, branch_id=branch_id)
    return len(new_bids), None


def submit_bid(po_number, supplier_id, supplier_name, bid_amount,
               delivery_days, warranty_months, payment_terms, notes="",
               branch_id=None):
    """Submit a bid for a PO within this branch."""
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return False, "Please select a specific branch."

    bids_df = load_bids(branch_id=branch_id)
    existing = bids_df[
        (bids_df["po_number"] == po_number) & (bids_df["supplier_id"] == supplier_id)
    ]

    if not existing.empty:
        idx = existing.index[0]
        bids_df.loc[idx, "bid_amount"] = bid_amount
        bids_df.loc[idx, "delivery_days"] = delivery_days
        bids_df.loc[idx, "warranty_months"] = warranty_months
        bids_df.loc[idx, "payment_terms"] = payment_terms
        bids_df.loc[idx, "notes"] = notes
        bids_df.loc[idx, "bid_date"] = datetime.now().isoformat()
        save_bids(bids_df, branch_id=branch_id)
        return True, "Bid updated successfully"

    po_bids = bids_df[bids_df["po_number"] == po_number]
    if len(po_bids) >= 20:
        return False, "Maximum bids reached for this PO"

    bid_id = hashlib.md5(
        f"{po_number}{supplier_id}{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]

    purchases_df = _load_scoped(load_purchases, branch_id)
    po_col = _get_po_col(purchases_df) if purchases_df is not None else None
    total_col = _get_total_col(purchases_df) if purchases_df is not None else None
    original_amount = bid_amount
    if purchases_df is not None and not purchases_df.empty and po_col and total_col:
        po_data = purchases_df[purchases_df[po_col] == po_number]
        if not po_data.empty:
            original_amount = float(po_data[total_col].iloc[0])

    new_bid = pd.DataFrame([{
        "bid_id": bid_id,
        "branch_id": _branch_slug(branch_id),
        "po_number": po_number,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "bid_amount": bid_amount,
        "original_amount": original_amount,
        "bid_date": datetime.now().isoformat(),
        "delivery_days": delivery_days,
        "warranty_months": warranty_months,
        "payment_terms": payment_terms,
        "status": "PENDING",
        "notes": notes,
        "evaluated_by": "",
        "evaluated_date": "",
    }])

    bids_df = pd.concat([bids_df, new_bid], ignore_index=True)
    save_bids(bids_df, branch_id=branch_id)
    return True, "Bid submitted successfully"


def evaluate_bids(po_number, branch_id=None):
    """Score all pending bids for a PO and optionally accept the best one."""
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return None, "Please select a specific branch."

    bids_df = load_bids(branch_id=branch_id)
    settings = load_bidding_settings()

    po_bids = bids_df[
        (bids_df["po_number"] == po_number) & (bids_df["status"] == "PENDING")
    ]
    if po_bids.empty:
        return None, "No bids to evaluate"

    scores = []
    for _, bid in po_bids.iterrows():
        min_bid = po_bids["bid_amount"].min()
        price_score = (min_bid / bid["bid_amount"]) * 50 if min_bid > 0 else 0

        min_delivery = po_bids["delivery_days"].min()
        delivery_score = (min_delivery / bid["delivery_days"]) * 20 if min_delivery > 0 else 0

        max_warranty = po_bids["warranty_months"].max()
        warranty_score = (bid["warranty_months"] / max_warranty) * 15 if max_warranty > 0 else 0

        payment_score = 15 if bid["payment_terms"] in ["NET15", "COD"] else 10

        scores.append({
            "bid": bid,
            "score": price_score + delivery_score + warranty_score + payment_score,
            "price_score": price_score,
            "delivery_score": delivery_score,
            "warranty_score": warranty_score,
            "payment_score": payment_score,
        })

    scores.sort(key=lambda x: x["score"], reverse=True)
    best = scores[0]

    if settings.get("auto_accept_lowest_bid", True):
        original_amount = best["bid"]["original_amount"]
        reduction_pct = (
            ((original_amount - best["bid"]["bid_amount"]) / original_amount) * 100
            if original_amount > 0 else 0
        )
        min_reduction = settings.get("minimum_bid_reduction", 5)
        if reduction_pct >= min_reduction:
            accept_bid(best["bid"]["bid_id"], branch_id=branch_id)
            return best["bid"], (
                f"Auto-accepted {best['bid']['supplier_name']} "
                f"(${best['bid']['bid_amount']:,.2f}) for {_branch_label(branch_id)}"
            )

    return best["bid"], (
        f"Best bid for {_branch_label(branch_id)}: {best['bid']['supplier_name']} "
        f"(Score: {best['score']:.1f})"
    )


def accept_bid(bid_id, branch_id=None):
    """Accept a bid within a branch. Updates this branch's purchases only."""
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return False

    bids_df = load_bids(branch_id=branch_id)
    idx = bids_df[bids_df["bid_id"] == bid_id].index
    if len(idx) == 0:
        return False

    bids_df.loc[idx[0], "status"] = "ACCEPTED"
    bids_df.loc[idx[0], "evaluated_date"] = datetime.now().isoformat()

    po_number = bids_df.loc[idx[0], "po_number"]
    winning_supplier = bids_df.loc[idx[0], "supplier_name"]

    # Reject all other bids for this PO within the same branch
    bids_df.loc[
        (bids_df["po_number"] == po_number) & (bids_df["bid_id"] != bid_id),
        "status"
    ] = "REJECTED"
    save_bids(bids_df, branch_id=branch_id)

    # Update the branch's purchases only
    purchases_df = _load_scoped(load_purchases, branch_id)
    if purchases_df is None or purchases_df.empty:
        return True  # Nothing to update

    po_col = _get_po_col(purchases_df)
    if po_col is None:
        return True

    mask = purchases_df[po_col].astype(str) == str(po_number)
    if mask.any():
        purchases_df.loc[mask, "supplier"] = winning_supplier
        if "status" in purchases_df.columns:
            purchases_df.loc[mask, "status"] = "APPROVED"
        save_purchases(purchases_df, branch_id=branch_id)

    return True


def get_bidding_summary(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    bids_df = load_bids(branch_id=branch_id)

    if bids_df is None or bids_df.empty:
        return {
            "total_bids": 0, "pending_bids": 0, "accepted_bids": 0,
            "rejected_bids": 0, "total_savings": 0, "avg_discount": 0,
        }

    total_bids = len(bids_df)
    pending = len(bids_df[bids_df["status"] == "PENDING"])
    accepted = len(bids_df[bids_df["status"] == "ACCEPTED"])
    rejected = len(bids_df[bids_df["status"] == "REJECTED"])

    accepted_bids = bids_df[bids_df["status"] == "ACCEPTED"]
    if not accepted_bids.empty:
        savings = (accepted_bids["original_amount"] - accepted_bids["bid_amount"]).sum()
        avg_discount = (
            (accepted_bids["original_amount"] - accepted_bids["bid_amount"])
            / accepted_bids["original_amount"] * 100
        ).mean()
    else:
        savings = 0
        avg_discount = 0

    return {
        "total_bids": total_bids,
        "pending_bids": pending,
        "accepted_bids": accepted,
        "rejected_bids": rejected,
        "total_savings": savings,
        "avg_discount": avg_discount,
    }


# ==============================
# SUPPLIER MANAGEMENT PAGE
# ==============================
def supplier_management_page(branch_id=None):
    st.markdown("## Supplier Management")
    st.caption("Manage suppliers for the bidding system — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can manage suppliers.")
        return

    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        st.warning("Select a specific branch to add or delete suppliers.")
        suppliers_df = load_suppliers(branch_id=ALL_BRANCHES)
        if not suppliers_df.empty:
            st.dataframe(suppliers_df, use_container_width=True, hide_index=True)
        return

    label = _branch_label(branch_id)

    if "supplier_added" not in st.session_state:
        st.session_state.supplier_added = False
    if "supplier_button_clicked" not in st.session_state:
        st.session_state.supplier_button_clicked = False
    if "supplier_to_delete" not in st.session_state:
        st.session_state.supplier_to_delete = None

    sync_suppliers_from_purchases(branch_id=branch_id)

    tab1, tab2 = st.tabs(["Add Supplier", "Supplier List"])

    with tab1:
        st.markdown(f"### Add New Supplier to {label}")

        supplier_suggestions = get_supplier_suggestions(branch_id=branch_id)

        col1, col2 = st.columns(2)
        with col1:
            if supplier_suggestions:
                supplier_name = st.selectbox(
                    "Supplier Name (from purchases)",
                    options=[""] + supplier_suggestions,
                    key=f"sup_name_select_{branch_id}",
                )
                supplier_name_input = st.text_input(
                    "Or type new supplier name",
                    value="" if supplier_name else "",
                    key=f"sup_name_input_{branch_id}",
                    placeholder="e.g., National Foods",
                )
                final_supplier_name = supplier_name if supplier_name else supplier_name_input
            else:
                final_supplier_name = st.text_input(
                    "Supplier Name *", key=f"sup_name_{branch_id}",
                    placeholder="e.g., National Foods",
                )
            contact_person = st.text_input(
                "Contact Person *", key=f"sup_contact_{branch_id}", placeholder="John Doe"
            )
            email = st.text_input(
                "Email", key=f"sup_email_{branch_id}", placeholder="supplier@company.com"
            )

        with col2:
            phone = st.text_input("Phone", key=f"sup_phone_{branch_id}",
                                  placeholder="0777123456")
            payment_terms = st.selectbox(
                "Payment Terms", ["NET15", "NET30", "NET45", "NET60", "COD"],
                key=f"sup_payment_{branch_id}",
            )
            lead_time = st.number_input(
                "Lead Time (days)", min_value=1, max_value=60, value=7,
                key=f"sup_lead_{branch_id}",
            )

        address = st.text_area("Address", key=f"sup_address_{branch_id}",
                               placeholder="Physical address")

        if st.button("Add Supplier", type="primary",
                     key=f"add_supplier_btn_{branch_id}", use_container_width=True):
            if not st.session_state.supplier_button_clicked:
                st.session_state.supplier_button_clicked = True

                if final_supplier_name and contact_person:
                    supplier_id, error = add_supplier(
                        supplier_name=final_supplier_name,
                        contact_person=contact_person,
                        email=email,
                        phone=phone,
                        address=address,
                        payment_terms=payment_terms,
                        lead_time_days=lead_time,
                        branch_id=branch_id,
                    )
                    if error:
                        st.error(error)
                    else:
                        st.success(f"Supplier {final_supplier_name} added to {label}! ID: {supplier_id}")
                        st.session_state.supplier_added = True
                        st.rerun()
                else:
                    st.error("Please enter supplier name and contact person")

                st.session_state.supplier_button_clicked = False

    with tab2:
        st.markdown(f"### Supplier List — {label}")

        suppliers_df = load_suppliers(branch_id=branch_id)

        if suppliers_df.empty:
            st.info(f"No suppliers found for {label}. Add one above.")
        else:
            for idx, supplier in suppliers_df.iterrows():
                col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 2, 2, 1, 1, 1, 1])
                with col1:
                    st.write(f"**{supplier['supplier_name']}**")
                    st.caption(f"ID: {supplier['supplier_id']}")
                with col2:
                    st.write(f"{supplier['contact_person']}")
                    st.caption(f"{supplier['email']}")
                with col3:
                    st.write(f"{supplier['payment_terms']}")
                    st.caption(f"{supplier['lead_time_days']} days")
                with col4:
                    rating = supplier.get('rating', 0)
                    st.write("⭐" * int(rating) if rating > 0 else "No rating")
                with col5:
                    st.write("Active" if supplier['active'] else "Inactive")
                with col6:
                    toggle_label = "Deactivate" if supplier['active'] else "Activate"
                    if st.button(toggle_label, key=f"toggle_{supplier['supplier_id']}_{branch_id}"):
                        if not st.session_state.supplier_button_clicked:
                            st.session_state.supplier_button_clicked = True
                            toggle_supplier_active(supplier['supplier_id'], branch_id=branch_id)
                            st.rerun()
                            st.session_state.supplier_button_clicked = False
                with col7:
                    if st.button("Delete", key=f"delete_{supplier['supplier_id']}_{branch_id}"):
                        if not st.session_state.supplier_button_clicked:
                            st.session_state.supplier_button_clicked = True
                            st.session_state.supplier_to_delete = supplier['supplier_id']
                st.divider()

            if st.session_state.supplier_to_delete:
                sid = st.session_state.supplier_to_delete
                match = suppliers_df[suppliers_df["supplier_id"] == sid]
                sname = match["supplier_name"].iloc[0] if not match.empty else sid

                st.warning(f"Are you sure you want to delete supplier **'{sname}'** from {label}?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Yes, Delete Permanently",
                                 key=f"confirm_delete_{branch_id}",
                                 use_container_width=True):
                        success, message = delete_supplier(sid, branch_id=branch_id)
                        st.session_state.supplier_to_delete = None
                        st.session_state.supplier_button_clicked = False
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                with col2:
                    if st.button("Cancel", key=f"cancel_delete_{branch_id}",
                                 use_container_width=True):
                        st.session_state.supplier_to_delete = None
                        st.session_state.supplier_button_clicked = False
                        st.rerun()

            csv = suppliers_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Suppliers (CSV)",
                data=csv,
                file_name=(
                    f"suppliers_{_branch_slug(branch_id)}_"
                    f"{datetime.now().strftime('%Y%m%d')}.csv"
                ),
                mime="text/csv",
                use_container_width=True,
            )


# ==============================
# DASHBOARD
# ==============================
def supplier_bidding_dashboard(branch_id=None):
    st.title("Supplier Bidding System")
    st.caption("Competitive bidding for purchase orders — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can manage supplier bidding.")
        return

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Bidding on behalf of: **{branch_label}**")

    init_bidding_files()
    if not _is_all_branches(branch_id):
        sync_suppliers_from_purchases(branch_id=branch_id)

    if "bid_created" not in st.session_state:
        st.session_state.bid_created = False
    if "bidding_button_clicked" not in st.session_state:
        st.session_state.bidding_button_clicked = False

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Bidding Overview",
        "Create Bid Opportunity",
        "Evaluate Bids",
        "Supplier Management",
        "Bidding Settings",
    ])

    # ==============================
    # TAB 1: OVERVIEW
    # ==============================
    with tab1:
        st.markdown("## Bidding Overview")

        summary = get_bidding_summary(branch_id=branch_id)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Bids", summary["total_bids"])
        with col2:
            st.metric("Pending Bids", summary["pending_bids"])
        with col3:
            st.metric("Accepted Bids", summary["accepted_bids"])
        with col4:
            st.metric("Total Savings", f"${summary['total_savings']:,.2f}")

        st.markdown("---")
        st.markdown("### Recent Bids")

        bids_df = load_bids(branch_id=branch_id)
        if not bids_df.empty:
            recent = bids_df.sort_values("bid_date", ascending=False).head(20)
            cols = [c for c in ["bid_date", "branch_id", "po_number", "supplier_name",
                                "bid_amount", "status"] if c in recent.columns]
            st.dataframe(
                recent[cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "bid_amount": st.column_config.NumberColumn("Bid Amount", format="$%.2f"),
                },
            )
        else:
            st.info(f"No bids yet for {branch_label}.")

        if summary["total_savings"] > 0:
            st.markdown("### Savings Impact")
            accepted_bids = bids_df[bids_df["status"] == "ACCEPTED"]
            if not accepted_bids.empty:
                savings_data = [
                    {
                        "PO": bid["po_number"],
                        "Supplier": bid["supplier_name"],
                        "Original": bid["original_amount"],
                        "Bid": bid["bid_amount"],
                        "Saved": bid["original_amount"] - bid["bid_amount"],
                    }
                    for _, bid in accepted_bids.iterrows()
                ]
                fig = px.bar(pd.DataFrame(savings_data), x="PO", y="Saved",
                             title=f"Savings per PO — {branch_label}", color="Supplier")
                st.plotly_chart(fig, use_container_width=True)

    # ==============================
    # TAB 2: CREATE OPPORTUNITY
    # ==============================
    with tab2:
        st.markdown(f"## Create Bid Opportunity — {branch_label}")

        if _is_all_branches(branch_id):
            st.warning("Select a specific branch to create a bidding opportunity.")
        else:
            purchases_df = _load_scoped(load_purchases, branch_id)
            if purchases_df is None or purchases_df.empty:
                st.info(f"No purchase orders found for {branch_label}.")
            else:
                po_col = _get_po_col(purchases_df)
                if po_col is None:
                    st.error("Purchases table has no po_number column.")
                else:
                    bids_df = load_bids(branch_id=branch_id)
                    pos_with_bids = bids_df["po_number"].unique().tolist() if not bids_df.empty else []
                    pending_pos = purchases_df[~purchases_df[po_col].isin(pos_with_bids)]
                    if "status" in pending_pos.columns:
                        pending_pos = pending_pos[
                            pending_pos["status"].isin(["PENDING", "APPROVED"])
                        ]

                    if pending_pos.empty:
                        st.info("No pending purchase orders available for bidding.")
                    else:
                        total_col = _get_total_col(pending_pos)
                        label_func = (
                            (lambda x: f"{x} — ${pending_pos[pending_pos[po_col] == x][total_col].iloc[0]:,.2f}")
                            if total_col else (lambda x: x)
                        )
                        selected_po = st.selectbox(
                            "Select Purchase Order",
                            pending_pos[po_col].tolist(),
                            key=f"select_po_bid_{branch_id}",
                            format_func=label_func,
                        )
                        if selected_po:
                            po_data = pending_pos[pending_pos[po_col] == selected_po].iloc[0]
                            po_total = po_data.get(total_col, 0) if total_col else 0

                            st.markdown("### PO Details")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**PO Number:** {selected_po}")
                                st.write(f"**Total Value:** ${po_total:,.2f}")
                            with col2:
                                items_count = len(purchases_df[purchases_df[po_col] == selected_po])
                                st.write(f"**Items:** {items_count}")

                            suppliers_df = load_suppliers(branch_id=branch_id)
                            if suppliers_df.empty:
                                st.warning(f"No suppliers found for {branch_label}. Add suppliers in the Supplier Management tab.")
                            else:
                                st.markdown("### Select Suppliers to Invite")
                                invite_all = st.checkbox("Invite All Active Suppliers", value=True,
                                                         key=f"invite_all_{branch_id}")

                                if invite_all:
                                    selected_suppliers = suppliers_df[
                                        suppliers_df["active"] == True  # noqa: E712
                                    ]["supplier_id"].tolist()
                                    st.info(f"Will invite {len(selected_suppliers)} suppliers for {branch_label}")
                                else:
                                    selected_suppliers = st.multiselect(
                                        "Select Suppliers",
                                        suppliers_df["supplier_id"].tolist(),
                                        key=f"selected_suppliers_list_{branch_id}",
                                        format_func=lambda x: suppliers_df[
                                            suppliers_df["supplier_id"] == x
                                        ]["supplier_name"].iloc[0],
                                    )

                                if st.button("Create Bidding Opportunity",
                                             type="primary",
                                             key=f"create_bid_btn_{branch_id}",
                                             use_container_width=True):
                                    if not st.session_state.bidding_button_clicked:
                                        st.session_state.bidding_button_clicked = True

                                        if selected_suppliers:
                                            count, error = create_bidding_opportunity(
                                                selected_po, po_total, selected_suppliers,
                                                branch_id=branch_id,
                                            )
                                            if error:
                                                st.warning(error)
                                            else:
                                                st.success(
                                                    f"Bidding opportunity created for {branch_label}! "
                                                    f"{count} suppliers invited."
                                                )
                                                st.session_state.bid_created = True
                                                st.rerun()
                                        else:
                                            st.error("Please select at least one supplier")

                                        st.session_state.bidding_button_clicked = False

    # ==============================
    # TAB 3: EVALUATE BIDS
    # ==============================
    with tab3:
        st.markdown(f"## Evaluate Bids — {branch_label}")

        if _is_all_branches(branch_id):
            st.warning("Select a specific branch to evaluate bids.")
        else:
            bids_df = load_bids(branch_id=branch_id)
            pending_bids = bids_df[bids_df["status"] == "PENDING"] if not bids_df.empty else pd.DataFrame()

            if pending_bids.empty:
                st.info(f"No pending bids for {branch_label}")
            else:
                for po_number in pending_bids["po_number"].unique():
                    po_bids = pending_bids[pending_bids["po_number"] == po_number]

                    with st.expander(f"PO: {po_number} — {len(po_bids)} bids received"):
                        bid_data = []
                        for _, bid in po_bids.iterrows():
                            reduction = (
                                (bid["original_amount"] - bid["bid_amount"]) / bid["original_amount"] * 100
                                if bid["original_amount"] > 0 else 0
                            )
                            bid_data.append({
                                "Supplier": bid["supplier_name"],
                                "Bid Amount": f"${bid['bid_amount']:,.2f}",
                                "Original": f"${bid['original_amount']:,.2f}",
                                "Savings": f"${bid['original_amount'] - bid['bid_amount']:,.2f}",
                                "Reduction": f"{reduction:.1f}%",
                                "Delivery": f"{bid['delivery_days']} days",
                                "Warranty": f"{bid['warranty_months']} months",
                                "Payment Terms": bid["payment_terms"],
                                "bid_id": bid["bid_id"],
                            })

                        bid_df = pd.DataFrame(bid_data)
                        st.dataframe(bid_df.drop(columns=["bid_id"]),
                                     use_container_width=True, hide_index=True)

                        if st.button(f"Evaluate Best Bid for {po_number}",
                                     key=f"eval_{po_number}_{branch_id}"):
                            if not st.session_state.bidding_button_clicked:
                                st.session_state.bidding_button_clicked = True
                                best_bid, message = evaluate_bids(po_number, branch_id=branch_id)
                                if best_bid is not None:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.warning(message)
                                st.session_state.bidding_button_clicked = False

                        st.markdown("**Or manually accept a bid:**")
                        selected_bid = st.selectbox(
                            "Select bid to accept",
                            bid_df["bid_id"].tolist(),
                            key=f"accept_{po_number}_{branch_id}",
                            format_func=lambda x: bid_df[bid_df["bid_id"] == x]["Supplier"].iloc[0],
                        )
                        if st.button("Accept Selected Bid",
                                     key=f"accept_btn_{po_number}_{branch_id}"):
                            if not st.session_state.bidding_button_clicked:
                                st.session_state.bidding_button_clicked = True
                                if accept_bid(selected_bid, branch_id=branch_id):
                                    st.success(
                                        f"Bid accepted for {branch_label}! Purchase order updated."
                                    )
                                    st.rerun()
                                st.session_state.bidding_button_clicked = False

    # ==============================
    # TAB 4: SUPPLIER MANAGEMENT
    # ==============================
    with tab4:
        supplier_management_page(branch_id=branch_id)

    # ==============================
    # TAB 5: SETTINGS
    # ==============================
    with tab5:
        st.markdown("## Bidding Settings")
        st.caption("Settings are shared across all branches.")

        settings = load_bidding_settings()

        col1, col2 = st.columns(2)
        with col1:
            auto_accept = st.toggle("Auto-accept lowest bid",
                                    value=settings.get("auto_accept_lowest_bid", True),
                                    key=f"auto_accept_{branch_id}")
            bidding_days = st.number_input(
                "Bidding duration (days)", min_value=1, max_value=30,
                value=settings.get("bidding_duration_days", 7),
                key=f"bidding_days_{branch_id}",
            )
            min_bids = st.number_input(
                "Minimum bids required", min_value=1, max_value=5,
                value=settings.get("require_minimum_bids", 2),
                key=f"min_bids_{branch_id}",
            )
        with col2:
            auto_reject = st.number_input(
                "Auto-reject after (days)", min_value=7, max_value=60,
                value=settings.get("auto_reject_after_days", 14),
                key=f"auto_reject_{branch_id}",
            )
            min_reduction = st.number_input(
                "Minimum reduction % for auto-accept", min_value=0, max_value=50,
                value=settings.get("minimum_bid_reduction", 5),
                key=f"min_reduction_{branch_id}",
            )
            preferred_bonus = st.number_input(
                "Preferred supplier bonus (%)", min_value=0, max_value=20,
                value=settings.get("preferred_supplier_bonus", 5),
                key=f"preferred_bonus_{branch_id}",
            )

        if st.button("Save Settings", type="primary",
                     key=f"save_settings_btn_{branch_id}",
                     use_container_width=True):
            if not st.session_state.bidding_button_clicked:
                st.session_state.bidding_button_clicked = True
                settings["auto_accept_lowest_bid"] = auto_accept
                settings["bidding_duration_days"] = bidding_days
                settings["require_minimum_bids"] = min_bids
                settings["auto_reject_after_days"] = auto_reject
                settings["minimum_bid_reduction"] = min_reduction
                settings["preferred_supplier_bonus"] = preferred_bonus
                settings["last_updated"] = datetime.now().isoformat()
                save_bidding_settings(settings)
                st.success("Settings saved successfully!")
                st.session_state.bidding_button_clicked = False

        st.markdown("---")
        st.markdown("### How Bidding Works")
        st.info(
            "**Bidding Process:**\n\n"
            "1. **Create Opportunity** — select a purchase order and invite suppliers for the current branch\n"
            "2. **Suppliers Bid** — suppliers submit their best offers\n"
            "3. **Automatic Evaluation** — bids are scored on price, delivery, warranty, and payment terms\n"
            "4. **Auto-Accept** — if a bid saves more than the configured %, it is auto-accepted\n"
            "5. **Manual Approval** — you can always review and accept any bid manually\n\n"
            "**Scoring Weights:**\n"
            "- Price: 50%\n"
            "- Delivery Time: 20%\n"
            "- Warranty: 15%\n"
            "- Payment Terms: 15%"
        )


# ==============================
# SUPPLIER PORTAL
# ==============================
def supplier_bidding_portal(branch_id=None):
    st.title("Supplier Bidding Portal")
    st.caption("View bidding opportunities and submit your best offers")

    branch_id = _resolve_branch(branch_id)
    supplier_id = st.session_state.get("supplier_id", None)
    supplier_name = st.session_state.get("supplier_name", None)

    if not supplier_id:
        st.warning("Please login as a supplier to access this portal")
        st.info("Demo Supplier Login - Coming Soon")
        return

    if _is_all_branches(branch_id):
        st.error("Please select a specific branch.")
        return

    if "supplier_bid_button_clicked" not in st.session_state:
        st.session_state.supplier_bid_button_clicked = False

    bids_df = load_bids(branch_id=branch_id)
    all_bids_for_supplier = (
        bids_df[bids_df["supplier_id"] == supplier_id] if not bids_df.empty else pd.DataFrame()
    )
    bid_pos = all_bids_for_supplier["po_number"].tolist() if not all_bids_for_supplier.empty else []

    purchases_df = _load_scoped(load_purchases, branch_id)
    if purchases_df is None or purchases_df.empty:
        open_pos = pd.DataFrame()
    else:
        po_col = _get_po_col(purchases_df)
        if po_col and "status" in purchases_df.columns:
            open_pos = purchases_df[
                (purchases_df["status"] == "PENDING") & (~purchases_df[po_col].isin(bid_pos))
            ]
        else:
            open_pos = pd.DataFrame()

    if not open_pos.empty and po_col:
        st.markdown(f"### Open Bidding Opportunities — {_branch_label(branch_id)}")
        selected_po = st.selectbox("Select PO to bid on", open_pos[po_col].tolist(),
                                   key=f"supplier_po_select_{branch_id}")

        if selected_po:
            po_data = open_pos[open_pos[po_col] == selected_po].iloc[0]
            total_col = _get_total_col(open_pos)

            st.markdown("### Submit Your Bid")
            col1, col2 = st.columns(2)
            with col1:
                bid_amount = st.number_input(
                    "Your Bid Amount ($)", min_value=0.01,
                    value=float(po_data.get(total_col, 0)) if total_col else 0.0,
                    step=10.0, key=f"supplier_bid_amount_{branch_id}",
                )
                delivery_days = st.number_input("Delivery Time (days)", min_value=1, value=7,
                                                 key=f"supplier_delivery_{branch_id}")
            with col2:
                warranty_months = st.number_input("Warranty (months)", min_value=0, value=12,
                                                   key=f"supplier_warranty_{branch_id}")
                payment_terms = st.selectbox(
                    "Payment Terms", ["NET15", "NET30", "NET45", "NET60", "COD"],
                    key=f"supplier_payment_{branch_id}",
                )

            notes = st.text_area("Additional Notes", key=f"supplier_notes_{branch_id}",
                                 placeholder="Any special conditions or offers...")

            if st.button("Submit Bid", type="primary",
                         key=f"submit_supplier_bid_{branch_id}",
                         use_container_width=True):
                if not st.session_state.supplier_bid_button_clicked:
                    st.session_state.supplier_bid_button_clicked = True
                    success, message = submit_bid(
                        po_number=selected_po,
                        supplier_id=supplier_id,
                        supplier_name=supplier_name,
                        bid_amount=bid_amount,
                        delivery_days=delivery_days,
                        warranty_months=warranty_months,
                        payment_terms=payment_terms,
                        notes=notes,
                        branch_id=branch_id,
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                    st.session_state.supplier_bid_button_clicked = False

    if not all_bids_for_supplier.empty:
        st.markdown("### Your Submitted Bids")
        cols = [c for c in ["po_number", "bid_amount", "delivery_days", "status", "bid_date"]
                if c in all_bids_for_supplier.columns]
        st.dataframe(
            all_bids_for_supplier[cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "bid_amount": st.column_config.NumberColumn("Bid Amount", format="$%.2f"),
            },
        )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    supplier_bidding_dashboard()