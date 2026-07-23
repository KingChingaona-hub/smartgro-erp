"""
Purchases Management Module
Handles purchase orders, receiving stock, and supplier management
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from backend.core.db_adapter import (
    load_products,
    load_purchases,
    save_purchases,
    save_products
)


# ==============================
# GENERATE PO NUMBER
# ==============================
def generate_po_number():
    """Generate unique purchase order number"""
    return f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"


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
# CREATE PURCHASE ORDER
# ==============================
def create_purchase_order(supplier, items, expected_date):
    """Create a purchase order before receiving stock"""
    
    if not supplier or not supplier.strip():
        return None, None, "Supplier name is required"
    
    if not items or len(items) == 0:
        return None, None, "No items in purchase order"
    
    po_number = generate_po_number()
    
    po_data = []
    
    # Loop through ALL items in the cart
    for item in items:
        # Skip items without name
        if not item.get("name"):
            continue
        
        cost = float(item.get("cost", 0))
        quantity = float(item.get("quantity", 1))  # Allow decimal quantities
        
        # Get category - preserve exactly what the user entered
        category = str(item.get("category", "")).strip()
        
        # Only set to "New Purchase" if the user didn't provide any category
        if not category or category == "nan" or category == "None" or category == "":
            category = "New Purchase"
        
        # Append each item as a separate row
        po_data.append({
            "po_number": po_number,
            "date_ordered": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "supplier": supplier.strip(),
            "product_name": str(item.get("name", "Unknown")),
            "barcode": str(item.get("barcode", "")),
            "quantity_ordered": quantity,
            "cost_price": cost,
            "total_cost": quantity * cost,
            "expected_date": str(expected_date),
            "date_received": "",
            "quantity_received": 0,
            "status": "PENDING",
            "payment_status": "UNPAID",
            "invoice_no": "",
            "category": category
        })
    
    if not po_data:
        return None, None, "No valid items to add to purchase order"
    
    po_df = pd.DataFrame(po_data)
    return po_number, po_df, None


# ==============================
# DELETE PURCHASE ORDER
# ==============================
def delete_purchase_order(po_number):
    """Delete a purchase order and all its items"""
    try:
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            return False, "No purchase orders found"
        
        # Check if PO exists
        if purchases_df[purchases_df["po_number"] == po_number].empty:
            return False, f"Purchase Order {po_number} not found"
        
        # Count items before deletion
        item_count = len(purchases_df[purchases_df["po_number"] == po_number])
        
        # Delete all items with this PO number
        purchases_df = purchases_df[purchases_df["po_number"] != po_number]
        
        # Save changes
        save_success = save_purchases(purchases_df)
        
        if save_success:
            return True, f"Purchase Order {po_number} deleted successfully. Removed {item_count} item(s)."
        else:
            return False, "Failed to save changes to database"
            
    except Exception as e:
        return False, f"Error deleting PO: {str(e)}"


# ==============================
# DELETE ALL PURCHASE ORDERS
# ==============================
def delete_all_purchase_orders():
    """Delete ALL purchase orders"""
    try:
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            return False, "No purchase orders found to delete"
        
        # Count total items
        total_items = len(purchases_df)
        unique_pos = purchases_df["po_number"].nunique()
        
        # Clear all data
        purchases_df = purchases_df.iloc[0:0]
        
        # Save changes
        save_success = save_purchases(purchases_df)
        
        if save_success:
            return True, f"All {unique_pos} purchase orders ({total_items} items) deleted successfully."
        else:
            return False, "Failed to save changes to database"
            
    except Exception as e:
        return False, f"Error deleting all POs: {str(e)}"


# ==============================
# RECEIVE PURCHASE ORDER
# ==============================
def receive_purchase_order(po_number, received_items, invoice_no):
    """Receive items against a purchase order and AUTO-UPDATE stock"""
    
    # Load current data
    purchases_df = load_purchases()
    products_df = load_products()
    
    # Ensure required columns exist
    if "status" not in purchases_df.columns:
        purchases_df["status"] = "PENDING"
    if "quantity_received" not in purchases_df.columns:
        purchases_df["quantity_received"] = 0
    if "date_received" not in purchases_df.columns:
        purchases_df["date_received"] = ""
    
    updated_products = []
    new_products = []
    
    # Get all rows for this PO
    po_mask = purchases_df["po_number"] == po_number
    po_items_indices = purchases_df[po_mask].index.tolist()
    
    # Create a mapping of barcode/name to index for this PO
    po_items_mapping = {}
    for idx in po_items_indices:
        row = purchases_df.loc[idx]
        barcode = str(row.get("barcode", "")).strip()
        product_name = str(row.get("product_name", "")).strip()
        
        # Use barcode as primary key, fallback to product name
        key = barcode if barcode else product_name
        if key:
            po_items_mapping[key] = idx
    
    # Process each received item
    for item in received_items:
        # Skip items with 0 received quantity
        if item["received_qty"] <= 0:
            continue
        
        barcode = str(item.get("barcode", "")).strip()
        product_name = str(item.get("name", "")).strip()
        received_qty = float(item["received_qty"])  # Allow decimal
        cost_price = float(item["cost"])  # Convert to float
        category = str(item.get("category", "New Purchase")).strip()
        if not category or category == "nan" or category == "None":
            category = "New Purchase"
        
        # Find the matching PO item
        matching_idx = None
        
        # First try to match by barcode
        if barcode:
            for key, idx in po_items_mapping.items():
                if key == barcode:
                    matching_idx = idx
                    break
        
        # If not found by barcode, try by product name
        if matching_idx is None and product_name:
            for key, idx in po_items_mapping.items():
                if key.lower() == product_name.lower():
                    matching_idx = idx
                    break
        
        # If still not found, try a more flexible match
        if matching_idx is None:
            for key, idx in po_items_mapping.items():
                if product_name and key and (product_name.lower() in key.lower() or key.lower() in product_name.lower()):
                    matching_idx = idx
                    break
        
        if matching_idx is not None:
            # Update purchase record
            purchases_df.loc[matching_idx, "quantity_received"] = received_qty
            purchases_df.loc[matching_idx, "date_received"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            purchases_df.loc[matching_idx, "status"] = "RECEIVED"
            purchases_df.loc[matching_idx, "invoice_no"] = invoice_no
            
            # Update product stock in inventory
            product_idx = products_df[products_df["barcode"] == barcode].index
            
            if len(product_idx) > 0:
                # Product exists - UPDATE existing stock
                current_stock = float(products_df.loc[product_idx[0], "stock"]) if "stock" in products_df.columns else 0
                new_stock = current_stock + received_qty
                products_df.loc[product_idx[0], "stock"] = new_stock
                products_df.loc[product_idx[0], "cost"] = cost_price
                if category and category != "New Purchase":
                    products_df.loc[product_idx[0], "category"] = category
                products_df.loc[product_idx[0], "price"] = cost_price * 1.3
                
                updated_products.append({
                    "name": product_name,
                    "old_stock": current_stock,
                    "added": received_qty,
                    "new_stock": new_stock,
                    "cost": cost_price,
                    "category": category
                })
            else:
                # Product doesn't exist - CREATE new product in inventory
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
                    "category": category if category and category != "New Purchase" else "New Purchase"
                })
        else:
            # Item not found in PO - add as new item to the PO
            st.warning(f"Item '{product_name}' not found in purchase order. Adding as new item.")
            
            # Add new row to purchases_df
            new_row = {
                "po_number": po_number,
                "date_ordered": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "supplier": purchases_df[purchases_df["po_number"] == po_number].iloc[0].get("supplier", "Unknown"),
                "product_name": product_name,
                "barcode": barcode,
                "quantity_ordered": received_qty,
                "cost_price": cost_price,
                "total_cost": received_qty * cost_price,
                "expected_date": datetime.now().strftime("%Y-%m-%d"),
                "date_received": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "quantity_received": received_qty,
                "status": "RECEIVED",
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
                    "category": category if category and category != "New Purchase" else "New Purchase"
                })
    
    # Check if all items in PO have been received
    po_items = purchases_df[purchases_df["po_number"] == po_number]
    all_received = True
    for idx in po_items.index:
        qty_ordered = float(po_items.loc[idx].get("quantity_ordered", 0))
        qty_received = float(po_items.loc[idx].get("quantity_received", 0))
        if qty_received < qty_ordered:
            all_received = False
            break
    
    # Update PO status
    if all_received:
        purchases_df.loc[purchases_df["po_number"] == po_number, "status"] = "COMPLETED"
    else:
        purchases_df.loc[purchases_df["po_number"] == po_number, "status"] = "PARTIALLY_RECEIVED"
    
    # Save all changes
    try:
        save_products(products_df)
        save_purchases(purchases_df)
        return True, updated_products, new_products
    except Exception as e:
        print(f"Error saving: {e}")
        return False, [], []


# ==============================
# SUPPLIER PERFORMANCE
# ==============================
def get_supplier_performance():
    """Calculate supplier performance metrics from purchase history"""
    
    purchases_df = load_purchases()
    
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
# GET PURCHASE ORDER DETAILS
# ==============================
def get_po_details(po_number):
    """Get complete details for a specific purchase order"""
    purchases_df = load_purchases()
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
        "status": po_items.iloc[0].get("status", "PENDING")
    }


# ==============================
# PURCHASES PAGE
# ==============================
def purchases_page():
    """Enhanced Purchases Management Page with Auto-Stock Update"""
    
    st.title("Purchases and Suppliers Management")
    st.caption("Create purchase orders, receive stock, and auto-update inventory")
    
    products_df = load_products()
    
    # Initialize session state
    if "po_cart" not in st.session_state:
        st.session_state.po_cart = []
    if "po_created" not in st.session_state:
        st.session_state.po_created = False
    if "last_po_number" not in st.session_state:
        st.session_state.last_po_number = None
    if "stock_updated" not in st.session_state:
        st.session_state.stock_updated = False
    if "last_received_po" not in st.session_state:
        st.session_state.last_received_po = None
    if "po_deleted" not in st.session_state:
        st.session_state.po_deleted = False
    if "deleted_po_number" not in st.session_state:
        st.session_state.deleted_po_number = None
    if "show_preview" not in st.session_state:
        st.session_state.show_preview = False
    if "preview_data" not in st.session_state:
        st.session_state.preview_data = None
    
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
        st.success(f"Purchase Order {st.session_state.deleted_po_number} deleted successfully!")
        st.session_state.po_deleted = False
        st.session_state.deleted_po_number = None
    
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
        st.markdown("## Create Purchase Order")
        st.caption("Create a purchase order before receiving stock from suppliers")
        
        if products_df.empty:
            st.warning("No products in inventory. You can still add manual items below.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            supplier_name = st.text_input("Supplier Name *", key="po_supplier", 
                                         placeholder="e.g., National Foods, Olivine, Delta")
        
        with col2:
            expected_date = st.date_input("Expected Delivery Date *", 
                                         min_value=datetime.now().date(), 
                                         value=datetime.now().date() + timedelta(days=7),
                                         key="po_expected_date")
        
        st.markdown("### Add Products to Order")
        
        if not products_df.empty:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                search = st.text_input("Search Product", key="po_search", 
                                      placeholder="Type product name or barcode")
                
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
                    
                    selected_display = st.selectbox("Select Product", product_display, key="po_product_select")
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
                    # Check if product supports decimal quantities
                    is_decimal = supports_decimal(selected_product["name"], selected_product.get("category", ""))
                    
                    # Quantity input with decimal support
                    if is_decimal:
                        po_qty = st.number_input(
                            "Quantity", 
                            min_value=0.0, 
                            value=1.0, 
                            step=0.5, 
                            format="%.2f", 
                            key="po_qty"
                        )
                        st.caption("🔢 Decimal quantities supported (e.g., 0.5, 1.5)")
                    else:
                        po_qty = st.number_input(
                            "Quantity", 
                            min_value=1, 
                            value=1, 
                            step=1, 
                            key="po_qty"
                        )
                    
                    st.caption(f"Current stock: {selected_product['stock']:.2f}")
                    st.caption(f"Cost: ${selected_product['cost']:.2f}")
                else:
                    po_qty = 1
            
            with col3:
                if selected_product is not None:
                    add_button = st.button("Add to Order", key="add_to_po", use_container_width=True)
                    if add_button:
                        existing = False
                        barcode_str = str(selected_product["barcode"])
                        for item in st.session_state.po_cart:
                            if str(item["barcode"]) == barcode_str:
                                # Handle decimal quantities
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
                            
                            # Store quantity as float to support decimals
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
                clear_button = st.button("Clear Cart", use_container_width=True)
                if clear_button:
                    st.session_state.po_cart = []
                    st.success("Cart cleared!")
        
        # ==============================
        # MANUAL ITEM ENTRY - WITH DECIMAL SUPPORT
        # ==============================
        st.markdown("### Manual Item Entry")
        st.caption("Add items not in inventory (new products, services, fees)")
        
        with st.form(key="add_manual_form", clear_on_submit=True):
            col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1, 1, 1])
            
            with col1:
                manual_item_name = st.text_input("Item Name *", key="manual_item_name", placeholder="e.g., New Product X, Delivery Fee")
            
            with col2:
                manual_item_category = st.text_input("Category", key="manual_item_category", placeholder="e.g., Drinks, Rice, Sugar")
            
            with col3:
                manual_item_cost = st.number_input("Cost Price ($)", min_value=0.01, value=0.01, step=5.0, key="manual_item_cost")
            
            with col4:
                # Check if manual item name suggests decimal support
                is_decimal_manual = supports_decimal(manual_item_name, manual_item_category)
                
                if is_decimal_manual:
                    manual_item_qty = st.number_input(
                        "Quantity", 
                        min_value=0.0, 
                        value=1.0, 
                        step=0.5, 
                        format="%.2f", 
                        key="manual_item_qty"
                    )
                    st.caption("🔢 Decimal quantities supported for this product")
                else:
                    manual_item_qty = st.number_input(
                        "Quantity", 
                        min_value=1, 
                        value=1, 
                        step=1, 
                        key="manual_item_qty"
                    )
            
            with col5:
                add_manual_button = st.form_submit_button("Add Item", use_container_width=True)
                
                if add_manual_button:
                    if manual_item_name and manual_item_name.strip():
                        # Get category exactly as typed
                        category_input = manual_item_category.strip()
                        
                        if category_input:
                            category = category_input
                        else:
                            category = "New Purchase"
                        
                        existing = False
                        for item in st.session_state.po_cart:
                            if str(item["name"]).lower() == manual_item_name.lower() and float(item["cost"]) == float(manual_item_cost):
                                # Add to existing quantity
                                if isinstance(manual_item_qty, float):
                                    item["quantity"] = float(item["quantity"]) + manual_item_qty
                                else:
                                    item["quantity"] = int(item["quantity"]) + int(manual_item_qty)
                                item["total"] = item["quantity"] * item["cost"]
                                if category != "New Purchase":
                                    item["category"] = category
                                existing = True
                                break
                        
                        if not existing:
                            unique_barcode = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                            # Store quantity as float to support decimals
                            if isinstance(manual_item_qty, float):
                                qty_val = float(manual_item_qty)
                            else:
                                qty_val = int(manual_item_qty)
                            
                            st.session_state.po_cart.append({
                                "barcode": unique_barcode,
                                "name": str(manual_item_name).strip(),
                                "quantity": qty_val,
                                "cost": float(manual_item_cost),
                                "total": float(manual_item_cost) * qty_val,
                                "category": category
                            })
                            
                            if isinstance(manual_item_qty, float) and manual_item_qty % 1 != 0:
                                st.success(f"Added {manual_item_qty:.2f} x {manual_item_name} (${manual_item_cost:.2f} each) - Category: {category}")
                            else:
                                st.success(f"Added {int(manual_item_qty)} x {manual_item_name} (${manual_item_cost:.2f} each) - Category: {category}")
                        else:
                            st.success(f"Updated {manual_item_name} quantity")
                    else:
                        st.error("Please enter an item name")
        
        # Display PO Cart
        st.markdown("---")
        st.markdown("### Purchase Order Cart")
        
        if st.session_state.po_cart:
            po_cart_df = pd.DataFrame(st.session_state.po_cart)
            
            display_cols = ["name", "quantity", "cost", "total"]
            if "category" in po_cart_df.columns:
                display_cols.insert(1, "category")
            
            st.dataframe(
                po_cart_df[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "quantity": st.column_config.NumberColumn("Quantity", format="%.2f"),
                    "cost": st.column_config.NumberColumn("Unit Cost ($)", format="$%.2f"),
                    "total": st.column_config.NumberColumn("Total ($)", format="$%.2f")
                }
            )
            
            po_total = po_cart_df["total"].sum()
            st.info(f"**Total Order Value: ${po_total:,.2f}**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                clear_all_button = st.button("Clear All Items", key="clear_all_items_btn", use_container_width=True)
                if clear_all_button:
                    st.session_state.po_cart = []
                    st.success("Cart cleared!")
            
            with col2:
                preview_button = st.button("Preview Purchase Order", key="preview_po_btn", use_container_width=True)
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
        
        # Show Preview
        if st.session_state.show_preview and st.session_state.preview_data:
            preview = st.session_state.preview_data
            
            st.markdown("---")
            st.markdown("### Purchase Order Preview")
            st.markdown(f"**Supplier:** {preview['supplier']}")
            st.markdown(f"**Expected Date:** {preview['expected_date']}")
            
            display_cols = ["name", "quantity", "cost", "total"]
            if "category" in preview['po_cart_df'].columns:
                display_cols.insert(1, "category")
            
            st.dataframe(
                preview['po_cart_df'][display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "quantity": st.column_config.NumberColumn("Quantity", format="%.2f"),
                    "cost": st.column_config.NumberColumn("Unit Cost ($)", format="$%.2f"),
                    "total": st.column_config.NumberColumn("Total ($)", format="$%.2f")
                }
            )
            
            st.info(f"**Total Order Value: ${preview['po_total']:,.2f}**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Edit Order", use_container_width=True):
                    st.session_state.show_preview = False
                    st.session_state.preview_data = None
                    #st.rerun()
            
            with col2:
                if st.button("Confirm and Create PO", type="primary", use_container_width=True):
                    po_number, po_df, error = create_purchase_order(
                        supplier=preview['supplier'],
                        items=preview['items'],
                        expected_date=preview['expected_date']
                    )
                    
                    if error:
                        st.error(error)
                    else:
                        existing_df = load_purchases()
                        
                        for col in po_df.columns:
                            if col not in existing_df.columns:
                                existing_df[col] = ""
                        
                        updated_df = pd.concat([existing_df, po_df], ignore_index=True)
                        save_success = save_purchases(updated_df)
                        
                        if save_success:
                            st.session_state.po_cart = []
                            st.session_state.po_created = True
                            st.session_state.last_po_number = po_number
                            st.session_state.show_preview = False
                            st.session_state.preview_data = None
                            
                            st.success(f"Purchase Order {po_number} created successfully with {len(po_df)} items!")
                            
                            po_text = f"""
{'='*50}
AZIEL INVESTMENTS - PURCHASE ORDER
{'='*50}

