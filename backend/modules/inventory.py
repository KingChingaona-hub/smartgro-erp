# backend/modules/inventory.py
"""
Inventory management page.

Guarantees:
  - No @st.cache_data anywhere; every render reads fresh from the DB.
  - Every write path is explicit:
        * Add Product           -> INSERT (barcode is always auto-generated)
        * Single Product Update -> UPDATE that one row by (branch_id, barcode)
        * Batch Update          -> UPDATE only the edited rows by (branch_id, barcode)
        * Batch Delete          -> SQL DELETE via delete_products
        * Delete All            -> SQL DELETE via delete_all_products
  - Barcodes are never changed on update; they are the stable identity of a
    product within a branch.
  - Add Product refuses to accept a user-typed barcode and refuses duplicate
    names within the branch.
  - Before any batch/single update, the barcode sent to the DB is looked up
    via UPPER(TRIM(...)) and replaced with the DB's exact stored value. This
    makes the ON CONFLICT hit the existing row instead of inserting a
    duplicate when the DB has a slightly different spelling.
  - After a successful save or a "Clear Selection", the edit widgets AND the
    pick checkboxes are dropped, so Streamlit actually unchecks them.
  - On any save failure, the page shows the exact rows, dtypes, branch_id,
    and DB state so the cause is visible without reading the terminal.
"""

import pandas as pd
import streamlit as st
from datetime import datetime
import traceback

from backend.core.db_adapter import (
    load_products,
    save_products,
    delete_products,
    delete_all_products,
    load_branches,
    get_db_cursor,
)
from backend.core.auth import check_login

try:
    from backend.scripts.remove_duplicate_products import duplicate_products_page
except ImportError:
    def duplicate_products_page():
        st.warning("Duplicate products cleanup tool is not available in this build.")


# ==============================
# BRANCH HELPERS
# ==============================
def _get_session_branch():
    return (
        st.session_state.get("current_branch_code")
        or st.session_state.get("user_branch")
        or "HO"
    )


def _branch_display_name(branch_id):
    try:
        df = load_branches()
        if df is not None and not df.empty and "branch_id" in df.columns:
            m = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not m.empty:
                name = m.iloc[0].get("branch_name", "")
                if name:
                    return f"{name} ({branch_id})"
    except Exception:
        pass
    return str(branch_id)


def _generate_numeric_barcode(seed_index=0):
    """13-digit numeric barcode that passes validate_barcode."""
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    core = stamp[:12]
    idx = f"{seed_index % 100:02d}"
    raw = "2" + core + idx
    return raw[:13].ljust(13, "0")


# ==============================
# DB BARCODE LOOKUP
# ==============================
def _resolve_db_barcode(barcode, branch_id):
    """
    Return the DB's exact stored barcode for this branch if a row exists
    whose barcode matches modulo case and whitespace. Otherwise return the
    input unchanged.
    """
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return barcode
            cur.execute(
                "SELECT barcode FROM products "
                "WHERE branch_id = %s "
                "  AND UPPER(TRIM(barcode)) = UPPER(TRIM(%s)) "
                "LIMIT 1",
                (str(branch_id).strip(), str(barcode).strip()),
            )
            row = cur.fetchone()
            if row:
                db_bc = row["barcode"] if isinstance(row, dict) else row[0]
                if db_bc:
                    return str(db_bc)
    except Exception as e:
        print(f"[_resolve_db_barcode] lookup failed for {barcode!r}: {e}")
    return barcode


def _barcode_exists_in_db(barcode, branch_id):
    """True if this barcode is already in the DB for this branch."""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return False
            cur.execute(
                "SELECT 1 FROM products "
                "WHERE branch_id = %s AND UPPER(TRIM(barcode)) = UPPER(TRIM(%s)) "
                "LIMIT 1",
                (str(branch_id).strip(), str(barcode).strip()),
            )
            return cur.fetchone() is not None
    except Exception as e:
        print(f"[_barcode_exists_in_db] lookup failed for {barcode!r}: {e}")
        return False


