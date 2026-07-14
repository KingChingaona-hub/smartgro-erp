# backend/analytics/inventory_optimizer.py
"""
Inventory ABC Analysis and Optimization
Classify products by value, optimize stock levels, and reduce holding costs
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_products,
    load_sales,
    load_purchases,
    to_float
)


# ==============================
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_product_column(df):
    """Find product name column"""
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in df.columns:
            return col
    return None


def get_date_column(df):
    """Find date column"""
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def get_quantity_column(df):
    """Find quantity column"""
    if df is None or df.empty:
        return None
    for col in ["items", "quantity", "qty", "item_count"]:
        if col in df.columns:
            return col
    return None


# ==============================
# ABC ANALYSIS ENGINE
# ==============================

class InventoryOptimizer:
    """Inventory optimization using ABC analysis and EOQ"""
    
    def __init__(self):
        self.abc_classification = pd.DataFrame()
        self.analysis_date = None
        self.total_inventory_value = 0
        self.class_counts = {}
        
    def perform_abc_analysis(self, products_df, sales_df, purchases_df):
        """
        Perform ABC analysis on inventory.
        A items: High value (top 20% value, 80% of total)
        B items: Medium value (next 30% value, 15% of total)
        C items: Low value (remaining 50% value, 5% of total)
        """
        
        if products_df.empty:
            return False, "No products found"
        
        # Find columns
        product_col = get_product_column(products_df)
        if product_col is None:
            return False, "Could not find product column"
        
        # Calculate annual usage value
        product_analysis = []
        
        for _, product in products_df.iterrows():
            product_name = product.get(product_col, "")
            stock = safe_float(product.get("stock", 0))
            price = safe_float(product.get("price", 0))
            cost = safe_float(product.get("cost", price * 0.7))
            reorder_level = safe_int(product.get("reorder_level", 5))
            category = product.get("category", "Uncategorized")
            
            # Calculate stock value
            stock_value = stock * cost
            selling_value = stock * price
            potential_profit = selling_value - stock_value
            
            # Calculate annual demand from sales
            annual_demand = 0
            if not sales_df.empty:
                sale_product_col = get_product_column(sales_df)
                qty_col = get_quantity_column(sales_df)
                
                if sale_product_col:
                    product_sales = sales_df[sales_df[sale_product_col].astype(str).str.contains(
                        product_name, case=False, na=False
                    )]
                    
                    if not product_sales.empty and qty_col:
                        annual_demand = safe_int(product_sales[qty_col].sum())
                    else:
                        annual_demand = len(product_sales)
            
            # Calculate annual value (demand * cost)
            annual_value = annual_demand * cost
            
            product_analysis.append({
                "product": product_name,
                "stock": stock,
                "price": price,
                "cost": cost,
                "stock_value": stock_value,
                "selling_value": selling_value,
                "potential_profit": potential_profit,
                "annual_demand": annual_demand,
                "annual_value": annual_value,
                "reorder_level": reorder_level,
                "category": category,
                "barcode": product.get("barcode", "")
            })
        
        analysis_df = pd.DataFrame(product_analysis)
        
        if analysis_df.empty:
            return False, "No data to analyze"
        
        # Sort by annual value (descending)
        analysis_df = analysis_df.sort_values("annual_value", ascending=False)
        
        # Calculate cumulative percentages
        total_annual_value = analysis_df["annual_value"].sum()
        
        if total_annual_value == 0:
            # Fall back to stock value if no sales
            total_annual_value = analysis_df["stock_value"].sum()
            analysis_df["annual_value"] = analysis_df["stock_value"]
            analysis_df = analysis_df.sort_values("stock_value", ascending=False)
        
        cumulative_value = 0
        classifications = []
        
        for _, row in analysis_df.iterrows():
            cumulative_value += row["annual_value"]
            cumulative_percent = (cumulative_value / total_annual_value * 100) if total_annual_value > 0 else 0
            
            if cumulative_percent <= 80:
                classification = "A"
            elif cumulative_percent <= 95:
                classification = "B"
            else:
                classification = "C"
            
            classifications.append({
                "product": row["product"],
                "classification": classification,
                "annual_value": row["annual_value"],
                "cumulative_percent": cumulative_percent,
                **row.to_dict()
            })
        
        self.abc_classification = pd.DataFrame(classifications)
        self.analysis_date = datetime.now()
        self.total_inventory_value = analysis_df["stock_value"].sum()
        
        # Count classifications
        self.class_counts = self.abc_classification["classification"].value_counts().to_dict()
        
        return True, f"Analyzed {len(self.abc_classification)} products"
    
    def get_abc_summary(self):
        """Get summary of ABC analysis"""
        if self.abc_classification.empty:
            return {}
        
        summary = {
            "total_products": len(self.abc_classification),
            "total_value": self.total_inventory_value,
            "analysis_date": self.analysis_date,
            "class_counts": self.class_counts
        }
        
        # Calculate value by class
        value_by_class = self.abc_classification.groupby("classification")["stock_value"].sum().to_dict()
        summary["value_by_class"] = value_by_class
        
        # Calculate percentage by class
        for class_letter in ["A", "B", "C"]:
            count = self.class_counts.get(class_letter, 0)
            summary[f"class_{class_letter}_count"] = count
            summary[f"class_{class_letter}_percent"] = (count / summary["total_products"] * 100) if summary["total_products"] > 0 else 0
        
        return summary
    
    def get_reorder_recommendations(self):
        """Get reorder recommendations based on ABC analysis"""
        if self.abc_classification.empty:
            return pd.DataFrame()
        
        recommendations = []
        
        for _, row in self.abc_classification.iterrows():
            stock = safe_float(row.get("stock", 0))
            reorder_level = safe_int(row.get("reorder_level", 5))
            classification = row.get("classification", "C")
            annual_demand = safe_int(row.get("annual_demand", 0))
            
            # Different strategies per class
            if classification == "A":
                # A items: Tight control, frequent review
                safety_stock = max(5, annual_demand * 0.1 if annual_demand > 0 else 10)
                suggested_reorder = max(10, annual_demand * 0.2 if annual_demand > 0 else 20)
                urgency = "HIGH" if stock <= reorder_level else ("MEDIUM" if stock <= reorder_level * 1.5 else "LOW")
                action = "Review weekly, maintain tight control"
                
            elif classification == "B":
                # B items: Moderate control
                safety_stock = max(3, annual_demand * 0.05 if annual_demand > 0 else 5)
                suggested_reorder = max(5, annual_demand * 0.1 if annual_demand > 0 else 10)
                urgency = "MEDIUM" if stock <= reorder_level else "LOW"
                action = "Review monthly, maintain standard control"
                
            else:
                # C items: Simple control, bulk ordering
                safety_stock = max(1, annual_demand * 0.02 if annual_demand > 0 else 2)
                suggested_reorder = max(3, annual_demand * 0.05 if annual_demand > 0 else 5)
                urgency = "LOW" if stock <= reorder_level else "VERY_LOW"
                action = "Review quarterly, simple ordering"
            
            # Calculate days of stock
            daily_demand = annual_demand / 365 if annual_demand > 0 else 0
            days_of_stock = stock / daily_demand if daily_demand > 0 else 999
            
            recommendations.append({
                "product": row["product"],
                "classification": classification,
                "stock": stock,
                "reorder_level": reorder_level,
                "annual_demand": annual_demand,
                "days_of_stock": round(days_of_stock, 1),
                "safety_stock": safety_stock,
                "suggested_reorder": suggested_reorder,
                "urgency": urgency,
                "action": action,
                "stock_value": row.get("stock_value", 0)
            })
        
        return pd.DataFrame(recommendations)
    
    def get_slow_movers(self, days_threshold=90):
        """Identify slow-moving products"""
        if self.abc_classification.empty:
            return pd.DataFrame()
        
        slow_movers = []
        
        for _, row in self.abc_classification.iterrows():
            annual_demand = safe_int(row.get("annual_demand", 0))
            
            if annual_demand == 0:
                slow_movers.append({
                    "product": row["product"],
                    "classification": row["classification"],
                    "stock": row.get("stock", 0),
                    "stock_value": row.get("stock_value", 0),
                    "annual_demand": 0,
                    "reason": "No sales in period",
                    "suggested_action": "Consider discounting or removal"
                })
            elif annual_demand < 5:
                slow_movers.append({
                    "product": row["product"],
                    "classification": row["classification"],
                    "stock": row.get("stock", 0),
                    "stock_value": row.get("stock_value", 0),
                    "annual_demand": annual_demand,
                    "reason": f"Only {annual_demand} units sold per year",
                    "suggested_action": "Review pricing or promote"
                })
        
        return pd.DataFrame(slow_movers)
    
    def calculate_eoq(self, annual_demand, order_cost=50, holding_cost_percent=0.25):
        """Calculate Economic Order Quantity"""
        if annual_demand <= 0:
            return 0
        
        # Get average cost
        avg_cost = self.abc_classification["cost"].mean() if not self.abc_classification.empty else 10
        holding_cost = avg_cost * holding_cost_percent
        
        if holding_cost <= 0:
            return 0
        
        eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost)
        return int(np.ceil(eoq))
    
    def get_optimization_recommendations(self):
        """Get comprehensive optimization recommendations"""
        if self.abc_classification.empty:
            return []
        
        recommendations = []
        
        # 1. Check A items with low stock
        a_items = self.abc_classification[self.abc_classification["classification"] == "A"]
        a_low_stock = a_items[a_items["stock"] <= a_items["reorder_level"]]
        
        if not a_low_stock.empty:
            recommendations.append({
                "priority": "HIGH",
                "category": "A Items",
                "title": f"{len(a_low_stock)} A items need reordering",
                "description": "These high-value items are below reorder level",
                "action": "Place urgent orders for these items",
                "impact": "Prevents loss of high-value sales"
            })
        
        # 2. Check overstocked items
        overstocked = self.abc_classification[
            (self.abc_classification["stock"] > self.abc_classification["reorder_level"] * 3)
        ]
        
        if not overstocked.empty:
            recommendations.append({
                "priority": "MEDIUM",
                "category": "Overstocked",
                "title": f"{len(overstocked)} items overstocked",
                "description": "These items have excessive stock",
                "action": "Consider running promotions or returning to supplier",
                "impact": "Frees up cash and warehouse space"
            })
        
        # 3. C items with high stock value
        c_items = self.abc_classification[self.abc_classification["classification"] == "C"]
        c_high_value = c_items[c_items["stock_value"] > 100]
        
        if not c_high_value.empty:
            recommendations.append({
                "priority": "MEDIUM",
                "category": "C Items",
                "title": f"{len(c_high_value)} C items with high stock value",
                "description": "Low-value items tying up cash",
                "action": "Review necessity, consider bulk reduction",
                "impact": "Reduces holding costs for low-margin items"
            })
        
        # 4. Slow movers
        slow_movers = self.get_slow_movers()
        if not slow_movers.empty:
            recommendations.append({
                "priority": "MEDIUM",
                "category": "Slow Movers",
                "title": f"{len(slow_movers)} slow-moving products",
                "description": "Products with low or no sales",
                "action": "Run clearance sales or discontinue",
                "impact": "Frees up warehouse space and cash"
            })
        
        # 5. Total inventory value
        if self.total_inventory_value > 10000:
            recommendations.append({
                "priority": "LOW",
                "category": "Inventory Value",
                "title": f"High inventory value: ${self.total_inventory_value:,.2f}",
                "description": "Total inventory value exceeds threshold",
                "action": "Review purchasing patterns and reduce stock levels",
                "impact": "Reduces cash tied up in inventory"
            })
        
        return recommendations


# ==============================
# INVENTORY OPTIMIZER DASHBOARD
# ==============================

def inventory_optimizer_dashboard():
    """Inventory ABC Analysis and Optimization Dashboard"""
    
    st.title("Inventory Optimizer")
    st.caption("ABC analysis, optimization, and inventory intelligence")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access inventory optimizer.")
        return
    
    # Load data
    with st.spinner("Loading data..."):
        products_df = load_products()
        sales_df = load_sales()
        purchases_df = load_purchases()
    
    if products_df.empty:
        st.warning("No products found. Please add products first.")
        return
    
    # Initialize optimizer in session state
    if "inventory_optimizer" not in st.session_state:
        st.session_state.inventory_optimizer = InventoryOptimizer()
        st.session_state.optimizer_ready = False
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "ABC Analysis",
        "Reorder Recommendations",
        "Slow Movers",
        "Optimization Tips",
        "Inventory Metrics"
    ])
    
    # ==============================
    # TAB 1: ABC ANALYSIS
    # ==============================
    with tab1:
        st.markdown("## ABC Analysis")
        
        if not st.session_state.optimizer_ready:
            st.warning("Run ABC analysis to classify your inventory.")
            
            st.info("""
            **ABC Analysis Classifies Products by Value:**
            - **A Items (20% of products, 80% of value)** - High priority, tight control
            - **B Items (30% of products, 15% of value)** - Medium priority, standard control
            - **C Items (50% of products, 5% of value)** - Low priority, simple control
            """)
            
            if st.button("Run ABC Analysis", type="primary", use_container_width=True):
                with st.spinner("Analyzing products..."):
                    success, message = st.session_state.inventory_optimizer.perform_abc_analysis(
                        products_df, sales_df, purchases_df
                    )
                    if success:
                        st.session_state.optimizer_ready = True
                        st.success(f"{message}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"{message}")
        else:
            # Show summary
            summary = st.session_state.inventory_optimizer.get_abc_summary()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Products", summary.get("total_products", 0))
            with col2:
                st.metric("Total Value", f"${summary.get('total_value', 0):,.2f}")
            with col3:
                st.metric("Analyzed", summary.get("analysis_date", datetime.now()).strftime("%Y-%m-%d"))
            with col4:
                total_class = sum(summary.get("class_counts", {}).values())
                st.metric("Classes", f"{len(summary.get('class_counts', {}))}")
            
            st.markdown("---")
            
            # Class distribution
            st.markdown("### Class Distribution")
            
            col1, col2 = st.columns(2)
            
            with col1:
                class_data = []
                for class_letter in ["A", "B", "C"]:
                    count = summary.get(f"class_{class_letter}_count", 0)
                    percent = summary.get(f"class_{class_letter}_percent", 0)
                    class_data.append({
                        "Class": class_letter,
                        "Count": count,
                        "Percent": f"{percent:.1f}%"
                    })
                
                st.dataframe(pd.DataFrame(class_data), use_container_width=True, hide_index=True)
            
            with col2:
                # Pie chart
                fig = px.pie(
                    pd.DataFrame(class_data),
                    values="Count",
                    names="Class",
                    title="Product Distribution by Class",
                    color="Class",
                    color_discrete_map={"A": "#ef4444", "B": "#f59e0b", "C": "#10b981"},
                    hole=0.4
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            
            # Class table
            st.markdown("### ABC Classification")
            
            abc_df = st.session_state.inventory_optimizer.abc_classification.copy()
            
            display_cols = ["product", "classification", "stock", "price", "stock_value", "annual_value", "annual_demand"]
            available_cols = [col for col in display_cols if col in abc_df.columns]
            
            st.dataframe(
                abc_df[available_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "stock_value": st.column_config.NumberColumn("Stock Value", format="$%.2f"),
                    "annual_value": st.column_config.NumberColumn("Annual Value", format="$%.2f"),
                    "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "classification": st.column_config.TextColumn("Class")
                }
            )
            
            # Export
            csv = abc_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download ABC Analysis (CSV)",
                data=csv,
                file_name=f"abc_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            # Re-run analysis button
            if st.button("Re-run Analysis", use_container_width=True):
                with st.spinner("Re-analyzing..."):
                    success, message = st.session_state.inventory_optimizer.perform_abc_analysis(
                        products_df, sales_df, purchases_df
                    )
                    if success:
                        st.session_state.optimizer_ready = True
                        st.success(f"{message}")
                        st.rerun()
                    else:
                        st.error(f"{message}")
    
    # ==============================
    # TAB 2: REORDER RECOMMENDATIONS
    # ==============================
    with tab2:
        st.markdown("## Reorder Recommendations")
        
        if not st.session_state.optimizer_ready:
            st.warning("Run ABC analysis first in the ABC Analysis tab.")
        else:
            recommendations = st.session_state.inventory_optimizer.get_reorder_recommendations()
            
            if not recommendations.empty:
                # Filters
                col1, col2 = st.columns(2)
                with col1:
                    class_filter = st.selectbox("Filter by Class", ["All", "A", "B", "C"])
                with col2:
                    urgency_filter = st.selectbox("Filter by Urgency", ["All", "HIGH", "MEDIUM", "LOW", "VERY_LOW"])
                
                filtered = recommendations.copy()
                if class_filter != "All":
                    filtered = filtered[filtered["classification"] == class_filter]
                if urgency_filter != "All":
                    filtered = filtered[filtered["urgency"] == urgency_filter]
                
                # Show urgent items count
                high_urgency = len(recommendations[recommendations["urgency"] == "HIGH"])
                if high_urgency > 0:
                    st.error(f"{high_urgency} items require URGENT reordering!")
                
                st.dataframe(
                    filtered[["product", "classification", "stock", "reorder_level", "days_of_stock", "urgency", "action"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "urgency": st.column_config.TextColumn("Urgency"),
                        "days_of_stock": st.column_config.NumberColumn("Days of Stock", format="%.1f")
                    }
                )
                
                # Export
                csv = filtered.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Recommendations (CSV)",
                    data=csv,
                    file_name=f"reorder_recommendations_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No reorder recommendations available")
    
    # ==============================
    # TAB 3: SLOW MOVERS
    # ==============================
    with tab3:
        st.markdown("## Slow-Moving Products")
        
        if not st.session_state.optimizer_ready:
            st.warning("Run ABC analysis first in the ABC Analysis tab.")
        else:
            days_threshold = st.slider("Days without sale to classify as slow mover", 30, 180, 90)
            
            slow_movers = st.session_state.inventory_optimizer.get_slow_movers(days_threshold)
            
            if not slow_movers.empty:
                st.warning(f"{len(slow_movers)} products are slow-moving or have no sales")
                
                total_value = slow_movers["stock_value"].sum()
                st.metric("Total value at risk", f"${total_value:,.2f}")
                
                st.dataframe(
                    slow_movers[["product", "classification", "stock", "stock_value", "annual_demand", "reason", "suggested_action"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "stock_value": st.column_config.NumberColumn("Stock Value", format="$%.2f")
                    }
                )
                
                if st.button("Generate Markdown Suggestions", use_container_width=True):
                    st.info("Suggested actions sent to manager's dashboard")
                
                # Export
                csv = slow_movers.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Slow Movers (CSV)",
                    data=csv,
                    file_name=f"slow_movers_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.success("No slow-moving products detected! All products are selling well.")
    
    # ==============================
    # TAB 4: OPTIMIZATION TIPS
    # ==============================
    with tab4:
        st.markdown("## Optimization Recommendations")
        
        if not st.session_state.optimizer_ready:
            st.warning("Run ABC analysis first in the ABC Analysis tab.")
        else:
            recommendations = st.session_state.inventory_optimizer.get_optimization_recommendations()
            
            if recommendations:
                for rec in recommendations:
                    priority = rec.get("priority", "LOW")
                    if priority == "HIGH":
                        st.error(f"### {rec['title']}")
                    elif priority == "MEDIUM":
                        st.warning(f"### {rec['title']}")
                    else:
                        st.info(f"### {rec['title']}")
                    
                    st.write(f"**Category:** {rec['category']}")
                    st.write(f"**Description:** {rec['description']}")
                    st.write(f"**Action:** {rec['action']}")
                    st.write(f"**Impact:** {rec['impact']}")
                    st.markdown("---")
            else:
                st.success("No optimization recommendations at this time. Inventory is well managed!")
    
    # ==============================
    # TAB 5: INVENTORY METRICS
    # ==============================
    with tab5:
        st.markdown("## Inventory Metrics")
        
        if not products_df.empty:
            # Calculate metrics
            total_products = len(products_df)
            total_stock = safe_int(products_df["stock"].sum())
            total_value = safe_float((products_df["stock"] * products_df["price"]).sum())
            
            low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]])
            out_of_stock = len(products_df[products_df["stock"] == 0])
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Products", total_products)
            with col2:
                st.metric("Total Stock Units", f"{total_stock:,}")
            with col3:
                st.metric("Total Stock Value", f"${total_value:,.2f}")
            with col4:
                st.metric("Low Stock Items", low_stock)
            
            st.markdown("---")
            
            # Stock by category
            if "category" in products_df.columns:
                st.markdown("### Stock by Category")
                
                category_summary = products_df.groupby("category").agg({
                    "stock": "sum",
                    "price": "mean"
                }).reset_index()
                
                category_summary["value"] = category_summary["stock"] * category_summary["price"]
                category_summary = category_summary.sort_values("value", ascending=False)
                
                fig = px.bar(
                    category_summary,
                    x="category",
                    y="value",
                    title="Inventory Value by Category",
                    color="value",
                    color_continuous_scale="Viridis",
                    text="value"
                )
                fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # Stock health gauge
            st.markdown("### Stock Health")
            
            if total_products > 0:
                health_score = ((total_products - low_stock - out_of_stock) / total_products * 100)
                health_score = max(0, min(100, health_score))
                
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=health_score,
                    title={"text": "Stock Health Score"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "darkgreen" if health_score > 70 else "orange" if health_score > 40 else "red"},
                        "steps": [
                            {"range": [0, 30], "color": "lightcoral"},
                            {"range": [30, 60], "color": "khaki"},
                            {"range": [60, 100], "color": "lightgreen"}
                        ],
                        "threshold": {
                            "line": {"color": "red", "width": 4},
                            "thickness": 0.75,
                            "value": 90
                        }
                    }
                ))
                fig_gauge.update_layout(height=250)
                st.plotly_chart(fig_gauge, use_container_width=True)
                
                st.caption(f"Health Score: {health_score:.1f}% - {low_stock} items low stock, {out_of_stock} items out of stock")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    inventory_optimizer_dashboard()