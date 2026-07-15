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
# CREATE PURCHASE ORDER - FIXED
# ==============================
def create_purchase_order(supplier, items, expected_date):
    """Create a purchase order before receiving stock"""
    
    if not supplier or not supplier.strip():
        return None, None, "Supplier name is required"
    
    if not items or len(items) == 0:
        return None, None, "No items in purchase order"
    
    po_number = generate_po_number()
    
    po_data = []
    for item in items:
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
    
    # Debug output
    print(f"📝 Creating PO {po_number} with {len(po_data)} items")
    for item in po_data:
        print(f"   - {item['product_name']} (barcode: {item['barcode']}) x {item['quantity_ordered']}")
    
    po_df = pd.DataFrame(po_data)
    return po_number, po_df, None


# ==============================
# RECEIVE PURCHASE ORDER
# ==============================
def receive_purchase_order(po_number, received_items, invoice_no):
    """Receive items against a purchase order and AUTO-UPDATE stock"""
    
    # Load current data
    purchases_df = load_purchases()
    products_df = load_products()
    
    # Debug: Show what we're trying to receive
    print(f"📦 Receiving PO {po_number} with {len(received_items)} items")
    for item in received_items:
        print(f"   - {item['name']}: {item['received_qty']} units")
    
    # Ensure required columns exist
    if "status" not in purchases_df.columns:
        purchases_df["status"] = "PENDING"
    if "quantity_received" not in purchases_df.columns:
        purchases_df["quantity_received"] = 0
    if "date_received" not in purchases_df.columns:
        purchases_df["date_received"] = ""
    
    updated_products = []
    new_products = []
    
    # Debug: Show all items in this PO from database
    po_items = purchases_df[purchases_df["po_number"] == po_number]
    print(f"📊 Found {len(po_items)} items in database for PO {po_number}")
    for _, item in po_items.iterrows():
        print(f"   - DB: {item.get('product_name', 'Unknown')} (barcode: {item.get('barcode', 'N/A')})")
    
    for item in received_items:
        # Skip items with 0 received quantity
        if item["received_qty"] <= 0:
            continue
            
        mask = (purchases_df["po_number"] == po_number) & (purchases_df["barcode"] == str(item["barcode"]))
        idx = purchases_df[mask].index
        
        received_qty = int(item["received_qty"])
        cost_price = float(item["cost"])
        barcode = str(item["barcode"])
        product_name = item["name"]
        
        print(f"🔍 Looking for barcode: {barcode} in PO {po_number}")
        print(f"   Found {len(idx)} matches")
        
        if len(idx) > 0:
            # Update purchase record
            purchases_df.loc[idx, "quantity_received"] = received_qty
            purchases_df.loc[idx, "date_received"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            purchases_df.loc[idx, "status"] = "RECEIVED"
            purchases_df.loc[idx, "invoice_no"] = invoice_no
            
            # Update product stock in inventory
            product_idx = products_df[products_df["barcode"] == barcode].index
            
            if len(product_idx) > 0:
                # Product exists - UPDATE existing stock
                current_stock = float(products_df.loc[product_idx[0], "stock"])
                new_stock = current_stock + received_qty
                products_df.loc[product_idx[0], "stock"] = new_stock
                products_df.loc[product_idx[0], "cost"] = cost_price
                
                updated_products.append({
                    "name": product_name,
                    "old_stock": current_stock,
                    "added": received_qty,
                    "new_stock": new_stock,
                    "cost": cost_price
                })
            else:
                # Product doesn't exist - CREATE new product in inventory
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
        else:
            print(f"⚠️ WARNING: No match found for barcode {barcode} in PO {po_number}")
    
    # Save all changes
    save_products(products_df)
    save_purchases(purchases_df)
    
    return True, updated_products, new_products


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
    
    st.title("Purchases & Suppliers Management")
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
    
    # Display success messages
    if st.session_state.po_created and st.session_state.last_po_number:
        st.success(f"Purchase Order **{st.session_state.last_po_number}** created successfully!")
        st.balloons()
        st.session_state.po_created = False
    
    if st.session_state.stock_updated and st.session_state.last_received_po:
        st.success(f"Stock for PO **{st.session_state.last_received_po}** has been added to inventory!")
        st.balloons()
        st.session_state.stock_updated = False
    
    # DEBUG: Show cart contents
    with st.expander("🔍 Debug: Cart Contents", expanded=False):
        st.write(f"Cart has {len(st.session_state.po_cart)} items")
        if st.session_state.po_cart:
            for i, item in enumerate(st.session_state.po_cart):
                st.write(f"  {i+1}. {item['name']} - Qty: {item['quantity']} - Barcode: {item['barcode']}")
        else:
            st.write("Cart is empty")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Create Purchase Order",
        "Receive Stock (Auto-Update)",
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
                                         placeholder="e.g., National Foods, Olivine, Delta...")
        
        with col2:
            expected_date = st.date_input("Expected Delivery Date *", 
                                         min_value=datetime.now().date(), 
                                         value=datetime.now().date() + timedelta(days=7),
                                         key="po_expected_date")
        
        st.markdown("### Add Products to Order")
        
        # Product selection
        if not products_df.empty:
            with st.form(key="add_product_form"):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    search = st.text_input("Search Product", 
                                          placeholder="Type product name or barcode...")
                    
                    filtered_products = products_df.copy()
                    if search:
                        filtered_products = products_df[
                            products_df["name"].astype(str).str.contains(search, case=False) |
                            products_df["barcode"].astype(str).str.contains(search, case=False)
                        ]
                    
                    if not filtered_products.empty:
                        product_display = []
                        for _, p in filtered_products.iterrows():
                            stock_status = "🟢" if p["stock"] > p["reorder_level"] else ("🟡" if p["stock"] > 0 else "🔴")
                            display_text = f"{stock_status} {p['name']} - Stock: {p['stock']} | Cost: ${p['cost']:.2f}"
                            product_display.append(display_text)
                        
                        selected_display = st.selectbox("Select Product", product_display)
                        if selected_display:
                            selected_product_name = selected_display.split(" - ")[0].split(" ", 1)[-1] if " - " in selected_display else selected_display
                            selected_product = filtered_products[filtered_products["name"] == selected_product_name].iloc[0]
                        else:
                            selected_product = None
                    else:
                        selected_product = None
                        st.info("No products found matching your search")
                
                with col2:
                    if selected_product is not None:
                        po_qty = st.number_input("Quantity", min_value=1, value=1, step=1)
                    else:
                        po_qty = 1
                
                with col3:
                    add_to_cart = st.form_submit_button("➕ Add to Cart", use_container_width=True)
                    
                    if add_to_cart:
                        if selected_product is not None:
                            # Check if product already exists in cart
                            existing_item = None
                            for item in st.session_state.po_cart:
                                if item["barcode"] == selected_product["barcode"]:
                                    existing_item = item
                                    break
                            
                            if existing_item:
                                existing_item["quantity"] += po_qty
                                existing_item["total"] = existing_item["quantity"] * existing_item["cost"]
                                st.success(f"Updated {selected_product['name']} quantity to {existing_item['quantity']}")
                            else:
                                cost_val = float(selected_product["cost"]) if selected_product["cost"] > 0 else 0
                                st.session_state.po_cart.append({
                                    "barcode": selected_product["barcode"],
                                    "name": selected_product["name"],
                                    "quantity": po_qty,
                                    "cost": cost_val,
                                    "total": cost_val * po_qty
                                })
                                st.success(f"Added {po_qty} x {selected_product['name']} to cart")
                            
                            #st.rerun()
                        else:
                            st.error("Please select a product first")
        
        # Manual item entry
        st.markdown("### ➕ Manual Item Entry")
        st.caption("Add items not in inventory (new products, services, fees)")
        
        with st.form(key="add_manual_form"):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                manual_item_name = st.text_input("Item Name", placeholder="e.g., New Product X, Delivery Fee")
            
            with col2:
                manual_item_cost = st.number_input("Cost Price ($)", min_value=0.01, value=10.0, step=5.0)
            
            with col3:
                manual_item_qty = st.number_input("Quantity", min_value=1, value=1, step=1)
            
            with col4:
                add_manual = st.form_submit_button("➕ Add Manual Item", use_container_width=True)
                
                if add_manual:
                    if manual_item_name:
                        # Check if item already exists in cart
                        existing_item = None
                        for item in st.session_state.po_cart:
                            if item["name"].lower() == manual_item_name.lower() and abs(item["cost"] - float(manual_item_cost)) < 0.01:
                                existing_item = item
                                break
                        
                        if existing_item:
                            existing_item["quantity"] += manual_item_qty
                            existing_item["total"] = existing_item["quantity"] * existing_item["cost"]
                            st.success(f"Updated {manual_item_name} quantity to {existing_item['quantity']}")
                        else:
                            unique_barcode = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                            st.session_state.po_cart.append({
                                "barcode": unique_barcode,
                                "name": manual_item_name,
                                "quantity": manual_item_qty,
                                "cost": float(manual_item_cost),
                                "total": float(manual_item_cost) * manual_item_qty
                            })
                            st.success(f"Added {manual_item_qty} x {manual_item_name} (${manual_item_cost:.2f} each)")
                        
                        #st.rerun()
                    else:
                        st.error("Please enter an item name")
        
        # Display cart
        st.markdown("---")
        st.markdown("### 📦 Purchase Order Cart")
        
        if st.session_state.po_cart:
            cart_df = pd.DataFrame(st.session_state.po_cart)
            
            st.markdown(f"**Total Items in Cart: {len(cart_df)}**")
            
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
            
            # Remove items
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
                    remove_btn = st.button("🗑️ Remove", use_container_width=True)
                    if remove_btn:
                        item_name = item_to_remove.split(" (Qty:")[0]
                        for i, item in enumerate(st.session_state.po_cart):
                            if item["name"] == item_name:
                                st.session_state.po_cart.pop(i)
                                st.success(f"Removed '{item_name}' from cart")
                                st.rerun()
                                break
            
            # Action buttons
            col1, col2 = st.columns(2)
            
            with col1:
                clear_all = st.button("🗑️ Clear All Items", use_container_width=True)
                if clear_all:
                    st.session_state.po_cart = []
                    st.success("Cart cleared!")
                    st.rerun()
            
            with col2:
                create_po = st.button("📄 Create Purchase Order", type="primary", use_container_width=True)
                if create_po:
                    if not supplier_name or not supplier_name.strip():
                        st.error("Please enter a supplier name")
                    else:
                        po_number, po_df, error = create_purchase_order(
                            supplier=supplier_name,
                            items=st.session_state.po_cart,
                            expected_date=expected_date
                        )
                        
                        if error:
                            st.error(error)
                        else:
                            # Load existing purchases
                            existing_df = load_purchases()
                            
                            # Ensure all columns match
                            for col in po_df.columns:
                                if col not in existing_df.columns:
                                    existing_df[col] = ""
                            
                            # Append new PO to existing
                            updated_df = pd.concat([existing_df, po_df], ignore_index=True)
                            
                            # DEBUG: Show what we're saving
                            st.write(f"📊 Saving PO with {len(po_df)} items to database")
                            
                            # Save to database
                            save_success = save_purchases(updated_df)
                            
                            if save_success:
                                st.session_state.po_cart = []
                                st.session_state.po_created = True
                                st.session_state.last_po_number = po_number
                                
                                st.success(f"✅ Purchase Order {po_number} created successfully with {len(po_df)} items!")
                                
                                # Show PO summary
                                st.info(f"""
                                **PO Summary:**
                                - PO Number: {po_number}
                                - Supplier: {supplier_name}
                                - Items: {len(po_df)}
                                - Total Value: ${cart_total:,.2f}
                                - Expected Date: {expected_date}
                                """)
                                
                                #st.rerun()
                            else:
                                st.error("❌ Failed to save purchase order to database")
        else:
            st.info("🛒 Cart is empty. Add products or manual items above.")
    
    # ==============================
    # TAB 2: RECEIVE STOCK
    # ==============================
    with tab2:
        st.markdown("## Receive Stock - Auto Update Inventory")
        st.caption("Confirm receipt of stock. Inventory will be automatically updated.")
        
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            st.info("No purchase orders found. Create a PO first in the 'Create Purchase Order' tab.")
        else:
            if "status" not in purchases_df.columns:
                purchases_df["status"] = "PENDING"
            
            # DEBUG: Show all POs
            with st.expander("Debug: All Purchase Orders", expanded=False):
                st.write(f"Total POs: {purchases_df['po_number'].nunique()}")
                st.dataframe(purchases_df[["po_number", "product_name", "barcode", "quantity_ordered", "status"]])
            
            pending_pos = purchases_df[purchases_df["status"] == "PENDING"]["po_number"].unique().tolist()
            
            if not pending_pos:
                st.info("No pending purchase orders. All orders have been received.")
            else:
                selected_po = st.selectbox("Select Purchase Order to Receive", pending_pos, key="receive_po")
                
                if selected_po:
                    po_details = get_po_details(selected_po)
                    
                    if po_details:
                        st.markdown(f"### PO: {selected_po}")
                        st.markdown(f"**Supplier:** {po_details['supplier']}")
                        st.markdown(f"**Order Date:** {po_details['date_ordered']}")
                        st.markdown(f"**Expected Date:** {po_details['expected_date']}")
                        
                        st.markdown("### Items Ordered")
                        items_df = pd.DataFrame(po_details['items'])
                        
                        # DEBUG: Show all items in this PO
                        st.write(f"Found {len(items_df)} items in PO {selected_po}")
                        
                        display_cols = ["product_name", "barcode", "quantity_ordered", "cost_price", "total_cost"]
                        available_cols = [col for col in display_cols if col in items_df.columns]
                        st.dataframe(items_df[available_cols], use_container_width=True, hide_index=True)
                        
                        po_total = po_details['total_value']
                        st.info(f"PO Total: ${po_total:,.2f}")
                        
                        st.markdown("---")
                        st.markdown("### Receiving Details")
                        st.info("When you receive items, stock will be AUTOMATICALLY added to inventory.")
                        
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
                                st.caption(f"Ordered: {qty_ordered} | Barcode: {barcode_val}")
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
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            confirm_button = st.button("Confirm Receipt & Update Stock", type="primary", use_container_width=True)
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
                                                st.write(f"   • {p['name']}: {p['old_stock']} → {p['new_stock']} (+{p['added']})")
                                            if len(updated_products) > 5:
                                                st.write(f"   ... and {len(updated_products) - 5} more")
                                        
                                        if new_products:
                                            st.info(f"Created {len(new_products)} new products in inventory!")
                                            for p in new_products:
                                                st.write(f"   • {p['name']}: Added {p['stock']} units at ${p['cost']:.2f}")
                                        
                                        st.rerun()
                        
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
            st.dataframe(supplier_perf, use_container_width=True, hide_index=True)
            
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
                st.metric("Total Items Ordered", f"{int(total_items):,}")
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
                    "total_cost": st.column_config.NumberColumn("Total ($)", format="$%.2f")
                }
            )
            
            st.markdown("---")
            
            with st.expander("View Detailed Purchase Records"):
                display_cols = ["po_number", "date_ordered", "supplier", "product_name", "barcode", "quantity_ordered", "quantity_received", "cost_price", "total_cost", "status"]
                available_cols = [col for col in display_cols if col in purchases_df.columns]
                
                if "date_ordered" in purchases_df.columns:
                    purchases_df = purchases_df.sort_values("date_ordered", ascending=False)
                
                st.dataframe(purchases_df[available_cols].head(100), use_container_width=True, hide_index=True)
            
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