# ==============================
# DIAGNOSTIC HELPER
# ==============================
def _diagnose_save_failure(edited_df, branch_id):
    st.error("save_products returned False. Diagnostics below.")

    st.write("**Rows attempted:**")
    st.dataframe(edited_df, use_container_width=True, hide_index=True)

    st.write("**Column dtypes:**")
    st.write(edited_df.dtypes.astype(str))

    st.write(f"**branch_id passed to save_products:** `{branch_id!r}`")

    st.write("**Per-row DB state:**")
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                st.warning("Could not open DB cursor for diagnostics.")
                return
            for _, r in edited_df.iterrows():
                bc = str(r["barcode"])
                cur.execute(
                    "SELECT id, branch_id, barcode, LENGTH(barcode) AS bc_len, "
                    "       name, stock, price "
                    "FROM products WHERE barcode = %s",
                    (bc,),
                )
                rows = cur.fetchall() or []
                st.write(f"`barcode={bc!r}` → {[dict(x) for x in rows]}")
    except Exception as e:
        st.write(f"DB diagnostic failed: {e}")


# ==============================
# SESSION STATE HELPERS
# ==============================
def _init_session():
    if "batch_selected" not in st.session_state:
        st.session_state.batch_selected = []
    if "show_duplicate_cleanup" not in st.session_state:
        st.session_state.show_duplicate_cleanup = False
    if "_inv_last_branch" not in st.session_state:
        st.session_state["_inv_last_branch"] = None


def _drop_edit_widgets(barcode, branch_id):
    """Drop the edit widgets AND the pick checkbox for one product."""
    prefixes = (
        "be_name", "be_cat", "be_price", "be_cost", "be_stock", "be_reorder",
        "bu_pick",
    )
    for prefix in prefixes:
        k = f"{prefix}_{barcode}_{branch_id}"
        if k in st.session_state:
            del st.session_state[k]


def _clear_batch_edit_state(branch_id):
    """Drop every batch-edit widget, every pick checkbox, and select-all."""
    for k in list(st.session_state.keys()):
        if k == f"bu_select_all_{branch_id}":
            del st.session_state[k]
            continue
        if (
            k.startswith(("be_name_", "be_cat_", "be_price",
                          "be_cost_", "be_stock_", "be_reorder_", "bu_pick_"))
            and k.endswith(f"_{branch_id}")
        ):
            del st.session_state[k]
    st.session_state.batch_selected = []


def _ensure_branch_consistency():
    current = _get_session_branch()
    last = st.session_state.get("_inv_last_branch")
    if last != current:
        for k in list(st.session_state.keys()):
            if k.startswith(("be_name_", "be_cat_", "be_price",
                             "be_cost_", "be_stock_", "be_reorder_", "bu_pick_")):
                del st.session_state[k]
        st.session_state.batch_selected = []
        st.session_state["_inv_last_branch"] = current


