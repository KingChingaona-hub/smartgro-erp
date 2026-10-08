# backend/modules/inventory_page.py
"""
Inventory management page.

Design rules (post-fix):
  - No @st.cache_data anywhere. Every render reads fresh from the DB.
  - Every write sends ONLY the row(s) that changed to save_products /
    delete_products, never the whole catalog. This eliminates the
    read-modify-write race where stale rows overwrite fresh stock.
  - Batch delete uses delete_products (real SQL DELETE) instead of
    silently re-saving the surviving rows.
  - Batch update sends only the edited rows to save_products.
  - Barcodes are validated with the relaxed validate_barcode, so SKUs,
    EAN-8/12/13, and alphanumeric codes are all accepted.
  - Empty barcodes on "Add Product" are auto-generated as 13-digit
    numeric codes that pass validate_barcode.
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
# SESSION BRANCH HELPER
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
            match = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                name = match.iloc[0].get("branch_name", "")
                if name:
                    return f"{name} ({branch_id})"
    except Exception:
        pass
    return str(branch_id)


# ==============================
# BARCODE GENERATOR
# ==============================
def _generate_numeric_barcode(seed_index=0):
    """
    Generate a 13-digit numeric barcode that passes validate_barcode.
    """
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")  # 20 digits
    core = stamp[:12]
    idx = f"{seed_index % 100:02d}"
    raw = "2" + core + idx  # 15 chars
    return raw[:13].ljust(13, "0")


# ==============================
# SESSION STATE INIT
# ==============================
def init_session_state():
    defaults = {
        "batch_delete_selected": [],
        "batch_edit_data": {},
        "batch_selected": [],
        "show_duplicate_cleanup": False,
        "batch_delete_confirm": False,
        "batch_edit_confirm": False,
        "_inv_last_branch": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
        elif k in ("batch_delete_selected", "batch_selected") and not isinstance(st.session_state[k], list):
            st.session_state[k] = []
        elif k == "batch_edit_data" and not isinstance(st.session_state[k], dict):
            st.session_state[k] = {}


def _ensure_branch_consistency():
    """Drop per-branch selection state if the session branch changed."""
    current = _get_session_branch()
    last = st.session_state.get("_inv_last_branch")
    if last != current:
        st.session_state.batch_delete_selected = []
        st.session_state.batch_selected = []
        st.session_state.batch_edit_data = {}
        st.session_state["_inv_last_branch"] = current


# ==============================
# INVENTORY PAGE
# ==============================
def inventory_page():
    init_session_state()
    _ensure_branch_consistency()

    branch_id = _get_session_branch()
    branch_label = _branch_display_name(branch_id)

    # Always read fresh — no cache
    df = load_products(branch_id=branch_id)

    st.title(f"Inventory Management - {branch_label}")
    st.info(f"Managing inventory for Branch: **{branch_label}**")

    # ---------- Smart stock alerts ----------
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

    # ---------- Search ----------
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

    # ---------- All products ----------
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

    # ---------- Tools ----------
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

    # ---------- Add product ----------
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
                            "Failed to save product. The barcode may be invalid "
                            "or the database rejected the row. See terminal for details."
                        )

    st.markdown("---")

    # ==========================================================
    # BATCH DELETE PRODUCTS
    # ==========================================================
    st.markdown("## Batch Delete Products")
    st.caption("Select multiple products and delete them all at once")

    if not df.empty:
        st.markdown("### Select Products to Delete")

        with st.form(f"batch_delete_form_{branch_id}", clear_on_submit=False):
            select_all_delete = st.checkbox("Select All", key=f"select_all_delete_{branch_id}")

            delete_selected = []
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
                        key=f"del_check_{i}_{branch_id}",
                        value=select_all_delete,
                    )
                    if checked:
                        delete_selected.append(i)

            confirm_delete_batch = st.checkbox(
                "I confirm I want to permanently delete the selected products",
                key=f"confirm_batch_delete_{branch_id}",
            )

            col1, col2, col3 = st.columns([1, 1, 1])

            with col1:
                clear_selected = st.form_submit_button("Clear Selection", use_container_width=True)
                if clear_selected:
                    st.rerun()

            with col2:
                if delete_selected:
                    st.info(f"**{len(delete_selected)} products selected**")

            with col3:
                delete_button = st.form_submit_button(
                    f"Delete {len(delete_selected)} Products",
                    type="secondary",
                    use_container_width=True,
                    disabled=len(delete_selected) == 0,
                )

                if delete_button and delete_selected:
                    if not confirm_delete_batch:
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
                                f"Successfully deleted {len(barcodes_to_delete)} product(s): "
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
    # BATCH UPDATE PRODUCTS  (RESTORED)
    # ==========================================================
    st.markdown("## Batch Update Products")
    st.caption("Select multiple products, edit their details manually, then save all at once")

    if not df.empty:
        st.markdown("### Select Products to Edit")

        # ---- selection step (own form so it doesn't collide with the edit form) ----
        with st.form(f"batch_edit_select_form_{branch_id}", clear_on_submit=False):
            select_all_edit = st.checkbox("Select All", key=f"select_all_batch_edit_form_{branch_id}")

            cols_per_row = 2
            product_list = df.to_dict("records")
            edit_selected = []

            for i, product in enumerate(product_list):
                col_idx = i % cols_per_row
                if col_idx == 0:
                    cols = st.columns(cols_per_row)

                name = str(product.get("name", ""))
                stock = float(product.get("stock", 0) or 0)
                price = float(product.get("price", 0) or 0)

                is_selected = select_all_edit or (i in st.session_state.batch_selected)

                with cols[col_idx]:
                    checked = st.checkbox(
                        f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})",
                        key=f"edit_check_{i}_{branch_id}",
                        value=is_selected,
                    )
                    if checked:
                        edit_selected.append(i)
                        if i not in st.session_state.batch_edit_data:
                            st.session_state.batch_edit_data[i] = {
                                "name": str(product.get("name", "")),
                                "category": str(product.get("category", "")),
                                "price": float(product.get("price", 0) or 0),
                                "cost": float(product.get("cost", 0) or 0),
                                "stock": float(product.get("stock", 0) or 0),
                                "reorder_level": float(product.get("reorder_level", 0) or 0),
                            }

            if st.form_submit_button("Update Selection", use_container_width=True):
                st.session_state.batch_selected = edit_selected
                st.rerun()

        # ---- edit step ----
        if st.session_state.batch_selected:
            st.markdown("---")
            st.markdown(f"### Editing {len(st.session_state.batch_selected)} Product(s)")
            st.info(
                "Edit the fields below for each selected product. Changes will be "
                "saved together when you click 'Save All Changes'."
            )

            with st.form(f"batch_edit_form_{branch_id}", clear_on_submit=False):
                updates = {}

                for idx in st.session_state.batch_selected:
                    if idx < len(df):
                        product = df.iloc[idx]
                        current_name = str(product.get("name", ""))
                        edit_data = st.session_state.batch_edit_data.get(idx, {})

                        st.markdown(f"**Product {idx + 1}: {current_name}**")

                        col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])

                        with col1:
                            new_name = st.text_input(
                                "Name",
                                value=edit_data.get("name", current_name),
                                key=f"edit_name_{idx}_{branch_id}",
                                label_visibility="collapsed",
                            )
                            st.caption("Product Name")

                        with col2:
                            new_category = st.text_input(
                                "Category",
                                value=edit_data.get("category", product.get("category", "")),
                                key=f"edit_category_{idx}_{branch_id}",
                                label_visibility="collapsed",
                            )
                            st.caption("Category")

                        with col3:
                            new_price = st.number_input(
                                "Price ($)",
                                min_value=0.0,
                                value=float(edit_data.get("price", product.get("price", 0) or 0)),
                                step=0.5,
                                format="%.2f",
                                key=f"edit_price_{idx}_{branch_id}",
                                label_visibility="collapsed",
                            )
                            st.caption("Price ($)")

                        with col4:
                            new_cost = st.number_input(
                                "Cost ($)",
                                min_value=0.0,
                                value=float(edit_data.get("cost", product.get("cost", 0) or 0)),
                                step=0.5,
                                format="%.2f",
                                key=f"edit_cost_{idx}_{branch_id}",
                                label_visibility="collapsed",
                            )
                            st.caption("Cost ($)")

                        with col5:
                            new_stock = st.number_input(
                                "Stock",
                                min_value=0.0,
                                value=float(edit_data.get("stock", product.get("stock", 0) or 0)),
                                step=0.5,
                                format="%.2f",
                                key=f"edit_stock_{idx}_{branch_id}",
                                label_visibility="collapsed",
                            )
                            st.caption("Stock")

                        col1b, col2b = st.columns([1, 4])
                        with col1b:
                            new_reorder = st.number_input(
                                "Reorder Level",
                                min_value=0.0,
                                value=float(edit_data.get("reorder_level", product.get("reorder_level", 0) or 0)),
                                step=0.5,
                                format="%.2f",
                                key=f"edit_reorder_{idx}_{branch_id}",
                                label_visibility="collapsed",
                            )
                            st.caption("Reorder Level")

                        updates[idx] = {
                            "name": new_name,
                            "category": new_category,
                            "price": new_price,
                            "cost": new_cost,
                            "stock": new_stock,
                            "reorder_level": new_reorder,
                        }

                        st.divider()

                # persist entered values into session state (survives the Save submit)
                for idx, data in updates.items():
                    st.session_state.batch_edit_data[idx] = data

                col1, col2, col3 = st.columns([1, 1, 1])

                with col1:
                    if st.form_submit_button("Clear All Selections", use_container_width=True):
                        st.session_state.batch_selected = []
                        st.session_state.batch_edit_data = {}
                        st.rerun()

                with col2:
                    if st.form_submit_button("Reset Changes", use_container_width=True):
                        for idx in st.session_state.batch_selected:
                            if idx < len(df):
                                product = df.iloc[idx]
                                st.session_state.batch_edit_data[idx] = {
                                    "name": str(product.get("name", "")),
                                    "category": str(product.get("category", "")),
                                    "price": float(product.get("price", 0) or 0),
                                    "cost": float(product.get("cost", 0) or 0),
                                    "stock": float(product.get("stock", 0) or 0),
                                    "reorder_level": float(product.get("reorder_level", 0) or 0),
                                }
                        st.rerun()

                with col3:
                    save_all = st.form_submit_button(
                        f"Save All {len(st.session_state.batch_selected)} Product(s)",
                        type="primary",
                        use_container_width=True,
                    )

                    if save_all:
                        # Build ONE DataFrame containing ONLY the edited rows,
                        # and send that to save_products. This is the fix that
                        # prevents the whole catalog from being re-saved on
                        # every batch update.
                        edited_rows = []
                        for idx, data in st.session_state.batch_edit_data.items():
                            if idx < len(df):
                                original = df.iloc[idx]
                                edited_rows.append({
                                    "branch_id": branch_id,
                                    "barcode": str(original.get("barcode", "")),
                                    "name": str(data.get("name", original.get("name", ""))),
                                    "category": str(data.get("category", original.get("category", ""))) or "Uncategorized",
                                    "price": float(data.get("price", original.get("price", 0) or 0)),
                                    "cost": float(data.get("cost", original.get("cost", 0) or 0)),
                                    "stock": float(data.get("stock", original.get("stock", 0) or 0)),
                                    "reorder_level": float(data.get("reorder_level", original.get("reorder_level", 0) or 0)),
                                })

                        if not edited_rows:
                            st.warning("No products selected to save.")
                        else:
                            edited_df = pd.DataFrame(edited_rows)
                            if save_products(edited_df, branch_id=branch_id):
                                st.success(
                                    f"Successfully updated {len(edited_rows)} product(s)!"
                                )
                                st.balloons()
                                st.session_state.batch_selected = []
                                st.session_state.batch_edit_data = {}
                                st.rerun()
                            else:
                                st.error(
                                    "Failed to save some products. See terminal for the exact "
                                    "validation error(s)."
                                )
                                with st.expander("Debug Info"):
                                    st.write("Rows being saved:")
                                    st.dataframe(edited_df)

            # ---- selected products summary ----
            with st.expander("Selected Products Summary"):
                summary_data = []
                for idx in st.session_state.batch_selected:
                    if idx < len(df):
                        product = df.iloc[idx]
                        edit_data = st.session_state.batch_edit_data.get(idx, {})
                        summary_data.append({
                            "Product": product.get("name", ""),
                            "Stock": edit_data.get("stock", product.get("stock", 0)),
                            "Price": edit_data.get("price", product.get("price", 0)),
                            "Cost": edit_data.get("cost", product.get("cost", 0)),
                            "Category": edit_data.get("category", product.get("category", "")),
                        })

                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    st.dataframe(
                        summary_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                            "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                            "Cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                        },
                    )

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
            key=f"update_product_select_{branch_id}",
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

                with st.form(f"update_product_form_{branch_id}", clear_on_submit=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.text_input(
                            "Barcode (read-only)",
                            value=original_barcode,
                            disabled=True,
                            key=f"single_barcode_ro_{branch_id}",
                        )
                        update_name = st.text_input(
                            "Product Name",
                            value=str(product_data["name"]),
                            key=f"single_name_{branch_id}",
                        )
                        update_category = st.text_input(
                            "Category",
                            value=str(product_data.get("category", "")),
                            key=f"single_category_{branch_id}",
                        )
                        update_price = st.number_input(
                            "Price ($)",
                            min_value=0.0,
                            value=float(product_data["price"]),
                            step=0.5,
                            format="%.2f",
                            key=f"single_price_{branch_id}",
                        )

                    with col2:
                        update_cost = st.number_input(
                            "Cost ($)",
                            min_value=0.0,
                            value=float(product_data.get("cost", 0) or 0),
                            step=0.5,
                            format="%.2f",
                            key=f"single_cost_{branch_id}",
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
                            key=f"single_stock_{branch_id}",
                        )
                        update_reorder = st.number_input(
                            "Reorder Level",
                            min_value=0.0,
                            value=float(product_data.get("reorder_level", 0) or 0),
                            step=step,
                            format=fmt,
                            key=f"single_reorder_{branch_id}",
                        )

                    if is_decimal_product:
                        st.info("Decimal quantities supported for this product.")

                    save_changes = st.form_submit_button(
                        "Save Changes", type="primary", use_container_width=True
                    )

                    if save_changes:
                        # Build ONE-ROW DataFrame — only this product is written
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
                            st.error(
                                "Failed to update product. See terminal for details."
                            )

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