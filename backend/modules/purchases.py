"""
Purchases Management Module for SmartGro ERP
Handles purchase orders, stock receiving, and supplier management
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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_po_number():
    """Generate a unique purchase order number"""
    return f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def get_supplier_performance():
    """Calculate supplier performance metrics from purchase history"""
    purchases_df = load_purchases()
    
    if purchases_df.empty:
        return pd.DataFrame()
    
    # Ensure required columns exist
    if "quantity_received" not in purchases_df.columns:
        purchases_df["quantity_received"] = 0
    
    if "total_cost" not in purchases_df.columns:
        purchases_df["total_cost"] = purchases_df.get("quantity_ordered", 0) * purchases_df.get("cost_price", 0)
    
    # Group by supplier
    supplier_stats = purchases_df.groupby("supplier").agg({
        "po_number": "nunique",
        "total_cost": "sum",
        "quantity_ordered": "sum",
        "quantity_received": "sum"
    }).reset_index()
    
    supplier_stats.columns = ["Supplier", "Orders", "Total Spent", "Units Ordered", "Units Received"]
    
    # Calculate fulfillment rate
    supplier_stats["Fulfillment Rate"] = supplier_stats.apply(
        lambda x: (x["Units Received"] / x["Units Ordered"] * 100) if x["Units Ordered"] > 0 else 0, 
        axis=1
    )
    
    return supplier_stats.sort_values("Total Spent", ascending=False)


def get_po_details(po_number):
    """Get complete details for a specific purchase order"""
    purchases_df = load_purchases()
    po_items = purchases_df[purchases_df["po_number"] == po_number]
    
    if po_items.empty:
        return None
    
    return {
        "po_number": po_number,
        "supplier": po_items.iloc[0].get("supplier", "Unknown"),
        "date_ordered": str(po_items.iloc[0].get("date_ordered", "Unknown")),
        "expected_date": str(po_items.iloc[0].get("expected_date", "N/A")),
        "items": po_items.to_dict('records'),
        "total_value": float(po_items["total_cost"].sum()) if "total_cost" in po_items.columns else 0,
        "status": po_items.iloc[0].get("status", "PENDING")
    }


def create_purchase_order(supplier, cart_items, expected_date):
    """
    Create a purchase order from cart items
    
    Args:
        supplier: Supplier name
        cart_items: List of items in cart
        expected_date: Expected delivery date
    
    Returns:
        tuple: (po_number, DataFrame, error_message)
    """
    if not supplier or not supplier.strip():
        return None, None, "Supplier name is required"
    
    if not cart_items or len(cart_items) == 0:
        return None, None, "No items in purchase order"
    
    po_number = generate_po_number()
    po_data = []
    
    for item in cart_items:
        if not item.get("name") or not item.get("barcode"):
            continue
        
        cost = float(item.get("cost", 0))
        quantity = int(item.get("quantity", 1))
            
        po_data.append({
            "po_number": po_number,
            "date_ordered": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "supplier": supplier.strip(),
            "product_name": item["name"],
            "barcode": str(item["barcode"]),
            "quantity_ordered": quantity,
            "cost_price": cost,
            "total_cost": quantity * cost,
            "expected_date": str(expected_date),
            "date_received": "",
            "quantity_received": 0,
            "status": "PENDING",
            "payment_status": "UNPAID",
            "invoice_no": ""
        })
    
    if not po_data:
        return None, None, "No valid items to add to purchase order"
    
    return po_number, pd.DataFrame(po_data), None


def receive_purchase_order(po_number, received_items, invoice_no):
    """
    Receive items against a purchase order and update stock
    
    Args:
        po_number: Purchase order number
        received_items: List of items with received quantities
        invoice_no: Supplier invoice number
    
    Returns:
        tuple: (success, updated_products, new_products)
    """
    purchases_df = load_purchases()
    products_df = load_products()
    
    # Ensure required columns exist
    for col in ["status", "quantity_received", "date_received"]:
        if col not in purchases_df.columns:
            purchases_df[col] = "" if col == "date_received" else 0
    
    updated_products = []
    new_products = []
    
    for item in received_items:
        if item["received_qty"] <= 0:
            continue
        
        barcode = str(item["barcode"])
        received_qty = int(item["received_qty"])
        cost_price = float(item["cost"])
        product_name = item["name"]
        
        # Find the purchase order item
        mask = (purchases_df["po_number"] == po_number) & (purchases_df["barcode"] == barcode)
        idx = purchases_df[mask].index
        
        if len(idx) == 0:
            print(f"Warning: No match found for barcode {barcode} in PO {po_number}")
            continue
        
        # Update purchase record
        purchases_df.loc[idx, "quantity_received"] = received_qty
        purchases_df.loc[idx, "date_received"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        purchases_df.loc[idx, "status"] = "RECEIVED"
        purchases_df.loc[idx, "invoice_no"] = invoice_no
        
        # Update or create product in inventory
        product_idx = products_df[products_df["barcode"] == barcode].index
        
        if len(product_idx) > 0:
            # Update existing product
            current_stock = float(products_df.loc[product_idx[0], "stock"])
            products_df.loc[product_idx[0], "stock"] = current_stock + received_qty
            products_df.loc[product_idx[0], "cost"] = cost_price
            
            updated_products.append({
                "name": product_name,
                "old_stock": current_stock,
                "added": received_qty,
                "new_stock": current_stock + received_qty
            })
        else:
            # Create new product
            new_product = pd.DataFrame([{
                "barcode": barcode,
                "name": product_name,
                "category": "New Purchase",
                "price": cost_price * 1.3,
                "cost": cost_price,
                "stock": received_qty,
                "reorder_level": 5
            }])
            products_df = pd.concat([products_df, new_product], ignore_index=True)
            
            new_products.append({
                "name": product_name,
                "stock": received_qty,
                "cost": cost_price
            })
    
    # Save changes
    save_products(products_df)
    save_purchases(purchases_df)
    
    return True, updated_products, new_products


# ============================================================================
# UI FUNCTIONS
# ============================================================================

def render_cart():
    """Render the purchase order cart"""
    
    if not st.session_state.po_cart:
        st.info("Cart is empty. Add products or manual items above.")
        return
    
    cart_df = pd.DataFrame(st.session_state.po_cart)
    
    # Show cart summary
    st.markdown("---")
    st.markdown("### Purchase Order Cart")
    st.markdown(f"**Total Items in Cart: {len(cart_df)}**")
    
    # Display cart items
    display_df = cart_df[["name", "quantity", "cost", "total"]].copy()
    display_df.columns = ["Product", "Qty", "Unit Cost ($)", "Total ($)"]
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Unit Cost ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Total ($)": st.column_config.NumberColumn(format="$%.2f")
        }
    )
    
    cart_total = cart_df["total"].sum()
    st.info(f"**Total Order Value: ${cart_total:,.2f}**")
    
    return cart_total


def render_remove_item():
    """Render the remove item section"""
    
    if not st.session_state.po_cart:
        return
    
    st.markdown("#### Remove Items")
    remove_options = [f"{item['name']} (Qty: {item['quantity']})" for item in st.session_state.po_cart]
    
    if remove_options:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            item_to_remove = st.selectbox(
                "Select item to remove",
                options=remove_options,
                key="remove_select"
            )
        
        with col2:
            if st.button("Remove Item", use_container_width=True):
                item_name = item_to_remove.split(" (Qty:")[0]
                for i, item in enumerate(st.session_state.po_cart):
                    if item["name"] == item_name:
                        st.session_state.po_cart.pop(i)
                        st.success(f"Removed '{item_name}' from cart")
                        st.rerun()
                        break


def render_action_buttons(supplier_name, expected_date, cart_total):
    """Render the action buttons for the cart"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Clear All Items", use_container_width=True):
            st.session_state.po_cart = []
            st.success("Cart cleared!")
            st.rerun()
    
    with col2:
        if st.button("Create Purchase Order", type="primary", use_container_width=True):
            if not supplier_name or not supplier_name.strip():
                st.error("Please enter a supplier name")
                return
            
            # Create PO
            po_number, po_df, error = create_purchase_order(
                supplier=supplier_name,
                cart_items=st.session_state.po_cart,
                expected_date=expected_date
            )
            
            if error:
                st.error(error)
                return
            
            # Show debug info
            st.write(f"Creating PO with {len(st.session_state.po_cart)} items")
            st.write(f"PO DataFrame has {len(po_df)} rows")
            
            # Check if this PO already exists in the database
            existing_df = load_purchases()
            existing_po_items = existing_df[existing_df["po_number"] == po_number]
            
            if not existing_po_items.empty:
                st.warning(f"PO {po_number} already has {len(existing_po_items)} items in the database.")
                st.write("Existing items:")
                st.dataframe(existing_po_items[["product_name", "barcode", "quantity_ordered"]])
                
                # Ask user what to do
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Cancel - Go Back"):
                        return
                with col2:
                    if st.button("Replace Existing PO"):
                        # Delete existing items for this PO
                        st.write(f"Deleting existing PO {po_number}...")
                        # We need a delete function
                        # For now, we'll continue but the save will update
            
            # Ensure all columns match
            for col in po_df.columns:
                if col not in existing_df.columns:
                    existing_df[col] = ""
            
            # Remove any existing items with same (po_number, barcode)
            for _, row in po_df.iterrows():
                existing_df = existing_df[
                    ~((existing_df["po_number"] == row["po_number"]) & 
                      (existing_df["barcode"] == row["barcode"]))
                ]
            
            # Append new PO
            updated_df = pd.concat([existing_df, po_df], ignore_index=True)
            
            # Save to database
            try:
                success = save_purchases(updated_df)
                
                if success:
                    st.session_state.po_cart = []
                    st.session_state.po_created = True
                    st.session_state.last_po_number = po_number
                    
                    st.success(f"Purchase Order {po_number} created successfully with {len(po_df)} items!")
                    st.info(f"""
                    **PO Summary:**
                    - PO Number: {po_number}
                    - Supplier: {supplier_name}
                    - Items: {len(po_df)}
                    - Total Value: ${cart_total:,.2f}
                    - Expected Date: {expected_date}
                    """)
                    st.rerun()
                else:
                    st.error("Failed to save purchase order to database.")
            except Exception as e:
                st.error(f"Error: {str(e)}")


