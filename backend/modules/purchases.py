"""
Purchases Management Module - Simplified Single Item Version
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
    return f"PO-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def create_purchase_order(supplier, product_name, barcode, quantity, cost, expected_date):
    """Create a single purchase order item"""
    
    if not supplier or not supplier.strip():
        return None, "Supplier name is required"
    
    if not product_name or not product_name.strip():
        return None, "Product name is required"
    
    if quantity <= 0:
        return None, "Quantity must be greater than 0"
    
    if cost <= 0:
        return None, "Cost must be greater than 0"
    
    po_number = generate_po_number()
    
    po_data = [{
        "po_number": po_number,
        "date_ordered": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "supplier": supplier.strip(),
        "product_name": product_name.strip(),
        "barcode": str(barcode),
        "quantity_ordered": int(quantity),
        "quantity_received": 0,
        "cost_price": float(cost),
        "total_cost": float(cost) * int(quantity),
        "expected_date": str(expected_date),
        "date_received": "",
        "status": "PENDING",
        "payment_status": "UNPAID",
        "invoice_no": ""
    }]
    
    return pd.DataFrame(po_data), None


def receive_purchase_order(po_number, received_qty, cost_price, product_name, barcode, invoice_no):
    """Receive a single purchase order item and update stock"""
    
    # Load current data
    purchases_df = load_purchases()
    products_df = load_products()
    
    # Find the purchase order item
    mask = (purchases_df["po_number"] == po_number) & (purchases_df["barcode"] == str(barcode))
    idx = purchases_df[mask].index
    
    if len(idx) == 0:
        return False, "Purchase order item not found"
    
    # Update purchase record
    purchases_df.loc[idx, "quantity_received"] = received_qty
    purchases_df.loc[idx, "date_received"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    purchases_df.loc[idx, "status"] = "RECEIVED"
    purchases_df.loc[idx, "invoice_no"] = invoice_no
    
    # Update or create product in inventory
    product_idx = products_df[products_df["barcode"] == str(barcode)].index
    
    if len(product_idx) > 0:
        # Update existing product
        current_stock = float(products_df.loc[product_idx[0], "stock"])
        products_df.loc[product_idx[0], "stock"] = current_stock + received_qty
        products_df.loc[product_idx[0], "cost"] = float(cost_price)
    else:
        # Create new product
        new_product = pd.DataFrame([{
            "barcode": str(barcode),
            "name": product_name,
            "category": "New Purchase",
            "price": float(cost_price) * 1.3,
            "cost": float(cost_price),
            "stock": received_qty,
            "reorder_level": 5
        }])
        products_df = pd.concat([products_df, new_product], ignore_index=True)
    
    # Save changes
    save_products(products_df)
    save_purchases(purchases_df)
    
    return True, "Stock updated successfully"


def get_po_details(po_number):
    """Get details for a specific purchase order"""
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


def get_supplier_performance():
    """Calculate supplier performance metrics"""
    purchases_df = load_purchases()
    
    if purchases_df.empty:
        return pd.DataFrame()
    
    if "quantity_received" not in purchases_df.columns:
        purchases_df["quantity_received"] = 0
    
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
    
    return supplier_stats.sort_values("Total Spent", ascending=False)


# ============================================================================
# MAIN PAGE
# ============================================================================

def purchases_page():
    """Main purchases management page - Single item version"""
    
    st.title("Purchases Management")
    st.caption("Create purchase orders and receive stock - one item at a time")
    
    # Initialize session state
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
        st.caption("Create a purchase order for a single item")
        
        # Load products for dropdown
        products_df = load_products()
        
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
        
        st.markdown("---")
        st.markdown("### Product Details")
        
        # Product selection
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            if not products_df.empty:
                # Search and select existing product
                search = st.text_input(
                    "Search or enter product name",
                    placeholder="Type product name or barcode...",
                    key="po_search"
                )
                
                filtered_products = products_df.copy()
                if search:
                    filtered_products = products_df[
                        products_df["name"].astype(str).str.contains(search, case=False) |
                        products_df["barcode"].astype(str).str.contains(search, case=False)
                    ]
                
                if not filtered_products.empty:
                    product_options = ["New Product (Manual Entry)"] + [
                        f"{p['name']} - Stock: {p['stock']} - Cost: ${p['cost']:.2f}" 
                        for _, p in filtered_products.iterrows()
                    ]
                    
                    selected_option = st.selectbox("Select Product", product_options)
                    
                    if selected_option and selected_option != "New Product (Manual Entry)":
                        # Extract product name
                        product_name = selected_option.split(" - ")[0]
                        selected_product = filtered_products[filtered_products["name"] == product_name].iloc[0]
                        barcode = str(selected_product["barcode"])
                        cost = float(selected_product["cost"])
                        st.info(f"Selected: {product_name} | Barcode: {barcode} | Current Cost: ${cost:.2f}")
                    else:
                        product_name = ""
                        barcode = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                        cost = 0.0
                else:
                    # Manual entry when no products found
                    product_name = st.text_input("Product Name *", placeholder="Enter product name...")
                    barcode = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    cost = st.number_input("Cost Price ($)", min_value=0.01, value=10.0, step=1.0)
                    st.caption(f"Auto-generated barcode: {barcode}")
            else:
                # Manual entry when no products exist
                product_name = st.text_input("Product Name *", placeholder="Enter product name...")
                barcode = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                cost = st.number_input("Cost Price ($)", min_value=0.01, value=10.0, step=1.0)
                st.caption(f"Auto-generated barcode: {barcode}")
        
        with col2:
            quantity = st.number_input("Quantity *", min_value=1, value=1, step=1)
        
        with col3:
            if cost > 0:
                total_cost = quantity * cost
                st.metric("Total Cost", f"${total_cost:,.2f}")
            else:
                st.metric("Total Cost", "$0.00")
        
        with col4:
            create_po = st.button("Create Purchase Order", type="primary", use_container_width=True)
            
            if create_po:
                # Validate
                if not supplier_name:
                    st.error("Please enter a supplier name")
                elif not product_name:
                    st.error("Please enter a product name")
                else:
                    # Create PO
                    po_df, error = create_purchase_order(
                        supplier=supplier_name,
                        product_name=product_name,
                        barcode=barcode,
                        quantity=quantity,
                        cost=cost,
                        expected_date=expected_date
                    )
                    
                    if error:
                        st.error(error)
                    else:
                        # Save to database
                        try:
                            existing_df = load_purchases()
                            
                            for col in po_df.columns:
                                if col not in existing_df.columns:
                                    existing_df[col] = ""
                            
                            updated_df = pd.concat([existing_df, po_df], ignore_index=True)
                            
                            save_success = save_purchases(updated_df)
                            
                            if save_success:
                                st.session_state.po_created = True
                                st.session_state.last_po_number = po_df.iloc[0]["po_number"]
                                
                                st.success(f"Purchase Order {po_df.iloc[0]['po_number']} created successfully!")
                                
                                # Show PO details
                                st.info(f"""
                                **PO Summary:**
                                - PO Number: {po_df.iloc[0]['po_number']}
                                - Supplier: {supplier_name}
                                - Product: {product_name}
                                - Quantity: {quantity}
                                - Total Cost: ${total_cost:,.2f}
                                - Expected Date: {expected_date}
                                """)
                                
                                st.rerun()
                            else:
                                st.error("Failed to save purchase order to database.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
    
    # ========================================================================
    # TAB 2: RECEIVE STOCK
    # ========================================================================
    with tab2:
        st.markdown("## Receive Stock")
        st.caption("Confirm receipt of stock and update inventory")
        
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            st.info("No purchase orders found. Create a PO first.")
        else:
            if "status" not in purchases_df.columns:
                purchases_df["status"] = "PENDING"
            
            pending_pos = purchases_df[purchases_df["status"] == "PENDING"]["po_number"].unique().tolist()
            
            if not pending_pos:
                st.info("No pending purchase orders. All orders have been received.")
            else:
                selected_po = st.selectbox("Select Purchase Order to Receive", pending_pos, key="receive_po")
                
                if selected_po:
                    po_details = get_po_details(selected_po)
                    
                    if po_details:
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
                        
                        invoice_no = st.text_input("Supplier Invoice Number *", key="invoice_no")
                        
                        # Show receiving form for each item
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
                        
                        if st.button("Confirm Receipt and Update Stock", type="primary", use_container_width=True):
                            if not invoice_no:
                                st.error("Please enter supplier invoice number")
                            else:
                                success_count = 0
                                for item in received_items:
                                    if item["received_qty"] > 0:
                                        success, message = receive_purchase_order(
                                            selected_po,
                                            item["received_qty"],
                                            item["cost"],
                                            item["name"],
                                            item["barcode"],
                                            invoice_no
                                        )
                                        if success:
                                            success_count += 1
                                
                                if success_count > 0:
                                    st.session_state.stock_updated = True
                                    st.session_state.last_received_po = selected_po
                                    st.success(f"Successfully received {success_count} items!")
                                    st.rerun()
                                else:
                                    st.error("No items were received. Please check quantities.")
    
    # ========================================================================
    # TAB 3: SUPPLIER PERFORMANCE
    # ========================================================================
    with tab3:
        st.markdown("## Supplier Performance Dashboard")
        
        supplier_perf = get_supplier_performance()
        
        if supplier_perf.empty:
            st.info("No purchase data available yet.")
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
    
    # ========================================================================
    # TAB 4: PURCHASE HISTORY
    # ========================================================================
    with tab4:
        st.markdown("## Purchase History")
        
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            st.info("No purchase records found.")
        else:
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
# MAIN GUARD
# ============================================================================
if __name__ == "__main__":
    purchases_page()