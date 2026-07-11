# backend/analytics/recommendation_engine.py
"""
Product Recommendation Engine
AI-powered product recommendations using collaborative filtering and association rules
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import Counter
from itertools import combinations
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_customers,
    load_customer_transactions,
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


def get_barcode_column(df):
    """Find barcode column"""
    if df is None or df.empty:
        return None
    for col in ["barcode", "product_barcode", "sku", "code"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    """Find receipt/order column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "order_id", "transaction_id", "invoice_no"]:
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
# RECOMMENDATION ENGINE
# ==============================

class RecommendationEngine:
    """Product Recommendation Engine using association rules and collaborative filtering"""
    
    def __init__(self):
        self.product_pair_counts = {}
        self.product_frequencies = {}
        self.product_categories = {}
        self.product_prices = {}
        self.recommendations_cache = {}
        self.engine_ready = False
        self.last_update = None
    
    def build_association_rules(self, sales_df, products_df, min_support=0.01, min_confidence=0.3):
        """
        Build association rules from sales data.
        Uses Apriori-like algorithm for frequent itemsets.
        """
        
        if sales_df.empty or products_df.empty:
            return False, "No data available"
        
        # Find columns
        product_col = get_product_column(sales_df)
        receipt_col = get_receipt_column(sales_df)
        
        if product_col is None or receipt_col is None:
            return False, "Could not find product or receipt columns"
        
        # Group by receipt
        baskets = sales_df.groupby(receipt_col)[product_col].apply(list).reset_index()
        baskets[product_col] = baskets[product_col].apply(lambda x: list(set(x)))  # Remove duplicates
        
        # Count product frequencies
        all_products = []
        for basket in baskets[product_col]:
            all_products.extend(basket)
        
        self.product_frequencies = Counter(all_products)
        total_baskets = len(baskets)
        
        # Find product pairs
        pair_counter = Counter()
        
        for basket in baskets[product_col]:
            if len(basket) > 1:
                # Sort to avoid duplicates (A,B) vs (B,A)
                basket = sorted(basket)
                for pair in combinations(basket, 2):
                    pair_counter[pair] += 1
        
        # Store pair counts
        self.product_pair_counts = dict(pair_counter)
        
        # Store product info
        product_col_products = get_product_column(products_df)
        barcode_col = get_barcode_column(products_df)
        
        if product_col_products:
            for _, product in products_df.iterrows():
                name = str(product.get(product_col_products, ""))
                if name:
                    self.product_prices[name] = safe_float(product.get("price", 0))
                    self.product_categories[name] = product.get("category", "Uncategorized")
        
        self.engine_ready = True
        self.last_update = datetime.now()
        
        # Calculate support and confidence for stats
        num_pairs = len(pair_counter)
        
        return True, f"Built recommendations from {len(baskets)} transactions, {len(all_products)} products, {num_pairs} product pairs"
    
    def get_frequently_bought_together(self, product_name, top_n=10):
        """Get products frequently bought with a given product"""
        if not self.engine_ready:
            return pd.DataFrame()
        
        recommendations = []
        
        # Find all pairs containing this product
        for (prod_a, prod_b), count in self.product_pair_counts.items():
            if prod_a == product_name:
                recommendations.append({
                    "product": prod_b,
                    "frequency": count,
                    "support": count / len(self.product_frequencies) if self.product_frequencies else 0
                })
            elif prod_b == product_name:
                recommendations.append({
                    "product": prod_a,
                    "frequency": count,
                    "support": count / len(self.product_frequencies) if self.product_frequencies else 0
                })
        
        if not recommendations:
            # Return top selling products as fallback
            return self.get_top_products(top_n)
        
        # Sort by frequency
        recommendations.sort(key=lambda x: x["frequency"], reverse=True)
        
        # Add product info
        for rec in recommendations[:top_n]:
            rec["price"] = self.product_prices.get(rec["product"], 0)
            rec["category"] = self.product_categories.get(rec["product"], "Uncategorized")
        
        return pd.DataFrame(recommendations[:top_n])
    
    def get_top_products(self, top_n=10):
        """Get top selling products"""
        if not self.product_frequencies:
            return pd.DataFrame()
        
        top = []
        for product, count in self.product_frequencies.most_common(top_n):
            top.append({
                "product": product,
                "frequency": count,
                "price": self.product_prices.get(product, 0),
                "category": self.product_categories.get(product, "Uncategorized")
            })
        
        return pd.DataFrame(top)
    
    def get_personalized_recommendations(self, customer_purchases, top_n=10):
        """
        Get personalized recommendations based on customer purchase history.
        Uses collaborative filtering approach.
        """
        if not self.engine_ready or not customer_purchases:
            return self.get_top_products(top_n)
        
        # Get products customer bought
        purchased_products = set(customer_purchases)
        
        # Score potential recommendations
        recommendation_scores = {}
        
        for product in purchased_products:
            # Get products frequently bought with this product
            related = self.get_frequently_bought_together(product, top_n=20)
            
            if not related.empty:
                for _, row in related.iterrows():
                    rec_product = row["product"]
                    # Skip if customer already bought this
                    if rec_product in purchased_products:
                        continue
                    
                    # Score based on frequency and product value
                    score = row["frequency"]
                    
                    # Add price factor (higher value products get slightly more weight)
                    if self.product_prices.get(rec_product, 0) > 50:
                        score *= 1.2
                    
                    recommendation_scores[rec_product] = recommendation_scores.get(rec_product, 0) + score
        
        # Sort by score
        sorted_recs = sorted(recommendation_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for product, score in sorted_recs[:top_n]:
            results.append({
                "product": product,
                "score": score,
                "price": self.product_prices.get(product, 0),
                "category": self.product_categories.get(product, "Uncategorized")
            })
        
        if not results:
            return self.get_top_products(top_n)
        
        return pd.DataFrame(results)
    
    def get_cross_sell_recommendations(self, product_name, top_n=5):
        """Get cross-sell recommendations for a specific product"""
        return self.get_frequently_bought_together(product_name, top_n)
    
    def get_up_sell_recommendations(self, product_name, products_df, top_n=5):
        """Get up-sell recommendations (similar but higher value products)"""
        if not self.engine_ready:
            return pd.DataFrame()
        
        # Get product category and price
        category = self.product_categories.get(product_name, "Uncategorized")
        current_price = self.product_prices.get(product_name, 0)
        
        # Find products in same category with higher price
        similar_products = []
        for prod, price in self.product_prices.items():
            if prod != product_name and self.product_categories.get(prod, "Uncategorized") == category:
                if price > current_price * 1.2:  # At least 20% higher
                    similar_products.append({
                        "product": prod,
                        "price": price,
                        "price_diff": price - current_price,
                        "price_ratio": price / current_price if current_price > 0 else 0
                    })
        
        # Sort by price (highest first)
        similar_products.sort(key=lambda x: x["price"], reverse=True)
        
        # Add frequency score
        for item in similar_products[:top_n]:
            # Check if this product appears in pairs
            freq = 0
            for (a, b), count in self.product_pair_counts.items():
                if a == item["product"] or b == item["product"]:
                    freq += count
            item["frequency"] = freq
            item["category"] = category
        
        return pd.DataFrame(similar_products[:top_n])
    
    def get_recommendations_for_customer(self, customer_name, sales_df, top_n=10):
        """Get complete recommendations for a customer"""
        if not self.engine_ready:
            return pd.DataFrame()
        
        # Find customer's purchases
        product_col = get_product_column(sales_df)
        customer_col = get_customer_column(sales_df)
        
        if product_col is None or customer_col is None:
            return self.get_top_products(top_n)
        
        customer_sales = sales_df[sales_df[customer_col].astype(str).str.contains(
            customer_name, case=False, na=False
        )]
        
        if customer_sales.empty:
            return self.get_top_products(top_n)
        
        customer_products = customer_sales[product_col].tolist()
        
        return self.get_personalized_recommendations(customer_products, top_n)
    
    def get_bundle_recommendations(self, products_in_cart, top_n=3):
        """Get bundle recommendations based on items in cart"""
        if not self.engine_ready or not products_in_cart:
            return pd.DataFrame()
        
        # Get recommendations for each product in cart
        all_recs = {}
        for product in products_in_cart:
            recs = self.get_frequently_bought_together(product, top_n=10)
            if not recs.empty:
                for _, row in recs.iterrows():
                    rec_product = row["product"]
                    if rec_product in products_in_cart:
                        continue
                    all_recs[rec_product] = all_recs.get(rec_product, 0) + row["frequency"]
        
        # Sort and return
        sorted_recs = sorted(all_recs.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for product, score in sorted_recs[:top_n]:
            results.append({
                "product": product,
                "score": score,
                "price": self.product_prices.get(product, 0),
                "category": self.product_categories.get(product, "Uncategorized")
            })
        
        return pd.DataFrame(results)
    
    def get_recommendation_stats(self):
        """Get statistics about the recommendation engine"""
        return {
            "engine_ready": self.engine_ready,
            "last_update": self.last_update,
            "product_count": len(self.product_frequencies),
            "pair_count": len(self.product_pair_counts),
            "top_product": self.product_frequencies.most_common(1)[0][0] if self.product_frequencies else None,
            "top_product_frequency": self.product_frequencies.most_common(1)[0][1] if self.product_frequencies else 0
        }


def get_customer_column(df):
    """Find customer column"""
    if df is None or df.empty:
        return None
    for col in ["customer", "customer_name", "client", "buyer"]:
        if col in df.columns:
            return col
    return None


# ==============================
# RECOMMENDATION DASHBOARD
# ==============================

def recommendation_engine_dashboard():
    """Product Recommendation Engine Dashboard"""
    
    st.title("🛍️ Product Recommendation Engine")
    st.caption("AI-powered product recommendations for cross-selling and up-selling")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access the recommendation engine.")
        return
    
    # Load data
    with st.spinner("Loading data..."):
        sales_df = load_sales()
        products_df = load_products()
        customers_df = load_customers()
        transactions_df = load_customer_transactions()
    
    if sales_df.empty:
        st.warning("No sales data available. Please complete some transactions first.")
        return
    
    if products_df.empty:
        st.warning("No products available. Please add products first.")
        return
    
    # Initialize engine in session state
    if "recommendation_engine" not in st.session_state:
        st.session_state.recommendation_engine = RecommendationEngine()
        st.session_state.recommendation_engine_ready = False
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard",
        "🔍 Product Lookup",
        "👤 Customer Recommendations",
        "📦 Bundle Builder"
    ])
    
    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## 📊 Recommendation Engine Dashboard")
        
        # Check if engine is built
        if not st.session_state.recommendation_engine_ready:
            st.warning("⚠️ Recommendation engine not built. Click below to build.")
            
            if st.button("🚀 Build Recommendation Engine", type="primary", use_container_width=True):
                with st.spinner("Building recommendation engine..."):
                    success, message = st.session_state.recommendation_engine.build_association_rules(
                        sales_df, products_df
                    )
                    if success:
                        st.session_state.recommendation_engine_ready = True
                        st.success(f"✅ {message}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        else:
            # Show stats
            stats = st.session_state.recommendation_engine.get_recommendation_stats()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📦 Products Analyzed", stats.get("product_count", 0))
            with col2:
                st.metric("🔗 Product Pairs", stats.get("pair_count", 0))
            with col3:
                st.metric("🏆 Top Product", stats.get("top_product", "N/A"))
            with col4:
                st.metric("📊 Last Updated", stats.get("last_update", "Never").strftime("%Y-%m-%d") if stats.get("last_update") else "Never")
            
            # Show top products
            st.markdown("---")
            st.markdown("### 🏆 Top Selling Products")
            
            top_products = st.session_state.recommendation_engine.get_top_products(10)
            
            if not top_products.empty:
                fig = px.bar(
                    top_products,
                    x="frequency",
                    y="product",
                    orientation="h",
                    title="Top 10 Products by Purchase Frequency",
                    color="frequency",
                    color_continuous_scale="Blues",
                    text="frequency"
                )
                fig.update_traces(texttemplate="%{text}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    top_products[["product", "frequency", "category", "price"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "price": st.column_config.NumberColumn("Price", format="$%.2f")
                    }
                )
            
            # Rebuild button
            st.markdown("---")
            if st.button("🔄 Rebuild Recommendations", use_container_width=True):
                with st.spinner("Rebuilding..."):
                    success, message = st.session_state.recommendation_engine.build_association_rules(
                        sales_df, products_df
                    )
                    if success:
                        st.session_state.recommendation_engine_ready = True
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
    
    # ==============================
    # TAB 2: PRODUCT LOOKUP
    # ==============================
    with tab2:
        st.markdown("## 🔍 Product Recommendations")
        
        if not st.session_state.recommendation_engine_ready:
            st.warning("⚠️ Recommendation engine not built yet. Build it first in the Dashboard tab.")
        else:
            # Product search
            product_col = get_product_column(products_df)
            
            if product_col:
                search_term = st.text_input("Search Product", placeholder="Type product name...")
                
                # Filter products
                filtered_products = products_df[products_df[product_col].astype(str).str.contains(
                    search_term, case=False, na=False
                )] if search_term else products_df
                
                if not filtered_products.empty:
                    selected_product = st.selectbox(
                        "Select Product",
                        filtered_products[product_col].tolist()
                    )
                    
                    if selected_product:
                        st.markdown(f"### 📦 Recommendations for: {selected_product}")
                        
                        rec_type = st.radio(
                            "Recommendation Type",
                            ["Frequently Bought Together (Cross-sell)", "Up-sell (Higher Value)"],
                            horizontal=True
                        )
                        
                        if rec_type == "Frequently Bought Together (Cross-sell)":
                            recommendations = st.session_state.recommendation_engine.get_cross_sell_recommendations(
                                selected_product, 10
                            )
                        else:
                            recommendations = st.session_state.recommendation_engine.get_up_sell_recommendations(
                                selected_product, products_df, 10
                            )
                        
                        if not recommendations.empty:
                            st.markdown("#### 📋 Recommendations")
                            
                            # Add confidence/score column
                            if "score" not in recommendations.columns:
                                recommendations["score"] = recommendations["frequency"] if "frequency" in recommendations.columns else 0
                            
                            st.dataframe(
                                recommendations[["product", "price", "category", "score"]],
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                                    "score": "Relevance Score"
                                }
                            )
                            
                            # Display as cards
                            st.markdown("#### 🎯 Recommended Products")
                            
                            cols = st.columns(min(3, len(recommendations)))
                            for idx, (_, row) in enumerate(recommendations.head(6).iterrows()):
                                with cols[idx % 3]:
                                    st.markdown(f"""
                                    <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; text-align: center; margin: 5px; border: 1px solid #e5e7eb;">
                                        <h4 style="margin: 0;">📦 {row['product'][:20]}</h4>
                                        <p style="font-size: 20px; color: #2ecc71; margin: 5px 0;">${row['price']:.2f}</p>
                                        <p style="font-size: 11px; color: #666;">{row.get('category', 'Uncategorized')}</p>
                                        <p style="font-size: 12px; color: #999; margin-top: 5px;">🎯 Relevance: {row.get('score', 0):.0f}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                            
                            # Visualization
                            fig = px.bar(
                                recommendations.head(10),
                                x="score" if "score" in recommendations.columns else "frequency",
                                y="product",
                                orientation="h",
                                title="Recommendation Strength",
                                color="price",
                                color_continuous_scale="Viridis",
                                text="price"
                            )
                            fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                            fig.update_layout(height=350)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No recommendations found for this product")
                else:
                    st.info("No products found matching your search")
            else:
                st.warning("Product column not found in data")
    
    # ==============================
    # TAB 3: CUSTOMER RECOMMENDATIONS
    # ==============================
    with tab3:
        st.markdown("## 👤 Personalized Customer Recommendations")
        
        if not st.session_state.recommendation_engine_ready:
            st.warning("⚠️ Recommendation engine not built yet. Build it first in the Dashboard tab.")
        else:
            customer_col = get_customer_column(customers_df)
            
            if customer_col:
                search_customer = st.text_input("Search Customer", placeholder="Type customer name...")
                
                if search_customer:
                    # Find customer
                    customer_results = customers_df[
                        customers_df[customer_col].astype(str).str.contains(search_customer, case=False, na=False)
                    ]
                    
                    if not customer_results.empty:
                        selected_customer = customer_results.iloc[0][customer_col]
                        
                        st.markdown(f"### 🛍️ Recommendations for: {selected_customer}")
                        
                        # Get recommendations
                        recommendations = st.session_state.recommendation_engine.get_recommendations_for_customer(
                            selected_customer, sales_df, 10
                        )
                        
                        if not recommendations.empty:
                            st.markdown("#### 🎯 Recommended Products")
                            
                            # Display as cards
                            cols = st.columns(min(3, len(recommendations)))
                            for idx, (_, row) in enumerate(recommendations.head(6).iterrows()):
                                with cols[idx % 3]:
                                    st.markdown(f"""
                                    <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; text-align: center; margin: 5px; border: 1px solid #e5e7eb;">
                                        <h4 style="margin: 0;">📦 {row['product'][:20]}</h4>
                                        <p style="font-size: 20px; color: #2ecc71; margin: 5px 0;">${row['price']:.2f}</p>
                                        <p style="font-size: 11px; color: #666;">{row.get('category', 'Uncategorized')}</p>
                                        <p style="font-size: 12px; color: #999; margin-top: 5px;">🎯 Score: {row.get('score', 0):.0f}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                            
                            # Show as table
                            st.markdown("#### 📋 Recommendation Details")
                            st.dataframe(
                                recommendations[["product", "price", "category", "score"]],
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "price": st.column_config.NumberColumn("Price", format="$%.2f")
                                }
                            )
                            
                            # Customer purchase history summary
                            st.markdown("#### 📜 Customer Purchase History")
                            
                            customer_sales = sales_df[sales_df[get_customer_column(sales_df)].astype(str).str.contains(
                                selected_customer, case=False, na=False
                            )] if get_customer_column(sales_df) else pd.DataFrame()
                            
                            if not customer_sales.empty:
                                product_col_sales = get_product_column(customer_sales)
                                if product_col_sales:
                                    purchase_summary = customer_sales[product_col_sales].value_counts().reset_index()
                                    purchase_summary.columns = ["Product", "Times Purchased"]
                                    st.dataframe(purchase_summary.head(10), use_container_width=True, hide_index=True)
                        else:
                            st.info("No personalized recommendations found for this customer")
                    else:
                        st.warning("Customer not found")
            else:
                st.warning("Customer column not found")
    
    # ==============================
    # TAB 4: BUNDLE BUILDER
    # ==============================
    with tab4:
        st.markdown("## 📦 Smart Bundle Builder")
        st.caption("Build product bundles based on purchase patterns")
        
        if not st.session_state.recommendation_engine_ready:
            st.warning("⚠️ Recommendation engine not built yet. Build it first in the Dashboard tab.")
        else:
            # Cart builder
            st.markdown("### 🛒 Add Products to Cart")
            
            product_col = get_product_column(products_df)
            
            if product_col:
                cart_products = []
                
                # Product search for cart
                search_cart = st.text_input("Search Product to Add", placeholder="Type product name...")
                
                filtered_cart = products_df[products_df[product_col].astype(str).str.contains(
                    search_cart, case=False, na=False
                )] if search_cart else products_df.head(10)
                
                if not filtered_cart.empty:
                    selected_cart_product = st.selectbox(
                        "Select Product",
                        filtered_cart[product_col].tolist()
                    )
                    
                    if st.button("➕ Add to Cart", use_container_width=True):
                        if selected_cart_product:
                            if "bundle_cart" not in st.session_state:
                                st.session_state.bundle_cart = []
                            if selected_cart_product not in st.session_state.bundle_cart:
                                st.session_state.bundle_cart.append(selected_cart_product)
                                st.success(f"Added {selected_cart_product} to cart")
                            else:
                                st.warning(f"{selected_cart_product} already in cart")
                
                # Display cart
                if "bundle_cart" in st.session_state and st.session_state.bundle_cart:
                    st.markdown("#### 🧾 Current Cart")
                    
                    cart_df = pd.DataFrame({
                        "Product": st.session_state.bundle_cart,
                        "Price": [st.session_state.recommendation_engine.product_prices.get(p, 0) for p in st.session_state.bundle_cart]
                    })
                    
                    st.dataframe(cart_df, use_container_width=True, hide_index=True)
                    st.info(f"💰 Total: ${cart_df['Price'].sum():.2f}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Clear Cart", use_container_width=True):
                            st.session_state.bundle_cart = []
                            st.rerun()
                    
                    with col2:
                        if st.button("🎯 Get Bundle Recommendations", type="primary", use_container_width=True):
                            if len(st.session_state.bundle_cart) >= 2:
                                recommendations = st.session_state.recommendation_engine.get_bundle_recommendations(
                                    st.session_state.bundle_cart, 5
                                )
                                
                                if not recommendations.empty:
                                    st.markdown("#### 🎯 Recommended Add-ons")
                                    
                                    cols = st.columns(min(3, len(recommendations)))
                                    for idx, (_, row) in enumerate(recommendations.iterrows()):
                                        with cols[idx % 3]:
                                            st.markdown(f"""
                                            <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; text-align: center; margin: 5px; border: 1px solid #e5e7eb;">
                                                <h4 style="margin: 0;">📦 {row['product'][:20]}</h4>
                                                <p style="font-size: 20px; color: #2ecc71; margin: 5px 0;">${row['price']:.2f}</p>
                                                <p style="font-size: 11px; color: #666;">{row.get('category', 'Uncategorized')}</p>
                                                <p style="font-size: 12px; color: #999; margin-top: 5px;">🎯 Score: {row.get('score', 0):.0f}</p>
                                                <button style="background:#6366F1;color:white;border:none;border-radius:5px;padding:5px 10px;cursor:pointer;margin-top:5px;">Add to Cart</button>
                                            </div>
                                            """, unsafe_allow_html=True)
                                else:
                                    st.info("No bundle recommendations found")
                            else:
                                st.warning("Add at least 2 products for bundle recommendations")
                else:
                    st.info("Add products to build a bundle")
            else:
                st.warning("Product column not found")


# ==============================
# POS INTEGRATION FUNCTIONS
# ==============================

def get_recommendations_for_pos(cart_products, top_n=5):
    """Get recommendations for POS integration"""
    engine = st.session_state.get("recommendation_engine")
    if not engine or not st.session_state.get("recommendation_engine_ready", False):
        return pd.DataFrame()
    
    return engine.get_bundle_recommendations(cart_products, top_n)


def display_pos_recommendations(cart_products):
    """Display recommendations in POS sidebar"""
    if not cart_products or len(cart_products) < 2:
        return
    
    recs = get_recommendations_for_pos(cart_products, 5)
    
    if not recs.empty:
        st.markdown("### 🎯 You Might Also Like")
        for _, row in recs.iterrows():
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(row["product"][:25])
            with col2:
                st.write(f"${row['price']:.2f}")
            with col3:
                if st.button("➕ Add", key=f"pos_rec_{row['product']}"):
                    return row["product"]
        st.caption("💡 These products are frequently bought together")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    recommendation_engine_dashboard()