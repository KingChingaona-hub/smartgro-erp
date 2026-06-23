import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import numpy as np

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
REPLENISHMENT_FILE = DATA_DIR / "replenishment_settings.json"
AUTO_PO_FILE = DATA_DIR / "auto_purchase_orders.csv"
REPLENISHMENT_LOG_FILE = DATA_DIR / "replenishment_logs.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_replenishment_files():
    """Initialize replenishment-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Replenishment settings
    if not REPLENISHMENT_FILE.exists():
        settings = {
            "auto_replenish": True,
            "reorder_point_multiplier": 1.5,
            "safety_stock_days": 7,
            "lead_time_days": 3,
            "max_order_quantity": 1000,
            "min_order_quantity": 10,
            "supplier_preference": "best_price",
            "auto_approve": False
        }
        with open(REPLENISHMENT_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    
    # Auto PO records
    if not AUTO_PO_FILE.exists():
        df = pd.DataFrame(columns=[
            "po_number", "supplier", "product_name", "product_barcode",
            "quantity", "cost_price", "total_cost", "reorder_level",
            "current_stock", "reason", "status", "created_date",
            "approved_date", "approved_by", "notes"
        ])
        df.to_csv(AUTO_PO_FILE, index=False)
    
    # Replenishment logs
    if not REPLENISHMENT_LOG_FILE.exists():
        df = pd.DataFrame(columns=[
            "log_id", "date", "product_name", "barcode",
            "current_stock", "reorder_level", "recommended_qty",
            "action", "status", "notes"
        ])
        df.to_csv(REPLENISHMENT_LOG_FILE, index=False)


def load_replenishment_settings():
    """Load replenishment settings"""
    init_replenishment_files()
    with open(REPLENISHMENT_FILE, "r") as f:
        return json.load(f)


def save_replenishment_settings(settings):
    """Save replenishment settings"""
    with open(REPLENISHMENT_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_auto_po():
    """Load auto purchase orders"""
    init_replenishment_files()
    return pd.read_csv(AUTO_PO_FILE)


def save_auto_po(df):
    """Save auto purchase orders"""
    df.to_csv(AUTO_PO_FILE, index=False)


def load_replenishment_logs():
    """Load replenishment logs"""
    init_replenishment_files()
    return pd.read_csv(REPLENISHMENT_LOG_FILE)


def save_replenishment_logs(df):
    """Save replenishment logs"""
    df.to_csv(REPLENISHMENT_LOG_FILE, index=False)


# ==============================
# CORE REPLENISHMENT LOGIC
# ==============================
def calculate_reorder_quantity(product, settings, daily_sales_rate):
    """Calculate recommended reorder quantity using EOQ model"""
    
    current_stock = float(product.get("stock", 0))
    reorder_level = float(product.get("reorder_level", 0))
    cost = float(product.get("cost", 0))
    price = float(product.get("price", 0))
    
    # If stock is above reorder level, no need to reorder
    if current_stock > reorder_level:
        return 0, None
    
    # Calculate lead time demand
    lead_time_days = settings.get("lead_time_days", 3)
    safety_stock_days = settings.get("safety_stock_days", 7)
    
    lead_time_demand = daily_sales_rate * lead_time_days
    safety_stock = daily_sales_rate * safety_stock_days
    
    # Calculate Economic Order Quantity (EOQ)
    annual_demand = daily_sales_rate * 365
    ordering_cost = 50  # Assumed fixed cost per order
    holding_cost = cost * 0.25  # 25% of unit cost
    
    if holding_cost > 0:
        eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost)
    else:
        eoq = 0
    
    # Recommended order quantity
    recommended_qty = max(
        eoq,
        lead_time_demand + safety_stock - current_stock
    )
    
    # Apply min/max constraints
    min_qty = settings.get("min_order_quantity", 10)
    max_qty = settings.get("max_order_quantity", 1000)
    
    recommended_qty = max(min_qty, recommended_qty)
    recommended_qty = min(max_qty, recommended_qty)
    
    # Round up to nearest 10
    recommended_qty = int(np.ceil(recommended_qty / 10) * 10)
    
    return recommended_qty, {
        "lead_time_demand": lead_time_demand,
        "safety_stock": safety_stock,
        "eoq": eoq,
        "daily_sales": daily_sales_rate
    }


def get_supplier_for_product(product_name, settings):
    """Get the best supplier for a product"""
    from backend.core.database import load_suppliers, load_purchases
    
    suppliers_df = load_suppliers()
    purchases_df = load_purchases()
    
    if suppliers_df.empty:
        return None
    
    # Get purchase history for this product
    product_purchases = purchases_df[purchases_df["product_name"] == product_name]
    
    if not product_purchases.empty:
        # Find supplier with best price
        best_supplier = product_purchases.groupby("supplier")["cost_price"].min().idxmin()
        return best_supplier
    
    # If no history, use first available supplier
    return suppliers_df.iloc[0]["name"]


def generate_auto_po(product, recommended_qty, supplier, settings):
    """Generate automatic purchase order"""
    
    po_number = f"PO-AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total_cost = float(product["cost"]) * recommended_qty
    
    new_po = pd.DataFrame([{
        "po_number": po_number,
        "supplier": supplier,
        "product_name": product["name"],
        "product_barcode": product["barcode"],
        "quantity": recommended_qty,
        "cost_price": float(product["cost"]),
        "total_cost": total_cost,
        "reorder_level": product.get("reorder_level", 0),
        "current_stock": product.get("stock", 0),
        "reason": f"Auto-replenishment: Stock below reorder level",
        "status": "PENDING_APPROVAL" if not settings.get("auto_approve", False) else "APPROVED",
        "created_date": datetime.now().isoformat(),
        "approved_date": datetime.now().isoformat() if settings.get("auto_approve", False) else "",
        "approved_by": "System" if settings.get("auto_approve", False) else "",
        "notes": f"Auto-generated based on reorder level. Recommended qty: {recommended_qty}"
    }])
    
    return new_po


# ==============================
# SMART REPLENISHMENT DASHBOARD
# ==============================
def smart_replenishment_dashboard():
    """Smart Replenishment Dashboard"""
    
    st.title("📦 Smart Replenishment")
    st.caption("AI-powered automatic purchase order generation and inventory optimization")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access smart replenishment.")
        return
    
    init_replenishment_files()
    
    # Load data
    from backend.core.database import load_products, load_sales, load_suppliers
    
    products_df = load_products()
    sales_df = load_sales()
    suppliers_df = load_suppliers()
    settings = load_replenishment_settings()
    
    if products_df.empty:
        st.warning("No products found. Please add products first.")
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "🔄 Replenishment Recommendations",
        "📋 Auto Purchase Orders",
        "⚙️ Settings",
        "📜 Replenishment Logs"
    ])
    
    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## 📊 Replenishment Dashboard")
        
        # Calculate daily sales rate for each product
        sales_df["date"] = pd.to_datetime(sales_df["date"])
        
        # Products that need replenishment
        products_df["stock"] = pd.to_numeric(products_df["stock"], errors="coerce").fillna(0)
        products_df["reorder_level"] = pd.to_numeric(products_df["reorder_level"], errors="coerce").fillna(0)
        
        # Calculate days of stock
        product_sales = {}
        for product in products_df["name"].unique():
            product_sales_data = sales_df[sales_df["name"] == product]
            if not product_sales_data.empty:
                recent_sales = product_sales_data[product_sales_data["date"] >= datetime.now() - timedelta(days=30)]
                daily_rate = recent_sales["items"].sum() / 30 if not recent_sales.empty else 0
                product_sales[product] = daily_rate
        
        # Calculate replenishment needs
        needs_replenishment = []
        for _, product in products_df.iterrows():
            current_stock = float(product["stock"])
            reorder_level = float(product["reorder_level"])
            daily_rate = product_sales.get(product["name"], 0)
            
            if current_stock <= reorder_level and daily_rate > 0:
                days_of_stock = current_stock / daily_rate if daily_rate > 0 else 0
                needs_replenishment.append({
                    "Product": product["name"],
                    "Barcode": product["barcode"],
                    "Current Stock": current_stock,
                    "Reorder Level": reorder_level,
                    "Daily Sales": daily_rate,
                    "Days of Stock": days_of_stock,
                    "Category": product.get("category", "Uncategorized")
                })
        
        needs_df = pd.DataFrame(needs_replenishment)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔄 Needs Replenishment", len(needs_df))
        with col2:
            st.metric("📦 Total Products", len(products_df))
        with col3:
            total_stock = products_df["stock"].sum()
            st.metric("📊 Total Stock Units", f"{total_stock:,.0f}")
        with col4:
            low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]])
            st.metric("⚠️ Low Stock Items", low_stock)
        
        if not needs_df.empty:
            st.markdown("### 🚨 Products Needing Replenishment")
            
            st.dataframe(
                needs_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Days of Stock": st.column_config.NumberColumn("Days of Stock", format="%.1f"),
                    "Daily Sales": st.column_config.NumberColumn("Daily Sales", format="%.1f")
                }
            )
            
            # Chart
            fig = px.bar(
                needs_df,
                x="Product",
                y="Days of Stock",
                title="Days of Stock Remaining",
                color="Days of Stock",
                color_continuous_scale="RdYlGn_r"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("✅ All products have sufficient stock")
    
    # ==============================
    # TAB 2: REPLENISHMENT RECOMMENDATIONS
    # ==============================
    with tab2:
        st.markdown("## 🔄 Replenishment Recommendations")
        
        # Calculate daily sales rate
        product_sales = {}
        for product in products_df["name"].unique():
            product_sales_data = sales_df[sales_df["name"] == product]
            if not product_sales_data.empty:
                recent_sales = product_sales_data[product_sales_data["date"] >= datetime.now() - timedelta(days=30)]
                daily_rate = recent_sales["items"].sum() / 30 if not recent_sales.empty else 0
                product_sales[product] = daily_rate
        
        # Generate recommendations
        recommendations = []
        for _, product in products_df.iterrows():
            current_stock = float(product["stock"])
            reorder_level = float(product["reorder_level"])
            daily_rate = product_sales.get(product["name"], 0)
            
            if current_stock <= reorder_level and daily_rate > 0:
                recommended_qty, details = calculate_reorder_quantity(product, settings, daily_rate)
                
                if recommended_qty > 0:
                    supplier = get_supplier_for_product(product["name"], settings)
                    
                    recommendations.append({
                        "Product": product["name"],
                        "Barcode": product["barcode"],
                        "Current Stock": current_stock,
                        "Reorder Level": reorder_level,
                        "Daily Sales": daily_rate,
                        "Recommended Qty": recommended_qty,
                        "Suggested Supplier": supplier or "No supplier found",
                        "Estimated Cost": recommended_qty * float(product["cost"]),
                        "Priority": "High" if current_stock < reorder_level * 0.3 else "Medium"
                    })
        
        recommendations_df = pd.DataFrame(recommendations)
        
        if not recommendations_df.empty:
            st.info(f"📋 Found {len(recommendations_df)} products needing replenishment")
            
            st.dataframe(
                recommendations_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Estimated Cost": st.column_config.NumberColumn("Estimated Cost", format="$%.2f")
                }
            )
            
            # Generate PO button
            if st.button("📝 Generate Purchase Orders for All", type="primary", use_container_width=True):
                po_count = 0
                for _, rec in recommendations_df.iterrows():
                    product = products_df[products_df["barcode"] == rec["Barcode"]].iloc[0]
                    supplier = rec["Suggested Supplier"]
                    
                    if supplier and supplier != "No supplier found":
                        new_po = generate_auto_po(product, rec["Recommended Qty"], supplier, settings)
                        df = load_auto_po()
                        df = pd.concat([df, new_po], ignore_index=True)
                        save_auto_po(df)
                        po_count += 1
                
                st.success(f"✅ Generated {po_count} purchase orders!")
                
                # Log
                logs_df = load_replenishment_logs()
                for _, rec in recommendations_df.iterrows():
                    new_log = pd.DataFrame([{
                        "log_id": f"LOG{len(logs_df)+1:08d}",
                        "date": datetime.now().isoformat(),
                        "product_name": rec["Product"],
                        "barcode": rec["Barcode"],
                        "current_stock": rec["Current Stock"],
                        "reorder_level": rec["Reorder Level"],
                        "recommended_qty": rec["Recommended Qty"],
                        "action": "PO_GENERATED",
                        "status": "SUCCESS",
                        "notes": f"Auto PO created for {rec['Recommended Qty']} units"
                    }])
                    logs_df = pd.concat([logs_df, new_log], ignore_index=True)
                save_replenishment_logs(logs_df)
                
                st.rerun()
        else:
            st.success("✅ No replenishment recommendations at this time")
    
    # ==============================
    # TAB 3: AUTO PURCHASE ORDERS
    # ==============================
    with tab3:
        st.markdown("## 📋 Auto Purchase Orders")
        
        po_df = load_auto_po()
        
        if not po_df.empty:
            # Filter by status
            status_filter = st.selectbox("Filter by Status", ["All", "PENDING_APPROVAL", "APPROVED", "REJECTED", "COMPLETED"])
            
            filtered_df = po_df.copy()
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df["status"] == status_filter]
            
            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "total_cost": st.column_config.NumberColumn("Total Cost", format="$%.2f")
                }
            )
            
            # Approve/reject buttons for pending POs
            pending_po = po_df[po_df["status"] == "PENDING_APPROVAL"]
            if not pending_po.empty:
                st.markdown("### 🔄 Pending Approvals")
                
                selected_po = st.selectbox("Select PO to Review", pending_po["po_number"].tolist())
                po_data = pending_po[pending_po["po_number"] == selected_po].iloc[0]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**Product:** {po_data['product_name']}")
                with col2:
                    st.info(f"**Quantity:** {po_data['quantity']}")
                with col3:
                    st.info(f"**Total Cost:** ${po_data['total_cost']:.2f}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve", use_container_width=True):
                        idx = po_df[po_df["po_number"] == selected_po].index[0]
                        po_df.loc[idx, "status"] = "APPROVED"
                        po_df.loc[idx, "approved_date"] = datetime.now().isoformat()
                        po_df.loc[idx, "approved_by"] = st.session_state.get("username", "system")
                        save_auto_po(po_df)
                        st.success("✅ PO Approved!")
                        st.rerun()
                
                with col2:
                    if st.button("❌ Reject", use_container_width=True):
                        idx = po_df[po_df["po_number"] == selected_po].index[0]
                        po_df.loc[idx, "status"] = "REJECTED"
                        save_auto_po(po_df)
                        st.warning("❌ PO Rejected")
                        st.rerun()
        else:
            st.info("No auto purchase orders found")
    
    # ==============================
    # TAB 4: SETTINGS
    # ==============================
    with tab4:
        st.markdown("## ⚙️ Replenishment Settings")
        
        settings = load_replenishment_settings()
        
        col1, col2 = st.columns(2)
        
        with col1:
            auto_replenish = st.checkbox("Enable Auto-Replenishment", value=settings.get("auto_replenish", True))
            reorder_point = st.number_input(
                "Reorder Point Multiplier",
                min_value=1.0,
                max_value=3.0,
                value=float(settings.get("reorder_point_multiplier", 1.5)),
                step=0.1,
                help="Multiplier for reorder point calculation"
            )
            safety_stock = st.number_input(
                "Safety Stock (Days)",
                min_value=1,
                max_value=30,
                value=int(settings.get("safety_stock_days", 7)),
                help="Days of safety stock to maintain"
            )
        
        with col2:
            lead_time = st.number_input(
                "Supplier Lead Time (Days)",
                min_value=1,
                max_value=30,
                value=int(settings.get("lead_time_days", 3)),
                help="Days for supplier delivery"
            )
            min_order = st.number_input(
                "Minimum Order Quantity",
                min_value=1,
                max_value=100,
                value=int(settings.get("min_order_quantity", 10)),
                help="Minimum quantity to order"
            )
            max_order = st.number_input(
                "Maximum Order Quantity",
                min_value=10,
                max_value=10000,
                value=int(settings.get("max_order_quantity", 1000)),
                help="Maximum quantity to order"
            )
        
        auto_approve = st.checkbox("Auto-Approve Purchase Orders", value=settings.get("auto_approve", False))
        supplier_pref = st.selectbox(
            "Supplier Selection Preference",
            ["best_price", "best_rating", "fastest_delivery"],
            index=["best_price", "best_rating", "fastest_delivery"].index(settings.get("supplier_preference", "best_price"))
        )
        
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
            settings.update({
                "auto_replenish": auto_replenish,
                "reorder_point_multiplier": reorder_point,
                "safety_stock_days": safety_stock,
                "lead_time_days": lead_time,
                "min_order_quantity": min_order,
                "max_order_quantity": max_order,
                "auto_approve": auto_approve,
                "supplier_preference": supplier_pref
            })
            save_replenishment_settings(settings)
            st.success("✅ Settings saved successfully!")
            st.rerun()
    
    # ==============================
    # TAB 5: REPLENISHMENT LOGS
    # ==============================
    with tab5:
        st.markdown("## 📜 Replenishment Logs")
        
        logs_df = load_replenishment_logs()
        
        if not logs_df.empty:
            # Format dates
            logs_df["date"] = pd.to_datetime(logs_df["date"])
            logs_df["date"] = logs_df["date"].dt.strftime("%Y-%m-%d %H:%M")
            
            st.dataframe(
                logs_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Export
            csv = logs_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Logs (CSV)",
                data=csv,
                file_name=f"replenishment_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No replenishment logs found")


if __name__ == "__main__":
    smart_replenishment_dashboard()