PO Number: {po_number}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
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
                            
                            #st.rerun()
                        else:
                            st.error("Failed to save purchase order. Please try again.")
        
        # Quick create option
        if not st.session_state.show_preview and st.session_state.po_cart:
            col1, col2 = st.columns(2)
            
            with col1:
                st.empty()
            
            with col2:
                quick_create = st.button("Create PO (No Preview)", key="quick_create_po", use_container_width=True)
                if quick_create:
                    if not supplier_name or not supplier_name.strip():
                        st.error("Please enter a supplier name")
                    elif not st.session_state.po_cart:
                        st.error("Cart is empty. Add products to create a purchase order.")
                    else:
                        cart_items = st.session_state.po_cart.copy()
                        po_cart_df = pd.DataFrame(cart_items)
                        po_total = po_cart_df["total"].sum()
                        
                        po_number, po_df, error = create_purchase_order(
                            supplier=supplier_name,
                            items=cart_items,
                            expected_date=expected_date
                        )
                        
                        if error:
                            st.error(error)
                        else:
                            existing_df = load_purchases()
                            
                            for col in po_df.columns:
                                if col not in existing_df.columns:
                                    existing_df[col] = ""
                            
                            updated_df = pd.concat([existing_df, po_df], ignore_index=True)
                            save_success = save_purchases(updated_df)
                            
                            if save_success:
                                st.session_state.po_cart = []
                                st.session_state.po_created = True
                                st.session_state.last_po_number = po_number
                                
                                st.success(f"Purchase Order {po_number} created successfully with {len(po_df)} items!")
                                st.info(f"""
                                Purchase Order Summary:
                                - PO Number: {po_number}
                                - Supplier: {supplier_name}
                                - Items: {len(po_df)}
                                - Total Value: ${po_total:,.2f}
                                - Expected Date: {expected_date}
                                """)
                                #st.rerun()
                            else:
                                st.error("Failed to save purchase order.")
        elif st.session_state.show_preview:
            st.info("Review the preview above and click 'Confirm and Create PO' to save.")
    
    # ==============================
    # TAB 2: RECEIVE STOCK
    # ==============================
    with tab2:
        st.markdown("## Receive Stock - Auto Update Inventory")
        st.caption("Confirm receipt of stock. Inventory will be automatically updated.")
        
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            st.info("No purchase orders found. Create a PO first in the Create Purchase Order tab.")
        else:
            if "status" not in purchases_df.columns:
                purchases_df["status"] = "PENDING"
            
            pending_pos = purchases_df[purchases_df["status"] == "PENDING"]["po_number"].unique().tolist()
            partial_pos = purchases_df[purchases_df["status"] == "PARTIALLY_RECEIVED"]["po_number"].unique().tolist()
            all_receivable = list(set(pending_pos + partial_pos))
            
            if not all_receivable:
                st.info("No pending or partially received purchase orders. All orders have been completed.")
            else:
                st.info(f"Found {len(all_receivable)} orders ready for receiving")
                
                selected_po = st.selectbox("Select Purchase Order to Receive", all_receivable, key="receive_po")
                
                if selected_po:
                    po_details = get_po_details(selected_po)
                    
                    if po_details:
                        status_label = "PENDING" if po_details['status'] == "PENDING" else "PARTIALLY RECEIVED"
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
                        
                        # Delete buttons
                        if po_details['status'] == "PENDING":
                            st.markdown("---")
                            st.markdown("### Delete Purchase Order")
                            st.warning("This will permanently delete this purchase order and all its items.")
                            
                            col1, col2, col3 = st.columns([2, 1, 1])
                            with col1:
                                confirm_delete = st.checkbox(f"Confirm delete PO {selected_po}")
                            with col2:
                                delete_button = st.button("Delete PO", type="secondary", use_container_width=True)
                                if delete_button and confirm_delete:
                                    success, message = delete_purchase_order(selected_po)
                                    if success:
                                        st.session_state.po_deleted = True
                                        st.session_state.deleted_po_number = selected_po
                                        st.success(message)
                                        #st.rerun()
                                    else:
                                        st.error(message)
                                elif delete_button and not confirm_delete:
                                    st.error("Please confirm deletion by checking the box")
                            
                            # Delete All button
                            with col3:
                                delete_all_button = st.button("Delete All POs", type="secondary", use_container_width=True)
                                if delete_all_button:
                                    confirm_all = st.checkbox("Confirm delete ALL purchase orders")
                                    if confirm_all:
                                        success, message = delete_all_purchase_orders()
                                        if success:
                                            st.session_state.po_deleted = True
                                            st.session_state.deleted_po_number = "ALL"
                                            st.success(message)
                                            #st.rerun()
                                        else:
                                            st.error(message)
                                    else:
                                        st.error("Please confirm deletion by checking the box")
                        
                        st.markdown("---")
                        st.markdown("### Receiving Details")
                        st.info("When you receive items, stock will be automatically added to inventory.")
                        
                        invoice_no = st.text_input("Supplier Invoice Number *", key="invoice_no")
                        
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
                                # Allow decimal received quantity
                                received_qty = st.number_input(
                                    "Qty Received",
                                    min_value=0.0,
                                    max_value=float(remaining),
                                    value=float(remaining),
                                    step=0.5,
                                    format="%.2f",
                                    key=f"rec_qty_{barcode_val}_{idx}",
                                    label_visibility="collapsed"
                                )
                            
                            with col3:
                                cost_price = float(item.get("cost_price", 0))  # Convert to float
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
                            confirm_button = st.button("Confirm Receipt and Update Stock", type="primary", use_container_width=True)
                            if confirm_button:
                                if not invoice_no:
                                    st.error("Please enter supplier invoice number")
                                else:
                                    success, updated_products, new_products = receive_purchase_order(
                                        selected_po, received_items, invoice_no
                                    )
                                    
                                    if success:
                                        st.session_state.stock_updated = True
                                        st.session_state.last_received_po = selected_po
                                        
                                        if updated_products:
                                            st.success(f"Stock updated for {len(updated_products)} existing products!")
                                            for p in updated_products[:5]:
                                                st.write(f"   - {p['name']}: {p['old_stock']:.2f} -> {p['new_stock']:.2f} (+{p['added']:.2f}) - Category: {p.get('category', 'New Purchase')}")
                                            if len(updated_products) > 5:
                                                st.write(f"   ... and {len(updated_products) - 5} more")
                                        
                                        if new_products:
                                            st.info(f"Created {len(new_products)} new products in inventory!")
                                            for p in new_products:
                                                st.write(f"   - {p['name']}: Added {p['stock']:.2f} units at ${p['cost']:.2f} - Category: {p.get('category', 'New Purchase')}")
                                        
                                        #st.rerun()
                        
                        with col2:
                            refresh_button = st.button("Refresh", use_container_width=True)
                            if refresh_button:
                                st.rerun()
    
    # ==============================
    # TAB 3: SUPPLIER PERFORMANCE
    # ==============================
    with tab3:
        st.markdown("## Supplier Performance Dashboard")
        
        supplier_perf = get_supplier_performance()
        
        if supplier_perf.empty:
            st.info("No purchase data available yet. Create purchase orders to see supplier performance.")
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
        st.markdown("## Purchase History")
        
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            st.info("No purchase records found.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                date_filter = st.selectbox("Filter by", ["All", "Last 30 Days", "Last 90 Days", "This Year"], key="purchase_filter")
            
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
            
            po_summary = purchases_df.groupby(["po_number", "supplier", "date_ordered", "status"]).agg({
                "total_cost": "sum",
                "quantity_ordered": "sum"
            }).reset_index()
            
            po_summary = po_summary.sort_values("date_ordered", ascending=False)
            
            st.dataframe(
                po_summary[["po_number", "supplier", "date_ordered", "total_cost", "quantity_ordered", "status"]],
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
                file_name=f"purchase_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    purchases_page()