def render_receive_stock():
    """Render the receive stock tab"""
    
    st.markdown("## Receive Stock - Auto Update Inventory")
    st.caption("Confirm receipt of stock. Inventory will be automatically updated.")
    
    purchases_df = load_purchases()
    
    if purchases_df.empty:
        st.info("No purchase orders found.")
        return
    
    # Ensure status column exists
    if "status" not in purchases_df.columns:
        purchases_df["status"] = "PENDING"
    
    # Get pending POs
    pending_pos = purchases_df[purchases_df["status"] == "PENDING"]["po_number"].unique().tolist()
    
    if not pending_pos:
        st.info("No pending purchase orders. All orders have been received.")
        return
    
    selected_po = st.selectbox("Select Purchase Order to Receive", pending_pos, key="receive_po")
    
    if not selected_po:
        return
    
    po_details = get_po_details(selected_po)
    
    if not po_details:
        st.error("Could not load PO details")
        return
    
    # Display PO details
    st.markdown(f"### PO: {selected_po}")
    st.markdown(f"**Supplier:** {po_details['supplier']}")
    st.markdown(f"**Order Date:** {po_details['date_ordered']}")
    st.markdown(f"**Expected Date:** {po_details['expected_date']}")
    
    # Display items
    st.markdown("### Items Ordered")
    items_df = pd.DataFrame(po_details['items'])
    
    display_cols = ["product_name", "barcode", "quantity_ordered", "cost_price", "total_cost"]
    available_cols = [col for col in display_cols if col in items_df.columns]
    st.dataframe(items_df[available_cols], use_container_width=True, hide_index=True)
    
    po_total = po_details['total_value']
    st.info(f"PO Total: ${po_total:,.2f}")
    
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
            qty_ordered = item.get("quantity_ordered", 0)
            barcode_val = str(item.get("barcode", f"item_{idx}"))
            st.write(f"**{product_name}**")
            st.caption(f"Ordered: {qty_ordered}")
        
        with col2:
            received_qty = st.number_input(
                "Qty Received",
                min_value=0,
                max_value=int(qty_ordered),
                value=int(qty_ordered),
                key=f"rec_qty_{barcode_val}_{idx}",
                step=1,
                label_visibility="collapsed"
            )
        
        with col3:
            cost_price = item.get("cost_price", 0)
            st.write(f"Cost: ${cost_price:.2f}")
        
        with col4:
            item_total = received_qty * cost_price
            total_received_value += item_total
            st.write(f"Total: ${item_total:.2f}")
        
        received_items.append({
            "barcode": barcode_val,
            "received_qty": received_qty,
            "cost": float(cost_price),
            "name": product_name
        })
    
    st.markdown(f"**Total Received Value: ${total_received_value:,.2f}**")
    
    # Confirm button
    if st.button("Confirm Receipt and Update Stock", type="primary", use_container_width=True):
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
                        st.write(f"   - {p['name']}: {p['old_stock']} -> {p['new_stock']} (+{p['added']})")
                    if len(updated_products) > 5:
                        st.write(f"   ... and {len(updated_products) - 5} more")
                
                if new_products:
                    st.info(f"Created {len(new_products)} new products in inventory!")
                    for p in new_products:
                        st.write(f"   - {p['name']}: Added {p['stock']} units at ${p['cost']:.2f}")
                
                st.rerun()
            else:
                st.error("Failed to receive stock")


