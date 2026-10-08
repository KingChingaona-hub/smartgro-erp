# backend/modules/inventory_page.py
"""
Inventory management page — cache-free, branch-scoped, race-free.

Design rules:
  - No @st.cache_data anywhere. Every render reads fresh from the DB.
  - Every write sends ONLY the row(s) that changed to save_products /
    delete_products, never the whole catalog.
  - Batch update reads widget values from session_state at the moment
    the Save button is pressed (no intermediate dict, no forced rerun
    between select and edit), so it always persists exactly what you
    typed.
  - Batch delete issues a real SQL DELETE via delete_products.
  - Barcodes are validated with the relaxed validate_barcode.
  - Blank barcodes are auto-generated as 13-digit numeric codes.
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
)
from backend.core.auth import check_login

try:
    from backend.scripts.remove_duplicate_products import duplicate_products_page
except ImportError:
    def duplicate_products_page():
        st.warning("Duplicate products cleanup tool is not available in this build.")


# ==============================
# SESSION BRANCH HELPERS
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


# ==============================
# BARCODE GENERATOR
# ==============================
def _generate_numeric_barcode(seed_index=0):
    """Generate a 13-digit numeric barcode that passes validate_barcode."""
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")  # 20 digits
    core = stamp[:12]
    idx = f"{seed_index % 100:02d}"
    raw = "2" + core + idx  # 15 chars
    return raw[:13].ljust(13, "0")


# ==============================
# SESSION STATE
# ==============================
def _init_session():
    defaults = {
        "batch_selected": [],
        "batch_delete_selected": [],
        "show_duplicate_cleanup": False,
        "_inv_last_branch": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
        elif k in ("batch_selected", "batch_delete_selected") and not isinstance(st.session_state[k], list):
            st.session_state[k] = []


def _drop_edit_state_for(branch_id):
    """Drop all widget keys tied to batch edit / delete for a given branch."""
    for k in list(st.session_state.keys()):
        if (
            k.startswith("be_name_")
            or k.startswith("be_cat_")
            or k.startswith("be_price_")
            or k.startswith("be_cost_")
            or k.startswith("be_stock_")
            or k.startswith("be_reorder_")
            or k.startswith("be_pick_")
        ) and k.endswith(f"_{branch_id}"):
            del st.session_state[k]


def _ensure_branch_consistency():
    current = _get_session_branch()
    last = st.session_state.get("_inv_last_branch")
    if last != current:
        st.session_state.batch_selected = []
        st.session_state.batch_delete_selected = []
        _drop_edit_state_for(current)
        st.session_state["_inv_last_branch"] = current


# ==============================
# INVENTORY PAGE
# ==============================
def inventory_page():
    _init_session()
    _ensure_branch_consistency()

    branch_id = _get_session_branch()
    branch_label = _branch_display_name(branch_id)

    # Always fresh read — no caching
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
        key=f"inventory_search_{branch_id}",
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
        display_cols = ["barcode", "name", "category", "price", "stock", "reorder_level"]
        available_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
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
        if st.button("Duplicate Products Cleanup", use_container_width=True, key=f"dup_cleanup_{branch_id}"):
            st.session_state.current_page = "Duplicate Products"
            st.session_state.show_duplicate_cleanup = True
            st.rerun()
    with col2:
        if st.button("Refresh Inventory", use_container_width=True, key=f"refresh_inventory_{branch_id}"):
            st.rerun()

    if st.session_state.get("show_duplicate_cleanup", False):
        st.markdown("---")
        st.markdown("## Duplicate Products Cleanup")
        duplicate_products_page()
        if st.button("Close Cleanup Tool", use_container_width=True, key=f"close_cleanup_{branch_id}"):
            st.session_state.show_duplicate_cleanup = False
            st.rerun()

    st.markdown("---")

    # ==============================
    # ADD PRODUCT
    # ==============================
    st.markdown("## Add Product")
    with st.form(f"add_product_form_{branch_id}", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            barcode = st.text_input(
                "Barcode (leave blank to auto-generate)",
                key=f"add_barcode_{branch_id}",
            )
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
                barcode_clean = (barcode or "").strip()
                if not barcode_clean:
                    barcode_clean = _generate_numeric_barcode(len(df) if not df.empty else 0)

                if not df.empty and barcode_clean in df["barcode"].astype(str).values:
                    st.error(f"Barcode '{barcode_clean}' already exists in this branch.")
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

                    if save_products(new_row, branch_id=branch_id):
                        st.success(f"Product '{name}' added successfully!")
                        st.rerun()
                    else:
                        st.error(
                            "Failed to save product. Check the terminal for the "
                            "exact validation error."
                        )

    st.markdown("---")

    # ==========================================================
    # BATCH DELETE
    # ==========================================================
    st.markdown("## Batch Delete Products")
    st.caption("Select products and delete them permanently.")

    if not df.empty:
        with st.form(f"batch_delete_form_{branch_id}", clear_on_submit=False):
            select_all_delete = st.checkbox(
                "Select All",
                key=f"bd_select_all_{branch_id}",
            )

            delete_selected = []
            cols_per_row = 2
            product_list = df.to_dict("records")

            for i, product in enumerate(product_list):
                col_idx = i % cols_per_row
                if col_idx == 0:
                    cols = st.columns(cols_per_row)

                name = str(product.get("name", ""))
                stock = float(product.get("stock", 0) or 0)
                price = float(product.get("price", 0) or 0)

                with cols[col_idx]:
                    checked = st.checkbox(
                        f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})",
                        key=f"bd_pick_{i}_{branch_id}",
                        value=select_all_delete,
                    )
                    if checked:
                        delete_selected.append(i)

            confirm_delete = st.checkbox(
                "I confirm I want to permanently delete the selected products",
                key=f"bd_confirm_{branch_id}",
            )

            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                st.form_submit_button("Clear Selection", use_container_width=True)
            with col2:
                if delete_selected:
                    st.info(f"**{len(delete_selected)} products selected**")
            with col3:
                do_delete = st.form_submit_button(
                    f"Delete {len(delete_selected)} Products",
                    type="secondary",
                    use_container_width=True,
                    disabled=len(delete_selected) == 0,
                )

            if do_delete and delete_selected:
                if not confirm_delete:
                    st.error("Please confirm deletion by checking the box above.")
                else:
                    barcodes_to_delete = []
                    names_deleted = []
                    for idx in delete_selected:
                        if 0 <= idx < len(df):
                            barcodes_to_delete.append(str(df.iloc[idx]["barcode"]))
                            names_deleted.append(str(df.iloc[idx]["name"]))

                    if delete_products(barcodes_to_delete, branch_id=branch_id):
                        st.success(
                            f"Deleted {len(barcodes_to_delete)} product(s): "
                            f"{', '.join(names_deleted[:5])}"
                            f"{'...' if len(names_deleted) > 5 else ''}"
                        )
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("Delete failed. See terminal for details.")
    else:
        st.info("No products in inventory to delete.")

    st.markdown("---")

    # ==========================================================
    # BATCH UPDATE  — single-form flow, no intermediate rerun
    # ==========================================================
    st.markdown("## Batch Update Products")
    st.caption("Pick the products you want to edit, change their fields, then click Save All.")

    if df.empty:
        st.info("No products to update.")
    else:
        # ---- Step 1: select products (outside a form so toggles apply instantly) ----
        st.markdown("### 1. Select Products to Edit")

        select_all_edit = st.checkbox(
            "Select All",
            key=f"bu_select_all_{branch_id}",
        )

        # Build a stable list of selected barcodes for this render.
        # We store barcodes (not row indices) so selection survives across reruns.
        selected_barcodes = set(st.session_state.get("batch_selected", []))

        product_list = df.to_dict("records")
        cols_per_row = 2
        currently_checked_barcodes = []

        for i, product in enumerate(product_list):
            col_idx = i % cols_per_row
            if col_idx == 0:
                cols = st.columns(cols_per_row)

            barcode = str(product.get("barcode", ""))
            name = str(product.get("name", ""))
            stock = float(product.get("stock", 0) or 0)
            price = float(product.get("price", 0) or 0)

            default_checked = select_all_edit or (barcode in selected_barcodes)

            with cols[col_idx]:
                checked = st.checkbox(
                    f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})",
                    key=f"bu_pick_{barcode}_{branch_id}",
                    value=default_checked,
                )
                if checked:
                    currently_checked_barcodes.append(barcode)

        st.session_state.batch_selected = currently_checked_barcodes

        if not currently_checked_barcodes:
            st.info("Select one or more products above to edit them.")
        else:
            st.markdown(f"### 2. Edit {len(currently_checked_barcodes)} Product(s)")

            # ---- Step 2: edit rows. No form wrapper so widget state persists between reruns. ----
            # We read widget values directly at save time, so we don't need
            # to mirror anything into session_state on every render.
            for idx_in_list, barcode in enumerate(currently_checked_barcodes):
                rows = df[df["barcode"].astype(str) == barcode]
                if rows.empty:
                    continue
                product = rows.iloc[0]

                name_val = str(product.get("name", ""))
                category_val = str(product.get("category", ""))
                price_val = float(product.get("price", 0) or 0)
                cost_val = float(product.get("cost", 0) or 0)
                stock_val = float(product.get("stock", 0) or 0)
                reorder_val = float(product.get("reorder_level", 0) or 0)

                st.markdown(f"**Product {idx_in_list + 1}: {name_val}**  `(barcode: {barcode})`")

                c1, c2, c3, c4, c5, c6 = st.columns([2, 1.5, 1.2, 1.2, 1.2, 1.2])

                with c1:
                    st.text_input(
                        "Name",
                        value=name_val,
                        key=f"be_name_{barcode}_{branch_id}",
                    )
                    st.caption("Name")

                with c2:
                    st.text_input(
                        "Category",
                        value=category_val,
                        key=f"be_cat_{barcode}_{branch_id}",
                    )
                    st.caption("Category")

                with c3:
                    st.number_input(
                        "Price",
                        min_value=0.0,
                        value=price_val,
                        step=0.5,
                        format="%.2f",
                        key=f"be_price_{barcode}_{branch_id}",
                    )
                    st.caption("Price ($)")

                with c4:
                    st.number_input(
                        "Cost",
                        min_value=0.0,
                        value=cost_val,
                        step=0.5,
                        format="%.2f",
                        key=f"be_cost_{barcode}_{branch_id}",
                    )
                    st.caption("Cost ($)")

                with c5:
                    st.number_input(
                        "Stock",
                        min_value=0.0,
                        value=stock_val,
                        step=0.5,
                        format="%.2f",
                        key=f"be_stock_{barcode}_{branch_id}",
                    )
                    st.caption("Stock")

                with c6:
                    st.number_input(
                        "Reorder",
                        min_value=0.0,
                        value=reorder_val,
                        step=0.5,
                        format="%.2f",
                        key=f"be_reorder_{barcode}_{branch_id}",
                    )
                    st.caption("Reorder Level")

                st.divider()

            # ---- Step 3: actions (outside any form so reads happen on the same render) ----
            c1, c2, c3 = st.columns([1, 1, 2])

            with c1:
                if st.button("Clear Selection", use_container_width=True, key=f"bu_clear_{branch_id}"):
                    st.session_state.batch_selected = []
                    st.rerun()

            with c2:
                if st.button("Reset Changes", use_container_width=True, key=f"bu_reset_{branch_id}"):
                    # Drop widget keys so each field reverts to the DB value on next render
                    for barcode in currently_checked_barcodes:
                        for prefix in ("be_name", "be_cat", "be_price", "be_cost", "be_stock", "be_reorder"):
                            k = f"{prefix}_{barcode}_{branch_id}"
                            if k in st.session_state:
                                del st.session_state[k]
                    st.rerun()

            with c3:
                save_all = st.button(
                    f"Save All {len(currently_checked_barcodes)} Product(s)",
                    type="primary",
                    use_container_width=True,
                    key=f"bu_save_{branch_id}",
                )

            if save_all:
                edited_rows = []
                validation_problems = []

                for barcode in currently_checked_barcodes:
                    rows = df[df["barcode"].astype(str) == barcode]
                    if rows.empty:
                        continue
                    original = rows.iloc[0]

                    new_name = st.session_state.get(f"be_name_{barcode}_{branch_id}", str(original.get("name", "")))
                    new_category = st.session_state.get(f"be_cat_{barcode}_{branch_id}", str(original.get("category", "")))
                    new_price = st.session_state.get(f"be_price_{barcode}_{branch_id}", float(original.get("price", 0) or 0))
                    new_cost = st.session_state.get(f"be_cost_{barcode}_{branch_id}", float(original.get("cost", 0) or 0))
                    new_stock = st.session_state.get(f"be_stock_{barcode}_{branch_id}", float(original.get("stock", 0) or 0))
                    new_reorder = st.session_state.get(f"be_reorder_{barcode}_{branch_id}", float(original.get("reorder_level", 0) or 0))

                    if not str(new_name).strip():
                        validation_problems.append(f"{barcode}: name cannot be empty")
                        continue

                    edited_rows.append({
                        "branch_id": branch_id,
                        "barcode": barcode,
                        "name": str(new_name).strip(),
                        "category": str(new_category).strip() or "Uncategorized",
                        "price": float(new_price),
                        "cost": float(new_cost),
                        "stock": float(new_stock),
                        "reorder_level": float(new_reorder),
                    })

                if validation_problems:
                    for p in validation_problems:
                        st.error(p)

                if edited_rows:
                    edited_df = pd.DataFrame(edited_rows)
                    with st.expander("Rows being saved (debug)", expanded=False):
                        st.dataframe(edited_df, use_container_width=True, hide_index=True)

                    if save_products(edited_df, branch_id=branch_id):
                        st.success(f"Updated {len(edited_rows)} product(s).")
                        st.balloons()
                        # Drop edit widget keys so next render re-reads from DB
                        for barcode in currently_checked_barcodes:
                            for prefix in ("be_name", "be_cat", "be_price", "be_cost", "be_stock", "be_reorder"):
                                k = f"{prefix}_{barcode}_{branch_id}"
                                if k in st.session_state:
                                    del st.session_state[k]
                        st.session_state.batch_selected = []
                        st.rerun()
                    else:
                        st.error(
                            "Failed to save some products. See terminal for the "
                            "exact validation error(s) printed by save_products."
                        )
                elif not validation_problems:
                    st.warning("No rows were prepared for saving.")

    st.markdown("---")

    # ==========================================================
    # SINGLE PRODUCT UPDATE
    # ==========================================================
    st.markdown("## Single Product Update")
    st.caption("Update one product at a time. Barcodes cannot be changed here.")

    if not df.empty:
        product_names = df["name"].astype(str).tolist()
        selected_product = st.selectbox(
            "Select Product to Update",
            product_names,
            key=f"single_select_{branch_id}",
        )

        if selected_product:
            rows = df[df["name"].astype(str) == selected_product]
            if rows.empty:
                st.warning("Selected product no longer exists.")
            else:
                product_data = rows.iloc[0]
                original_barcode = str(product_data["barcode"])

                name_lower = str(product_data["name"]).lower()
                category_lower = str(product_data.get("category", "")).lower()
                is_decimal_product = any(
                    kw in name_lower or kw in category_lower
                    for kw in ["gas", "kg", "bread", "loaf", "flour", "sugar",
                               "rice", "maize meal", "cooking oil", "milk",
                               "liquid", "weight"]
                )

                with st.form(f"single_update_form_{branch_id}", clear_on_submit=False):
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
                            value=str(product_data["name"]),
                            key=f"su_name_{branch_id}",
                        )
                        update_category = st.text_input(
                            "Category",
                            value=str(product_data.get("category", "")),
                            key=f"su_cat_{branch_id}",
                        )
                        update_price = st.number_input(
                            "Price ($)",
                            min_value=0.0,
                            value=float(product_data["price"]),
                            step=0.5,
                            format="%.2f",
                            key=f"su_price_{branch_id}",
                        )

                    with col2:
                        update_cost = st.number_input(
                            "Cost ($)",
                            min_value=0.0,
                            value=float(product_data.get("cost", 0) or 0),
                            step=0.5,
                            format="%.2f",
                            key=f"su_cost_{branch_id}",
                        )

                        if is_decimal_product:
                            step = 0.5
                            fmt = "%.2f"
                        else:
                            step = 1.0
                            fmt = "%.0f"

                        update_stock = st.number_input(
                            "Stock",
                            min_value=0.0,
                            value=float(product_data["stock"]),
                            step=step,
                            format=fmt,
                            key=f"su_stock_{branch_id}",
                        )
                        update_reorder = st.number_input(
                            "Reorder Level",
                            min_value=0.0,
                            value=float(product_data.get("reorder_level", 0) or 0),
                            step=step,
                            format=fmt,
                            key=f"su_reorder_{branch_id}",
                        )

                    if is_decimal_product:
                        st.info("Decimal quantities supported for this product.")

                    save_changes = st.form_submit_button(
                        "Save Changes", type="primary", use_container_width=True
                    )

                    if save_changes:
                        edited = pd.DataFrame([{
                            "branch_id": branch_id,
                            "barcode": original_barcode,
                            "name": update_name.strip() or str(product_data["name"]),
                            "category": update_category.strip() or "Uncategorized",
                            "price": float(update_price),
                            "cost": float(update_cost),
                            "stock": float(update_stock),
                            "reorder_level": float(update_reorder),
                        }])

                        if save_products(edited, branch_id=branch_id):
                            st.success(f"Product '{update_name}' updated successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to update product. See terminal for details.")

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
                key=f"confirm_delete_all_{branch_id}",
            )
            admin_password = st.text_input(
                "Enter Admin Password to Confirm",
                type="password",
                key=f"admin_password_delete_all_{branch_id}",
            )

            if st.button(
                "DELETE ALL PRODUCTS",
                type="secondary",
                use_container_width=True,
                key=f"delete_all_products_{branch_id}",
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
    if st.button("Refresh Inventory", use_container_width=True, key=f"refresh_bottom_{branch_id}"):
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    inventory_page()