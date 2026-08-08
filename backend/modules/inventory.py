import pandas as pd
import streamlit as st
from backend.core.db_adapter import load_products, save_products
from backend.core.auth import check_login
import traceback
import os
from pathlib import Path


# ==============================
# INVENTORY PAGE - WITH DEBUG DELETE
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
    # DELETE PRODUCT - DIRECT DELETE WITH DEBUG
    # ==============================
    st.markdown("## Delete Product")
    st.caption("Select a product and delete it directly")
    
    if not df.empty:
        # Create a list of products with barcodes
        product_options = []
        product_map = {}
        
        for idx, row in df.iterrows():
            name = str(row.get("name", ""))
            barcode = str(row.get("barcode", ""))
            display_text = f"{name} (Barcode: {barcode})"
            product_options.append(display_text)
            product_map[display_text] = idx
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            selected_product = st.selectbox(
                "Select Product to Delete", 
                product_options,
                key="delete_product_select"
            )
        
        if selected_product:
            product_idx = product_map[selected_product]
            product_data = df.iloc[product_idx]
            
            # Show product details
            with st.container(border=True):
                st.write(f"**Product:** {product_data.get('name', '')}")
                st.write(f"**Barcode:** {product_data.get('barcode', '')}")
                st.write(f"**Stock:** {product_data.get('stock', 0)}")
                st.write(f"**Price:** ${product_data.get('price', 0):.2f}")
            
            with col2:
                confirm_delete = st.checkbox(
                    f"Confirm delete",
                    key="confirm_direct_delete"
                )
            
            if st.button("Delete Selected Product", type="secondary", use_container_width=True, key="direct_delete_btn"):
                if confirm_delete:
                    try:
                        product_name = product_data.get("name", "Unknown")
                        product_barcode = product_data.get("barcode", "")
                        
                        st.write(f"Attempting to delete: {product_name} (Barcode: {product_barcode})")
                        
                        # Method 1: Drop by index
                        df_new = df.drop(product_idx)
                        df_new = df_new.reset_index(drop=True)
                        
                        st.write(f"New DataFrame shape after drop: {df_new.shape}")
                        
                        # Save the updated DataFrame
                        if save_products(df_new):
                            st.success(f"Successfully deleted '{product_name}'!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Failed to save changes. save_products returned False.")
                            
                            # Try direct file deletion as fallback
                            try:
                                st.write("Attempting direct file operation...")
                                from backend.core.db_adapter import DATA_DIR, PRODUCTS_FILE
                                
                                if PRODUCTS_FILE.exists():
                                    # Read current file
                                    current_df = pd.read_csv(PRODUCTS_FILE)
                                    # Remove the product by barcode
                                    current_df = current_df[current_df["barcode"].astype(str) != str(product_barcode)]
                                    # Save
                                    current_df.to_csv(PRODUCTS_FILE, index=False)
                                    st.success(f"Successfully deleted '{product_name}' via direct file operation!")
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error("Products file not found for direct operation.")
                            except Exception as direct_e:
                                st.error(f"Direct file operation failed: {str(direct_e)}")
                                
                    except Exception as e:
                        st.error(f"Error deleting product: {str(e)}")
                        st.code(traceback.format_exc())
                else:
                    st.error("Please confirm deletion by checking the box above.")
    else:
        st.info("No products in inventory to delete.")
    
    st.markdown("---")
    
    # ==============================
    # BATCH DELETE PRODUCTS - SIMPLIFIED
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
            select_all_delete = st.checkbox("Select All", key="select_all_batch_delete_simple")
        
        # Reset selection if select all
        if select_all_delete:
            st.session_state.batch_delete_selected = df.index.tolist()
        
        # Show products with checkboxes - simple list
        for i, row in df.iterrows():
            name = str(row.get("name", ""))
            barcode = str(row.get("barcode", ""))
            stock = float(row.get("stock", 0))
            price = float(row.get("price", 0))
            
            is_selected = i in st.session_state.batch_delete_selected
            selected = st.checkbox(
                f"{name} (Barcode: {barcode}) - Stock: {stock:.2f} - Price: ${price:.2f}", 
                key=f"batch_delete_simple_{i}",
                value=is_selected
            )
            
            if selected and i not in st.session_state.batch_delete_selected:
                st.session_state.batch_delete_selected.append(i)
            elif not selected and i in st.session_state.batch_delete_selected:
                st.session_state.batch_delete_selected.remove(i)
        
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
                        hide_index=True
                    )
            
            # Confirmation and delete button
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                confirm_delete_batch = st.checkbox(
                    f"I confirm deleting {len(st.session_state.batch_delete_selected)} products", 
                    key="confirm_batch_delete_simple"
                )
            
            with col2:
                if st.button("Clear Selection", use_container_width=True, key="clear_batch_delete_simple"):
                    st.session_state.batch_delete_selected = []
                    st.rerun()
            
            with col3:
                if st.button(
                    f"Delete {len(st.session_state.batch_delete_selected)} Products", 
                    type="secondary", 
                    use_container_width=True,
                    key="execute_batch_delete_simple"
                ):
                    if confirm_delete_batch:
                        try:
                            # Get product names for the message
                            product_names = []
                            for idx in st.session_state.batch_delete_selected:
                                if idx < len(df):
                                    product_names.append(df.iloc[idx].get("name", "Unknown"))
                            
                            # Create new DataFrame without selected products
                            keep_indices = [i for i in df.index if i not in st.session_state.batch_delete_selected]
                            df_new = df.loc[keep_indices].copy()
                            df_new = df_new.reset_index(drop=True)
                            
                            # Save
                            if save_products(df_new):
                                st.success(f"Successfully deleted {len(product_names)} products: {', '.join(product_names[:5])}{'...' if len(product_names) > 5 else ''}")
                                st.balloons()
                                st.session_state.batch_delete_selected = []
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("Failed to delete products. Please try again.")
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