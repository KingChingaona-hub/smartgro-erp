# backend/modules/inventory_page.py
import pandas as pd
import streamlit as st
from backend.core.db_adapter import load_products, save_products
from backend.core.auth import check_login
from backend.scripts.remove_duplicate_products import duplicate_products_page
import traceback
import numpy as np


# ==============================
# HELPER: Clean DataFrame for saving
# ==============================
def clean_dataframe_for_save(df):
    """Clean DataFrame to ensure all data is valid for database save"""
    if df.empty:
        return df
    
    # Create a copy to avoid modifying original
    df_clean = df.copy()
    
    # Ensure required columns exist
    required_cols = ["barcode", "name", "category", "price", "cost", "stock", "reorder_level"]
    for col in required_cols:
        if col not in df_clean.columns:
            if col in ["price", "cost", "stock", "reorder_level"]:
                df_clean[col] = 0
            else:
                df_clean[col] = ""
    
    # Clean string columns
    for col in ["barcode", "name", "category"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna("").astype(str).str.strip()
            # Replace empty with default
            if col == "name":
                df_clean.loc[df_clean[col] == "", col] = "Unknown Product"
            if col == "category":
                df_clean.loc[df_clean[col] == "", col] = "Uncategorized"
            if col == "barcode":
                # Generate barcode if empty
                mask = df_clean[col] == ""
                df_clean.loc[mask, col] = "BC-" + df_clean.loc[mask].index.astype(str)
    
    # Convert numeric columns
    for col in ["price", "cost", "stock", "reorder_level"]:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").fillna(0)
    
    return df_clean


# ==============================
# HELPER: Save with retry
# ==============================
def save_with_retry(df, max_retries=3):
    """Attempt to save with multiple retries"""
    for attempt in range(max_retries):
        try:
            print(f"Save attempt {attempt + 1}/{max_retries}")
            # Clean data before saving
            df_clean = clean_dataframe_for_save(df)
            print(f"Cleaned data: {len(df_clean)} rows, columns: {df_clean.columns.tolist()}")
            
            # Try to save
            success = save_products(df_clean)
            if success:
                print(f"Save successful on attempt {attempt + 1}")
                return True, "Products saved successfully!", df_clean
            else:
                print(f"Save failed on attempt {attempt + 1}")
                # If it's the last attempt, show more details
                if attempt == max_retries - 1:
                    # Try to identify the problematic row
                    for idx, row in df_clean.iterrows():
                        try:
                            # Test each row individually
                            test_df = pd.DataFrame([row])
                            save_products(test_df)
                        except Exception as e:
                            print(f"Problematic row {idx}: {e}")
                            print(f"Row data: {row.to_dict()}")
        except Exception as e:
            print(f"Attempt {attempt + 1} error: {e}")
            traceback.print_exc()
            if attempt == max_retries - 1:
                return False, f"Error after {max_retries} attempts: {str(e)}", df
    
    return False, "Failed to save after multiple attempts", df


# ==============================
# HELPER: Initialize session state safely
# ==============================
def init_session_state():
    """Initialize session state variables safely"""
    default_states = {
        "batch_delete_selected": [],
        "batch_edit_data": {},
        "batch_selected": [],
        "show_duplicate_cleanup": False,
        "batch_delete_confirm": False,
        "batch_edit_confirm": False
    }
    
    for key, default_value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
        # Validate and clean existing state
        elif key == "batch_delete_selected" and not isinstance(st.session_state[key], list):
            st.session_state[key] = []
        elif key == "batch_selected" and not isinstance(st.session_state[key], list):
            st.session_state[key] = []
        elif key == "batch_edit_data" and not isinstance(st.session_state[key], dict):
            st.session_state[key] = {}


# ==============================
# HELPER: Validate indices
# ==============================
def validate_indices(indices, df_length):
    """Filter out invalid indices"""
    if not indices:
        return []
    return [i for i in indices if isinstance(i, int) and 0 <= i < df_length]


# ==============================
# INVENTORY PAGE - WITH BATCH DELETE AND DUPLICATE CLEANUP
# ==============================
def inventory_page():
    # Initialize session state safely
    init_session_state()
    
    # Load products fresh each time
    def load_fresh_products():
        return load_products()
    
    df = load_fresh_products()
    
    # Validate existing indices against current DataFrame
    if not df.empty:
        st.session_state.batch_delete_selected = validate_indices(
            st.session_state.batch_delete_selected, len(df)
        )
        st.session_state.batch_selected = validate_indices(
            st.session_state.batch_selected, len(df)
        )
        # Clean up batch_edit_data for invalid indices
        valid_edit_keys = [k for k in st.session_state.batch_edit_data.keys() if 0 <= k < len(df)]
        if len(valid_edit_keys) != len(st.session_state.batch_edit_data):
            st.session_state.batch_edit_data = {
                k: v for k, v in st.session_state.batch_edit_data.items() 
                if k in valid_edit_keys
            }
    else:
        # If DataFrame is empty, clear all selections
        st.session_state.batch_delete_selected = []
        st.session_state.batch_selected = []
        st.session_state.batch_edit_data = {}
    
    st.title("Inventory Management")
    
    # ==============================
    # DEBUG: Check what's loaded
    # ==============================
    st.sidebar.markdown("### Debug Info")
    st.sidebar.write(f"Products loaded: {len(df)}")
    
    if not df.empty:
        st.sidebar.write(f"Columns: {df.columns.tolist()}")
        # Show branch distribution if available
        if "branch_id" in df.columns:
            branches = df["branch_id"].value_counts()
            st.sidebar.write("Products by branch:")
            for branch, count in branches.items():
                st.sidebar.write(f"  {branch}: {count}")
        # Show sample
        st.sidebar.write(f"First product: {df.iloc[0]['name'] if 'name' in df.columns else 'N/A'}")
        st.sidebar.write(f"Last product: {df.iloc[-1]['name'] if 'name' in df.columns else 'N/A'}")
    else:
        st.sidebar.error("❌ No products loaded!")
        
        # Try to check database directly
        try:
            from backend.core.db_adapter import get_db_connection, get_current_branch
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                current_branch = get_current_branch()
                cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = %s", (current_branch,))
                count = cursor.fetchone()[0]
                if count > 0:
                    st.sidebar.error(f"⚠️ Found {count} products in database but they're not loading!")
                    st.sidebar.info(f"Current branch: {current_branch}")
                cursor.close()
                conn.close()
        except Exception as e:
            st.sidebar.write(f"Debug error: {e}")
    
    # ==============================
    # DISPLAY CURRENT BRANCH
    # ==============================
    current_branch = st.session_state.get("user_branch", "HO")
    st.info(f"Managing inventory for Branch: **{current_branch}**")
    
    # ==============================
    # SMART STOCK ALERTS
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
                    "price": st.column_config.NumberColumn("Price", format="$%.2f")
                }
            )
        else:
            st.success("All products are sufficiently stocked.")
    else:
        st.info("Add products to see stock alerts")
    
    st.markdown("---")
    
    # ==============================
    # SEARCH PRODUCT
    # ==============================
    st.markdown("## Search Product")
    
    search = st.text_input("Enter Barcode or Name", key="inventory_search", placeholder="Type to search...")
    
    if search and not df.empty:
        result = df[
            df["barcode"].astype(str).str.contains(search, case=False) |
            df["name"].str.contains(search, case=False)
        ]
        
        if not result.empty:
            st.dataframe(
                result, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                    "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "cost": st.column_config.NumberColumn("Cost", format="$%.2f")
                }
            )
            st.success(f"Found {len(result)} product(s)")
        else:
            st.warning("No product found")
    
    st.markdown("---")
    
    # ==============================
    # ALL PRODUCTS TABLE
    # ==============================
    st.markdown("## All Products")
    
    if not df.empty:
        display_cols = ["barcode", "name", "category", "price", "stock", "reorder_level"]
        available_cols = [col for col in display_cols if col in df.columns]
        
        st.dataframe(
            df[available_cols], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "reorder_level": st.column_config.NumberColumn("Reorder Level", format="%.2f")
            }
        )
        st.caption(f"Total products: {len(df)}")
    else:
        st.warning("No products in inventory. Add your first product below.")
    
    st.markdown("---")
    
    # ==============================
    # DUPLICATE PRODUCTS CLEANUP TOOL
    # ==============================
    st.markdown("## Tools")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Duplicate Products Cleanup", use_container_width=True, key="go_to_duplicate_cleanup"):
            # Set the page to show duplicate cleanup
            st.session_state.current_page = "Duplicate Products"
            st.session_state.show_duplicate_cleanup = True
            st.rerun()
    
    with col2:
        if st.button("Refresh Inventory", use_container_width=True, key="refresh_inventory"):
            st.cache_data.clear()
            st.rerun()
    
    # Show duplicate cleanup if flag is set
    if st.session_state.get("show_duplicate_cleanup", False):
        st.markdown("---")
        st.markdown("## Duplicate Products Cleanup")
        st.caption("Find and remove duplicate products in your inventory")
        
        # Call the duplicate cleanup function
        duplicate_products_page()
        
        # Add a button to close the cleanup tool
        if st.button("Close Cleanup Tool", use_container_width=True):
            st.session_state.show_duplicate_cleanup = False
            st.rerun()
    
    st.markdown("---")
    
    # ==============================
    # ADD PRODUCT
    # ==============================
    st.markdown("## Add Product")
    
    with st.form("add_product_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            barcode = st.text_input("Barcode *", key="add_barcode")
            name = st.text_input("Product Name *", key="add_name")
            category = st.text_input("Category", key="add_category")
            price = st.number_input("Price ($) *", min_value=0.0, step=0.5, format="%.2f", key="add_price")
        
        with col2:
            cost = st.number_input("Cost ($)", min_value=0.0, step=0.5, format="%.2f", key="add_cost")
            stock = st.number_input("Stock", min_value=0.0, step=0.5, format="%.2f", key="add_stock")
            reorder_level = st.number_input("Reorder Level", min_value=0.0, step=0.5, format="%.2f", key="add_reorder")
            
            st.caption("Use decimals (e.g., 0.5, 1.5) for gas, bread, and weight-based products")
        
        submitted = st.form_submit_button("Add Product", type="primary", use_container_width=True)
        
        if submitted:
            if barcode and name and price > 0:
                if not df.empty and barcode in df["barcode"].astype(str).values:
                    st.error(f"Barcode '{barcode}' already exists!")
                else:
                    new_row = pd.DataFrame([{
                        "barcode": barcode.strip(),
                        "name": name,
                        "category": category if category else "Uncategorized",
                        "price": float(price),
                        "cost": float(cost),
                        "stock": float(stock),
                        "reorder_level": float(reorder_level)
                    }])
                    
                    if df.empty:
                        df = new_row
                    else:
                        df = pd.concat([df, new_row], ignore_index=True)
                    
                    success, message, _ = save_with_retry(df)
                    if success:
                        st.success(f"Product '{name}' added successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Failed to save product: {message}")
            else:
                st.error("Barcode, Name, and Price are required.")
    
    st.markdown("---")
    
    # ==============================
    # BATCH DELETE PRODUCTS - FIXED
    # ==============================
    st.markdown("## Batch Delete Products")
    st.caption("Select multiple products and delete them all at once")
    
    if not df.empty:
        st.markdown("### Select Products to Delete")
        
        # Use a form for batch delete to prevent callback issues
        with st.form("batch_delete_form", clear_on_submit=False):
            # Create checkboxes for each product
            delete_selected = []
            
            # Select All checkbox
            select_all_delete = st.checkbox("Select All", key="select_all_batch_delete_form")
            
            # Show products with checkboxes in grid layout
            cols_per_row = 2
            product_list = df.to_dict('records')
            
            for i, product in enumerate(product_list):
                col_idx = i % cols_per_row
                if col_idx == 0:
                    cols = st.columns(cols_per_row)
                
                barcode = str(product.get("barcode", ""))
                name = str(product.get("name", ""))
                stock = float(product.get("stock", 0))
                price = float(product.get("price", 0))
                
                # Check if this product should be selected
                is_selected = select_all_delete or (i in st.session_state.batch_delete_selected)
                
                with cols[col_idx]:
                    checked = st.checkbox(
                        f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})", 
                        key=f"del_check_{i}",
                        value=is_selected
                    )
                    if checked:
                        delete_selected.append(i)
            
            # Confirm checkbox
            confirm_delete_batch = st.checkbox(
                f"I confirm deleting selected products", 
                key="confirm_batch_delete_form"
            )
            
            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                clear_selected = st.form_submit_button("Clear Selection", use_container_width=True)
                if clear_selected:
                    st.session_state.batch_delete_selected = []
                    st.session_state.batch_delete_confirm = False
                    st.rerun()
            
            with col2:
                # Show selected count
                if delete_selected:
                    st.info(f"**{len(delete_selected)} products selected**")
            
            with col3:
                delete_button = st.form_submit_button(
                    f"Delete {len(delete_selected)} Products", 
                    type="secondary", 
                    use_container_width=True,
                    disabled=len(delete_selected) == 0
                )
                
                if delete_button and delete_selected:
                    if confirm_delete_batch:
                        try:
                            # Store selected indices for processing
                            st.session_state.batch_delete_selected = delete_selected
                            
                            # Get product names for the message
                            product_names = []
                            for idx in delete_selected:
                                if idx < len(df):
                                    product_names.append(df.iloc[idx].get("name", "Unknown"))
                            
                            # Delete selected products
                            keep_indices = [i for i in df.index if i not in delete_selected]
                            df_new = df.loc[keep_indices].copy()
                            df_new = df_new.reset_index(drop=True)
                            
                            # Verify the deletion
                            deleted_count = len(df) - len(df_new)
                            
                            if deleted_count == len(delete_selected):
                                # Save the updated DataFrame
                                success, message, _ = save_with_retry(df_new)
                                if success:
                                    # Clear cache to force reload
                                    st.cache_data.clear()
                                    
                                    # Clear selection
                                    st.session_state.batch_delete_selected = []
                                    st.session_state.batch_delete_confirm = False
                                    
                                    # Show success message
                                    st.success(f"Successfully deleted {deleted_count} products: {', '.join(product_names[:5])}{'...' if len(product_names) > 5 else ''}")
                                    st.balloons()
                                    
                                    # Force reload
                                    st.rerun()
                                else:
                                    st.error(f"Failed to save changes: {message}")
                            else:
                                st.error(f"Failed to delete products. Expected {len(delete_selected)} but deleted {deleted_count}.")
                        except Exception as e:
                            st.error(f"Error deleting products: {str(e)}")
                            st.code(traceback.format_exc())
                    else:
                        st.error("Please confirm deletion by checking the box above.")
        
        # Show selected products summary outside form
        if st.session_state.batch_delete_selected:
            with st.expander("Selected Products to Delete"):
                selected_data = []
                for idx in st.session_state.batch_delete_selected:
                    if idx < len(df):
                        product = df.iloc[idx]
                        selected_data.append({
                            "Name": product.get("name", ""),
                            "Barcode": product.get("barcode", ""),
                            "Stock": product.get("stock", 0),
                            "Price": product.get("price", 0)
                        })
                
                if selected_data:
                    selected_df = pd.DataFrame(selected_data)
                    st.dataframe(
                        selected_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                            "Price": st.column_config.NumberColumn("Price", format="$%.2f")
                        }
                    )
    else:
        st.info("No products in inventory to delete.")
    
    st.markdown("---")
    
    # ==============================
    # BATCH UPDATE PRODUCTS - FIXED
    # ==============================
    st.markdown("## Batch Update Products")
    st.caption("Select multiple products, edit their details manually, then save all at once")
    
    if not df.empty:
        st.markdown("### Select Products to Edit")
        
        # Use a form for batch edit selection
        with st.form("batch_edit_select_form", clear_on_submit=False):
            # Select All checkbox
            select_all_edit = st.checkbox("Select All", key="select_all_batch_edit_form")
            
            # Show products with checkboxes
            cols_per_row = 2
            product_list = df.to_dict('records')
            edit_selected = []
            
            for i, product in enumerate(product_list):
                col_idx = i % cols_per_row
                if col_idx == 0:
                    cols = st.columns(cols_per_row)
                
                barcode = str(product.get("barcode", ""))
                name = str(product.get("name", ""))
                stock = float(product.get("stock", 0))
                price = float(product.get("price", 0))
                
                is_selected = select_all_edit or (i in st.session_state.batch_selected)
                
                with cols[col_idx]:
                    checked = st.checkbox(
                        f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})", 
                        key=f"edit_check_{i}",
                        value=is_selected
                    )
                    if checked:
                        edit_selected.append(i)
                        # Initialize edit data for new selections
                        if i not in st.session_state.batch_edit_data:
                            st.session_state.batch_edit_data[i] = {
                                "name": str(product.get("name", "")),
                                "category": str(product.get("category", "")),
                                "price": float(product.get("price", 0)),
                                "cost": float(product.get("cost", 0)),
                                "stock": float(product.get("stock", 0)),
                                "reorder_level": float(product.get("reorder_level", 0))
                            }
                    else:
                        # Remove from selected if unchecked
                        if i in st.session_state.batch_edit_data:
                            # Don't delete edit data, just mark as not selected
                            pass
            
            # Update selection
            if st.form_submit_button("Update Selection", use_container_width=True):
                st.session_state.batch_selected = edit_selected
                st.rerun()
        
        # Show selected products for editing
        if st.session_state.batch_selected:
            st.markdown("---")
            st.markdown(f"### Editing {len(st.session_state.batch_selected)} Product(s)")
            st.info("Edit the fields below for each selected product. Changes will be saved together when you click 'Save All Changes'.")
            
            # Create editable fields for each selected product
            with st.form("batch_edit_form", clear_on_submit=False):
                updates = {}
                
                for idx in st.session_state.batch_selected:
                    if idx < len(df):
                        product = df.iloc[idx]
                        current_name = str(product.get("name", ""))
                        
                        # Get existing edit data or use current values
                        edit_data = st.session_state.batch_edit_data.get(idx, {})
                        
                        st.markdown(f"**Product {idx+1}: {current_name}**")
                        
                        col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
                        
                        with col1:
                            new_name = st.text_input(
                                "Name",
                                value=edit_data.get("name", current_name),
                                key=f"edit_name_{idx}",
                                label_visibility="collapsed"
                            )
                            st.caption("Product Name")
                        
                        with col2:
                            new_category = st.text_input(
                                "Category",
                                value=edit_data.get("category", product.get("category", "")),
                                key=f"edit_category_{idx}",
                                label_visibility="collapsed"
                            )
                            st.caption("Category")
                        
                        with col3:
                            new_price = st.number_input(
                                "Price ($)",
                                min_value=0.0,
                                value=float(edit_data.get("price", product.get("price", 0))),
                                step=0.5,
                                format="%.2f",
                                key=f"edit_price_{idx}",
                                label_visibility="collapsed"
                            )
                            st.caption("Price ($)")
                        
                        with col4:
                            new_cost = st.number_input(
                                "Cost ($)",
                                min_value=0.0,
                                value=float(edit_data.get("cost", product.get("cost", 0))),
                                step=0.5,
                                format="%.2f",
                                key=f"edit_cost_{idx}",
                                label_visibility="collapsed"
                            )
                            st.caption("Cost ($)")
                        
                        with col5:
                            new_stock = st.number_input(
                                "Stock",
                                min_value=0.0,
                                value=float(edit_data.get("stock", product.get("stock", 0))),
                                step=0.5,
                                format="%.2f",
                                key=f"edit_stock_{idx}",
                                label_visibility="collapsed"
                            )
                            st.caption("Stock")
                        
                        # Reorder level
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            new_reorder = st.number_input(
                                "Reorder Level",
                                min_value=0.0,
                                value=float(edit_data.get("reorder_level", product.get("reorder_level", 0))),
                                step=0.5,
                                format="%.2f",
                                key=f"edit_reorder_{idx}",
                                label_visibility="collapsed"
                            )
                            st.caption("Reorder Level")
                        
                        # Store updates
                        updates[idx] = {
                            "name": new_name,
                            "category": new_category,
                            "price": new_price,
                            "cost": new_cost,
                            "stock": new_stock,
                            "reorder_level": new_reorder
                        }
                        
                        st.divider()
                
                # Update session state with latest values
                for idx, data in updates.items():
                    st.session_state.batch_edit_data[idx] = data
                
                # Action buttons
                col1, col2, col3 = st.columns([1, 1, 1])
                
                with col1:
                    if st.form_submit_button("Clear All Selections", use_container_width=True):
                        st.session_state.batch_selected = []
                        st.session_state.batch_edit_data = {}
                        st.rerun()
                
                with col2:
                    if st.form_submit_button("Reset Changes", use_container_width=True):
                        # Reset to original values
                        for idx in st.session_state.batch_selected:
                            if idx < len(df):
                                product = df.iloc[idx]
                                st.session_state.batch_edit_data[idx] = {
                                    "name": str(product.get("name", "")),
                                    "category": str(product.get("category", "")),
                                    "price": float(product.get("price", 0)),
                                    "cost": float(product.get("cost", 0)),
                                    "stock": float(product.get("stock", 0)),
                                    "reorder_level": float(product.get("reorder_level", 0))
                                }
                        st.rerun()
                
                with col3:
                    save_all = st.form_submit_button(
                        f"Save All {len(st.session_state.batch_selected)} Product(s)",
                        type="primary",
                        use_container_width=True
                    )
                    
                    if save_all:
                        try:
                            # Apply all updates to DataFrame
                            for idx, data in st.session_state.batch_edit_data.items():
                                if idx < len(df):
                                    df.at[idx, "name"] = str(data.get("name", df.at[idx, "name"]))
                                    df.at[idx, "category"] = str(data.get("category", df.at[idx, "category"]))
                                    df.at[idx, "price"] = float(data.get("price", df.at[idx, "price"]))
                                    df.at[idx, "cost"] = float(data.get("cost", df.at[idx, "cost"]))
                                    df.at[idx, "stock"] = float(data.get("stock", df.at[idx, "stock"]))
                                    df.at[idx, "reorder_level"] = float(data.get("reorder_level", df.at[idx, "reorder_level"]))
                            
                            # Save all changes at once
                            success, message, _ = save_with_retry(df)
                            if success:
                                st.success(f"Successfully updated {len(st.session_state.batch_selected)} products!")
                                st.balloons()
                                # Clear selections
                                st.session_state.batch_selected = []
                                st.session_state.batch_edit_data = {}
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Failed to save changes: {message}")
                                # Show debug info
                                with st.expander("Debug Info"):
                                    st.write("First 5 rows of data being saved:")
                                    st.dataframe(df.head(5))
                                    st.write("Data types:")
                                    st.write(df.dtypes)
                                    
                                    # Check for common issues
                                    issues = []
                                    if "name" in df.columns:
                                        empty_names = df[df["name"].isna() | (df["name"] == "")]
                                        if not empty_names.empty:
                                            issues.append(f"Found {len(empty_names)} products with empty names")
                                    
                                    if "barcode" in df.columns:
                                        empty_barcodes = df[df["barcode"].isna() | (df["barcode"] == "")]
                                        if not empty_barcodes.empty:
                                            issues.append(f"Found {len(empty_barcodes)} products with empty barcodes")
                                    
                                    if issues:
                                        st.warning("Issues found:")
                                        for issue in issues:
                                            st.write(f"- {issue}")
                            
                        except Exception as e:
                            st.error(f"Error saving products: {str(e)}")
                            st.code(traceback.format_exc())
            
            # Show summary of selected products
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
                            "Category": edit_data.get("category", product.get("category", ""))
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
                            "Cost": st.column_config.NumberColumn("Cost", format="$%.2f")
                        }
                    )
    
    st.markdown("---")
    
    # ==============================
    # SINGLE PRODUCT UPDATE
    # ==============================
    st.markdown("## Single Product Update")
    st.caption("Update one product at a time")
    
    if not df.empty:
        product_names = df["name"].tolist()
        selected_product = st.selectbox("Select Product to Update", product_names, key="update_product_select_single")
        
        if selected_product:
            product_data = df[df["name"] == selected_product].iloc[0]
            product_index = df[df["name"] == selected_product].index[0]
            
            name_lower = str(product_data["name"]).lower()
            category_lower = str(product_data.get("category", "")).lower()
            is_decimal_product = any(keyword in name_lower or keyword in category_lower 
                                     for keyword in ["gas", "kg", "bread", "loaf", "flour", "sugar", 
                                                     "rice", "maize meal", "cooking oil", "milk", 
                                                     "liquid", "weight"])
            
            with st.form("update_product_form_single", clear_on_submit=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    update_barcode = st.text_input("Barcode", value=str(product_data["barcode"]), key="single_update_barcode")
                    update_name = st.text_input("Product Name", value=product_data["name"], key="single_update_name")
                    update_category = st.text_input("Category", value=product_data.get("category", ""), key="single_update_category")
                    update_price = st.number_input(
                        "Price ($)", 
                        value=float(product_data["price"]), 
                        min_value=0.0, 
                        step=0.5, 
                        format="%.2f",
                        key="single_update_price"
                    )
                
                with col2:
                    update_cost = st.number_input(
                        "Cost ($)", 
                        value=float(product_data.get("cost", 0)), 
                        min_value=0.0, 
                        step=0.5, 
                        format="%.2f",
                        key="single_update_cost"
                    )
                    
                    current_stock = float(product_data["stock"])
                    current_reorder = float(product_data["reorder_level"])
                    
                    if is_decimal_product:
                        stock_step = 0.5
                        stock_min = 0.0
                        stock_format = "%.2f"
                    else:
                        stock_step = 1.0
                        stock_min = 0.0
                        stock_format = "%.0f"
                    
                    update_stock = st.number_input(
                        "Stock", 
                        min_value=stock_min, 
                        value=current_stock, 
                        step=stock_step,
                        format=stock_format,
                        key="single_update_stock"
                    )
                    
                    update_reorder = st.number_input(
                        "Reorder Level", 
                        min_value=stock_min, 
                        value=current_reorder, 
                        step=stock_step,
                        format=stock_format,
                        key="single_update_reorder"
                    )
                
                if is_decimal_product:
                    st.info("Decimal quantities supported for this product (e.g., 0.5, 1.5, 2.0)")
                
                save_changes = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
                
                if save_changes:
                    try:
                        df.at[product_index, "barcode"] = update_barcode.strip()
                        df.at[product_index, "name"] = update_name
                        df.at[product_index, "category"] = update_category if update_category else "Uncategorized"
                        df.at[product_index, "price"] = float(update_price)
                        df.at[product_index, "cost"] = float(update_cost)
                        df.at[product_index, "stock"] = float(update_stock)
                        df.at[product_index, "reorder_level"] = float(update_reorder)
                        
                        success, message, _ = save_with_retry(df)
                        if success:
                            st.success(f"Product '{update_name}' updated successfully!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Failed to save product changes: {message}")
                    except Exception as e:
                        st.error(f"Error updating product: {str(e)}")
    
    # ==============================
    # DELETE ALL PRODUCTS - ADMIN ONLY
    # ==============================
    st.markdown("---")
    st.markdown("## Danger Zone")
    st.warning("This section is for administrators only. Proceed with caution.")
    
    user_role = st.session_state.get("role", "")
    is_admin = user_role in ["owner", "admin"]
    
    if is_admin:
        with st.expander("Delete All Products (Admin Only)", expanded=False):
            st.error("DANGER: This action will permanently delete ALL products from inventory!")
            
            product_count = len(df) if not df.empty else 0
            st.warning(f"You are about to delete {product_count} products. This action CANNOT be undone.")
            
            confirm_action = st.checkbox("I understand this will delete ALL products", key="confirm_delete_all")
            admin_password = st.text_input("Enter Admin Password to Confirm", type="password", key="admin_password_delete_all")
            
            if st.button("DELETE ALL PRODUCTS", type="secondary", use_container_width=True):
                if not confirm_action:
                    st.error("Please confirm that you understand this action.")
                elif not admin_password:
                    st.error("Please enter your admin password.")
                else:
                    username = st.session_state.get("username", "")
                    login_success, role = check_login(username, admin_password)
                    
                    if login_success and role in ["owner", "admin"]:
                        if df.empty:
                            st.info("No products to delete.")
                        else:
                            empty_df = pd.DataFrame(columns=df.columns.tolist())
                            success, message, _ = save_with_retry(empty_df)
                            if success:
                                st.success(f"Successfully deleted ALL {product_count} products!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Failed to delete products: {message}")
                    else:
                        st.error("Invalid admin password. Deletion cancelled.")
    else:
        st.info("Only administrators can delete all products. Contact your system administrator.")
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    st.caption("Click the button below to refresh the inventory list and see latest changes.")
    
    if st.button("Refresh Inventory", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    inventory_page()