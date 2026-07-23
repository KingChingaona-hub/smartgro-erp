import pandas as pd
import streamlit as st
from backend.core.db_adapter import load_products, save_products
from backend.core.auth import check_login


# ==============================
# INVENTORY PAGE - WITH BATCH EDITING
# ==============================
def inventory_page():
    
    # Load products fresh each time
    df = load_products()
    
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
        
        # Display with decimal formatting for stock
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
    # ADD PRODUCT - WITH DECIMAL SUPPORT
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
            
            st.caption("💡 Use decimals (e.g., 0.5, 1.5) for gas, bread, and weight-based products")
        
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
                        st.rerun()
                    else:
                        st.error("Failed to save product.")
            else:
                st.error("Barcode, Name, and Price are required.")
    
    st.markdown("---")
    
    # ==============================
    # BATCH UPDATE PRODUCTS - NEW FEATURE
    # ==============================
    st.markdown("## Batch Update Products")
    st.caption("Select multiple products and update their stock/price in bulk")
    
    if not df.empty:
        # Initialize batch cart in session state
        if "batch_cart" not in st.session_state:
            st.session_state.batch_cart = []
        
        # Display products with checkboxes
        st.markdown("### Select Products to Update")
        
        # Add select/deselect all
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            select_all = st.checkbox("Select All", key="select_all_batch")
        
        # Create a dataframe with checkboxes
        selected_products = []
        display_df = df.copy()
        
        # Add selection column
        if "selected" not in display_df.columns:
            display_df["selected"] = False
        
        if select_all:
            display_df["selected"] = True
        
        # Show products with checkboxes using columns
        st.write("**Select products to update:**")
        
        # Use columns for better display
        cols_per_row = 3
        product_list = display_df.to_dict('records')
        
        for i, product in enumerate(product_list):
            col_idx = i % cols_per_row
            if col_idx == 0:
                cols = st.columns(cols_per_row)
            
            barcode = str(product.get("barcode", ""))
            name = str(product.get("name", ""))
            stock = float(product.get("stock", 0))
            price = float(product.get("price", 0))
            
            with cols[col_idx]:
                # Checkbox with product info
                key = f"batch_select_{barcode}_{i}"
                selected = st.checkbox(f"{name}\n(Stock: {stock:.2f})", key=key, value=display_df.at[i, "selected"])
                display_df.at[i, "selected"] = selected
                
                if selected:
                    selected_products.append({
                        "index": i,
                        "barcode": barcode,
                        "name": name,
                        "stock": stock,
                        "price": price
                    })
        
        if selected_products:
            st.markdown("---")
            st.markdown(f"### {len(selected_products)} Product(s) Selected")
            
            # Show selected products in a table
            selected_df = pd.DataFrame(selected_products)
            st.dataframe(
                selected_df[["name", "stock", "price"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "stock": st.column_config.NumberColumn("Current Stock", format="%.2f"),
                    "price": st.column_config.NumberColumn("Current Price", format="$%.2f")
                }
            )
            
            # Batch update form
            with st.form("batch_update_form", clear_on_submit=False):
                st.markdown("### Update Selected Products")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Stock update options
                    stock_action = st.selectbox(
                        "Stock Action",
                        ["Set to Value", "Add", "Subtract", "Multiply"],
                        key="batch_stock_action"
                    )
                    
                    stock_value = st.number_input(
                        "Stock Value",
                        min_value=0.0,
                        value=1.0,
                        step=0.5,
                        format="%.2f",
                        key="batch_stock_value"
                    )
                    
                    st.caption("💡 For 'Set to Value', stock will become this number. For 'Add/Subtract', this number will be added/subtracted.")
                
                with col2:
                    # Price update options
                    price_action = st.selectbox(
                        "Price Action",
                        ["No Change", "Set to Value", "Add", "Subtract", "Percentage Increase", "Percentage Decrease"],
                        key="batch_price_action"
                    )
                    
                    price_value = st.number_input(
                        "Price Value",
                        min_value=0.0,
                        value=0.50,
                        step=0.10,
                        format="%.2f",
                        key="batch_price_value"
                    )
                    
                    if price_action in ["Percentage Increase", "Percentage Decrease"]:
                        st.caption("💡 Enter percentage (e.g., 10 for 10%)")
                    else:
                        st.caption("💡 Enter amount in dollars")
                
                # Preview updates
                st.markdown("### Preview Changes")
                
                # Calculate preview
                preview_data = []
                for prod in selected_products:
                    new_stock = prod["stock"]
                    new_price = prod["price"]
                    
                    # Calculate new stock
                    if stock_action == "Set to Value":
                        new_stock = stock_value
                    elif stock_action == "Add":
                        new_stock = prod["stock"] + stock_value
                    elif stock_action == "Subtract":
                        new_stock = max(0, prod["stock"] - stock_value)
                    elif stock_action == "Multiply":
                        new_stock = prod["stock"] * stock_value
                    
                    # Calculate new price
                    if price_action == "Set to Value":
                        new_price = price_value
                    elif price_action == "Add":
                        new_price = prod["price"] + price_value
                    elif price_action == "Subtract":
                        new_price = max(0, prod["price"] - price_value)
                    elif price_action == "Percentage Increase":
                        new_price = prod["price"] * (1 + price_value / 100)
                    elif price_action == "Percentage Decrease":
                        new_price = prod["price"] * (1 - price_value / 100)
                    
                    preview_data.append({
                        "Product": prod["name"],
                        "Old Stock": prod["stock"],
                        "New Stock": round(new_stock, 2),
                        "Old Price": prod["price"],
                        "New Price": round(new_price, 2)
                    })
                
                preview_df = pd.DataFrame(preview_data)
                st.dataframe(
                    preview_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Old Stock": st.column_config.NumberColumn("Old Stock", format="%.2f"),
                        "New Stock": st.column_config.NumberColumn("New Stock", format="%.2f"),
                        "Old Price": st.column_config.NumberColumn("Old Price", format="$%.2f"),
                        "New Price": st.column_config.NumberColumn("New Price", format="$%.2f")
                    }
                )
                
                # Submit button
                batch_save = st.form_submit_button(
                    f"💾 Save Changes to {len(selected_products)} Product(s)",
                    type="primary",
                    use_container_width=True
                )
                
                if batch_save:
                    try:
                        # Apply updates to DataFrame
                        for prod in selected_products:
                            idx = prod["index"]
                            
                            # Calculate new stock
                            if stock_action == "Set to Value":
                                new_stock = stock_value
                            elif stock_action == "Add":
                                new_stock = float(df.at[idx, "stock"]) + stock_value
                            elif stock_action == "Subtract":
                                new_stock = max(0, float(df.at[idx, "stock"]) - stock_value)
                            elif stock_action == "Multiply":
                                new_stock = float(df.at[idx, "stock"]) * stock_value
                            else:
                                new_stock = float(df.at[idx, "stock"])
                            
                            # Calculate new price
                            if price_action == "Set to Value":
                                new_price = price_value
                            elif price_action == "Add":
                                new_price = float(df.at[idx, "price"]) + price_value
                            elif price_action == "Subtract":
                                new_price = max(0, float(df.at[idx, "price"]) - price_value)
                            elif price_action == "Percentage Increase":
                                new_price = float(df.at[idx, "price"]) * (1 + price_value / 100)
                            elif price_action == "Percentage Decrease":
                                new_price = float(df.at[idx, "price"]) * (1 - price_value / 100)
                            else:
                                new_price = float(df.at[idx, "price"])
                            
                            # Update DataFrame
                            df.at[idx, "stock"] = round(float(new_stock), 2)
                            df.at[idx, "price"] = round(float(new_price), 2)
                        
                        # Save all changes at once - FAST
                        if save_products(df):
                            st.success(f"✅ Successfully updated {len(selected_products)} products!")
                            st.balloons()
                            # Reset selections
                            display_df["selected"] = False
                            st.session_state.batch_cart = []
                            st.rerun()
                        else:
                            st.error("Failed to save changes. Please try again.")
                            
                    except Exception as e:
                        st.error(f"Error updating products: {str(e)}")
            
            # Clear selection button
            if st.button("Clear Selection", use_container_width=True):
                display_df["selected"] = False
                st.session_state.batch_cart = []
                st.rerun()
    
    st.markdown("---")
    
    # ==============================
    # SINGLE PRODUCT UPDATE (Original)
    # ==============================
    st.markdown("## Single Product Update")
    st.caption("Update one product at a time")
    
    if not df.empty:
        product_names = df["name"].tolist()
        selected_product = st.selectbox("Select Product to Update", product_names, key="update_product_select")
        
        if selected_product:
            product_data = df[df["name"] == selected_product].iloc[0]
            product_index = df[df["name"] == selected_product].index[0]
            
            name_lower = str(product_data["name"]).lower()
            category_lower = str(product_data.get("category", "")).lower()
            is_decimal_product = any(keyword in name_lower or keyword in category_lower 
                                     for keyword in ["gas", "kg", "bread", "loaf", "flour", "sugar", 
                                                     "rice", "maize meal", "cooking oil", "milk", 
                                                     "liquid", "weight"])
            
            with st.form("update_product_form", clear_on_submit=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    update_barcode = st.text_input("Barcode", value=str(product_data["barcode"]), key="update_barcode")
                    update_name = st.text_input("Product Name", value=product_data["name"], key="update_name")
                    update_category = st.text_input("Category", value=product_data.get("category", ""), key="update_category")
                    update_price = st.number_input(
                        "Price ($)", 
                        value=float(product_data["price"]), 
                        min_value=0.0, 
                        step=0.5, 
                        format="%.2f",
                        key="update_price"
                    )
                
                with col2:
                    update_cost = st.number_input(
                        "Cost ($)", 
                        value=float(product_data.get("cost", 0)), 
                        min_value=0.0, 
                        step=0.5, 
                        format="%.2f",
                        key="update_cost"
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
                        key="update_stock"
                    )
                    
                    update_reorder = st.number_input(
                        "Reorder Level", 
                        min_value=stock_min, 
                        value=current_reorder, 
                        step=stock_step,
                        format=stock_format,
                        key="update_reorder"
                    )
                
                if is_decimal_product:
                    st.info("🔢 Decimal quantities supported for this product (e.g., 0.5, 1.5, 2.0)")
                
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
                            st.rerun()
                        else:
                            st.error("Failed to save product changes.")
                    except Exception as e:
                        st.error(f"Error updating product: {str(e)}")
            
            # Delete section
            st.markdown("### Delete Product")
            st.warning("This will permanently delete the selected product.")
            
            confirm_delete = st.checkbox(f"Confirm delete '{selected_product}'", key="confirm_delete")
            
            if st.button("Delete Product", type="secondary", use_container_width=True):
                if confirm_delete:
                    df = df[df["name"] != selected_product].reset_index(drop=True)
                    if save_products(df):
                        st.success(f"Product '{selected_product}' deleted successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to delete product.")
                else:
                    st.error("Please confirm deletion by checking the box above.")
    else:
        st.info("No products in inventory. Add your first product above.")
    
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