def render_supplier_performance():
    """Render the supplier performance tab"""
    
    st.markdown("## Supplier Performance Dashboard")
    
    supplier_perf = get_supplier_performance()
    
    if supplier_perf.empty:
        st.info("No purchase data available yet.")
        return
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Suppliers", len(supplier_perf))
    with col2:
        st.metric("Total Spent", f"${supplier_perf['Total Spent'].sum():,.2f}")
    with col3:
        avg_fulfillment = supplier_perf["Fulfillment Rate"].mean()
        st.metric("Avg Fulfillment Rate", f"{avg_fulfillment:.1f}%")
    
    st.markdown("---")
    
    # Supplier list
    st.markdown("### Supplier Performance Metrics")
    st.dataframe(supplier_perf, use_container_width=True, hide_index=True)
    
    # Low fulfillment warning
    low_fulfillment = supplier_perf[supplier_perf["Fulfillment Rate"] < 80]
    if not low_fulfillment.empty:
        st.warning(f"{len(low_fulfillment)} suppliers have fulfillment rate below 80%")
        st.dataframe(low_fulfillment[["Supplier", "Fulfillment Rate"]], use_container_width=True, hide_index=True)


def render_purchase_history():
    """Render the purchase history tab"""
    
    st.markdown("## Purchase History")
    
    purchases_df = load_purchases()
    
    if purchases_df.empty:
        st.info("No purchase records found.")
        return
    
    # Date filter
    date_filter = st.selectbox(
        "Filter by",
        ["All", "Last 30 Days", "Last 90 Days", "This Year"],
        key="purchase_filter"
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
    
    # Metrics
    total_purchases = purchases_df["total_cost"].sum() if "total_cost" in purchases_df.columns else 0
    total_items = purchases_df["quantity_ordered"].sum() if "quantity_ordered" in purchases_df.columns else 0
    unique_pos = purchases_df["po_number"].nunique() if "po_number" in purchases_df.columns else len(purchases_df)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Purchases", f"${total_purchases:,.2f}")
    with col2:
        st.metric("Total Items Ordered", f"{int(total_items):,}")
    with col3:
        st.metric("Orders", unique_pos)
    
    st.markdown("---")
    
    # PO Summary
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
            "total_cost": st.column_config.NumberColumn("Total ($)", format="$%.2f")
        }
    )
    
    # Download button
    csv = purchases_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Purchase History (CSV)",
        data=csv,
        file_name=f"purchase_history_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================================
