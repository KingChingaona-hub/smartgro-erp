# backend/analytics/recommendation_engine.py
"""
Product Recommendation Engine — branch-aware.

Every recommendation is learned from and applied to a single branch. When an
owner explicitly selects "All Branches", the engine trains on the union.

Cache note:
    get_customer_suggestions() and get_customer_phone_mapping() are cached
    with @st.cache_data(ttl=300). They now take branch_id as an argument so
    the cache key includes the branch — HO and NAT no longer share results.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import Counter
from itertools import combinations
import re
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_customers,
    load_customer_transactions,
    load_loyalty,
    load_branches,
    to_float,
)


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("user_branch")
            or st.session_state.get("current_branch_code")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_all_branches(branch_id):
    return isinstance(branch_id, str) and branch_id.upper() == ALL_BRANCHES


def _load_scoped(loader, branch_id, **kwargs):
    if _is_all_branches(branch_id):
        try:
            bdf = load_branches()
        except Exception:
            bdf = pd.DataFrame()
        if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
            try:
                return loader(**kwargs)
            except Exception:
                return pd.DataFrame()
        frames = []
        for bid in bdf["branch_id"].astype(str).tolist():
            try:
                df = loader(branch_id=bid, **kwargs)
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    try:
        return loader(branch_id=branch_id, **kwargs)
    except TypeError:
        try:
            return loader(**kwargs)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _branch_label(branch_id):
    if _is_all_branches(branch_id):
        return "All Branches"
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                return f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()
    except Exception:
        pass
    return str(branch_id)


# ==============================
# HELPERS
# ==============================
def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_product_column(df):
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in df.columns:
            return col
    return None


def get_barcode_column(df):
    if df is None or df.empty:
        return None
    for col in ["barcode", "product_barcode", "sku", "code"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "order_id", "transaction_id", "invoice_no"]:
        if col in df.columns:
            return col
    return None


def get_quantity_column(df):
    if df is None or df.empty:
        return None
    for col in ["items", "quantity", "qty", "item_count"]:
        if col in df.columns:
            return col
    return None


def get_customer_column(df):
    if df is None or df.empty:
        return None
    for col in ["customer_name", "customer", "client", "buyer"]:
        if col in df.columns:
            return col
    return None


# ==============================
# CUSTOMER SUGGESTIONS (cache key includes branch_id)
# ==============================
@st.cache_data(ttl=300)
def get_customer_suggestions(branch_id=None):
    """
    Unique customer names for a branch, sourced from sales data first.
    branch_id is part of the cache key, so HO and NAT do not collide.
    """
    try:
        if branch_id is None or _is_all_branches(branch_id):
            sales_df = _load_scoped(load_sales, branch_id)
        else:
            sales_df = load_sales(branch_id=branch_id)

        if sales_df is not None and not sales_df.empty:
            customer_col = get_customer_column(sales_df)
            if customer_col:
                customers = sales_df[sales_df[customer_col].notna()][customer_col].unique().tolist()
                customers = [
                    str(c).strip() for c in customers
                    if str(c).strip() and str(c).strip().lower() != "walk-in"
                ]
                if customers:
                    return sorted(set(customers))

        # Fallback to customers table
        if branch_id is None or _is_all_branches(branch_id):
            customers_df = _load_scoped(load_customers, branch_id)
        else:
            customers_df = load_customers(branch_id=branch_id)

        if customers_df is not None and not customers_df.empty:
            customer_col = get_customer_column(customers_df)
            if customer_col:
                customers = customers_df[customer_col].dropna().unique().tolist()
                customers = [str(c).strip() for c in customers if str(c).strip()]
                if customers:
                    return sorted(set(customers))

        return []
    except Exception as e:
        print(f"[recommendation_engine] get_customer_suggestions error: {e}")
        return []


@st.cache_data(ttl=300)
def get_customer_phone_mapping(branch_id=None):
    """Customer -> phone mapping for a branch. Cache key includes branch_id."""
    try:
        if branch_id is None or _is_all_branches(branch_id):
            sales_df = _load_scoped(load_sales, branch_id)
        else:
            sales_df = load_sales(branch_id=branch_id)

        if sales_df is None or sales_df.empty:
            return {}

        name_col = get_customer_column(sales_df)
        phone_col = None
        for col in ["customer_phone", "phone", "Phone", "mobile"]:
            if col in sales_df.columns:
                phone_col = col
                break

        if name_col and phone_col:
            mapping = {}
            for _, row in sales_df.iterrows():
                name = str(row.get(name_col, "")).strip()
                phone = str(row.get(phone_col, "")).strip()
                if name and name.lower() != "walk-in" and phone:
                    mapping[name] = phone
            return mapping
        return {}
    except Exception as e:
        print(f"[recommendation_engine] get_customer_phone_mapping error: {e}")
        return {}


# ==============================
# RECOMMENDATION ENGINE (unchanged logic, now branch-tagged)
# ==============================
class RecommendationEngine:
    """Product Recommendation Engine using association rules and collaborative filtering."""

    def __init__(self, branch_id=None):
        self.branch_id = branch_id
        self.product_pair_counts = {}
        self.product_frequencies = {}
        self.product_categories = {}
        self.product_prices = {}
        self.recommendations_cache = {}
        self.engine_ready = False
        self.last_update = None

    def build_association_rules(self, sales_df, products_df, min_support=0.01, min_confidence=0.3):
        """Learn rules from the provided (scoped) sales DataFrame."""
        if sales_df is None or sales_df.empty or products_df is None or products_df.empty:
            return False, "No data available"

        product_col = get_product_column(sales_df)
        receipt_col = get_receipt_column(sales_df)
        if product_col is None or receipt_col is None:
            return False, "Could not find product or receipt columns"

        baskets = sales_df.groupby(receipt_col)[product_col].apply(list).reset_index()
        baskets[product_col] = baskets[product_col].apply(lambda x: list(set(x)))

        all_products = []
        for basket in baskets[product_col]:
            all_products.extend(basket)

        self.product_frequencies = Counter(all_products)

        pair_counter = Counter()
        for basket in baskets[product_col]:
            if len(basket) > 1:
                basket = sorted(basket)
                for pair in combinations(basket, 2):
                    pair_counter[pair] += 1

        self.product_pair_counts = dict(pair_counter)

        product_col_products = get_product_column(products_df)
        if product_col_products:
            for _, product in products_df.iterrows():
                name = str(product.get(product_col_products, ""))
                if name:
                    self.product_prices[name] = safe_float(product.get("price", 0))
                    self.product_categories[name] = product.get("category", "Uncategorized")

        self.engine_ready = True
        self.last_update = datetime.now()
        return True, (
            f"Built recommendations from {len(baskets)} transactions, "
            f"{len(all_products)} products, {len(pair_counter)} product pairs"
        )

    def get_frequently_bought_together(self, product_name, top_n=10):
        if not self.engine_ready:
            return pd.DataFrame()

        recommendations = []
        for (prod_a, prod_b), count in self.product_pair_counts.items():
            if prod_a == product_name:
                recommendations.append({
                    "product": prod_b, "frequency": count,
                    "support": count / len(self.product_frequencies) if self.product_frequencies else 0,
                })
            elif prod_b == product_name:
                recommendations.append({
                    "product": prod_a, "frequency": count,
                    "support": count / len(self.product_frequencies) if self.product_frequencies else 0,
                })

        if not recommendations:
            return self.get_top_products(top_n)

        recommendations.sort(key=lambda x: x["frequency"], reverse=True)
        for rec in recommendations[:top_n]:
            rec["price"] = self.product_prices.get(rec["product"], 0)
            rec["category"] = self.product_categories.get(rec["product"], "Uncategorized")

        return pd.DataFrame(recommendations[:top_n])

    def get_top_products(self, top_n=10):
        if not self.product_frequencies:
            return pd.DataFrame()
        top = []
        for product, count in self.product_frequencies.most_common(top_n):
            top.append({
                "product": product,
                "frequency": count,
                "price": self.product_prices.get(product, 0),
                "category": self.product_categories.get(product, "Uncategorized"),
            })
        return pd.DataFrame(top)

    def get_personalized_recommendations(self, customer_purchases, top_n=10):
        if not self.engine_ready or not customer_purchases:
            return self.get_top_products(top_n)

        purchased_products = set(customer_purchases)
        recommendation_scores = {}

        for product in purchased_products:
            related = self.get_frequently_bought_together(product, top_n=20)
            if not related.empty:
                for _, row in related.iterrows():
                    rec_product = row["product"]
                    if rec_product in purchased_products:
                        continue
                    score = row["frequency"]
                    if self.product_prices.get(rec_product, 0) > 50:
                        score *= 1.2
                    recommendation_scores[rec_product] = recommendation_scores.get(rec_product, 0) + score

        sorted_recs = sorted(recommendation_scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for product, score in sorted_recs[:top_n]:
            results.append({
                "product": product, "score": score,
                "price": self.product_prices.get(product, 0),
                "category": self.product_categories.get(product, "Uncategorized"),
            })
        return pd.DataFrame(results) if results else self.get_top_products(top_n)

    def get_cross_sell_recommendations(self, product_name, top_n=5):
        return self.get_frequently_bought_together(product_name, top_n)

    def get_up_sell_recommendations(self, product_name, products_df, top_n=5):
        if not self.engine_ready:
            return pd.DataFrame()

        category = self.product_categories.get(product_name, "Uncategorized")
        current_price = self.product_prices.get(product_name, 0)

        similar_products = []
        for prod, price in self.product_prices.items():
            if prod != product_name and self.product_categories.get(prod, "Uncategorized") == category:
                if price > current_price * 1.2:
                    similar_products.append({
                        "product": prod, "price": price,
                        "price_diff": price - current_price,
                        "price_ratio": price / current_price if current_price > 0 else 0,
                    })
        similar_products.sort(key=lambda x: x["price"], reverse=True)

        for item in similar_products[:top_n]:
            freq = 0
            for (a, b), count in self.product_pair_counts.items():
                if a == item["product"] or b == item["product"]:
                    freq += count
            item["frequency"] = freq
            item["category"] = category

        return pd.DataFrame(similar_products[:top_n])

    def get_recommendations_for_customer(self, customer_name, sales_df, top_n=10):
        if not self.engine_ready:
            return pd.DataFrame()

        product_col = get_product_column(sales_df)
        customer_col = get_customer_column(sales_df)
        if product_col is None or customer_col is None:
            return self.get_top_products(top_n)

        customer_sales = sales_df[
            sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
        ]
        if customer_sales.empty:
            return self.get_top_products(top_n)

        customer_products = customer_sales[product_col].tolist()
        return self.get_personalized_recommendations(customer_products, top_n)

    def get_bundle_recommendations(self, products_in_cart, top_n=3):
        if not self.engine_ready or not products_in_cart:
            return pd.DataFrame()

        all_recs = {}
        for product in products_in_cart:
            recs = self.get_frequently_bought_together(product, top_n=10)
            if not recs.empty:
                for _, row in recs.iterrows():
                    rec_product = row["product"]
                    if rec_product in products_in_cart:
                        continue
                    all_recs[rec_product] = all_recs.get(rec_product, 0) + row["frequency"]

        sorted_recs = sorted(all_recs.items(), key=lambda x: x[1], reverse=True)
        results = []
        for product, score in sorted_recs[:top_n]:
            results.append({
                "product": product, "score": score,
                "price": self.product_prices.get(product, 0),
                "category": self.product_categories.get(product, "Uncategorized"),
            })
        return pd.DataFrame(results)

    def get_recommendation_stats(self):
        return {
            "engine_ready": self.engine_ready,
            "last_update": self.last_update,
            "product_count": len(self.product_frequencies),
            "pair_count": len(self.product_pair_counts),
            "top_product": (
                self.product_frequencies.most_common(1)[0][0]
                if self.product_frequencies else None
            ),
            "top_product_frequency": (
                self.product_frequencies.most_common(1)[0][1]
                if self.product_frequencies else 0
            ),
            "branch_id": self.branch_id,
        }


# ==============================
# DASHBOARD
# ==============================
def recommendation_engine_dashboard():
    st.title("Product Recommendation Engine")
    st.caption("AI-powered product recommendations for cross-selling and up-selling — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access the recommendation engine.")
        return

    # ---- Branch scope ----
    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        branch_options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})" for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            branch_options,
            key="rec_branch_scope",
            help="Owners may build rules company-wide or for a single branch.",
        )
        if choice == "All Branches":
            branch_id = ALL_BRANCHES
            branch_label = "All Branches"
        else:
            m = re.search(r"\(([^)]+)\)\s*$", choice)
            branch_id = m.group(1).strip() if m else choice
            branch_label = choice
    else:
        branch_id = _resolve_branch(None)
        branch_label = _branch_label(branch_id)
        st.info(f"Recommendation engine locked to your branch: **{branch_label}**")

    st.caption(f"Recommendation scope: **{branch_label}**")

    # ---- Scoped loads ----
    with st.spinner("Loading data..."):
        sales_df = _load_scoped(load_sales, branch_id)
        products_df = _load_scoped(load_products, branch_id)
        customers_df = _load_scoped(load_customers, branch_id)
        transactions_df = _load_scoped(load_customer_transactions, branch_id)

    if sales_df is None or sales_df.empty:
        st.warning(f"No sales data available for {branch_label}. Complete some transactions first.")
        return
    if products_df is None or products_df.empty:
        st.warning(f"No products available for {branch_label}. Add products first.")
        return

    # ---- Per-branch engine state ----
    engine_key = f"recommendation_engine_{branch_id}"
    ready_key = f"recommendation_engine_ready_{branch_id}"

    if engine_key not in st.session_state:
        st.session_state[engine_key] = RecommendationEngine(branch_id=branch_id)
        st.session_state[ready_key] = False

    tab1, tab2, tab3, tab4 = st.tabs([
        "Dashboard", "Product Lookup", "Customer Recommendations", "Bundle Builder",
    ])

    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## Recommendation Engine Dashboard")
        st.caption(f"Branch: **{branch_label}**")

        if not st.session_state.get(ready_key, False):
            st.warning(f"Recommendation engine not built for {branch_label}. Click below to build.")

            if st.button("Build Recommendation Engine", type="primary", use_container_width=True,
                         key=f"rec_build_{branch_id}"):
                with st.spinner(f"Building engine for {branch_label}..."):
                    success, message = st.session_state[engine_key].build_association_rules(
                        sales_df, products_df,
                    )
                    if success:
                        st.session_state[ready_key] = True
                        st.success(message)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(message)
        else:
            stats = st.session_state[engine_key].get_recommendation_stats()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Products Analyzed", stats.get("product_count", 0))
            with col2:
                st.metric("Product Pairs", stats.get("pair_count", 0))
            with col3:
                st.metric("Top Product", stats.get("top_product", "N/A"))
            with col4:
                lu = stats.get("last_update")
                st.metric("Last Updated", lu.strftime("%Y-%m-%d") if lu else "Never")

            st.markdown("---")
            st.markdown("### Top Selling Products")

            top_products = st.session_state[engine_key].get_top_products(10)
            if not top_products.empty:
                fig = px.bar(
                    top_products, x="frequency", y="product", orientation="h",
                    title=f"Top 10 Products by Purchase Frequency — {branch_label}",
                    color="frequency", color_continuous_scale="Blues", text="frequency",
                )
                fig.update_traces(texttemplate="%{text}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

                st.dataframe(
                    top_products[["product", "frequency", "category", "price"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    },
                )

            st.markdown("---")
            if st.button("Rebuild Recommendations", use_container_width=True,
                         key=f"rec_rebuild_{branch_id}"):
                with st.spinner("Rebuilding..."):
                    success, message = st.session_state[engine_key].build_association_rules(
                        sales_df, products_df,
                    )
                    if success:
                        st.session_state[ready_key] = True
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    # ==============================
    # TAB 2: PRODUCT LOOKUP
    # ==============================
    with tab2:
        st.markdown("## Product Recommendations")
        st.caption(f"Branch: **{branch_label}**")

        if not st.session_state.get(ready_key, False):
            st.warning("Recommendation engine not built yet. Build it first in the Dashboard tab.")
        else:
            product_col = get_product_column(products_df)
            if product_col:
                search_term = st.text_input(
                    "Search Product", placeholder="Type product name...",
                    key=f"rec_search_{branch_id}",
                )
                filtered_products = (
                    products_df[products_df[product_col].astype(str).str.contains(
                        search_term, case=False, na=False
                    )] if search_term else products_df
                )

                if not filtered_products.empty:
                    selected_product = st.selectbox(
                        "Select Product",
                        filtered_products[product_col].tolist(),
                        key=f"rec_product_{branch_id}",
                    )
                    if selected_product:
                        st.markdown(f"### Recommendations for: {selected_product}")
                        rec_type = st.radio(
                            "Recommendation Type",
                            ["Frequently Bought Together (Cross-sell)", "Up-sell (Higher Value)"],
                            horizontal=True, key=f"rec_type_{branch_id}",
                        )
                        if rec_type == "Frequently Bought Together (Cross-sell)":
                            recommendations = st.session_state[engine_key].get_cross_sell_recommendations(
                                selected_product, 10,
                            )
                        else:
                            recommendations = st.session_state[engine_key].get_up_sell_recommendations(
                                selected_product, products_df, 10,
                            )

                        if not recommendations.empty:
                            st.markdown("#### Recommendations")
                            if "score" not in recommendations.columns:
                                recommendations["score"] = (
                                    recommendations["frequency"]
                                    if "frequency" in recommendations.columns else 0
                                )
                            st.dataframe(
                                recommendations[["product", "price", "category", "score"]],
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                                    "score": "Relevance Score",
                                },
                            )

                            st.markdown("#### Recommended Products")
                            cols = st.columns(min(3, len(recommendations)))
                            for idx, (_, row) in enumerate(recommendations.head(6).iterrows()):
                                with cols[idx % 3]:
                                    st.markdown(f"""
                                    <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; text-align: center; margin: 5px; border: 1px solid #e5e7eb;">
                                        <h4 style="margin: 0;">{row['product'][:20]}</h4>
                                        <p style="font-size: 20px; color: #2ecc71; margin: 5px 0;">${row['price']:.2f}</p>
                                        <p style="font-size: 11px; color: #666;">{row.get('category', 'Uncategorized')}</p>
                                        <p style="font-size: 12px; color: #999; margin-top: 5px;">Score: {row.get('score', 0):.0f}</p>
                                    </div>
                                    """, unsafe_allow_html=True)

                            fig = px.bar(
                                recommendations.head(10),
                                x="score" if "score" in recommendations.columns else "frequency",
                                y="product", orientation="h",
                                title=f"Recommendation Strength — {branch_label}",
                                color="price", color_continuous_scale="Viridis", text="price",
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
        st.markdown("## Personalized Customer Recommendations")
        st.caption(f"Branch: **{branch_label}**")

        if not st.session_state.get(ready_key, False):
            st.warning("Recommendation engine not built yet. Build it first in the Dashboard tab.")
        else:
            customer_suggestions = get_customer_suggestions(branch_id)
            customer_phones = get_customer_phone_mapping(branch_id)

            st.markdown("### Select Customer")
            if customer_suggestions:
                selected_customer = st.selectbox(
                    "Select Customer",
                    options=[""] + customer_suggestions,
                    key=f"rec_customer_{branch_id}",
                )
            else:
                selected_customer = st.text_input(
                    "Enter Customer Name", key=f"rec_customer_text_{branch_id}",
                )
                st.caption(f"No existing customers found in {branch_label}. Type the customer name.")

            if selected_customer:
                st.markdown(f"### Recommendations for: {selected_customer}")
                if selected_customer in customer_phones:
                    st.caption(f"Phone: {customer_phones[selected_customer]}")
                else:
                    st.caption("No phone number found for this customer")

                recommendations = st.session_state[engine_key].get_recommendations_for_customer(
                    selected_customer, sales_df, 10,
                )

                if not recommendations.empty:
                    st.markdown("#### Recommended Products")
                    cols = st.columns(min(3, len(recommendations)))
                    for idx, (_, row) in enumerate(recommendations.head(6).iterrows()):
                        with cols[idx % 3]:
                            st.markdown(f"""
                            <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; text-align: center; margin: 5px; border: 1px solid #e5e7eb;">
                                <h4 style="margin: 0;">{row['product'][:20]}</h4>
                                <p style="font-size: 20px; color: #2ecc71; margin: 5px 0;">${row['price']:.2f}</p>
                                <p style="font-size: 11px; color: #666;">{row.get('category', 'Uncategorized')}</p>
                                <p style="font-size: 12px; color: #999; margin-top: 5px;">Score: {row.get('score', 0):.0f}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    st.markdown("#### Recommendation Details")
                    st.dataframe(
                        recommendations[["product", "price", "category", "score"]],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                        },
                    )

                    st.markdown("#### Customer Purchase History")
                    customer_col = get_customer_column(sales_df)
                    if customer_col:
                        customer_sales = sales_df[sales_df[customer_col].astype(str).str.contains(
                            selected_customer, case=False, na=False
                        )]
                        if not customer_sales.empty:
                            product_col_sales = get_product_column(customer_sales)
                            if product_col_sales:
                                purchase_summary = (
                                    customer_sales[product_col_sales]
                                    .value_counts().reset_index()
                                )
                                purchase_summary.columns = ["Product", "Times Purchased"]
                                st.dataframe(purchase_summary.head(10),
                                             use_container_width=True, hide_index=True)
                        else:
                            st.info("No purchase history found for this customer")
                else:
                    st.info("No personalized recommendations found for this customer")

    # ==============================
    # TAB 4: BUNDLE BUILDER
    # ==============================
    with tab4:
        st.markdown("## Smart Bundle Builder")
        st.caption(f"Branch: **{branch_label}** — build product bundles based on purchase patterns")

        if not st.session_state.get(ready_key, False):
            st.warning("Recommendation engine not built yet. Build it first in the Dashboard tab.")
        else:
            product_col = get_product_column(products_df)
            if product_col:
                cart_key = f"bundle_cart_{branch_id}"
                if cart_key not in st.session_state:
                    st.session_state[cart_key] = []

                st.markdown("### Add Products to Cart")
                search_cart = st.text_input(
                    "Search Product to Add", placeholder="Type product name...",
                    key=f"cart_search_{branch_id}",
                )
                filtered_cart = (
                    products_df[products_df[product_col].astype(str).str.contains(
                        search_cart, case=False, na=False
                    )] if search_cart else products_df.head(10)
                )

                if not filtered_cart.empty:
                    selected_cart_product = st.selectbox(
                        "Select Product",
                        filtered_cart[product_col].tolist(),
                        key=f"cart_product_{branch_id}",
                    )
                    if st.button("Add to Cart", use_container_width=True,
                                 key=f"add_to_cart_{branch_id}"):
                        if selected_cart_product:
                            if selected_cart_product not in st.session_state[cart_key]:
                                st.session_state[cart_key].append(selected_cart_product)
                                st.success(f"Added {selected_cart_product} to cart")
                            else:
                                st.warning(f"{selected_cart_product} already in cart")

                if st.session_state[cart_key]:
                    st.markdown("#### Current Cart")
                    cart_df = pd.DataFrame({
                        "Product": st.session_state[cart_key],
                        "Price": [
                            st.session_state[engine_key].product_prices.get(p, 0)
                            for p in st.session_state[cart_key]
                        ],
                    })
                    st.dataframe(cart_df, use_container_width=True, hide_index=True)
                    st.info(f"Total: ${cart_df['Price'].sum():.2f}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Clear Cart", use_container_width=True,
                                     key=f"clear_cart_{branch_id}"):
                            st.session_state[cart_key] = []
                            st.rerun()
                    with col2:
                        if st.button("Get Bundle Recommendations", type="primary",
                                     use_container_width=True, key=f"get_bundle_{branch_id}"):
                            if len(st.session_state[cart_key]) >= 2:
                                recommendations = st.session_state[engine_key].get_bundle_recommendations(
                                    st.session_state[cart_key], 5,
                                )
                                if not recommendations.empty:
                                    st.markdown("#### Recommended Add-ons")
                                    cols = st.columns(min(3, len(recommendations)))
                                    for idx, (_, row) in enumerate(recommendations.iterrows()):
                                        with cols[idx % 3]:
                                            st.markdown(f"""
                                            <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; text-align: center; margin: 5px; border: 1px solid #e5e7eb;">
                                                <h4 style="margin: 0;">{row['product'][:20]}</h4>
                                                <p style="font-size: 20px; color: #2ecc71; margin: 5px 0;">${row['price']:.2f}</p>
                                                <p style="font-size: 11px; color: #666;">{row.get('category', 'Uncategorized')}</p>
                                                <p style="font-size: 12px; color: #999; margin-top: 5px;">Score: {row.get('score', 0):.0f}</p>
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
# POS INTEGRATION
# ==============================
def get_recommendations_for_pos(cart_products, branch_id=None, top_n=5):
    """Get recommendations for POS integration — branch-scoped."""
    branch_id = _resolve_branch(branch_id)
    engine_key = f"recommendation_engine_{branch_id}"
    ready_key = f"recommendation_engine_ready_{branch_id}"

    engine = st.session_state.get(engine_key)
    if not engine or not st.session_state.get(ready_key, False):
        return pd.DataFrame()
    return engine.get_bundle_recommendations(cart_products, top_n)


def display_pos_recommendations(cart_products, branch_id=None):
    """Display recommendations in POS sidebar — branch-scoped."""
    if not cart_products or len(cart_products) < 2:
        return

    recs = get_recommendations_for_pos(cart_products, branch_id, 5)
    if not recs.empty:
        st.markdown("### You Might Also Like")
        for _, row in recs.iterrows():
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(row["product"][:25])
            with col2:
                st.write(f"${row['price']:.2f}")
            with col3:
                if st.button("Add", key=f"pos_rec_{row['product']}"):
                    return row["product"]
        st.caption("These products are frequently bought together")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    recommendation_engine_dashboard()