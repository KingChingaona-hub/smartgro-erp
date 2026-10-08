"""
Purchases Management Module
Handles purchase orders, receiving stock, and supplier management
ADDED: Bulk-confirm AND receive all pending POs in one action, using the
       exact same stock-update flow as the single PO receive.
Branch-aware: every loader and saver is scoped to the session branch.
Cache-safe: no @st.cache_data on reads, and every write path clears the
            Streamlit cache and reruns, so a fresh PO is visible in the
            Receive tab immediately.

FIXED: create paths now pass ONLY the new PO rows to save_purchases,
       and manual-item barcodes are generated as 13-digit numeric strings
       so validate_barcode accepts them.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from backend.core.db_adapter import (
    load_products,
    load_purchases,
    save_purchases,
    save_products,
    get_db_connection,
    load_branches,
)


# ==============================
# CANONICAL STATUS VOCABULARY
# ==============================
STATUS_PENDING = "PENDING"
STATUS_PARTIAL = "PARTIALLY_RECEIVED"
STATUS_COMPLETED = "COMPLETED"

RECEIVABLE_STATUSES = (STATUS_PENDING, STATUS_PARTIAL)

_LEGACY_STATUS_MAP = {
    "RECEIVED": STATUS_COMPLETED,
    "CONFIRMED": STATUS_PENDING,
}


def _normalize_status(value):
    """Map any stored status to a canonical value. Unknown -> PENDING."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return STATUS_PENDING
    s = str(value).strip().upper()
    if s in _LEGACY_STATUS_MAP:
        return _LEGACY_STATUS_MAP[s]
    if s in (STATUS_PENDING, STATUS_PARTIAL, STATUS_COMPLETED):
        return s
    if not s:
        return STATUS_PENDING
    return STATUS_PENDING


def _migrate_statuses(df):
    """In-memory normalization of the status column. Returns df."""
    if df is None or df.empty:
        return df
    df = df.copy()
    if "status" not in df.columns:
        df["status"] = STATUS_PENDING
    df["status"] = df["status"].apply(_normalize_status)
    return df


# ==============================
# SESSION BRANCH HELPERS
# ==============================
def _get_session_branch():
    """
    Return the authoritative branch for the current session.
    Prefers `current_branch_code` (set by the branch-selection screen)
    over `user_branch` (which may be a stale default).
    """
    return (
        st.session_state.get("current_branch_code")
        or st.session_state.get("user_branch")
        or "HO"
    )


def _branch_display_name(branch_id):
    try:
        df = load_branches()
        if df is not None and not df.empty and "branch_id" in df.columns:
            match = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                name = match.iloc[0].get("branch_name", "")
                if name:
                    return f"{name} ({branch_id})"
    except Exception:
        pass
    return str(branch_id)


# ==============================
# GENERATE PO NUMBER
# ==============================
def generate_po_number():
    """Generate unique purchase order number"""
    return f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"


# ==============================
# GENERATE 13-DIGIT NUMERIC BARCODE
# ==============================
def _generate_numeric_barcode(seed_index=0):
    """
    Generate a 13-digit numeric barcode that validate_barcode will accept.

    The old code produced strings like "MAN-20250101120000123456" which
    validate_barcode rejects (it requires digits only). This function
    produces a 13-character numeric string.
    """
    # Prefix with '2' so it never collides with the fallback '9...' barcodes
    # used elsewhere and is clearly a generated (not scanned) code.
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")  # 20 digits
    core = stamp[:12]
    idx = f"{seed_index % 100:02d}"
    raw = "2" + core + idx          # 1 + 12 + 2 = 15 chars
    return raw[:13].ljust(13, "0")


# ==============================
# HELPER: CHECK IF PRODUCT SUPPORTS DECIMAL
# ==============================
def supports_decimal(product_name, category=""):
    """Check if a product supports decimal quantities"""
    if not product_name:
        return False

    name_lower = str(product_name).lower()
    category_lower = str(category).lower()

    decimal_keywords = [
        "gas", "kg", "bread", "loaf", "flour", "sugar",
        "rice", "maize meal", "cooking oil", "milk",
        "liquid", "weight", "kg"
    ]

    for keyword in decimal_keywords:
        if keyword in name_lower or keyword in category_lower:
            return True

    return False


# ==============================
# GET SUPPLIER SUGGESTIONS - WITH CACHING (branch-scoped)
# ==============================
@st.cache_data(ttl=300)
def get_supplier_suggestions(branch_id: str):
    """Get unique supplier names from purchase history for autocomplete (branch-scoped)"""
    try:
        purchases_df = load_purchases(branch_id=branch_id)
        if purchases_df.empty:
            return []

        if "supplier" not in purchases_df.columns:
            return []

        suppliers = purchases_df["supplier"].dropna().unique().tolist()
        suppliers = [str(s).strip() for s in suppliers if str(s).strip()]
        return sorted(set(suppliers))
    except Exception as e:
        print(f"Error getting supplier suggestions: {e}")
        return []


# ==============================
# GET ALL PENDING POs (branch-scoped)
# ==============================
def get_all_pending_pos(branch_id=None):
    """
    Return a list of dicts summarising every PO currently PENDING or
    PARTIALLY_RECEIVED in this branch. Each dict contains: po_number,
    supplier, item_count, total_value, expected_date.
    """
    if branch_id is None:
        branch_id = _get_session_branch()

    try:
        purchases_df = _migrate_statuses(load_purchases(branch_id=branch_id))
        if purchases_df.empty:
            return []

        pending_mask = purchases_df["status"].isin(RECEIVABLE_STATUSES)
        pending_df = purchases_df[pending_mask].copy()
        if pending_df.empty:
            return []

        results = []
        for po_number, group in pending_df.groupby("po_number"):
            supplier = ""
            if "supplier" in group.columns and not group["supplier"].isna().all():
                supplier = str(group["supplier"].iloc[0])

            expected_date = ""
            if "expected_date" in group.columns and not group["expected_date"].isna().all():
                expected_date = str(group["expected_date"].iloc[0])

            total_value = 0.0
            if "total_cost" in group.columns:
                try:
                    total_value = float(group["total_cost"].sum())
                except Exception:
                    total_value = 0.0

            results.append({
                "po_number": str(po_number),
                "supplier": supplier,
                "item_count": len(group),
                "total_value": total_value,
                "expected_date": expected_date,
                "status": str(group["status"].iloc[0]),
            })

        results.sort(key=lambda x: x.get("po_number", ""))
        return results

    except Exception as e:
        print(f"Error getting pending POs: {e}")
        return []


