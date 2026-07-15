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
                return pd.DataFrame(rows)
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
        
        key = barcode if barcode else product_name
        if key:
            po_items_mapping[key] = idx
    
    for item in received_items:
        if item["received_qty"] <= 0:
            continue
        
        barcode = str(item.get("barcode", "")).strip()
        product_name = str(item.get("name", "")).strip()
        received_qty = int(item["received_qty"])
        cost_price = float(item["cost"])
        
        matching_idx = None
        
        if barcode:
            for key, idx in po_items_mapping.items():
                if key == barcode:
                    matching_idx = idx
                    break
        
        if matching_idx is None and product_name:
            for key, idx in po_items_mapping.items():
                if key.lower() == product_name.lower():
                    matching_idx = idx
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
# PURCHASES PAGE
# ==============================
def purchases_page():
    """Purchases Management - Create and Receive on One Page"""
    
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
    
    # Load data
    products_df = load_products()
    
    # ==============================
    # SECTION 1: CREATE PURCHASE ORDER
    # ==============================
    st.markdown("## Create Purchase Order")
    
    if products_df.empty:
        st.warning("No products in inventory. You can still add manual items below.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        supplier_name = st.text_input("Supplier Name *", key="po_supplier")
    
    with col2:
        expected_date = st.date_input("Expected Delivery Date *", 
                                     min_value=datetime.now().date(), 
                                     value=datetime.now().date() + timedelta(days=7),
                                     key="po_expected_date")
    
    st.markdown("### Add Products to Order")
    
    if not products_df.empty:
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            search = st.text_input("Search Product", key="po_search")
            filtered_products = products_df.copy()
            if search:
                filtered_products = products_df[
                    products_df["name"].astype(str).str.contains(search, case=False) |
                    products_df["barcode"].astype(str).str.contains(search, case=False)
                ]
            
            if not filtered_products.empty:
                selected_product = st.selectbox("Select Product", filtered_products["name"].tolist(), key="po_product_select")
                if selected_product:
                    selected_product = filtered_products[filtered_products["name"] == selected_product].iloc[0]
                else:
                    selected_product = None
            else:
                selected_product = None
                st.info("No products found")
        
        with col2:
            if selected_product is not None:
                po_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="po_qty")
                st.caption(f"Stock: {selected_product['stock']}")
            else:
                po_qty = 1
        
        with col3:
            if selected_product is not None:
                if st.button("Add to Order", key="add_to_po", use_container_width=True):
                    existing = False
                    for item in st.session_state.po_cart:
                        if item["barcode"] == selected_product["barcode"]:
                            item["quantity"] += po_qty
                            item["total"] = item["quantity"] * item["cost"]
                            existing = True
                            break
                    
                    if not existing:
                        st.session_state.po_cart.append({
                            "barcode": selected_product["barcode"],
                            "name": selected_product["name"],
                            "quantity": int(po_qty),
                            "cost": float(selected_product["cost"]),
                            "total": float(selected_product["cost"]) * int(po_qty)
                        })
                    
                    st.success(f"Added {po_qty} x {selected_product['name']}")
                    st.rerun()
        
        with col4:
            if st.button("Clear Cart", key="clear_cart", use_container_width=True):
                st.session_state.po_cart = []
                st.rerun()
    
    # Manual item entry
    st.markdown("### Manual Item Entry")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        manual_item_name = st.text_input("Item Name", key="manual_item_name")
    
    with col2:
        manual_item_cost = st.number_input("Cost ($)", min_value=0.01, value=10.0, step=5.0, key="manual_item_cost")
    
    with col3:
        manual_item_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="manual_item_qty")
    
    with col4:
        if st.button("Add Manual Item", key="add_manual", use_container_width=True):
            if manual_item_name:
                st.session_state.po_cart.append({
                    "barcode": f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    "name": manual_item_name,
                    "quantity": int(manual_item_qty),
                    "cost": float(manual_item_cost),
                    "total": float(manual_item_cost) * int(manual_item_qty)
                })
                st.success(f"Added {manual_item_qty} x {manual_item_name}")
                st.rerun()
            else:
                st.error("Please enter an item name")
    
    # Display Cart
    st.markdown("---")
    st.markdown("### Purchase Order Cart")
    
    if st.session_state.po_cart:
        po_cart_df = pd.DataFrame(st.session_state.po_cart)
        st.dataframe(po_cart_df[["name", "quantity", "cost", "total"]], use_container_width=True, hide_index=True)
        
        po_total = po_cart_df["total"].sum()
        st.info(f"Total Order Value: ${po_total:,.2f}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Clear All Items", key="clear_all", use_container_width=True):
                st.session_state.po_cart = []
                st.rerun()
        
        with col2:
            if st.button("Create Purchase Order", type="primary", key="create_po", use_container_width=True):
                if not supplier_name:
                    st.error("Please enter a supplier name")
                elif not st.session_state.po_cart:
                    st.error("Cart is empty")
                else:
                    po_number, po_df, error = create_purchase_order(
                        supplier=supplier_name,
                        items=st.session_state.po_cart,
                        expected_date=expected_date
                    )
                    
                    if error:
                        st.error(error)
                    else:
                        save_purchases(po_df)
                        st.session_state.po_cart = []
                        st.session_state.po_created = True
                        st.session_state.last_po_number = po_number
                        st.rerun()
    else:
        st.info("Cart is empty")
    
    # ==============================
    # SECTION 2: RECEIVE PURCHASE ORDER
    # ==============================
    st.markdown("---")
    st.markdown("## Receive Purchase Order")
    
    purchases_df = load_all_purchases()
    
    if purchases_df.empty:
        st.info("No purchase orders found")
    else:
        # Show all POs
        po_summary = purchases_df.groupby(["po_number", "supplier", "status"]).agg({
            "product_name": lambda x: len(list(x)),
            "total_cost": "sum"
        }).reset_index()
        po_summary.columns = ["PO Number", "Supplier", "Status", "Items", "Total"]
        
        st.dataframe(po_summary, use_container_width=True, hide_index=True)
        
        pending_pos = po_summary[po_summary["Status"] == "PENDING"]["PO Number"].tolist()
        
        if not pending_pos:
            st.info("No pending POs to receive")
        else:
            selected_po = st.selectbox("Select PO to Receive", pending_pos, key="receive_po")
            
            if selected_po:
                po_details = get_po_details(selected_po)
                
                if po_details:
                    st.markdown(f"### PO: {selected_po}")
                    st.markdown(f"Supplier: {po_details['supplier']}")
                    
                    items_df = pd.DataFrame(po_details['items'])
                    st.dataframe(items_df[["product_name", "quantity_ordered", "cost_price", "total_cost"]], 
                                use_container_width=True, hide_index=True)
                    
                    st.info(f"PO Total: ${po_details['total_value']:,.2f}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("Decline PO", key="decline_po", use_container_width=True):
                            success, message = delete_purchase_order(selected_po)
                            if success:
                                st.session_state.po_deleted = True
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    
                    with col2:
                        if st.button("Refresh", key="refresh_receive", use_container_width=True):
                            st.rerun()
                    
                    st.markdown("---")
                    
                    invoice_no = st.text_input("Invoice Number *", key="invoice_no")
                    
                    st.markdown("### Enter Received Quantities")
                    
                    received_items = []
                    total_received = 0
                    
                    for idx, item in enumerate(po_details['items']):
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                        
                        with col1:
                            product_name = item.get("product_name", "Unknown")
                            qty_ordered = item.get("quantity_ordered", 0)
                            st.write(f"**{product_name}**")
                            st.caption(f"Ordered: {qty_ordered}")
                        
                        with col2:
                            received_qty = st.number_input(
                                "Qty",
                                min_value=0,
                                max_value=int(qty_ordered),
                                value=int(qty_ordered),
                                key=f"rec_qty_{idx}",
                                step=1,
                                label_visibility="collapsed"
                            )
                        
                        with col3:
                            cost_price = item.get("cost_price", 0)
                            st.write(f"Cost: ${cost_price:.2f}")
                        
                        with col4:
                            item_total = received_qty * cost_price
                            total_received += item_total
                            st.write(f"Total: ${item_total:.2f}")
                        
                        received_items.append({
                            "barcode": str(item.get("barcode", "")),
                            "received_qty": received_qty,
                            "cost": float(cost_price),
                            "name": product_name
                        })
                    
                    st.info(f"Total Received Value: ${total_received:,.2f}")
                    
                    if st.button("Confirm Receipt", type="primary", use_container_width=True):
                        if not invoice_no:
                            st.error("Please enter invoice number")
                        else:
                            success, updated, new_items = receive_purchase_order(
                                selected_po, received_items, invoice_no
                            )
                            
                            if success:
                                st.session_state.stock_updated = True
                                st.session_state.last_received_po = selected_po
                                st.success("Stock received successfully!")
                                st.rerun()
    
    # ==============================
    # SECTION 3: PURCHASE HISTORY
    # ==============================
    st.markdown("---")
    st.markdown("## Purchase History")
    
    history_df = load_all_purchases()
    
    if history_df.empty:
        st.info("No purchase records")
    else:
        history_summary = history_df.groupby(["po_number", "supplier", "date_ordered", "status"]).agg({
            "product_name": lambda x: len(list(x)),
            "total_cost": "sum"
        }).reset_index()
        history_summary.columns = ["PO Number", "Supplier", "Date", "Status", "Items", "Total"]
        history_summary = history_summary.sort_values("Date", ascending=False)
        
        st.dataframe(history_summary, use_container_width=True, hide_index=True)
        
        csv = history_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
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