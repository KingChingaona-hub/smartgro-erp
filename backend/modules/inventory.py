# backend/modules/inventory_page.py
import pandas as pd
import streamlit as st
from backend.core.db_adapter import load_products, save_products
from backend.core.auth import check_login
from backend.scripts.remove_duplicate_products import find_duplicate_products, remove_duplicate_products
import traceback


# ==============================
# INVENTORY PAGE - WITH BATCH DELETE
# ==============================
def inventory_page():
    
    # Load products fresh each time
    @st.cache_data(ttl=0)
    def load_fresh_products():
        return load_products()
    
    df = load_fresh_products()
    
    st.title("Inventory Management")
    
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
        st.info("No products in inventory. Add your first product below.")
    
    st.markdown("---")
    
    # ==============================
    # DUPLICATE PRODUCTS CLEANUP - IMPORTED FROM MODULE
    # ==============================
    st.markdown("## Duplicate Products Cleanup")
    st.caption("Find and remove duplicate products in your inventory")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Find Duplicate Products", use_container_width=True, key="find_duplicates_btn"):
            with st.spinner("Scanning for duplicates..."):
                report_df, summary = find_duplicate_products()
                
                if report_df.empty:
                    st.success("No duplicate products found! Your inventory is clean.")
                    st.session_state.duplicate_report = None
                    st.session_state.duplicate_summary = None
                    st.session_state.show_duplicates = False
                else:
                    st.session_state.duplicate_report = report_df
                    st.session_state.duplicate_summary = summary
                    st.session_state.show_duplicates = True
                    st.rerun()
    
    with col2:
        if st.button("Go to Full Cleanup Tool", use_container_width=True, key="go_to_cleanup_tool"):
            st.session_state.current_page = "Duplicate Products"
            st.rerun()
    
    # Show duplicate results if available
    if st.session_state.get("show_duplicates", False):
        report_df = st.session_state.get("duplicate_report")
        summary = st.session_state.get("duplicate_summary")
        
        if report_df is not None and not report_df.empty:
            # Display summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Products", summary['total_products'])
            with col2:
                st.metric("Barcode Duplicates", summary['barcode_duplicates'])
            with col3:
                st.metric("Name Duplicates", summary['name_duplicates'])
            
            st.markdown("---")
            
            # Show duplicate details
            st.subheader("Duplicate Products Details")
            st.dataframe(
                report_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                    "Total Value": st.column_config.NumberColumn("Total Value", format="$%.2f")
                }
            )
            
            st.markdown("---")
            
            # Cleanup options
            st.subheader("Quick Cleanup")
            
            col1, col2 = st.columns(2)
            
            with col1:
                merge_stock = st.checkbox(
                    "Merge stock of duplicates",
                    value=True,
                    help="If checked, stock from duplicate products will be added together into the kept product."
                )
            
            with col2:
                st.caption(" ")
                st.warning("⚠️ This action cannot be undone.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Remove Duplicates Now", type="primary", use_container_width=True, key="remove_duplicates_btn"):
                    with st.spinner("Removing duplicates..."):
                        success, message, new_df = remove_duplicate_products(merge_stock=merge_stock)
                        if success:
                            st.success(message)
                            st.balloons()
                            st.session_state.show_duplicates = False
                            st.session_state.duplicate_report = None
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(message)
            
            with col2:
                if st.button("Cancel", use_container_width=True, key="cancel_duplicates_btn"):
                    st.session_state.show_duplicates = False
                    st.session_state.duplicate_report = None
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
                    
                    if save_products(df):
                        st.success(f"Product '{name}' added successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Failed to save product.")
            else:
                st.error("Barcode, Name, and Price are required.")
    
    st.markdown("---")
    
    # ==============================
    # BATCH DELETE PRODUCTS
    # ==============================
    st.markdown("## Batch Delete Products")
    st.caption("Select multiple products and delete them all at once")
    
    if not df.empty:
        # Initialize session state for batch delete
        if "batch_delete_selected" not in st.session_state:
            st.session_state.batch_delete_selected = []
        
        # Display products with checkboxes
        st.markdown("### Select Products to Delete")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            select_all_delete = st.checkbox("Select All", key="select_all_batch_delete")
        
        # Reset selection if select all
        if select_all_delete:
            st.session_state.batch_delete_selected = df.index.tolist()
        
        # Show products with checkboxes
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
            idx = i
            
            with cols[col_idx]:
                is_selected = idx in st.session_state.batch_delete_selected
                selected = st.checkbox(
                    f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})", 
                    key=f"batch_delete_{barcode}_{i}",
                    value=is_selected
                )
                
                if selected and idx not in st.session_state.batch_delete_selected:
                    st.session_state.batch_delete_selected.append(idx)
                elif not selected and idx in st.session_state.batch_delete_selected:
                    st.session_state.batch_delete_selected.remove(idx)
        
        # Show selected count and delete button
        if st.session_state.batch_delete_selected:
            st.markdown("---")
            st.warning(f"**{len(st.session_state.batch_delete_selected)} products selected for deletion**")
            
            # Show selected products summary
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
            
            # Confirmation and delete button
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                confirm_delete_batch = st.checkbox(
                    f"I confirm deleting {len(st.session_state.batch_delete_selected)} products", 
                    key="confirm_batch_delete"
                )
            
            with col2:
                if st.button("Clear Selection", use_container_width=True, key="clear_batch_delete"):
                    st.session_state.batch_delete_selected = []
                    st.rerun()
            
            with col3:
                if st.button(
                    f"Delete {len(st.session_state.batch_delete_selected)} Products", 
                    type="secondary", 
                    use_container_width=True,
                    key="execute_batch_delete"
                ):
                    if confirm_delete_batch:
                        try:
                            # Get product names for the message
                            product_names = []
                            for idx in st.session_state.batch_delete_selected:
                                if idx < len(df):
                                    product_names.append(df.iloc[idx].get("name", "Unknown"))
                            
                            # Delete selected products (keep only those not selected)
                            keep_indices = [i for i in df.index if i not in st.session_state.batch_delete_selected]
                            df_new = df.loc[keep_indices].copy()
                            df_new = df_new.reset_index(drop=True)
                            
                            # Verify the deletion
                            deleted_count = len(df) - len(df_new)
                            
                            if deleted_count == len(st.session_state.batch_delete_selected):
                                # Save the updated DataFrame
                                if save_products(df_new):
                                    # Clear cache to force reload
                                    st.cache_data.clear()
                                    
                                    # Clear selection
                                    st.session_state.batch_delete_selected = []
                                    
                                    # Show success message
                                    st.success(f"Successfully deleted {deleted_count} products: {', '.join(product_names[:5])}{'...' if len(product_names) > 5 else ''}")
                                    st.balloons()
                                    
                                    # Force reload
                                    st.rerun()
                                else:
                                    st.error("Failed to save changes. Please check the database connection.")
                            else:
                                st.error(f"Failed to delete products. Expected {len(st.session_state.batch_delete_selected)} but deleted {deleted_count}.")
                        except Exception as e:
                            st.error(f"Error deleting products: {str(e)}")
                            st.code(traceback.format_exc())
                    else:
                        st.error("Please confirm deletion by checking the box above.")
        else:
            st.info("Select products above to delete them in bulk")
    else:
        st.info("No products in inventory to delete.")
    
    st.markdown("---")
    
    # ==============================
    # BATCH UPDATE PRODUCTS
    # ==============================
    st.markdown("## Batch Update Products")
    st.caption("Select multiple products, edit their details manually, then save all at once")
    
    if not df.empty:
        # Initialize session state for batch editing
        if "batch_edit_data" not in st.session_state:
            st.session_state.batch_edit_data = {}
        if "batch_selected" not in st.session_state:
            st.session_state.batch_selected = []
        
        # Display products with checkboxes
        st.markdown("### Select Products to Edit")
        
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            select_all = st.checkbox("Select All", key="select_all_batch_manual")
        
        # Create a copy for display
        display_df = df.copy()
        
        # Reset selection if select all
        if select_all:
            st.session_state.batch_selected = df.index.tolist()
        
        # Show products with checkboxes
        cols_per_row = 2
        product_list = display_df.to_dict('records')
        
        for i, product in enumerate(product_list):
            col_idx = i % cols_per_row
            if col_idx == 0:
                cols = st.columns(cols_per_row)
            
            barcode = str(product.get("barcode", ""))
            name = str(product.get("name", ""))
            stock = float(product.get("stock", 0))
            price = float(product.get("price", 0))
            idx = i
            
            with cols[col_idx]:
                is_selected = idx in st.session_state.batch_selected
                selected = st.checkbox(
                    f"{name}\n(Stock: {stock:.2f} | Price: ${price:.2f})", 
                    key=f"batch_edit_select_{barcode}_{i}",
                    value=is_selected
                )
                
                if selected and idx not in st.session_state.batch_selected:
                    st.session_state.batch_selected.append(idx)
                    # Initialize edit data for this product
                    if idx not in st.session_state.batch_edit_data:
                        st.session_state.batch_edit_data[idx] = {
                            "name": name,
                            "category": product.get("category", ""),
                            "price": price,
                            "cost": float(product.get("cost", 0)),
                            "stock": stock,
                            "reorder_level": float(product.get("reorder_level", 0))
                        }
                elif not selected and idx in st.session_state.batch_selected:
                    st.session_state.batch_selected.remove(idx)
                    if idx in st.session_state.batch_edit_data:
                        del st.session_state.batch_edit_data[idx]
        
        # Show selected products for editing
        if st.session_state.batch_selected:
            st.markdown("---")
            st.markdown(f"### Editing {len(st.session_state.batch_selected)} Product(s)")
            st.info("Edit the fields below for each selected product. Changes will be saved together when you click 'Save All Changes'.")
            
            # Create editable fields for each selected product
            with st.form("batch_edit_form", clear_on_submit=False):
                # Store updates in a temporary dict
                updates = {}
                
                for idx in st.session_state.batch_selected:
                    if idx < len(df):
                        product = df.iloc[idx]
                        barcode = str(product.get("barcode", ""))
                        current_name = str(product.get("name", ""))
                        
                        # Get existing edit data or use current values
                        edit_data = st.session_state.batch_edit_data.get(idx, {})
                        
                        st.markdown(f"**Product {idx+1}: {current_name}**")
                        
                        col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
                        
                        with col1:
                            new_name = st.text_input(
                                "Name",
                                value=edit_data.get("name", current_name),
                                key=f"batch_edit_name_{idx}",
                                label_visibility="collapsed"
                            )
                            st.caption("Product Name")
                        
                        with col2:
                            new_category = st.text_input(
                                "Category",
                                value=edit_data.get("category", product.get("category", "")),
                                key=f"batch_edit_category_{idx}",
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
                                key=f"batch_edit_price_{idx}",
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
                                key=f"batch_edit_cost_{idx}",
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
                                key=f"batch_edit_stock_{idx}",
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
                                key=f"batch_edit_reorder_{idx}",
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
                            if save_products(df):
                                st.success(f"Successfully updated {len(st.session_state.batch_selected)} products!")
                                st.balloons()
                                # Clear selections
                                st.session_state.batch_selected = []
                                st.session_state.batch_edit_data = {}
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("Failed to save changes. Please try again.")
                                
                        except Exception as e:
                            st.error(f"Error saving products: {str(e)}")
            
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
    # SINGLE PRODUCT UPDATE (Legacy)
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
                        
                        if save_products(df):
                            st.success(f"Product '{update_name}' updated successfully!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Failed to save product changes.")
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
                            if save_products(empty_df):
                                st.success(f"Successfully deleted ALL {product_count} products!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("Failed to delete products.")
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