# ==============================
# BULK CONFIRM + RECEIVE ALL PENDING POs (branch-scoped)
# ==============================
def confirm_and_receive_all_pending_pos(invoice_no, confirmed_by="system", branch_id=None):
    """
    For every PO currently PENDING or PARTIALLY_RECEIVED in this branch:
      - Receive all remaining quantities
      - Auto-update product stock (create new products for unknown barcodes)
      - Write status ONCE per PO (PARTIALLY_RECEIVED or COMPLETED)

    Returns (success, message, summary_dict)
    """
    if branch_id is None:
        branch_id = _get_session_branch()

    summary = {
        "pos_completed": 0,
        "pos_partial": 0,
        "items_received": 0,
        "products_updated": 0,
        "products_created": 0,
        "total_received_value": 0.0,
    }

    if not invoice_no or not str(invoice_no).strip():
        return False, "Supplier invoice number is required", summary

    invoice_no = str(invoice_no).strip()

    try:
        purchases_df = _migrate_statuses(load_purchases(branch_id=branch_id))
        products_df = load_products(branch_id=branch_id)

        if purchases_df.empty:
            return True, "No purchase orders to confirm", summary

        for col, default in [
            ("quantity_received", 0),
            ("date_received", ""),
            ("invoice_no", ""),
        ]:
            if col not in purchases_df.columns:
                purchases_df[col] = default

        pending_mask = purchases_df["status"].isin(RECEIVABLE_STATUSES)
        pending_pos = purchases_df.loc[pending_mask, "po_number"].dropna().unique().tolist()

        if not pending_pos:
            return True, "No pending purchase orders to confirm", summary

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        products_updated_names = set()
        products_created_names = set()

        for po_number in pending_pos:
            po_mask = purchases_df["po_number"] == po_number
            po_indices = purchases_df[po_mask].index.tolist()
            if not po_indices:
                continue

            for idx in po_indices:
                row = purchases_df.loc[idx]

                try:
                    qty_ordered = float(row.get("quantity_ordered", 0) or 0)
                except Exception:
                    qty_ordered = 0.0
                try:
                    qty_received = float(row.get("quantity_received", 0) or 0)
                except Exception:
                    qty_received = 0.0

                remaining = qty_ordered - qty_received
                if remaining <= 0:
                    continue

                try:
                    cost_price = float(row.get("cost_price", 0) or 0)
                except Exception:
                    cost_price = 0.0

                product_name = str(row.get("product_name", "Unknown") or "Unknown")
                barcode = str(row.get("barcode", "") or "").strip()
                category = str(row.get("category", "New Purchase") or "New Purchase").strip()
                if not category or category.lower() in ("nan", "none"):
                    category = "New Purchase"

                # Per-row: only quantity_received, date_received, invoice_no
                purchases_df.loc[idx, "quantity_received"] = qty_ordered
                purchases_df.loc[idx, "date_received"] = now_str
                purchases_df.loc[idx, "invoice_no"] = invoice_no

                summary["items_received"] += 1
                summary["total_received_value"] += remaining * cost_price

                product_idx = products_df[products_df["barcode"] == barcode].index

                if len(product_idx) > 0:
                    current_stock = (
                        float(products_df.loc[product_idx[0], "stock"])
                        if "stock" in products_df.columns else 0.0
                    )
                    new_stock = current_stock + remaining
                    products_df.loc[product_idx[0], "stock"] = new_stock
                    if "cost" in products_df.columns and cost_price > 0:
                        products_df.loc[product_idx[0], "cost"] = cost_price
                    products_updated_names.add(product_name)
                else:
                    new_product = pd.DataFrame([{
                        "barcode": barcode,
                        "name": product_name,
                        "category": category if category != "New Purchase" else "New Purchase",
                        "price": cost_price * 1.3,
                        "cost": cost_price,
                        "stock": remaining,
                        "reorder_level": 5,
                    }])
                    products_df = pd.concat([products_df, new_product], ignore_index=True)
                    products_created_names.add(product_name)

            # Per-PO status: written exactly once
            po_rows = purchases_df.loc[po_indices]
            all_full = True
            for _, r in po_rows.iterrows():
                try:
                    qo = float(r.get("quantity_ordered", 0) or 0)
                    qr = float(r.get("quantity_received", 0) or 0)
                except Exception:
                    qo, qr = 0.0, 0.0
                if qr < qo:
                    all_full = False
                    break

            if all_full:
                purchases_df.loc[po_indices, "status"] = STATUS_COMPLETED
                summary["pos_completed"] += 1
            else:
                purchases_df.loc[po_indices, "status"] = STATUS_PARTIAL
                summary["pos_partial"] += 1

        summary["products_updated"] = len(products_updated_names)
        summary["products_created"] = len(products_created_names)

        try:
            save_products(products_df, branch_id=branch_id)
            save_purchases(purchases_df, branch_id=branch_id)
        except Exception as e:
            print(f"Error saving after bulk receive: {e}")
            return False, f"Failed to save: {str(e)}", summary

        try:
            st.cache_data.clear()
        except Exception:
            pass

        parts = [
            f"Confirmed and received {summary['items_received']} item(s) across "
            f"{summary['pos_completed'] + summary['pos_partial']} PO(s)."
        ]
        if summary["pos_partial"]:
            parts.append(f"{summary['pos_partial']} PO(s) marked PARTIALLY_RECEIVED.")
        if summary["products_created"]:
            parts.append(f"{summary['products_created']} new product(s) created.")
        if summary["products_updated"]:
            parts.append(f"{summary['products_updated']} product(s) restocked.")
        parts.append(f"Total received value: ${summary['total_received_value']:,.2f}.")

        return True, " ".join(parts), summary

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error during bulk confirm: {str(e)}", summary


# ==============================
# CREATE PURCHASE ORDER - OPTIMIZED (branch-scoped)
# ==============================
def create_purchase_order(supplier, items, expected_date, branch_id=None):
    """Create a purchase order before receiving stock (branch-scoped)"""

    if branch_id is None:
        branch_id = _get_session_branch()

    if not supplier or not supplier.strip():
        return None, None, "Supplier name is required"

    if not items or len(items) == 0:
        return None, None, "No items in purchase order"

    po_number = generate_po_number()

    po_data = []

    for idx, item in enumerate(items):
        if not item.get("name"):
            continue

        cost = float(item.get("cost", 0))
        quantity = float(item.get("quantity", 1))

        category = str(item.get("category", "")).strip()
        if not category or category == "nan" or category == "None" or category == "":
            category = "New Purchase"

        barcode = str(item.get("barcode", "")).strip()

        # Ensure we always hand a barcode that validate_barcode will accept.
        # validate_barcode requires digits only (typically 13 digits).
        # If the incoming barcode is empty, or looks like a manual "MAN-..."
        # placeholder, or is otherwise non-numeric, replace it with a
        # generated 13-digit numeric code.
        if (not barcode
                or barcode in ("nan", "None", "")
                or not barcode.isdigit()
                or len(barcode) != 13):
            barcode = _generate_numeric_barcode(idx)

        po_data.append({
            "branch_id": branch_id,
            "po_number": po_number,
            "date_ordered": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "supplier": supplier.strip(),
            "product_name": str(item.get("name", "Unknown")),
            "barcode": barcode,
            "quantity_ordered": quantity,
            "cost_price": cost,
            "total_cost": quantity * cost,
            "expected_date": str(expected_date),
            "date_received": "",
            "quantity_received": 0,
            "status": STATUS_PENDING,
            "payment_status": "UNPAID",
            "invoice_no": "",
            "category": category
        })

    if not po_data:
        return None, None, "No valid items to add to purchase order"

    po_df = pd.DataFrame(po_data)
    return po_number, po_df, None


# ==============================
# DELETE PURCHASE ORDER - DIRECT SQL (branch-scoped)
# ==============================
def delete_purchase_order(po_number, branch_id=None):
    """Delete a purchase order using direct SQL (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        po_number_str = str(po_number).strip()

        with get_db_connection() as conn:
            if conn is None:
                return False, "Database connection failed"

            cur = conn.cursor()

            cur.execute(
                "SELECT COUNT(*) FROM purchases WHERE po_number = %s AND branch_id = %s",
                (po_number_str, branch_id),
            )
            result = cur.fetchone()
            count = result[0] if result else 0

            if count == 0:
                return False, f"Purchase Order {po_number_str} not found in branch {branch_id}"

            cur.execute(
                "DELETE FROM purchases WHERE po_number = %s AND branch_id = %s",
                (po_number_str, branch_id),
            )
            conn.commit()

            cur.execute(
                "SELECT COUNT(*) FROM purchases WHERE po_number = %s AND branch_id = %s",
                (po_number_str, branch_id),
            )
            result = cur.fetchone()
            remaining = result[0] if result else 0

            cur.close()

            if remaining == 0:
                return True, f"Purchase Order {po_number_str} deleted successfully. Removed {count} item(s)."
            else:
                return False, f"Failed to delete PO {po_number_str}. {remaining} items remain."

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error deleting PO: {str(e)}"


# ==============================
# DELETE ALL PURCHASE ORDERS - DIRECT SQL (branch-scoped)
# ==============================
def delete_all_purchase_orders(branch_id=None):
    """Delete ALL purchase orders for this branch using direct SQL"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        with get_db_connection() as conn:
            if conn is None:
                return False, "Database connection failed"

            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM purchases WHERE branch_id = %s", (branch_id,))
            total_items = cur.fetchone()[0]

            if total_items == 0:
                return False, f"No purchase orders found in branch {branch_id} to delete"

            cur.execute(
                "SELECT COUNT(DISTINCT po_number) FROM purchases WHERE branch_id = %s",
                (branch_id,),
            )
            unique_pos = cur.fetchone()[0]

            cur.execute("DELETE FROM purchases WHERE branch_id = %s", (branch_id,))
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM purchases WHERE branch_id = %s", (branch_id,))
            remaining = cur.fetchone()[0]

            cur.close()

            if remaining == 0:
                return True, f"All {unique_pos} purchase orders ({total_items} items) in branch {branch_id} deleted successfully."
            else:
                return False, f"Failed to delete all POs. {remaining} items remain."

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error deleting all POs: {str(e)}"