# MAIN PAGE
# ============================================================================

def purchases_page():
    """Main purchases management page"""
    
    st.title("Purchases and Suppliers Management")
    st.caption("Create purchase orders, receive stock, and manage suppliers")
    
    # Load products
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
    
    # Show success messages
    if st.session_state.po_created and st.session_state.last_po_number:
        st.success(f"Purchase Order {st.session_state.last_po_number} created successfully!")
        st.balloons()
        st.session_state.po_created = False
    
    if st.session_state.stock_updated and st.session_state.last_received_po:
        st.success(f"Stock for PO {st.session_state.last_received_po} has been added to inventory!")
        st.balloons()
        st.session_state.stock_updated = False
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Create Purchase Order",
        "Receive Stock",
        "Supplier Performance",
        "Purchase History"
    ])
    
    # ========================================================================
    # TAB 1: CREATE PURCHASE ORDER
    # ========================================================================
    with tab1:
        st.markdown("## Create Purchase Order")
        st.caption("Create a purchase order before receiving stock from suppliers")
        
        if products_df.empty:
            st.warning("No products in inventory. You can add manual items below.")
        
        # Supplier and date
        col1, col2 = st.columns(2)
        
        with col1:
            supplier_name = st.text_input(
                "Supplier Name *",
                key="po_supplier",
                placeholder="Enter supplier name..."
            )
        
        with col2:
            expected_date = st.date_input(
                "Expected Delivery Date *",
                min_value=datetime.now().date(),
                value=datetime.now().date() + timedelta(days=7),
                key="po_expected_date"
            )
        
        st.markdown("### Add Products to Order")
        
        # Product selection
        if not products_df.empty:
            with st.form(key="add_product_form"):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    search = st.text_input(
                        "Search Product",
                        placeholder="Type product name or barcode..."
                    )
                    
                    filtered_products = products_df.copy()
                    if search:
                        filtered_products = products_df[
                            products_df["name"].astype(str).str.contains(search, case=False) |
                            products_df["barcode"].astype(str).str.contains(search, case=False)
                        ]
                    
                    if not filtered_products.empty:
                        product_options = []
                        for _, p in filtered_products.iterrows():
                            status = "In Stock" if p["stock"] > p["reorder_level"] else ("Low Stock" if p["stock"] > 0 else "Out of Stock")
                            label = f"{status} - {p['name']} - Stock: {p['stock']} - Cost: ${p['cost']:.2f}"
                            product_options.append(label)
                        
                        selected_label = st.selectbox("Select Product", product_options)
                        
                        if selected_label:
                            parts = selected_label.split(" - ")
                            if len(parts) >= 3:
                                product_name = parts[1]
                                selected_product = filtered_products[filtered_products["name"] == product_name].iloc[0]
                            else:
                                selected_product = None
                        else:
                            selected_product = None
                    else:
                        selected_product = None
                        st.info("No products found")
                
                with col2:
                    if selected_product is not None:
                        quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
                    else:
                        quantity = 1
                
                with col3:
                    if st.form_submit_button("Add to Cart", use_container_width=True):
                        if selected_product is not None:
                            # Check if already in cart
                            existing = None
                            for item in st.session_state.po_cart:
                                if item["barcode"] == selected_product["barcode"]:
                                    existing = item
                                    break
                            
                            if existing:
                                existing["quantity"] += quantity
                                existing["total"] = existing["quantity"] * existing["cost"]
                                st.success(f"Updated {selected_product['name']} to {existing['quantity']}")
                            else:
                                cost = float(selected_product["cost"]) if selected_product["cost"] > 0 else 0
                                st.session_state.po_cart.append({
                                    "barcode": selected_product["barcode"],
                                    "name": selected_product["name"],
                                    "quantity": quantity,
                                    "cost": cost,
                                    "total": cost * quantity
                                })
                                st.success(f"Added {quantity} x {selected_product['name']}")
                        else:
                            st.error("Please select a product")
        
        # Manual item entry
        st.markdown("### Manual Item Entry")
        st.caption("Add items not in inventory (new products, services, fees)")
        
        with st.form(key="add_manual_form"):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                manual_name = st.text_input("Item Name", placeholder="Enter item name...")
            
            with col2:
                manual_cost = st.number_input("Cost Price ($)", min_value=0.01, value=10.0, step=5.0)
            
            with col3:
                manual_qty = st.number_input("Quantity", min_value=1, value=1, step=1)
            
            with col4:
                if st.form_submit_button("Add Manual Item", use_container_width=True):
                    if manual_name:
                        # Check if already in cart
                        existing = None
                        for item in st.session_state.po_cart:
                            if item["name"].lower() == manual_name.lower() and abs(item["cost"] - float(manual_cost)) < 0.01:
                                existing = item
                                break
                        
                        if existing:
                            existing["quantity"] += manual_qty
                            existing["total"] = existing["quantity"] * existing["cost"]
                            st.success(f"Updated {manual_name} to {existing['quantity']}")
                        else:
                            barcode = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                            st.session_state.po_cart.append({
                                "barcode": barcode,
                                "name": manual_name,
                                "quantity": manual_qty,
                                "cost": float(manual_cost),
                                "total": float(manual_cost) * manual_qty
                            })
                            st.success(f"Added {manual_qty} x {manual_name}")
                    else:
                        st.error("Please enter an item name")
        
        # Render cart
        cart_total = render_cart()
        
        if st.session_state.po_cart:
            render_remove_item()
            render_action_buttons(supplier_name, expected_date, cart_total)
        else:
            st.info("Cart is empty. Add products or manual items above.")
    
    # ========================================================================
    # TAB 2: RECEIVE STOCK
    # ========================================================================
    with tab2:
        render_receive_stock()
    
    # ========================================================================
    # TAB 3: SUPPLIER PERFORMANCE
    # ========================================================================
    with tab3:
        render_supplier_performance()
    
    # ========================================================================
    # TAB 4: PURCHASE HISTORY
    # ========================================================================
    with tab4:
        render_purchase_history()


# ============================================================================
# MAIN GUARD
# ============================================================================
if __name__ == "__main__":
    purchases_page()