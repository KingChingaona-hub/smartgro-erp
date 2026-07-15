# backend/purchases/purchases.py
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
    save_products,
    get_db_cursor
)


# ==============================
# LOAD ALL PURCHASES (NO BRANCH FILTER)
# ==============================
def load_all_purchases():
    """Load ALL purchases without branch filter"""
    try:
        from backend.core.db_adapter import get_db_cursor
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("""
                SELECT id, branch_id, po_number, date_ordered, supplier,
                       product_name, barcode, quantity_ordered, quantity_received,
                       cost_price, total_cost, expected_date, status, payment_status, invoice_no,
                       line_item_id
                FROM purchases 
                ORDER BY date_ordered DESC
            """)
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows)
                return df
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading all purchases: {e}")
        return pd.DataFrame()


# ==============================
# GENERATE PO NUMBER
# ==============================
def generate_po_number():
    """Generate unique purchase order number"""
    return f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"


# ==============================
# DELETE PURCHASE ORDER
# ==============================
def delete_purchase_order(po_number):
    """Delete a purchase order completely"""
    try:
        purchases_df = load_all_purchases()
        if purchases_df.empty or po_number not in purchases_df["po_number"].values:
            return False, f"Purchase Order {po_number} not found"
        
        purchases_df = purchases_df[purchases_df["po_number"] != po_number]
        save_purchases(purchases_df)
        return True, f"Purchase Order {po_number} deleted successfully"
    except Exception as e:
        return False, f"Error deleting PO: {str(e)}"


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
    
    for idx, item in enumerate(items):
        if not item.get("name"):
            continue
        
        cost = float(item.get("cost", 0))
        quantity = int(item.get("quantity", 1))
        line_item_id = f"{po_number}_{idx+1:04d}"
        
        po_data.append({
            "po_number": po_number,
            "line_item_id": line_item_id,
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
            "invoice_no": ""
        })
    
    if not po_data:
        return None, None, "No valid items to add to purchase order"
    
    po_df = pd.DataFrame(po_data)
    return po_number, po_df, None