# ==============================
# RECEIVE PURCHASE ORDER (SINGLE) - branch-scoped
# ==============================
def receive_purchase_order(po_number, received_items, invoice_no, branch_id=None):
    """
    Receive items against a single PO and update stock (branch-scoped).
    Per-row writes update quantity_received / date_received / invoice_no only.
    Status is written once for the whole PO at the end.
    """
    if branch_id is None:
        branch_id = _get_session_branch()

    purchases_df = _migrate_statuses(load_purchases(branch_id=branch_id))
    products_df = load_products(branch_id=branch_id)

    for col, default in [
        ("quantity_received", 0),
        ("date_received", ""),
        ("invoice_no", ""),
    ]:
        if col not in purchases_df.columns:
            purchases_df[col] = default

    updated_products = []
    new_products = []

    po_mask = purchases_df["po_number"] == po_number
    po_items_indices = purchases_df[po_mask].index.tolist()

    po_items_mapping = {}
    for idx in po_items_indices:
        row = purchases_df.loc[idx]
        barcode = str(row.get("barcode", "")).strip()
        product_name = str(row.get("product_name", "")).strip()

        key = barcode if barcode else product_name
        if key:
            po_items_mapping[key] = idx

    for item in received_items:
        if item["received_qty"] <= 0:
            continue

        barcode = str(item.get("barcode", "")).strip()
        product_name = str(item.get("name", "")).strip()
        received_qty = float(item["received_qty"])
        cost_price = float(item["cost"])
        category = str(item.get("category", "New Purchase")).strip()
        if not category or category == "nan" or category == "None":
            category = "New Purchase"

        matching_idx = None

        if barcode:
            for key, idx in po_items_mapping.items():
                if key == barcode:
                    matching_idx = idx
                    break

        if matching_idx is None and product_name:
            for key, idx in po_items_mapping.items():
                if key.lower() == product_name.lower():
                    matching_idx = idx
                    break

        if matching_idx is None:
            for key, idx in po_items_mapping.items():
                if product_name and key and (product_name.lower() in key.lower() or key.lower() in product_name.lower()):
                    matching_idx = idx
                    break

        if matching_idx is not None:
            purchases_df.loc[matching_idx, "quantity_received"] = received_qty
            purchases_df.loc[matching_idx, "date_received"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            purchases_df.loc[matching_idx, "invoice_no"] = invoice_no

            product_idx = products_df[products_df["barcode"] == barcode].index

            if len(product_idx) > 0:
                current_stock = float(products_df.loc[product_idx[0], "stock"]) if "stock" in products_df.columns else 0
                new_stock = current_stock + received_qty

                products_df.loc[product_idx[0], "stock"] = new_stock

                updated_products.append({
                    "name": product_name,
                    "old_stock": current_stock,
                    "added": received_qty,
                    "new_stock": new_stock,
                    "cost": float(products_df.loc[product_idx[0], "cost"]) if "cost" in products_df.columns else 0,
                    "price": float(products_df.loc[product_idx[0], "price"]) if "price" in products_df.columns else 0,
                    "category": products_df.loc[product_idx[0], "category"] if "category" in products_df.columns else "Uncategorized"
                })
            else:
                new_product = pd.DataFrame([{
                    "barcode": barcode,
                    "name": product_name,
                    "category": category if category and category != "New Purchase" else "New Purchase",
                    "price": cost_price * 1.3,
                    "cost": cost_price,
                    "stock": received_qty,
                    "reorder_level": 5
                }])
                products_df = pd.concat([products_df, new_product], ignore_index=True)

                new_products.append({
                    "name": product_name,
                    "stock": received_qty,
                    "cost": cost_price,
                    "price": cost_price * 1.3,
                    "category": category if category and category != "New Purchase" else "New Purchase"
                })
        else:
            st.warning(f"Item '{product_name}' not found in purchase order. Adding as new item.")

            supplier_value = (
                purchases_df[purchases_df["po_number"] == po_number].iloc[0].get("supplier", "Unknown")
                if not purchases_df[purchases_df["po_number"] == po_number].empty
                else "Unknown"
            )

            new_row = {
                "branch_id": branch_id,
                "po_number": po_number,
                "date_ordered": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "supplier": supplier_value,
                "product_name": product_name,
                "barcode": barcode,
                "quantity_ordered": received_qty,
                "cost_price": cost_price,
                "total_cost": received_qty * cost_price,
                "expected_date": datetime.now().strftime("%Y-%m-%d"),
                "date_received": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "quantity_received": received_qty,
                "status": STATUS_PENDING,
                "payment_status": "UNPAID",
                "invoice_no": invoice_no,
                "category": category if category and category != "New Purchase" else "New Purchase"
            }

            for col in purchases_df.columns:
                if col not in new_row:
                    new_row[col] = ""

            purchases_df = pd.concat([purchases_df, pd.DataFrame([new_row])], ignore_index=True)

            product_idx = products_df[products_df["barcode"] == barcode].index
            if len(product_idx) == 0:
                new_product = pd.DataFrame([{
                    "barcode": barcode,
                    "name": product_name,
                    "category": category if category and category != "New Purchase" else "New Purchase",
                    "price": cost_price * 1.3,
                    "cost": cost_price,
                    "stock": received_qty,
                    "reorder_level": 5
                }])
                products_df = pd.concat([products_df, new_product], ignore_index=True)

                new_products.append({
                    "name": product_name,
                    "stock": received_qty,
                    "cost": cost_price,
                    "price": cost_price * 1.3,
                    "category": category if category and category != "New Purchase" else "New Purchase"
                })

    # Single authoritative status write for the whole PO
    po_items = purchases_df[purchases_df["po_number"] == po_number]
    all_received = True
    for idx in po_items.index:
        qty_ordered = float(po_items.loc[idx].get("quantity_ordered", 0))
        qty_received = float(po_items.loc[idx].get("quantity_received", 0))
        if qty_received < qty_ordered:
            all_received = False
            break

    purchases_df.loc[purchases_df["po_number"] == po_number, "status"] = (
        STATUS_COMPLETED if all_received else STATUS_PARTIAL
    )

    try:
        save_products(products_df, branch_id=branch_id)
        save_purchases(purchases_df, branch_id=branch_id)
        try:
            st.cache_data.clear()
        except Exception:
            pass
        return True, updated_products, new_products
    except Exception as e:
        print(f"Error saving: {e}")
        return False, [], []


# ==============================
# SUPPLIER PERFORMANCE (branch-scoped)
# ==============================
def get_supplier_performance(branch_id=None):
    """Calculate supplier performance metrics from purchase history (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()

    purchases_df = _migrate_statuses(load_purchases(branch_id=branch_id))

    if purchases_df.empty:
        return pd.DataFrame()

    if "quantity_received" not in purchases_df.columns:
        purchases_df["quantity_received"] = purchases_df.get("quantity_ordered", 0)

    if "total_cost" not in purchases_df.columns:
        purchases_df["total_cost"] = purchases_df.get("quantity_ordered", 0) * purchases_df.get("cost_price", 0)

    supplier_stats = purchases_df.groupby("supplier").agg({
        "po_number": "nunique",
        "total_cost": "sum",
        "quantity_ordered": "sum",
        "quantity_received": "sum"
    }).reset_index()

    supplier_stats.columns = ["Supplier", "Orders", "Total Spent", "Units Ordered", "Units Received"]

    supplier_stats["Fulfillment Rate"] = supplier_stats.apply(
        lambda x: (x["Units Received"] / x["Units Ordered"] * 100) if x["Units Ordered"] > 0 else 0,
        axis=1
    )
    supplier_stats = supplier_stats.sort_values("Total Spent", ascending=False)

    return supplier_stats


# ==============================
# GET PURCHASE ORDER DETAILS (branch-scoped)
# ==============================
def get_po_details(po_number, branch_id=None):
    """Get complete details for a specific purchase order (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()

    purchases_df = _migrate_statuses(load_purchases(branch_id=branch_id))
    po_items = purchases_df[purchases_df["po_number"] == po_number]

    if po_items.empty:
        return None

    date_ordered = po_items.iloc[0].get("date_ordered")
    if date_ordered:
        if hasattr(date_ordered, 'strftime'):
            date_ordered_str = date_ordered.strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_ordered_str = str(date_ordered)
    else:
        date_ordered_str = "Unknown"

    expected_date = po_items.iloc[0].get("expected_date")
    if expected_date:
        if hasattr(expected_date, 'strftime'):
            expected_date_str = expected_date.strftime('%Y-%m-%d')
        else:
            expected_date_str = str(expected_date)
    else:
        expected_date_str = "N/A"

    return {
        "po_number": po_number,
        "supplier": po_items.iloc[0].get("supplier", "Unknown"),
        "date_ordered": date_ordered_str,
        "expected_date": expected_date_str,
        "items": po_items.to_dict('records'),
        "total_value": float(po_items["total_cost"].sum()) if "total_cost" in po_items.columns else 0,
        "status": po_items.iloc[0].get("status", STATUS_PENDING)
    }


# ==============================
# SUPPLIER AUTOCOMPLETE COMPONENT (branch-scoped)
# ==============================
def supplier_autocomplete(key_suffix="", branch_id=None):
    """Supplier input with autocomplete from existing suppliers (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()

    supplier_suggestions = get_supplier_suggestions(branch_id)
    current_value = st.session_state.get(f"supplier_name_{key_suffix}", "")
    is_new_supplier = current_value and current_value not in supplier_suggestions and current_value.strip()

    options = supplier_suggestions.copy() if supplier_suggestions else []

    if is_new_supplier:
        options.append(current_value)

    options = [""] + sorted(set(options))

    try:
        current_index = options.index(current_value) if current_value in options else 0
    except ValueError:
        current_index = 0

    col1, col2 = st.columns([4, 1])

    with col1:
        selected_supplier = st.selectbox(
            "Supplier Name *",
            options=options,
            index=current_index,
            key=f"supplier_select_{key_suffix}_{branch_id}",
            placeholder="Type to search or select a supplier...",
            label_visibility="collapsed"
        )

    with col2:
        if selected_supplier and selected_supplier not in supplier_suggestions:
            st.caption("New Supplier")
        else:
            st.caption(" ")

    col1, col2 = st.columns([4, 1])

    with col1:
        new_supplier = st.text_input(
            "Or type new supplier name",
            value=selected_supplier if selected_supplier and selected_supplier not in supplier_suggestions else "",
            key=f"new_supplier_{key_suffix}_{branch_id}",
            placeholder="Enter new supplier name...",
            label_visibility="collapsed"
        )

    with col2:
        st.caption(" ")

    if new_supplier and new_supplier.strip():
        return new_supplier.strip()

    return selected_supplier if selected_supplier else ""


# ==============================
# PURCHASES PAGE (branch-scoped)
# ==============================
def purchases_page():
    """Enhanced Purchases Management Page (branch-scoped)"""

    branch_id = _get_session_branch()
    branch_label = _branch_display_name(branch_id)

    st.title(f"Purchases and Suppliers Management — {branch_label}")
    st.caption("Create purchase orders, receive stock, and auto-update inventory")

    # No caching across writes: reads always reflect the DB.
    products_df = load_products(branch_id=branch_id)

    # Initialize session state
    defaults = {
        "po_cart": [],
        "po_created": False,
        "last_po_number": None,
        "stock_updated": False,
        "last_received_po": None,
        "po_deleted": False,
        "deleted_po_number": None,
        "show_preview": False,
        "preview_data": None,
        "refresh_required": False,
        "confirm_delete_all": False,
        "batch_selected_products": [],
        "batch_quantities": {},
        "show_batch_add": False,
        "bulk_confirm_success": None,
        "bulk_confirm_message": None,
        "bulk_confirm_summary": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Handle refresh after deletion
    if st.session_state.refresh_required:
        st.session_state.refresh_required = False
        st.rerun()

    # Display success messages
    if st.session_state.po_created and st.session_state.last_po_number:
        st.success(f"Purchase Order {st.session_state.last_po_number} created successfully!")
        st.balloons()
        st.session_state.po_created = False

    if st.session_state.stock_updated and st.session_state.last_received_po:
        st.success(f"Stock for PO {st.session_state.last_received_po} has been added to inventory!")
        st.balloons()
        st.session_state.stock_updated = False

    if st.session_state.po_deleted and st.session_state.deleted_po_number:
        if st.session_state.deleted_po_number == "ALL":
            st.success("All purchase orders deleted successfully!")
        else:
            st.success(f"Purchase Order {st.session_state.deleted_po_number} deleted successfully!")
        st.session_state.po_deleted = False
        st.session_state.deleted_po_number = None

    if st.session_state.bulk_confirm_success is not None:
        if st.session_state.bulk_confirm_success:
            st.success(st.session_state.bulk_confirm_message or "Pending POs confirmed.")
            st.balloons()
            s = st.session_state.bulk_confirm_summary or {}
            if s:
                st.info(
                    f"📦 **Bulk receive summary** — "
                    f"POs completed: **{s.get('pos_completed', 0)}** "
                    f"(partial: {s.get('pos_partial', 0)}) • "
                    f"Items received: **{s.get('items_received', 0)}** • "
                    f"Products restocked: **{s.get('products_updated', 0)}** • "
                    f"New products created: **{s.get('products_created', 0)}** • "
                    f"Total value: **${s.get('total_received_value', 0):,.2f}**"
                )
        else:
            st.error(st.session_state.bulk_confirm_message or "Bulk confirm failed.")
        st.session_state.bulk_confirm_success = None
        st.session_state.bulk_confirm_message = None
        st.session_state.bulk_confirm_summary = None

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Create Purchase Order",
        "Receive Stock",
        "Supplier Performance",
        "Purchase History"
    ])

    # ==============================
    # TAB 1: CREATE PURCHASE ORDER
    # ==============================
    with tab1:
        st.markdown(f"## Create Purchase Order — {branch_label}")
        st.caption("Create a purchase order before receiving stock from suppliers")

        if products_df.empty:
            st.warning("No products in inventory. You can still add manual items below.")

        col1, col2 = st.columns(2)

        with col1:
            supplier_name = supplier_autocomplete("main", branch_id=branch_id)

        with col2:
            expected_date = st.date_input(
                "Expected Delivery Date *",
                min_value=datetime.now().date(),
                value=datetime.now().date() + timedelta(days=7),
                key=f"po_expected_date_{branch_id}"
            )

        st.markdown("---")
        st.markdown("### Add Products to Order")

        # ==============================
        # BATCH ADDITION SECTION
        # ==============================
        if not products_df.empty:
            st.markdown("#### Batch Add Products from Supplier")
            st.caption("Select multiple products to add to your order at once")

            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                search_batch = st.text_input(
                    "Search Products for Batch",
                    key=f"batch_search_{branch_id}",
                    placeholder="Type product name or barcode to filter..."
                )

            with col2:
                select_all_batch = st.checkbox("Select All Products", key=f"select_all_batch_{branch_id}")

            with col3:
                if st.button("Show Batch Add", key=f"show_batch_add_btn_{branch_id}", use_container_width=True):
                    st.session_state.show_batch_add = not st.session_state.show_batch_add
                    if st.session_state.show_batch_add:
                        st.session_state.batch_selected_products = []
                        st.session_state.batch_quantities = {}

            if st.session_state.show_batch_add:
                filtered_for_batch = products_df.copy()
                if search_batch:
                    filtered_for_batch = products_df[
                        products_df["name"].astype(str).str.contains(search_batch, case=False) |
                        products_df["barcode"].astype(str).str.contains(search_batch, case=False)
                    ]

                if not filtered_for_batch.empty:
                    st.markdown("##### Select Products and Enter Quantities")

                    cols_per_row = 3
                    product_list = filtered_for_batch.to_dict('records')

                    for i, product in enumerate(product_list):
                        barcode = str(product.get("barcode", ""))
                        if barcode not in st.session_state.batch_quantities:
                            st.session_state.batch_quantities[barcode] = 1.0

                    if select_all_batch:
                        for product in product_list:
                            barcode = str(product.get("barcode", ""))
                            if barcode not in st.session_state.batch_selected_products:
                                st.session_state.batch_selected_products.append(barcode)

                    for i, product in enumerate(product_list):
                        col_idx = i % cols_per_row
                        if col_idx == 0:
                            cols = st.columns(cols_per_row)

                        barcode = str(product.get("barcode", ""))
                        name = str(product.get("name", ""))
                        stock = float(product.get("stock", 0))
                        cost = float(product.get("cost", 0))
                        price = float(product.get("price", 0))
                        category = str(product.get("category", ""))

                        is_decimal = supports_decimal(name, category)

                        with cols[col_idx]:
                            with st.container(border=True):
                                is_selected = barcode in st.session_state.batch_selected_products
                                selected = st.checkbox(
                                    f"**{name}**",
                                    key=f"batch_check_{branch_id}_{barcode}",
                                    value=is_selected
                                )

                                if selected and barcode not in st.session_state.batch_selected_products:
                                    st.session_state.batch_selected_products.append(barcode)
                                elif not selected and barcode in st.session_state.batch_selected_products:
                                    st.session_state.batch_selected_products.remove(barcode)

                                st.caption(f"Category: {category if category else 'Uncategorized'}")
                                st.caption(f"Stock: {stock:.2f} | Cost: ${cost:.2f}")

                                if is_decimal:
                                    qty = st.number_input(
                                        "Qty",
                                        min_value=0.0,
                                        value=st.session_state.batch_quantities.get(barcode, 1.0),
                                        step=0.5,
                                        format="%.2f",
                                        key=f"batch_qty_{branch_id}_{barcode}",
                                        label_visibility="collapsed"
                                    )
                                    st.caption("Decimal quantities supported")
                                else:
                                    qty = st.number_input(
                                        "Qty",
                                        min_value=1,
                                        value=int(st.session_state.batch_quantities.get(barcode, 1)),
                                        step=1,
                                        key=f"batch_qty_{branch_id}_{barcode}",
                                        label_visibility="collapsed"
                                    )

                                st.session_state.batch_quantities[barcode] = qty

                    if st.session_state.batch_selected_products:
                        st.markdown("---")
                        st.markdown(f"**{len(st.session_state.batch_selected_products)} products selected**")

                        col1, col2, col3 = st.columns([1, 1, 1])

                        with col1:
                            if st.button("Clear Selection", key=f"clear_batch_selection_{branch_id}", use_container_width=True):
                                st.session_state.batch_selected_products = []
                                st.session_state.batch_quantities = {}
                                st.rerun()

                        with col2:
                            preview_btn = st.button("Preview Selected", key=f"preview_batch_{branch_id}", use_container_width=True)
                            if preview_btn:
                                selected_products = []
                                for barcode in st.session_state.batch_selected_products:
                                    product = products_df[products_df["barcode"].astype(str) == barcode]
                                    if not product.empty:
                                        p = product.iloc[0]
                                        qty = st.session_state.batch_quantities.get(barcode, 1)
                                        cost_val = float(p.get("cost", 0))
                                        selected_products.append({
                                            "name": str(p.get("name", "")),
                                            "barcode": barcode,
                                            "quantity": float(qty),
                                            "cost": cost_val,
                                            "total": float(qty) * cost_val,
                                            "category": str(p.get("category", "New Purchase"))
                                        })

                                if selected_products:
                                    preview_df = pd.DataFrame(selected_products)
                                    st.dataframe(
                                        preview_df[["name", "quantity", "cost", "total"]],
                                        use_container_width=True,
                                        hide_index=True,
                                        column_config={
                                            "quantity": st.column_config.NumberColumn("Qty", format="%.2f"),
                                            "cost": st.column_config.NumberColumn("Unit Cost", format="$%.2f"),
                                            "total": st.column_config.NumberColumn("Total", format="$%.2f")
                                        }
                                    )
                                    st.info(f"Total: ${preview_df['total'].sum():,.2f}")

                        with col3:
                            if st.button("Add Selected to Cart", type="primary", key=f"add_batch_to_cart_{branch_id}", use_container_width=True):
                                if not supplier_name or not supplier_name.strip():
                                    st.error("Please enter a supplier name first")
                                else:
                                    added_count = 0
                                    for barcode in st.session_state.batch_selected_products:
                                        product = products_df[products_df["barcode"].astype(str) == barcode]
                                        if not product.empty:
                                            p = product.iloc[0]
                                            qty = st.session_state.batch_quantities.get(barcode, 1)

                                            if qty <= 0:
                                                continue

                                            cost_val = float(p.get("cost", 0))
                                            category_val = str(p.get("category", "")).strip()
                                            if not category_val or category_val == "nan" or category_val == "None" or category_val == "":
                                                category_val = "New Purchase"

                                            existing = False
                                            for item in st.session_state.po_cart:
                                                if str(item["barcode"]) == barcode:
                                                    if isinstance(qty, float):
                                                        item["quantity"] = float(item["quantity"]) + qty
                                                    else:
                                                        item["quantity"] = int(item["quantity"]) + int(qty)
                                                    item["total"] = item["quantity"] * item["cost"]
                                                    existing = True
                                                    break

                                            if not existing:
                                                st.session_state.po_cart.append({
                                                    "barcode": barcode,
                                                    "name": str(p.get("name", "")),
                                                    "quantity": float(qty),
                                                    "cost": cost_val,
                                                    "total": cost_val * float(qty),
                                                    "category": category_val
                                                })
                                            added_count += 1

                                    if added_count > 0:
                                        st.success(f"Added {added_count} products to cart for {supplier_name}")
                                        st.session_state.batch_selected_products = []
                                        st.session_state.batch_quantities = {}
                                        st.rerun()
                                    else:
                                        st.warning("No products were added. Check quantities.")
                    else:
                        st.info("Select products above to add them to your cart")
                else:
                    st.info("No products found matching your search")

        st.markdown("---")

        # ==============================
        # SINGLE PRODUCT ADD
        # ==============================
        if not products_df.empty:
            st.markdown("#### Add Single Product")

            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            selected_product = None

            with col1:
                search = st.text_input(
                    "Search Product", key=f"po_search_{branch_id}",
                    placeholder="Type product name or barcode"
                )

                filtered_products = products_df.copy()
                if search:
                    filtered_products = products_df[
                        products_df["name"].astype(str).str.contains(search, case=False) |
                        products_df["barcode"].astype(str).str.contains(search, case=False)
                    ]

                if not filtered_products.empty:
                    product_display = []
                    for _, p in filtered_products.iterrows():
                        stock_status = "In Stock" if p["stock"] > p["reorder_level"] else ("Low Stock" if p["stock"] > 0 else "Out of Stock")
                        display_text = f"{stock_status} - {p['name']} - Stock: {p['stock']} - Price: ${p['price']:.2f}"
                        product_display.append(display_text)

                    selected_display = st.selectbox("Select Product", product_display, key=f"po_product_select_{branch_id}")
                    if selected_display:
                        parts = selected_display.split(" - ")
                        if len(parts) >= 2:
                            selected_product_name = parts[1]
                        else:
                            selected_product_name = selected_display
                        selected_product = filtered_products[filtered_products["name"] == selected_product_name].iloc[0]
                    else:
                        selected_product = None
                else:
                    selected_product = None
                    st.info("No products found matching your search")

            with col2:
                if selected_product is not None:
                    is_decimal = supports_decimal(selected_product["name"], selected_product.get("category", ""))

                    if is_decimal:
                        po_qty = st.number_input(
                            "Quantity",
                            min_value=0.0,
                            value=1.0,
                            step=0.5,
                            format="%.2f",
                            key=f"po_qty_{branch_id}"
                        )
                        st.caption("Decimal quantities supported (e.g., 0.5, 1.5)")
                    else:
                        po_qty = st.number_input(
                            "Quantity",
                            min_value=1,
                            value=1,
                            step=1,
                            key=f"po_qty_{branch_id}"
                        )

                    st.caption(f"Current stock: {selected_product['stock']:.2f}")
                    st.caption(f"Cost: ${selected_product['cost']:.2f}")
                else:
                    po_qty = 1

            with col3:
                if selected_product is not None:
                    add_button = st.button("Add to Order", key=f"add_to_po_{branch_id}", use_container_width=True)
                    if add_button:
                        if not supplier_name or not supplier_name.strip():
                            st.error("Please enter a supplier name first")
                        else:
                            existing = False
                            barcode_str = str(selected_product["barcode"])
                            for item in st.session_state.po_cart:
                                if str(item["barcode"]) == barcode_str:
                                    if isinstance(po_qty, float):
                                        item["quantity"] = float(item["quantity"]) + po_qty
                                    else:
                                        item["quantity"] = int(item["quantity"]) + int(po_qty)
                                    item["total"] = item["quantity"] * item["cost"]
                                    existing = True
                                    break

                            if not existing:
                                cost_val = float(selected_product["cost"]) if selected_product["cost"] > 0 else 0
                                category_val = str(selected_product.get("category", "")).strip()
                                if not category_val or category_val == "nan" or category_val == "None" or category_val == "":
                                    category_val = "New Purchase"

                                if isinstance(po_qty, float):
                                    quantity_val = float(po_qty)
                                else:
                                    quantity_val = int(po_qty)

                                st.session_state.po_cart.append({
                                    "barcode": str(selected_product["barcode"]),
                                    "name": str(selected_product["name"]),
                                    "quantity": quantity_val,
                                    "cost": cost_val,
                                    "total": cost_val * quantity_val,
                                    "category": category_val
                                })

                            if isinstance(po_qty, float) and po_qty % 1 != 0:
                                st.success(f"Added {po_qty:.2f} x {selected_product['name']} to order")
                            else:
                                st.success(f"Added {int(po_qty)} x {selected_product['name']} to order")

            with col4:
                clear_button = st.button("Clear Cart", key=f"clear_cart_po_{branch_id}", use_container_width=True)
                if clear_button:
                    st.session_state.po_cart = []
                    st.success("Cart cleared!")

        st.markdown("---")

        # ==============================
        # MANUAL ITEM ENTRY
        # ==============================
        st.markdown("### Manual Item Entry")
        st.caption("Add items not in inventory (new products, services, fees)")

        with st.form(key=f"add_manual_form_{branch_id}", clear_on_submit=True):
            col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 1, 1, 1, 1])

            with col1:
                manual_item_name = st.text_input("Item Name *", key=f"manual_item_name_{branch_id}", placeholder="e.g., New Product X, Delivery Fee")

            with col2:
                manual_item_category = st.text_input("Category", key=f"manual_item_category_{branch_id}", placeholder="e.g., Drinks, Rice, Sugar")

            with col3:
                manual_item_cost = st.number_input("Cost Price ($)", min_value=0.01, value=0.01, step=5.0, key=f"manual_item_cost_{branch_id}")
                st.caption("Cost at purchase")

            with col4:
                manual_item_price = st.number_input("Selling Price ($)", min_value=0.01, value=0.01, step=5.0, key=f"manual_item_price_{branch_id}")
                st.caption("Price to sell at")

            with col5:
                is_decimal_manual = supports_decimal(manual_item_name, manual_item_category)

                if is_decimal_manual:
                    manual_item_qty = st.number_input(
                        "Quantity",
                        min_value=0.0,
                        value=1.0,
                        step=0.5,
                        format="%.2f",
                        key=f"manual_item_qty_{branch_id}"
                    )
                    st.caption("Decimal quantities supported")
                else:
                    manual_item_qty = st.number_input(
                        "Quantity",
                        min_value=1,
                        value=1,
                        step=1,
                        key=f"manual_item_qty_{branch_id}"
                    )

            with col6:
                add_manual_button = st.form_submit_button("Add Item", use_container_width=True)

            if add_manual_button:
                if not supplier_name or not supplier_name.strip():
                    st.error("Please enter a supplier name first")
                elif manual_item_name and manual_item_name.strip():
                    if manual_item_cost <= 0 and manual_item_price <= 0:
                        st.error("Please enter at least a cost price or selling price")
                    else:
                        category_input = manual_item_category.strip()

                        if category_input:
                            category = category_input
                        else:
                            category = "New Purchase"

                        cost_val = float(manual_item_cost) if manual_item_cost > 0 else float(manual_item_price) * 0.7
                        price_val = float(manual_item_price) if manual_item_price > 0 else float(manual_item_cost) * 1.3

                        if price_val < cost_val:
                            price_val = cost_val * 1.3

                        existing = False
                        for item in st.session_state.po_cart:
                            if str(item["name"]).lower() == manual_item_name.lower() and float(item["cost"]) == cost_val:
                                if isinstance(manual_item_qty, float):
                                    item["quantity"] = float(item["quantity"]) + manual_item_qty
                                else:
                                    item["quantity"] = int(item["quantity"]) + int(manual_item_qty)
                                item["total"] = item["quantity"] * item["cost"]
                                if category != "New Purchase":
                                    item["category"] = category
                                if manual_item_price > 0:
                                    item["price"] = price_val
                                existing = True
                                break

                        if not existing:
                            # 13-digit numeric barcode so validate_barcode accepts it
                            unique_barcode = _generate_numeric_barcode(len(st.session_state.po_cart))
                            if isinstance(manual_item_qty, float):
                                qty_val = float(manual_item_qty)
                            else:
                                qty_val = int(manual_item_qty)

                            st.session_state.po_cart.append({
                                "barcode": unique_barcode,
                                "name": str(manual_item_name).strip(),
                                "quantity": qty_val,
                                "cost": cost_val,
                                "price": price_val,
                                "total": cost_val * qty_val,
                                "category": category
                            })

                            if isinstance(manual_item_qty, float) and manual_item_qty % 1 != 0:
                                st.success(f"Added {manual_item_qty:.2f} x {manual_item_name} (Cost: ${cost_val:.2f}, Price: ${price_val:.2f}) - Category: {category}")
                            else:
                                st.success(f"Added {int(manual_item_qty)} x {manual_item_name} (Cost: ${cost_val:.2f}, Price: ${price_val:.2f}) - Category: {category}")
                        else:
                            st.success(f"Updated {manual_item_name} quantity")
                else:
                    st.error("Please enter an item name")

        # ==============================
        # CART DISPLAY
        # ==============================
        st.markdown("---")
        st.markdown("### Purchase Order Cart")

        if st.session_state.po_cart:
            po_cart_df = pd.DataFrame(st.session_state.po_cart)

            display_cols = ["name", "quantity", "cost", "price", "total"]
            if "category" in po_cart_df.columns:
                display_cols.insert(1, "category")

            if "price" not in po_cart_df.columns:
                po_cart_df["price"] = po_cart_df["cost"] * 1.3

            st.dataframe(
                po_cart_df[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "quantity": st.column_config.NumberColumn("Quantity", format="%.2f"),
                    "cost": st.column_config.NumberColumn("Unit Cost ($)", format="$%.2f"),
                    "price": st.column_config.NumberColumn("Selling Price ($)", format="$%.2f"),
                    "total": st.column_config.NumberColumn("Total ($)", format="$%.2f")
                }
            )

            po_total = po_cart_df["total"].sum()
            st.info(f"**Total Order Value: ${po_total:,.2f}**")

            st.markdown("#### Remove Item from Cart")
            item_to_remove = st.selectbox(
                "Select item to remove",
                [item["name"] for item in st.session_state.po_cart],
                key=f"remove_item_select_{branch_id}"
            )

            if st.button("Remove Selected Item", key=f"remove_item_btn_{branch_id}", use_container_width=True):
                st.session_state.po_cart = [item for item in st.session_state.po_cart if item["name"] != item_to_remove]
                st.success(f"Removed '{item_to_remove}' from cart")
                st.rerun()

            col1, col2 = st.columns(2)

            with col1:
                clear_all_button = st.button("Clear All Items", key=f"clear_all_items_btn_{branch_id}", use_container_width=True)
                if clear_all_button:
                    st.session_state.po_cart = []
                    st.success("Cart cleared!")

            with col2:
                preview_button = st.button("Preview Purchase Order", key=f"preview_po_btn_{branch_id}", use_container_width=True)
                if preview_button:
                    if not supplier_name or not supplier_name.strip():
                        st.error("Please enter a supplier name")
                    elif not st.session_state.po_cart:
                        st.error("Cart is empty. Add products to create a purchase order.")
                    else:
                        cart_items = st.session_state.po_cart.copy()
                        po_cart_df = pd.DataFrame(cart_items)

                        st.session_state.preview_data = {
                            "supplier": supplier_name,
                            "items": cart_items,
                            "expected_date": expected_date,
                            "po_cart_df": po_cart_df,
                            "po_total": po_cart_df["total"].sum()
                        }
                        st.session_state.show_preview = True

        if st.session_state.show_preview and st.session_state.preview_data:
            preview = st.session_state.preview_data

            st.markdown("---")
            st.markdown("### Purchase Order Preview")
            st.markdown(f"**Supplier:** {preview['supplier']}")
            st.markdown(f"**Expected Date:** {preview['expected_date']}")

            display_cols = ["name", "quantity", "cost", "price", "total"]
            if "category" in preview['po_cart_df'].columns:
                display_cols.insert(1, "category")

            st.dataframe(
                preview['po_cart_df'][display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "quantity": st.column_config.NumberColumn("Quantity", format="%.2f"),
                    "cost": st.column_config.NumberColumn("Unit Cost ($)", format="$%.2f"),
                    "price": st.column_config.NumberColumn("Selling Price ($)", format="$%.2f"),
                    "total": st.column_config.NumberColumn("Total ($)", format="$%.2f")
                }
            )

            st.info(f"**Total Order Value: ${preview['po_total']:,.2f}**")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Edit Order", key=f"edit_order_{branch_id}", use_container_width=True):
                    st.session_state.show_preview = False
                    st.session_state.preview_data = None

            with col2:
                if st.button("Confirm and Create PO", type="primary", key=f"confirm_create_po_{branch_id}", use_container_width=True):
                    po_number, po_df, error = create_purchase_order(
                        supplier=preview['supplier'],
                        items=preview['items'],
                        expected_date=preview['expected_date'],
                        branch_id=branch_id
                    )

                    if error:
                        st.error(error)
                    else:
                        # ----------------------------------------------------------
                        # FIX: pass ONLY the new PO rows to save_purchases.
                        # Previously the whole purchases table was concatenated and
                        # re-saved, so other rows' success masked the new rows'
                        # validation failures and the UI showed a fake success.
                        # save_purchases handles ON CONFLICT DO UPDATE itself.
                        # ----------------------------------------------------------
                        save_success = save_purchases(po_df, branch_id=branch_id)

                        if save_success:
                            st.session_state.po_cart = []
                            st.session_state.po_created = True
                            st.session_state.last_po_number = po_number
                            st.session_state.show_preview = False
                            st.session_state.preview_data = None

                            st.success(f"Purchase Order {po_number} created successfully!")

                            po_text = f"""
{'='*50}
AZIEL INVESTMENTS - PURCHASE ORDER
{'='*50}

PO Number: {po_number}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Branch: {branch_label}
Supplier: {preview['supplier']}
Expected Delivery: {preview['expected_date']}

{'─'*40}
ITEMS ORDERED
{'─'*40}
"""
                            for _, item in preview['po_cart_df'].iterrows():
                                category_info = f" - Category: {item.get('category', 'New Purchase')}" if item.get('category') else ""
                                qty = item.get('quantity', 0)
                                if isinstance(qty, float) and qty % 1 != 0:
                                    qty_str = f"{qty:.2f}"
                                else:
                                    qty_str = f"{int(qty)}"
                                po_text += f"{item['name']}{category_info:<30} {qty_str:>5} x ${item['cost']:.2f} = ${item['total']:.2f}\n"

                            po_text += f"""
{'─'*40}
TOTAL: ${preview['po_total']:,.2f}
{'─'*40}

Terms: Payment due upon receipt
Order Status: PENDING - Awaiting delivery

{'='*50}
Aziel Investments - Retreat Park, Harare
Contact: +263 78 290 5853
{'='*50}
"""

                            st.download_button(
                                label="Download PO (TXT)",
                                data=po_text,
                                file_name=f"{po_number}.txt",
                                mime="text/plain",
                                use_container_width=True
                            )

                            try:
                                st.cache_data.clear()
                            except Exception:
                                pass
                            st.rerun()
                        else:
                            st.error(
                                "Failed to save purchase order. Some items failed validation. "
                                "Check the barcodes and try again."
                            )

        if not st.session_state.show_preview and st.session_state.po_cart:
            col1, col2 = st.columns(2)

            with col1:
                st.empty()

            with col2:
                quick_create = st.button("Create PO", key=f"quick_create_po_{branch_id}", use_container_width=True)
                if quick_create:
                    if not supplier_name or not supplier_name.strip():
                        st.error("Please enter a supplier name")
                    elif not st.session_state.po_cart:
                        st.error("Cart is empty")
                    else:
                        cart_items = st.session_state.po_cart.copy()
                        po_cart_df = pd.DataFrame(cart_items)
                        po_total = po_cart_df["total"].sum()

                        po_number, po_df, error = create_purchase_order(
                            supplier=supplier_name,
                            items=cart_items,
                            expected_date=expected_date,
                            branch_id=branch_id
                        )

                        if error:
                            st.error(error)
                        else:
                            # ----------------------------------------------------------
                            # FIX: pass ONLY the new PO rows to save_purchases.
                            # ----------------------------------------------------------
                            save_success = save_purchases(po_df, branch_id=branch_id)

                            if save_success:
                                st.session_state.po_cart = []
                                st.session_state.po_created = True
                                st.session_state.last_po_number = po_number

                                st.success(f"Purchase Order {po_number} created successfully!")
                                st.info(f"""
                                Purchase Order Summary:
                                - PO Number: {po_number}
                                - Supplier: {supplier_name}
                                - Items: {len(po_df)}
                                - Total Value: ${po_total:,.2f}
                                - Expected Date: {expected_date}
                                """)

                                try:
                                    st.cache_data.clear()
                                except Exception:
                                    pass
                                st.rerun()
                            else:
                                st.error(
                                    "Failed to save purchase order. Some items failed validation. "
                                    "Check the barcodes and try again."
                                )
        elif st.session_state.show_preview:
            st.info("Review the preview above and click 'Confirm and Create PO' to save.")

    # ==============================
    # TAB 2: RECEIVE STOCK - SAME FLOW FOR BULK AND SINGLE
    # ==============================
    with tab2:
        st.markdown(f"## Receive Stock - Auto Update Inventory — {branch_label}")
        st.caption("Confirm receipt of stock. Inventory will be automatically updated.")

        # ============================================================
        # BULK: CONFIRM ALL PENDING POs AND UPDATE STOCK
        # ============================================================
        st.markdown("### Confirm All Pending POs and Update Stock")
        st.caption(
            "This does exactly the same thing as the single receive flow, "
            "but for every pending PO at once: it marks each PO received, "
            "auto-updates inventory, and moves the PO out of the pending list."
        )

        pending_pos_for_confirm = get_all_pending_pos(branch_id=branch_id)

        if not pending_pos_for_confirm:
            st.info("No pending purchase orders to confirm.")
        else:
            preview_rows = []
            for po in pending_pos_for_confirm:
                preview_rows.append({
                    "PO Number": po.get("po_number", ""),
                    "Supplier": po.get("supplier", ""),
                    "Items": po.get("item_count", 0),
                    "Total Value": po.get("total_value", 0.0),
                    "Expected Date": po.get("expected_date", ""),
                })
            preview_df = pd.DataFrame(preview_rows)

            st.dataframe(
                preview_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total Value": st.column_config.NumberColumn("Total Value", format="$%.2f"),
                },
            )

            total_pending_value = preview_df["Total Value"].sum() if "Total Value" in preview_df else 0
            st.caption(
                f"**{len(pending_pos_for_confirm)}** pending PO(s) — "
                f"total value **${total_pending_value:,.2f}**"
            )

            bulk_invoice_no = st.text_input(
                "Supplier Invoice Number * (applied to all pending POs)",
                key=f"bulk_receive_invoice_no_{branch_id}",
                placeholder="Enter invoice number to stamp on every pending PO",
            )

            col_a, col_b = st.columns([1, 2])
            with col_a:
                bulk_confirm_clicked = st.button(
                    "✅ Confirm ALL & Update Stock",
                    key=f"bulk_confirm_and_receive_btn_{branch_id}",
                    type="primary",
                    use_container_width=True,
                )
            with col_b:
                st.caption(
                    "Every pending PO will be received in full and its stock "
                    "added to inventory, exactly like doing it one by one."
                )

            if bulk_confirm_clicked:
                if not bulk_invoice_no or not bulk_invoice_no.strip():
                    st.error("Please enter the supplier invoice number first.")
                else:
                    with st.spinner("Confirming and receiving all pending POs..."):
                        try:
                            confirmed_by = st.session_state.get("username", "system")
                        except Exception:
                            confirmed_by = "system"
                        ok, msg, summary = confirm_and_receive_all_pending_pos(
                            invoice_no=bulk_invoice_no.strip(),
                            confirmed_by=confirmed_by,
                            branch_id=branch_id,
                        )

                    st.session_state.bulk_confirm_success = ok
                    st.session_state.bulk_confirm_message = msg
                    st.session_state.bulk_confirm_summary = summary
                    if ok and summary.get("items_received", 0) > 0:
                        st.session_state.stock_updated = True
                        st.session_state.last_received_po = "BULK"
                    st.rerun()

        st.markdown("---")
        # ============================================================
        # END BULK
        # ============================================================

        # NOTE: no cache — reads always reflect the DB
        purchases_df = _migrate_statuses(load_purchases(branch_id=branch_id))

        if purchases_df.empty:
            st.info("No purchase orders found. Create a PO first in the Create Purchase Order tab.")
        else:
            receivable_pos = purchases_df[
                purchases_df["status"].isin(RECEIVABLE_STATUSES)
            ]["po_number"].unique().tolist()

            if not receivable_pos:
                st.info("No pending or partially received purchase orders. All orders have been completed.")
            else:
                st.info(f"Found {len(receivable_pos)} order(s) ready for receiving")

                selected_po = st.selectbox(
                    "Select Purchase Order to Receive",
                    receivable_pos,
                    key=f"receive_po_{branch_id}"
                )

                if selected_po:
                    po_details = get_po_details(selected_po, branch_id=branch_id)

                    if po_details:
                        status_label = str(po_details['status']).upper()
                        st.markdown(f"### PO: {selected_po} - {status_label}")
                        st.markdown(f"**Supplier:** {po_details['supplier']}")
                        st.markdown(f"**Order Date:** {po_details['date_ordered']}")
                        st.markdown(f"**Expected Date:** {po_details['expected_date']}")

                        st.markdown("### Items Ordered")
                        items_df = pd.DataFrame(po_details['items'])
                        display_cols = ["product_name", "quantity_ordered", "quantity_received", "cost_price", "total_cost"]
                        available_cols = [col for col in display_cols if col in items_df.columns]

                        if "quantity_received" in items_df.columns:
                            items_df["received_status"] = items_df.apply(
                                lambda row: "Received" if float(row["quantity_received"]) >= float(row["quantity_ordered"])
                                else f"{row['quantity_received']}/{row['quantity_ordered']} received",
                                axis=1
                            )
                            display_cols = ["product_name", "quantity_ordered", "received_status", "cost_price", "total_cost"]

                        st.dataframe(
                            items_df[display_cols],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "quantity_ordered": st.column_config.NumberColumn("Ordered", format="%.2f"),
                                "quantity_received": st.column_config.NumberColumn("Received", format="%.2f"),
                                "cost_price": st.column_config.NumberColumn("Cost", format="$%.2f"),
                                "total_cost": st.column_config.NumberColumn("Total", format="$%.2f")
                            }
                        )

                        po_total = po_details['total_value']
                        st.info(f"PO Total: ${po_total:,.2f}")

                        # ---------------- DELETE OPTIONS ----------------
                        if status_label in ["PENDING", "PARTIALLY_RECEIVED"]:
                            st.markdown("---")
                            st.markdown("### Delete Purchase Order")
                            st.warning(f"This will permanently delete this purchase order ({selected_po}) and all its items.")

                            col1, col2, col3 = st.columns([2, 1, 1])
                            with col1:
                                confirm_delete = st.checkbox(f"Confirm delete PO {selected_po}", key=f"confirm_delete_{branch_id}_{selected_po}")
                            with col2:
                                delete_button = st.button("Delete This PO", type="secondary", use_container_width=True, key=f"delete_po_{branch_id}_{selected_po}")
                                if delete_button and confirm_delete:
                                    success, message = delete_purchase_order(selected_po, branch_id=branch_id)
                                    if success:
                                        st.session_state.po_deleted = True
                                        st.session_state.deleted_po_number = selected_po
                                        st.session_state.refresh_required = True
                                        st.success(message)
                                        try:
                                            st.cache_data.clear()
                                        except Exception:
                                            pass
                                        st.rerun()
                                    else:
                                        st.error(message)
                                elif delete_button and not confirm_delete:
                                    st.error("Please confirm deletion")

                            with col3:
                                delete_all_btn = st.button("Delete All POs", type="secondary", use_container_width=True, key=f"delete_all_pos_{branch_id}")
                                if delete_all_btn:
                                    st.session_state.confirm_delete_all = True

                            if st.session_state.get("confirm_delete_all", False):
                                st.warning("⚠️ ARE YOU SURE? This will delete ALL purchase orders!")
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    confirm_all = st.button("✅ YES, DELETE ALL", type="primary", use_container_width=True, key=f"confirm_delete_all_yes_{branch_id}")
                                    if confirm_all:
                                        success, message = delete_all_purchase_orders(branch_id=branch_id)
                                        if success:
                                            st.session_state.po_deleted = True
                                            st.session_state.deleted_po_number = "ALL"
                                            st.session_state.refresh_required = True
                                            st.session_state.confirm_delete_all = False
                                            st.success(message)
                                            try:
                                                st.cache_data.clear()
                                            except Exception:
                                                pass
                                            st.rerun()
                                        else:
                                            st.error(message)
                                with col_b:
                                    if st.button("❌ Cancel", use_container_width=True, key=f"confirm_delete_all_no_{branch_id}"):
                                        st.session_state.confirm_delete_all = False
                                        st.rerun()

                        # ---------------- SINGLE RECEIVE ----------------
                        st.markdown("---")
                        st.markdown("### Receiving Details")
                        st.info("When you receive items, stock will be automatically added to inventory.")

                        invoice_no = st.text_input("Supplier Invoice Number *", key=f"invoice_no_{branch_id}")

                        st.markdown("### Enter Received Quantities")
                        st.caption("Enter the quantity received for each item. Partial receipts are supported.")

                        received_items = []
                        total_received_value = 0

                        for idx, item in enumerate(po_details['items']):
                            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                            with col1:
                                product_name = item.get("product_name", "Unknown")
                                qty_ordered = float(item.get("quantity_ordered", 0))
                                qty_received = float(item.get("quantity_received", 0))
                                remaining = qty_ordered - qty_received
                                category = item.get("category", "New Purchase")
                                st.write(f"**{product_name}**")
                                st.caption(f"Category: {category} | Ordered: {qty_ordered:.2f} | Received: {qty_received:.2f} | Remaining: {remaining:.2f}")

                            with col2:
                                barcode_val = str(item.get("barcode", f"item_{idx}"))
                                received_qty = st.number_input(
                                    "Qty Received",
                                    min_value=0.0,
                                    max_value=float(remaining),
                                    value=float(remaining),
                                    step=0.5,
                                    format="%.2f",
                                    key=f"rec_qty_{branch_id}_{barcode_val}_{idx}",
                                    label_visibility="collapsed"
                                )

                            with col3:
                                cost_price = float(item.get("cost_price", 0))
                                st.write(f"Cost: ${cost_price:.2f}")

                            with col4:
                                item_total = received_qty * cost_price
                                total_received_value += item_total
                                st.write(f"Total: ${item_total:.2f}")

                            received_items.append({
                                "barcode": str(item.get("barcode", "")),
                                "received_qty": float(received_qty),
                                "cost": float(cost_price),
                                "name": product_name,
                                "category": category
                            })

                        st.markdown(f"**Total Received Value: ${total_received_value:,.2f}**")

                        col1, col2 = st.columns(2)

                        with col1:
                            confirm_button = st.button("Confirm Receipt and Update Stock", type="primary", use_container_width=True, key=f"confirm_receipt_{branch_id}")
                            if confirm_button:
                                if not invoice_no:
                                    st.error("Please enter supplier invoice number")
                                else:
                                    success, updated_products, new_products = receive_purchase_order(
                                        selected_po, received_items, invoice_no, branch_id=branch_id
                                    )

                                    if success:
                                        st.session_state.stock_updated = True
                                        st.session_state.last_received_po = selected_po

                                        if updated_products:
                                            st.success(f"Stock updated for {len(updated_products)} existing products!")
                                            for p in updated_products[:5]:
                                                st.write(f"   - {p['name']}: +{p['added']:.2f} units (Stock: {p['old_stock']:.2f} -> {p['new_stock']:.2f})")
                                            if len(updated_products) > 5:
                                                st.write(f"   ... and {len(updated_products) - 5} more")

                                        if new_products:
                                            st.info(f"Created {len(new_products)} new products in inventory!")
                                            for p in new_products:
                                                st.write(f"   - {p['name']}: Added {p['stock']:.2f} units at ${p['cost']:.2f} - Category: {p.get('category', 'New Purchase')}")

                        with col2:
                            refresh_button = st.button("Refresh", use_container_width=True, key=f"refresh_receive_{branch_id}")
                            if refresh_button:
                                st.rerun()

    # ==============================
    # TAB 3: SUPPLIER PERFORMANCE
    # ==============================
    with tab3:
        st.markdown(f"## Supplier Performance Dashboard — {branch_label}")

        supplier_perf = get_supplier_performance(branch_id=branch_id)

        if supplier_perf.empty:
            st.info("No purchase data available yet.")
        else:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Suppliers", len(supplier_perf))
            with col2:
                st.metric("Total Spent", f"${supplier_perf['Total Spent'].sum():,.2f}")
            with col3:
                avg_fulfillment = supplier_perf["Fulfillment Rate"].mean()
                st.metric("Avg Fulfillment Rate", f"{avg_fulfillment:.1f}%")

            st.markdown("---")

            st.markdown("### Supplier Performance Metrics")
            st.dataframe(
                supplier_perf,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Units Ordered": st.column_config.NumberColumn("Units Ordered", format="%.2f"),
                    "Units Received": st.column_config.NumberColumn("Units Received", format="%.2f"),
                    "Total Spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                    "Fulfillment Rate": st.column_config.NumberColumn("Fulfillment Rate", format="%.1f%%")
                }
            )

            low_fulfillment = supplier_perf[supplier_perf["Fulfillment Rate"] < 80]
            if not low_fulfillment.empty:
                st.warning(f"{len(low_fulfillment)} suppliers have fulfillment rate below 80%")
                st.dataframe(low_fulfillment[["Supplier", "Fulfillment Rate"]], use_container_width=True, hide_index=True)

    # ==============================
    # TAB 4: PURCHASE HISTORY
    # ==============================
    with tab4:
        st.markdown(f"## Purchase History — {branch_label}")

        # NOTE: no cache — reads always reflect the DB
        purchases_df = _migrate_statuses(load_purchases(branch_id=branch_id))

        if purchases_df.empty:
            st.info("No purchase records found.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                date_filter = st.selectbox(
                    "Filter by",
                    ["All", "Last 30 Days", "Last 90 Days", "This Year"],
                    key=f"purchase_filter_{branch_id}"
                )

            with col2:
                status_filter = st.selectbox(
                    "Status",
                    ["All", "PENDING", "PARTIALLY_RECEIVED", "COMPLETED"],
                    key=f"purchase_status_filter_{branch_id}"
                )

            today = datetime.now()
            if "date_ordered" in purchases_df.columns:
                purchases_df["date_ordered_dt"] = pd.to_datetime(purchases_df["date_ordered"], errors="coerce")

                if date_filter == "Last 30 Days":
                    cutoff = today - timedelta(days=30)
                    purchases_df = purchases_df[purchases_df["date_ordered_dt"] >= cutoff]
                elif date_filter == "Last 90 Days":
                    cutoff = today - timedelta(days=90)
                    purchases_df = purchases_df[purchases_df["date_ordered_dt"] >= cutoff]
                elif date_filter == "This Year":
                    cutoff = today.replace(month=1, day=1)
                    purchases_df = purchases_df[purchases_df["date_ordered_dt"] >= cutoff]

            if status_filter != "All" and "status" in purchases_df.columns:
                purchases_df = purchases_df[
                    purchases_df["status"].astype(str).str.upper() == status_filter.upper()
                ]

            total_purchases = purchases_df["total_cost"].sum() if "total_cost" in purchases_df.columns else 0
            total_items = purchases_df["quantity_ordered"].sum() if "quantity_ordered" in purchases_df.columns else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Purchases", f"${total_purchases:,.2f}")
            with col2:
                st.metric("Total Items Ordered", f"{total_items:.2f}")
            with col3:
                unique_pos = purchases_df["po_number"].nunique() if "po_number" in purchases_df.columns else len(purchases_df)
                st.metric("Orders", unique_pos)

            st.markdown("---")

            st.markdown("### Purchase Order Summary")

            if purchases_df.empty:
                st.info("No records match the selected filters.")
            else:
                group_cols = ["po_number", "supplier", "date_ordered", "status"]
                group_cols = [c for c in group_cols if c in purchases_df.columns]
                po_summary = purchases_df.groupby(group_cols).agg({
                    "total_cost": "sum",
                    "quantity_ordered": "sum"
                }).reset_index()

                if "date_ordered" in po_summary.columns:
                    po_summary = po_summary.sort_values("date_ordered", ascending=False)

                summary_cols = ["po_number", "supplier", "date_ordered", "total_cost", "quantity_ordered", "status"]
                summary_cols = [c for c in summary_cols if c in po_summary.columns]

                st.dataframe(
                    po_summary[summary_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "quantity_ordered": st.column_config.NumberColumn("Total Qty", format="%.2f"),
                        "total_cost": st.column_config.NumberColumn("Total ($)", format="$%.2f")
                    }
                )

                st.markdown("---")

                with st.expander("View Detailed Purchase Records"):
                    display_cols = ["po_number", "date_ordered", "supplier", "product_name", "category", "quantity_ordered", "quantity_received", "cost_price", "total_cost", "status"]
                    available_cols = [col for col in display_cols if col in purchases_df.columns]

                    if "date_ordered" in purchases_df.columns:
                        purchases_df = purchases_df.sort_values("date_ordered", ascending=False)

                    st.dataframe(
                        purchases_df[available_cols].head(100),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "quantity_ordered": st.column_config.NumberColumn("Ordered", format="%.2f"),
                            "quantity_received": st.column_config.NumberColumn("Received", format="%.2f"),
                            "cost_price": st.column_config.NumberColumn("Unit Cost", format="$%.2f"),
                            "total_cost": st.column_config.NumberColumn("Total", format="$%.2f")
                        }
                    )

                csv = purchases_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download Purchase History (CSV)",
                    data=csv,
                    file_name=f"purchase_history_{branch_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    purchases_page()