# ==============================
# PAGE
# ==============================
def inventory_page():
    _init_session()
    _ensure_branch_consistency()

    branch_id = _get_session_branch()
    branch_label = _branch_display_name(branch_id)

    df = load_products(branch_id=branch_id)

    st.title(f"Inventory Management - {branch_label}")
    st.info(f"Managing inventory for Branch: **{branch_label}**")

    # ==============================
    # STOCK ALERTS
    # ==============================
    st.markdown("## Smart Stock Alerts")
    if not df.empty and "stock" in df.columns and "reorder_level" in df.columns:
        low_stock = df[df["stock"] <= df["reorder_level"]]
        if not low_stock.empty:
            st.error(f"{len(low_stock)} products need reordering!")
            st.dataframe(
                low_stock[["name", "stock", "reorder_level", "price"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                    "reorder_level": st.column_config.NumberColumn("Reorder Level", format="%.2f"),
                    "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                },
            )
        else:
            st.success("All products are sufficiently stocked.")
    else:
        st.info("Add products to see stock alerts")

    st.markdown("---")

    # ==============================
    # SEARCH
    # ==============================
    st.markdown("## Search Product")
    search = st.text_input(
        "Enter Barcode or Name",
        key=f"inv_search_{branch_id}",
        placeholder="Type to search...",
    )
    if search and not df.empty:
        result = df[
            df["barcode"].astype(str).str.contains(search, case=False, na=False)
            | df["name"].astype(str).str.contains(search, case=False, na=False)
        ]
        if not result.empty:
            st.dataframe(result, use_container_width=True, hide_index=True)
            st.success(f"Found {len(result)} product(s)")
        else:
            st.warning("No product found")

    st.markdown("---")

    # ==============================
    # ALL PRODUCTS
    # ==============================
    st.markdown("## All Products")
    if not df.empty:
        display_cols = ["barcode", "name", "category", "price", "cost", "stock", "reorder_level"]
        available_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                "reorder_level": st.column_config.NumberColumn("Reorder Level", format="%.2f"),
            },
        )
        st.caption(f"Total products: {len(df)}")
    else:
        st.warning("No products in inventory. Add your first product below.")

    st.markdown("---")

    # ==============================
    # TOOLS
    # ==============================
    st.markdown("## Tools")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Duplicate Products Cleanup", use_container_width=True, key=f"inv_dup_{branch_id}"):
            st.session_state.current_page = "Duplicate Products"
            st.session_state.show_duplicate_cleanup = True
            st.rerun()
    with col2:
        if st.button("Refresh Inventory", use_container_width=True, key=f"inv_refresh_{branch_id}"):
            st.rerun()

    if st.session_state.get("show_duplicate_cleanup", False):
        st.markdown("---")
        st.markdown("## Duplicate Products Cleanup")
        duplicate_products_page()
        if st.button("Close Cleanup Tool", use_container_width=True, key=f"inv_close_cleanup_{branch_id}"):
            st.session_state.show_duplicate_cleanup = False
            st.rerun()

    st.markdown("---")

    # ==============================
    # ADD PRODUCT  (barcode is always auto-generated)
    # ==============================
    st.markdown("## Add Product")
    st.caption(
        "The barcode is generated automatically. Product names must be unique "
        "within the branch."
    )

    with st.form(f"inv_add_form_{branch_id}", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Product Name *", key=f"add_name_{branch_id}")
            category = st.text_input("Category", key=f"add_category_{branch_id}")
            price = st.number_input(
                "Price ($) *", min_value=0.0, step=0.5, format="%.2f",
                key=f"add_price_{branch_id}",
            )

        with col2:
            cost = st.number_input(
                "Cost ($)", min_value=0.0, step=0.5, format="%.2f",
                key=f"add_cost_{branch_id}",
            )
            stock = st.number_input(
                "Stock", min_value=0.0, step=0.5, format="%.2f",
                key=f"add_stock_{branch_id}",
            )
            reorder_level = st.number_input(
                "Reorder Level", min_value=0.0, step=0.5, format="%.2f",
                key=f"add_reorder_{branch_id}",
            )
            st.caption("Decimals supported (e.g. 0.5, 1.5)")

        submitted = st.form_submit_button("Add Product", type="primary", use_container_width=True)

        if submitted:
            if not name or price <= 0:
                st.error("Product Name and Price are required.")
            else:
                normalized_name = name.strip().lower()

                existing_by_name = pd.DataFrame()
                if not df.empty:
                    existing_by_name = df[
                        df["name"].astype(str).str.strip().str.lower()
                        == normalized_name
                    ]

                if not existing_by_name.empty:
                    st.error(
                        f"A product named '{name.strip()}' already exists in this branch "
                        f"(barcode: {existing_by_name.iloc[0]['barcode']}). "
                        f"Edit the existing product instead of adding a new one."
                    )
                else:
                    existing_barcodes = set()
                    if not df.empty:
                        existing_barcodes = set(df["barcode"].astype(str).tolist())

                    barcode_clean = ""
                    for attempt in range(20):
                        candidate = _generate_numeric_barcode(attempt)
                        if candidate in existing_barcodes:
                            continue
                        if _barcode_exists_in_db(candidate, branch_id):
                            continue
                        barcode_clean = candidate
                        break

                    if not barcode_clean:
                        st.error("Could not generate a unique barcode. Please try again.")
                    else:
                        new_row = pd.DataFrame([{
                            "branch_id": branch_id,
                            "barcode": barcode_clean,
                            "name": name.strip(),
                            "category": category.strip() if category else "Uncategorized",
                            "price": float(price),
                            "cost": float(cost),
                            "stock": float(stock),
                            "reorder_level": float(reorder_level),
                        }])

                        ok = save_products(new_row, branch_id=branch_id)
                        if ok:
                            st.success(
                                f"Product '{name.strip()}' added successfully "
                                f"with barcode {barcode_clean}."
                            )
                            st.rerun()
                        else:
                            _diagnose_save_failure(new_row, branch_id)

    st.markdown("---")

    # ==============================
    # BATCH DELETE
    # ==============================
    st.markdown("## Batch Delete Products")
    st.caption("Select products and delete them permanently.")

    if not df.empty:
        with st.form(f"inv_batch_delete_form_{branch_id}", clear_on_submit=False):
            select_all_delete = st.checkbox(
                "Select All",
                key=f"bd_select_all_{branch_id}",
            )

            delete_selected_barcodes = []
            cols_per_row = 2
            product_list = df.to_dict("records")

            for i, product in enumerate(product_list):
                col_idx = i % cols_per_row
                if col_idx == 0:
                    cols = st.columns(cols_per_row)

                name = str(product.get("name", ""))
                barcode = str(product.get("barcode", ""))
                stock = float(product.get("stock", 0) or 0)
                price = float(product.get("price", 0) or 0)

                with cols[col_idx]:
                    checked = st.checkbox(
                        f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})",
                        key=f"bd_pick_{barcode}_{branch_id}",
                        value=select_all_delete,
                    )
                    if checked:
                        delete_selected_barcodes.append(barcode)

            confirm_delete = st.checkbox(
                "I confirm I want to permanently delete the selected products",
                key=f"bd_confirm_{branch_id}",
            )

            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                st.form_submit_button("Clear Selection", use_container_width=True)
            with col2:
                if delete_selected_barcodes:
                    st.info(f"**{len(delete_selected_barcodes)} products selected**")
            with col3:
                do_delete = st.form_submit_button(
                    f"Delete {len(delete_selected_barcodes)} Products",
                    type="secondary",
                    use_container_width=True,
                    disabled=len(delete_selected_barcodes) == 0,
                )

            if do_delete and delete_selected_barcodes:
                if not confirm_delete:
                    st.error("Please confirm deletion by checking the box above.")
                else:
                    if delete_products(delete_selected_barcodes, branch_id=branch_id):
                        st.success(f"Deleted {len(delete_selected_barcodes)} product(s).")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(
                            "Delete failed. Some barcodes may not exist in this branch. "
                            "See terminal for details."
                        )
    else:
        st.info("No products in inventory to delete.")

    st.markdown("---")

    # ==========================================================
    # BATCH UPDATE  (UPDATE ONLY — NO INSERTS)
    # ==========================================================
    st.markdown("## Batch Update Products")
    st.caption(
        "Pick the products you want to edit, change their fields, then click Save All. "
        "Barcodes are the stable identity of a product and cannot be changed here."
    )

    if df.empty:
        st.info("No products to update.")
    else:
        st.markdown("### 1. Select Products to Edit")

        select_all_edit = st.checkbox("Select All", key=f"bu_select_all_{branch_id}")

        selected_barcodes_prev = set(st.session_state.get("batch_selected", []))
        currently_checked = []

        product_list = df.to_dict("records")
        cols_per_row = 2

        for i, product in enumerate(product_list):
            col_idx = i % cols_per_row
            if col_idx == 0:
                cols = st.columns(cols_per_row)

            barcode = str(product.get("barcode", ""))
            name = str(product.get("name", ""))
            stock = float(product.get("stock", 0) or 0)
            price = float(product.get("price", 0) or 0)

            default_checked = select_all_edit or (barcode in selected_barcodes_prev)

            with cols[col_idx]:
                checked = st.checkbox(
                    f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})",
                    key=f"bu_pick_{barcode}_{branch_id}",
                    value=default_checked,
                )
                if checked:
                    currently_checked.append(barcode)

        st.session_state.batch_selected = currently_checked

        if not currently_checked:
            st.info("Select one or more products above to edit them.")
        else:
            st.markdown(f"### 2. Edit {len(currently_checked)} Product(s)")

            for idx_in_list, barcode in enumerate(currently_checked):
                rows = df[df["barcode"].astype(str) == barcode]
                if rows.empty:
                    continue
                p = rows.iloc[0]

                st.markdown(f"**Product {idx_in_list + 1}: {p.get('name', '')}**  `(barcode: {barcode})`")

                c1, c2, c3, c4, c5, c6 = st.columns([2, 1.5, 1.2, 1.2, 1.2, 1.2])

                with c1:
                    st.text_input(
                        "Name",
                        value=str(p.get("name", "")),
                        key=f"be_name_{barcode}_{branch_id}",
                    )
                    st.caption("Name")

                with c2:
                    st.text_input(
                        "Category",
                        value=str(p.get("category", "")),
                        key=f"be_cat_{barcode}_{branch_id}",
                    )
                    st.caption("Category")

                with c3:
                    st.number_input(
                        "Price",
                        min_value=0.0,
                        value=float(p.get("price", 0) or 0),
                        step=0.5,
                        format="%.2f",
                        key=f"be_price_{barcode}_{branch_id}",
                    )
                    st.caption("Price ($)")

                with c4:
                    st.number_input(
                        "Cost",
                        min_value=0.0,
                        value=float(p.get("cost", 0) or 0),
                        step=0.5,
                        format="%.2f",
                        key=f"be_cost_{barcode}_{branch_id}",
                    )
                    st.caption("Cost ($)")

                with c5:
                    st.number_input(
                        "Stock",
                        min_value=0.0,
                        value=float(p.get("stock", 0) or 0),
                        step=0.5,
                        format="%.2f",
                        key=f"be_stock_{barcode}_{branch_id}",
                    )
                    st.caption("Stock")

                with c6:
                    st.number_input(
                        "Reorder",
                        min_value=0.0,
                        value=float(p.get("reorder_level", 0) or 0),
                        step=0.5,
                        format="%.2f",
                        key=f"be_reorder_{barcode}_{branch_id}",
                    )
                    st.caption("Reorder Level")

                st.divider()

            c1, c2, c3 = st.columns([1, 1, 2])

            with c1:
                if st.button("Clear Selection", use_container_width=True, key=f"bu_clear_{branch_id}"):
                    _clear_batch_edit_state(branch_id)
                    st.rerun()

            with c2:
                if st.button("Reset Changes", use_container_width=True, key=f"bu_reset_{branch_id}"):
                    for barcode in currently_checked:
                        for prefix in ("be_name", "be_cat", "be_price",
                                       "be_cost", "be_stock", "be_reorder"):
                            k = f"{prefix}_{barcode}_{branch_id}"
                            if k in st.session_state:
                                del st.session_state[k]
                    st.rerun()

            with c3:
                save_all = st.button(
                    f"Save All {len(currently_checked)} Product(s)",
                    type="primary",
                    use_container_width=True,
                    key=f"bu_save_{branch_id}",
                )

            if save_all:
                edited_rows = []
                skipped = []

                for barcode in currently_checked:
                    rows = df[df["barcode"].astype(str) == barcode]
                    if rows.empty:
                        skipped.append(f"{barcode}: no longer in DB")
                        continue
                    original = rows.iloc[0]

                    db_barcode = _resolve_db_barcode(barcode, branch_id)

                    new_name = st.session_state.get(
                        f"be_name_{barcode}_{branch_id}", str(original.get("name", ""))
                    )
                    new_category = st.session_state.get(
                        f"be_cat_{barcode}_{branch_id}", str(original.get("category", ""))
                    )
                    new_price = st.session_state.get(
                        f"be_price_{barcode}_{branch_id}", float(original.get("price", 0) or 0)
                    )
                    new_cost = st.session_state.get(
                        f"be_cost_{barcode}_{branch_id}", float(original.get("cost", 0) or 0)
                    )
                    new_stock = st.session_state.get(
                        f"be_stock_{barcode}_{branch_id}", float(original.get("stock", 0) or 0)
                    )
                    new_reorder = st.session_state.get(
                        f"be_reorder_{barcode}_{branch_id}", float(original.get("reorder_level", 0) or 0)
                    )

                    if not str(new_name).strip():
                        skipped.append(f"{barcode}: name cannot be empty")
                        continue

                    edited_rows.append({
                        "branch_id": branch_id,
                        "barcode": db_barcode,
                        "name": str(new_name).strip(),
                        "category": str(new_category).strip() or "Uncategorized",
                        "price": float(new_price),
                        "cost": float(new_cost),
                        "stock": float(new_stock),
                        "reorder_level": float(new_reorder),
                    })

                if skipped:
                    st.warning("Skipped rows: " + "; ".join(skipped))

                if not edited_rows:
                    st.info("Nothing to save.")
                else:
                    edited_df = pd.DataFrame(edited_rows)
                    ok = save_products(edited_df, branch_id=branch_id)

                    if ok:
                        st.success(f"Updated {len(edited_rows)} product(s).")
                        st.balloons()
                        _clear_batch_edit_state(branch_id)
                        st.rerun()
                    else:
                        _diagnose_save_failure(edited_df, branch_id)

    st.markdown("---")

    # ==========================================================
    # SINGLE PRODUCT UPDATE  (UPDATE ONLY — NO INSERTS)
    # ==========================================================
    st.markdown("## Single Product Update")
    st.caption("Update one product at a time. Barcode is read-only.")

    if not df.empty:
        product_names = df["name"].astype(str).tolist()
        selected_product = st.selectbox(
            "Select Product to Update",
            product_names,
            key=f"su_select_{branch_id}",
        )

        if selected_product:
            rows = df[df["name"].astype(str) == selected_product]
            if rows.empty:
                st.warning("Selected product no longer exists.")
            else:
                p = rows.iloc[0]
                original_barcode = str(p["barcode"])
                db_barcode = _resolve_db_barcode(original_barcode, branch_id)

                name_lower = str(p["name"]).lower()
                category_lower = str(p.get("category", "")).lower()
                is_decimal = any(
                    kw in name_lower or kw in category_lower
                    for kw in ["gas", "kg", "bread", "loaf", "flour", "sugar",
                               "rice", "maize meal", "cooking oil", "milk",
                               "liquid", "weight"]
                )

                with st.form(f"su_form_{branch_id}", clear_on_submit=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.text_input(
                            "Barcode (read-only)",
                            value=original_barcode,
                            disabled=True,
                            key=f"su_barcode_{branch_id}",
                        )
                        update_name = st.text_input(
                            "Product Name",
                            value=str(p["name"]),
                            key=f"su_name_{branch_id}",
                        )
                        update_category = st.text_input(
                            "Category",
                            value=str(p.get("category", "")),
                            key=f"su_cat_{branch_id}",
                        )
                        update_price = st.number_input(
                            "Price ($)",
                            min_value=0.0,
                            value=float(p["price"]),
                            step=0.5,
                            format="%.2f",
                            key=f"su_price_{branch_id}",
                        )

                    with col2:
                        update_cost = st.number_input(
                            "Cost ($)",
                            min_value=0.0,
                            value=float(p.get("cost", 0) or 0),
                            step=0.5,
                            format="%.2f",
                            key=f"su_cost_{branch_id}",
                        )

                        step = 0.5 if is_decimal else 1.0
                        fmt = "%.2f" if is_decimal else "%.0f"

                        update_stock = st.number_input(
                            "Stock",
                            min_value=0.0,
                            value=float(p["stock"]),
                            step=step,
                            format=fmt,
                            key=f"su_stock_{branch_id}",
                        )
                        update_reorder = st.number_input(
                            "Reorder Level",
                            min_value=0.0,
                            value=float(p.get("reorder_level", 0) or 0),
                            step=step,
                            format=fmt,
                            key=f"su_reorder_{branch_id}",
                        )

                    if is_decimal:
                        st.info("Decimal quantities supported for this product.")

                    save_changes = st.form_submit_button(
                        "Save Changes", type="primary", use_container_width=True
                    )

                    if save_changes:
                        if not str(update_name).strip():
                            st.error("Product Name cannot be empty.")
                        else:
                            edited = pd.DataFrame([{
                                "branch_id": branch_id,
                                "barcode": db_barcode,
                                "name": update_name.strip(),
                                "category": update_category.strip() or "Uncategorized",
                                "price": float(update_price),
                                "cost": float(update_cost),
                                "stock": float(update_stock),
                                "reorder_level": float(update_reorder),
                            }])

                            ok = save_products(edited, branch_id=branch_id)
                            if ok:
                                st.success(f"Product '{update_name}' updated successfully!")
                                st.rerun()
                            else:
                                _diagnose_save_failure(edited, branch_id)

    st.markdown("---")

    # ==========================================================
    # DANGER ZONE
    # ==========================================================
    st.markdown("## Danger Zone")
    st.warning("Administrator actions. Proceed with caution.")

    user_role = st.session_state.get("role", "")
    is_admin = user_role in ("owner", "admin")

    if is_admin:
        with st.expander("Delete All Products (Admin Only)", expanded=False):
            st.error("This permanently deletes ALL products in this branch.")
            product_count = len(df) if not df.empty else 0
            st.warning(f"You are about to delete {product_count} product(s). This cannot be undone.")

            confirm_action = st.checkbox(
                "I understand this will delete ALL products in this branch",
                key=f"dz_confirm_{branch_id}",
            )
            admin_password = st.text_input(
                "Enter Admin Password to Confirm",
                type="password",
                key=f"dz_password_{branch_id}",
            )

            if st.button(
                "DELETE ALL PRODUCTS",
                type="secondary",
                use_container_width=True,
                key=f"dz_delete_all_{branch_id}",
            ):
                if not confirm_action:
                    st.error("Please confirm.")
                elif not admin_password:
                    st.error("Please enter your admin password.")
                else:
                    username = st.session_state.get("username", "")
                    login_success, role = check_login(username, admin_password)

                    if login_success and role in ("owner", "admin"):
                        if product_count == 0:
                            st.info("No products to delete.")
                        elif delete_all_products(branch_id=branch_id):
                            st.success(f"Deleted ALL {product_count} products in this branch.")
                            st.rerun()
                        else:
                            st.error("Failed to delete. See terminal for details.")
                    else:
                        st.error("Invalid admin password.")
    else:
        st.info("Only administrators can delete all products.")

    st.markdown("---")
    if st.button("Refresh Inventory", use_container_width=True, key=f"inv_refresh_bottom_{branch_id}"):
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    inventory_page()