# ==============================
# RECEIVE PURCHASE ORDER
# ==============================
def receive_purchase_order(po_number, received_items, invoice_no):
    """Receive items against a purchase order and AUTO-UPDATE stock"""
    
    purchases_df = load_all_purchases()
    products_df = load_products()
    
    if "status" not in purchases_df.columns:
        purchases_df["status"] = "PENDING"
    if "quantity_received" not in purchases_df.columns:
        purchases_df["quantity_received"] = 0
    if "date_received" not in purchases_df.columns:
        purchases_df["date_received"] = ""
    
    updated_products = []
    new_products = []
    
    po_mask = purchases_df["po_number"] == po_number
    po_items_indices = purchases_df[po_mask].index.tolist()
    
    po_items_mapping = {}
    for idx in po_items_indices:
        row = purchases_df.loc[idx]
        barcode = str(row.get("barcode", "")).strip()
        product_name = str(row.get("product_name", "")).strip()
        line_item_id = str(row.get("line_item_id", "")).strip()
        
        key = barcode if barcode else product_name
        if key:
            po_items_mapping[key] = {"idx": idx, "line_item_id": line_item_id}
    
    for item in received_items:
        if item["received_qty"] <= 0:
            continue
        
        barcode = str(item.get("barcode", "")).strip()
        product_name = str(item.get("name", "")).strip()
        received_qty = int(item["received_qty"])
        cost_price = float(item["cost"])
        
        matching_idx = None
        
        if barcode:
            for key, value in po_items_mapping.items():
                if key == barcode:
                    matching_idx = value["idx"]
                    break
        
        if matching_idx is None and product_name:
            for key, value in po_items_mapping.items():
                if key.lower() == product_name.lower():
                    matching_idx = value["idx"]
                    break
        
        if matching_idx is None:
            for key, value in po_items_mapping.items():
                if product_name and key and (product_name.lower() in key.lower() or key.lower() in product_name.lower()):
                    matching_idx = value["idx"]
                    break
        
        if matching_idx is not None:
            purchases_df.loc[matching_idx, "quantity_received"] = received_qty
            purchases_df.loc[matching_idx, "date_received"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            purchases_df.loc[matching_idx, "status"] = "RECEIVED"
            purchases_df.loc[matching_idx, "invoice_no"] = invoice_no
            
            product_idx = products_df[products_df["barcode"] == barcode].index
            
            if len(product_idx) > 0:
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
            st.warning(f"Item '{product_name}' not found in purchase order. Adding as new item.")
            
            new_line_item_id = f"{po_number}_{len(po_items_indices)+1:04d}"
            
            new_row = {
                "po_number": po_number,
                "line_item_id": new_line_item_id,
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
                "invoice_no": invoice_no
            }
            
            for col in purchases_df.columns:
                if col not in new_row:
                    new_row[col] = ""
            
            purchases_df = pd.concat([purchases_df, pd.DataFrame([new_row])], ignore_index=True)
    
    po_items = purchases_df[purchases_df["po_number"] == po_number]
    all_received = True
    for idx in po_items.index:
        qty_ordered = int(po_items.loc[idx].get("quantity_ordered", 0))
        qty_received = int(po_items.loc[idx].get("quantity_received", 0))
        if qty_received < qty_ordered:
            all_received = False
            break
    
    if all_received:
        purchases_df.loc[purchases_df["po_number"] == po_number, "status"] = "COMPLETED"
    else:
        purchases_df.loc[purchases_df["po_number"] == po_number, "status"] = "PARTIALLY_RECEIVED"
    
    save_products(products_df)
    save_purchases(purchases_df)
    
    return True, updated_products, new_products


# ==============================
# GET PURCHASE ORDER DETAILS
# ==============================
def get_po_details(po_number):
    """Get complete details for a specific purchase order"""
    purchases_df = load_all_purchases()
    po_items = purchases_df[purchases_df["po_number"] == po_number]
    
    if po_items.empty:
        return None
    
    first_item = po_items.iloc[0]
    
    date_ordered = first_item.get("date_ordered")
    if date_ordered:
        if hasattr(date_ordered, 'strftime'):
            date_ordered_str = date_ordered.strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_ordered_str = str(date_ordered)
    else:
        date_ordered_str = "Unknown"
    
    expected_date = first_item.get("expected_date")
    if expected_date:
        if hasattr(expected_date, 'strftime'):
            expected_date_str = expected_date.strftime('%Y-%m-%d')
        else:
            expected_date_str = str(expected_date)
    else:
        expected_date_str = "N/A"
    
    return {
        "po_number": po_number,
        "supplier": first_item.get("supplier", "Unknown"),
        "date_ordered": date_ordered_str,
        "expected_date": expected_date_str,
        "items": po_items.to_dict('records'),
        "total_value": float(po_items["total_cost"].sum()) if "total_cost" in po_items.columns else 0,
        "status": first_item.get("status", "PENDING")
    }


# ==============================
# SUPPLIER PERFORMANCE
# ==============================
def get_supplier_performance():
    """Calculate supplier performance metrics from purchase history"""
    purchases_df = load_all_purchases()
    
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
# PURCHASES PAGE - NEW SIMPLIFIED APPROACH
# ==============================
def purchases_page():
    """Enhanced Purchases Management Page with Simplified Receive System"""
    
    st.title("Purchases and Suppliers Management")
    
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
    if "selected_po" not in st.session_state:
        st.session_state.selected_po = None
    
    # Display success messages
    if st.session_state.po_created and st.session_state.last_po_number:
        st.success(f"Purchase Order {st.session_state.last_po_number} created successfully!")
        st.balloons()
        st.session_state.po_created = False
    
    if st.session_state.stock_updated and st.session_state.last_received_po:
        st.success(f"Stock for PO {st.session_state.last_received_po} has been added to inventory!")
        st.balloons()
        st.session_state.stock_updated = False
    
    if st.session_state.po_deleted:
        st.info("Purchase Order has been declined and removed.")
        st.session_state.po_deleted = False
    
    # Load all purchases
    all_purchases = load_all_purchases()
    
    # ==============================
    # SECTION 1: CREATE PURCHASE ORDER
    # ==============================
    st.markdown("---")
    st.markdown("## Create Purchase Order")
    
    products_df = load_products()
    
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
    
    # Product search and add
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
                po_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="po_qty")
                st.caption(f"Current stock: {selected_product['stock']}")
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
                            item["quantity"] = item["quantity"] + po_qty
                            item["total"] = item["quantity"] * item["cost"]
                            existing = True
                            break
                    
                    if not existing:
                        cost_val = float(selected_product["cost"]) if selected_product["cost"] > 0 else 0
                        st.session_state.po_cart.append({
                            "barcode": str(selected_product["barcode"]),
                            "name": str(selected_product["name"]),
                            "quantity": int(po_qty),
                            "cost": cost_val,
                            "total": cost_val * int(po_qty)
                        })
                    
                    st.success(f"Added {po_qty} x {selected_product['name']} to order")
                    st.rerun()
        
        with col4:
            clear_button = st.button("Clear Cart", use_container_width=True)
            if clear_button:
                st.session_state.po_cart = []
                st.success("Cart cleared!")
                st.rerun()
    
    # Manual item entry
    st.markdown("### Manual Item Entry")
    st.caption("Add items not in inventory (new products, services, fees)")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        manual_item_name = st.text_input("Item Name", key="manual_item_name", placeholder="e.g., New Product X, Delivery Fee")
    
    with col2:
        manual_item_cost = st.number_input("Cost Price ($)", min_value=0.01, value=10.0, step=5.0, key="manual_item_cost")
    
    with col3:
        manual_item_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="manual_item_qty")
    
    with col4:
        add_manual_button = st.button("Add Manual Item", key="add_manual", use_container_width=True)
        if add_manual_button:
            if manual_item_name and manual_item_name.strip():
                existing = False
                for item in st.session_state.po_cart:
                    if str(item["name"]).lower() == manual_item_name.lower() and float(item["cost"]) == float(manual_item_cost):
                        item["quantity"] = item["quantity"] + int(manual_item_qty)
                        item["total"] = item["quantity"] * item["cost"]
                        existing = True
                        break
                
                if not existing:
                    unique_barcode = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    st.session_state.po_cart.append({
                        "barcode": unique_barcode,
                        "name": str(manual_item_name).strip(),
                        "quantity": int(manual_item_qty),
                        "cost": float(manual_item_cost),
                        "total": float(manual_item_cost) * int(manual_item_qty)
                    })
                    st.success(f"Added {manual_item_qty} x {manual_item_name} (${manual_item_cost:.2f} each)")
                else:
                    st.success(f"Updated {manual_item_name} quantity to {item['quantity']}")
            else:
                st.error("Please enter an item name")
            
            st.rerun()
    
    # Display PO Cart
    st.markdown("---")
    st.markdown("### Purchase Order Cart")
    
    if st.session_state.po_cart:
        po_cart_df = pd.DataFrame(st.session_state.po_cart)
        
        st.info(f"**{len(po_cart_df)} items in cart**")
        
        st.dataframe(
            po_cart_df[["name", "quantity", "cost", "total"]],
            use_container_width=True,
            hide_index=True,
            column_config={
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
                st.rerun()
        
        with col2:
            create_po_button = st.button("Create Purchase Order", type="primary", key="create_po_btn", use_container_width=True)
            if create_po_button:
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
                        existing_df = load_all_purchases()
                        
                        for col in po_df.columns:
                            if col not in existing_df.columns:
                                existing_df[col] = ""
                        
                        updated_df = pd.concat([existing_df, po_df], ignore_index=True)
                        save_purchases(updated_df)
                        
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
                        
                        po_text = f"""
{'='*50}
AZIEL INVESTMENTS - PURCHASE ORDER
{'='*50}

PO Number: {po_number}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Supplier: {supplier_name}
Expected Delivery: {expected_date}

{'─'*40}
ITEMS ORDERED
{'─'*40}
"""
                        for _, item in po_cart_df.iterrows():
                            po_text += f"{item['name']:<30} {item['quantity']:>5} x ${item['cost']:.2f} = ${item['total']:.2f}\n"
                        
                        po_text += f"""
{'─'*40}
TOTAL: ${po_total:,.2f}
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
                        
                        st.rerun()
    else:
        st.info("Cart is empty. Add products above to create a purchase order.")
    
    # ==============================
    # SECTION 2: RECEIVE PURCHASE ORDER (SIMPLIFIED)
    # ==============================
    st.markdown("---")
    st.markdown("## Receive Purchase Order")
    st.caption("Select a pending purchase order to receive stock")
    
    # Reload purchases to get latest
    purchases_df = load_all_purchases()
    
    if purchases_df.empty:
        st.info("No purchase orders found. Create a PO first.")
    else:
        # Show all POs with their status
        po_summary = purchases_df.groupby(["po_number", "supplier", "status"]).agg({
            "product_name": lambda x: list(x),
            "quantity_ordered": "sum",
            "total_cost": "sum"
        }).reset_index()
        
        # Show summary table
        st.dataframe(
            po_summary[["po_number", "supplier", "status", "quantity_ordered", "total_cost"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_cost": st.column_config.NumberColumn("Total ($)", format="$%.2f"),
                "quantity_ordered": "Items"
            }
        )
        
        # Filter for pending POs
        pending_pos = po_summary[po_summary["status"] == "PENDING"]["po_number"].tolist()
        
        if not pending_pos:
            st.info("No pending purchase orders to receive. All orders have been completed.")
        else:
            st.markdown("---")
            
            selected_po = st.selectbox("Select Purchase Order to Receive", pending_pos, key="receive_po_select")
            
            if selected_po:
                po_details = get_po_details(selected_po)
                
                if po_details:
                    st.markdown(f"### Purchase Order: {selected_po}")
                    st.markdown(f"**Supplier:** {po_details['supplier']}")
                    st.markdown(f"**Order Date:** {po_details['date_ordered']}")
                    st.markdown(f"**Expected Date:** {po_details['expected_date']}")
                    
                    # Display items
                    items_df = pd.DataFrame(po_details['items'])
                    st.markdown("#### Items Ordered")
                    st.dataframe(
                        items_df[["product_name", "quantity_ordered", "cost_price", "total_cost"]],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "cost_price": st.column_config.NumberColumn("Unit Cost ($)", format="$%.2f"),
                            "total_cost": st.column_config.NumberColumn("Total ($)", format="$%.2f")
                        }
                    )
                    
                    po_total = po_details['total_value']
                    st.info(f"PO Total: ${po_total:,.2f}")
                    
                    # Action buttons
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        decline_button = st.button("Decline / Delete PO", key="decline_po_btn", use_container_width=True)
                        if decline_button:
                            success, message = delete_purchase_order(selected_po)
                            if success:
                                st.session_state.po_deleted = True
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    
                    with col2:
                        refresh_button = st.button("Refresh List", key="refresh_po_list", use_container_width=True)
                        if refresh_button:
                            st.rerun()
                    
                    with col3:
                        # Show if PO is ready to receive
                        st.info("Ready to receive")
                    
                    st.markdown("---")
                    
                    # Receive section
                    st.markdown("### Receive Stock")
                    st.info("Enter the supplier invoice number and confirm quantities received.")
                    
                    invoice_no = st.text_input("Supplier Invoice Number *", key="invoice_no_input")
                    
                    st.markdown("#### Enter Received Quantities")
                    
                    received_items = []
                    total_received_value = 0
                    
                    for idx, item in enumerate(po_details['items']):
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                        
                        with col1:
                            product_name = item.get("product_name", "Unknown")
                            qty_ordered = item.get("quantity_ordered", 0)
                            st.write(f"**{product_name}**")
                            st.caption(f"Ordered: {qty_ordered}")
                        
                        with col2:
                            barcode_val = str(item.get("barcode", f"item_{idx}"))
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
                            "barcode": str(item.get("barcode", "")),
                            "received_qty": received_qty,
                            "cost": float(cost_price),
                            "name": product_name
                        })
                    
                    st.markdown(f"**Total Received Value: ${total_received_value:,.2f}**")
                    
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
                                        st.write(f"   - {p['name']}: {p['old_stock']} -> {p['new_stock']} (+{p['added']})")
                                    if len(updated_products) > 5:
                                        st.write(f"   ... and {len(updated_products) - 5} more")
                                
                                if new_products:
                                    st.info(f"Created {len(new_products)} new products in inventory!")
                                
                                st.rerun()
    
    # ==============================
    # SECTION 3: PURCHASE HISTORY
    # ==============================
    st.markdown("---")
    st.markdown("## Purchase History")
    
    history_df = load_all_purchases()
    
    if history_df.empty:
        st.info("No purchase records found.")
    else:
        # Summary by PO
        history_summary = history_df.groupby(["po_number", "supplier", "date_ordered", "status"]).agg({
            "product_name": lambda x: len(list(x)),
            "total_cost": "sum"
        }).reset_index()
        history_summary.columns = ["PO Number", "Supplier", "Date", "Status", "Items", "Total"]
        
        st.dataframe(
            history_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total": st.column_config.NumberColumn("Total ($)", format="$%.2f")
            }
        )
        
        # Download button
        csv = history_df.to_csv(index=False).encode("utf-8")
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