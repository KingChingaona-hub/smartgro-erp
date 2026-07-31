# backend/analytics/profit_center.py
# Profit Center Analysis - With proper deduplication

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from decimal import Decimal
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import load_sales, load_products, load_customers, load_branches

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


def safe_str(value, default=""):
    """Safely convert value to string"""
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default


def convert_decimal_to_float(df):
    """Convert all Decimal columns to float for compatibility"""
    if df is None or df.empty:
        return df
    
    try:
        for col in df.columns:
            if df[col].dtype == object:
                sample = df[col].iloc[0] if len(df) > 0 else None
                if sample is not None and isinstance(sample, Decimal):
                    df[col] = df[col].astype(float)
    except Exception as e:
        print(f"Error converting decimals: {e}")
    
    return df


def find_column(df, possible_names, default=None):
    """Find the first column that matches any of the possible names"""
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return default


def get_sales_data():
    """Load and prepare sales data with proper column handling and deduplication"""
    try:
        sales_df = load_sales()
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Convert Decimal columns to float
        sales_df = convert_decimal_to_float(sales_df)
        
        # Find date column
        date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
        
        if date_col is None:
            return pd.DataFrame()
        
        # Convert date column
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Find receipt column for deduplication
        receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
        
        # ============================================================
        # DEDUPLICATION: Use unique receipts to avoid duplicates
        # ============================================================
        if receipt_col:
            # Drop duplicates by receipt number (keep first occurrence)
            sales_df = sales_df.drop_duplicates(subset=[receipt_col], keep="first")
        
        # Rename to standard 'date' for consistency
        if date_col != "date":
            sales_df["date"] = sales_df[date_col]
        
        # Find total column
        total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
        
        if total_col and total_col != "total":
            sales_df["total"] = pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0)
        elif not total_col:
            sales_df["total"] = 0
        
        # Ensure total is float
        sales_df["total"] = sales_df["total"].astype(float)
        
        # Find profit column
        profit_col = find_column(sales_df, ["profit", "profit_margin", "gross_profit"])
        
        if profit_col and profit_col != "profit":
            sales_df["profit"] = pd.to_numeric(sales_df[profit_col], errors="coerce").fillna(0)
        elif not profit_col:
            sales_df["profit"] = 0
        
        # Ensure profit is float
        sales_df["profit"] = sales_df["profit"].astype(float)
        
        # Find items column
        items_col = find_column(sales_df, ["items", "quantity", "qty", "item_count"])
        
        if items_col and items_col != "items":
            sales_df["items"] = pd.to_numeric(sales_df[items_col], errors="coerce").fillna(1)
        elif not items_col:
            sales_df["items"] = 1
        
        # Ensure items is int
        sales_df["items"] = sales_df["items"].astype(int)
        
        # Find product name column
        product_col = find_column(sales_df, ["name", "product_name", "Product", "item_name"])
        
        if product_col and product_col != "name":
            sales_df["name"] = sales_df[product_col].fillna("Unknown")
        elif not product_col:
            sales_df["name"] = "Unknown"
        
        sales_df["name"] = sales_df["name"].astype(str)
        
        # Find payment method column
        payment_col = find_column(sales_df, ["payment_method", "payment_type", "payment"])
        
        if payment_col and payment_col != "payment_method":
            sales_df["payment_method"] = sales_df[payment_col].fillna("CASH")
        elif not payment_col:
            sales_df["payment_method"] = "CASH"
        
        # Find customer column
        customer_col = find_column(sales_df, ["customer", "customer_name"])
        
        if customer_col and customer_col != "customer":
            sales_df["customer"] = sales_df[customer_col].fillna("Walk-in")
        elif not customer_col:
            sales_df["customer"] = "Walk-in"
        
        # Store receipt column for unique transactions
        if receipt_col:
            sales_df["receipt_no"] = sales_df[receipt_col].fillna("")
        else:
            sales_df["receipt_no"] = sales_df.index.astype(str)
        
        return sales_df
    except Exception as e:
        print(f"Error loading sales data: {e}")
        return pd.DataFrame()


def profit_center_analysis():
    """Main profit center analysis dashboard - With deduplication"""
    
    st.title("Profit Center Analysis")
    st.caption("Analyze profitability by product, category, payment method, and time")
    
    # Load data
    sales_df = get_sales_data()
    
    if sales_df.empty:
        st.warning("No sales data available for profit analysis")
        return
    
    products_df = load_products()
    
    if not products_df.empty:
        products_df = convert_decimal_to_float(products_df)
    
    # ==============================
    # SIDEBAR FILTERS
    # ==============================
    st.sidebar.header("Filters")
    
    # Date filter
    min_date = sales_df["date"].min().date()
    max_date = sales_df["date"].max().date()
    
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # Apply date filter
    filtered_df = sales_df.copy()
    
    if isinstance(date_range, tuple) and len(date_range) == 2:
        try:
            start_date, end_date = date_range
            mask = (filtered_df["date"].dt.date >= start_date) & (filtered_df["date"].dt.date <= end_date)
            filtered_df = filtered_df[mask].copy()
        except Exception:
            pass
    
    if filtered_df.empty:
        st.warning("No data matches the date filter")
        return
    
    # Product filter
    if "name" in filtered_df.columns and not filtered_df.empty:
        products = ["All Products"] + sorted(filtered_df["name"].unique().tolist())
        selected_product = st.sidebar.selectbox("Select Product", products)
        
        if selected_product != "All Products" and selected_product in filtered_df["name"].values:
            filtered_df = filtered_df[filtered_df["name"] == selected_product]
    
    # Payment method filter
    if "payment_method" in filtered_df.columns and not filtered_df.empty:
        payment_methods = ["All"] + sorted(filtered_df["payment_method"].unique().tolist())
        selected_payment = st.sidebar.selectbox("Payment Method", payment_methods)
        
        if selected_payment != "All" and selected_payment in filtered_df["payment_method"].values:
            filtered_df = filtered_df[filtered_df["payment_method"] == selected_payment]
    
    if filtered_df.empty:
        st.warning("No data matches the selected filters")
        return
    
    # ==============================
    # KEY METRICS - Using unique receipts
    # ==============================
    st.markdown("## Key Profit Metrics")
    
    # Get unique receipts for transaction count
    unique_receipts = filtered_df.drop_duplicates(subset=['receipt_no']) if 'receipt_no' in filtered_df.columns else filtered_df
    total_transactions = len(unique_receipts)
    
    # Calculate totals using unique receipts
    if 'receipt_no' in filtered_df.columns:
        # Group by receipt to get per-transaction totals
        receipt_totals = filtered_df.groupby('receipt_no').agg({
            'total': 'first',
            'profit': 'first'
        }).reset_index()
        total_revenue = safe_float(receipt_totals['total'].sum())
        total_profit = safe_float(receipt_totals['profit'].sum())
    else:
        total_revenue = safe_float(filtered_df["total"].sum())
        total_profit = safe_float(filtered_df["profit"].sum())
    
    total_items = safe_int(filtered_df["items"].sum())
    
    # Calculate profit margin
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Average transaction value
    avg_transaction = total_revenue / total_transactions if total_transactions > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    
    with col2:
        st.metric("Total Profit", f"${total_profit:,.2f}")
    
    with col3:
        st.metric("Profit Margin", f"{profit_margin:.1f}%")
    
    with col4:
        st.metric("Avg Transaction", f"${avg_transaction:.2f}")
    
    st.markdown("---")
    
    # ==============================
    # PROFIT BY CATEGORY / PRODUCT
    # ==============================
    st.markdown("## Profit by Product")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top 10 products by profit
        product_profit = filtered_df.groupby("name").agg({
            "profit": "sum",
            "total": "sum",
            "items": "sum"
        }).reset_index()
        
        product_profit["profit"] = product_profit["profit"].astype(float)
        product_profit["total"] = product_profit["total"].astype(float)
        product_profit["items"] = product_profit["items"].astype(float)
        
        product_profit["margin"] = product_profit.apply(
            lambda x: (x["profit"] / x["total"] * 100) if x["total"] > 0 else 0, axis=1
        )
        product_profit = product_profit.sort_values("profit", ascending=False).head(10)
        
        if not product_profit.empty:
            fig = px.bar(
                product_profit,
                x="profit",
                y="name",
                orientation='h',
                title="Top 10 Products by Profit",
                color="profit",
                color_continuous_scale="Greens",
                text="profit"
            )
            fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No product profit data available")
    
    with col2:
        # Profit margin by product
        product_margin = product_profit.sort_values("margin", ascending=False).head(10)
        
        if not product_margin.empty:
            fig = px.bar(
                product_margin,
                x="margin",
                y="name",
                orientation='h',
                title="Top 10 Products by Profit Margin",
                color="margin",
                color_continuous_scale="Blues",
                text="margin"
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No product margin data available")
    
    st.markdown("---")
    
    # ==============================
    # PROFIT BY PAYMENT METHOD
    # ==============================
    if "payment_method" in filtered_df.columns:
        st.markdown("## Profit by Payment Method")
        
        # Use unique receipts for payment method analysis
        if 'receipt_no' in filtered_df.columns:
            unique_by_payment = filtered_df.drop_duplicates(subset=['receipt_no', 'payment_method'])
            payment_profit = unique_by_payment.groupby("payment_method").agg({
                "profit": "sum",
                "total": "sum",
                "receipt_no": "nunique"
            }).reset_index()
        else:
            payment_profit = filtered_df.groupby("payment_method").agg({
                "profit": "sum",
                "total": "sum",
                "receipt_no": "count"
            }).reset_index()
        
        payment_profit["profit"] = payment_profit["profit"].astype(float)
        payment_profit["total"] = payment_profit["total"].astype(float)
        payment_profit["margin"] = payment_profit.apply(
            lambda x: (x["profit"] / x["total"] * 100) if x["total"] > 0 else 0, axis=1
        )
        payment_profit["avg_transaction"] = payment_profit.apply(
            lambda x: x["total"] / x["receipt_no"] if x["receipt_no"] > 0 else 0, axis=1
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if not payment_profit.empty and payment_profit["profit"].sum() > 0:
                fig = px.pie(
                    payment_profit,
                    values="profit",
                    names="payment_method",
                    title="Profit Distribution by Payment Method",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No profit data available by payment method")
        
        with col2:
            if not payment_profit.empty:
                st.dataframe(
                    payment_profit[["payment_method", "profit", "total", "margin", "avg_transaction"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "payment_method": "Payment Method",
                        "profit": st.column_config.NumberColumn("Profit", format="$%.2f"),
                        "total": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                        "margin": st.column_config.NumberColumn("Margin", format="%.1f%%"),
                        "avg_transaction": st.column_config.NumberColumn("Avg Transaction", format="$%.2f")
                    }
                )
        
        st.markdown("---")
    
    # ==============================
    # PROFIT TREND OVER TIME
    # ==============================
    st.markdown("## Profit Trend Over Time")
    
    # Use unique receipts for daily aggregation
    if 'receipt_no' in filtered_df.columns:
        # Get unique receipts per day
        daily_data = filtered_df.drop_duplicates(subset=['receipt_no', 'date'])
        daily_profit = daily_data.groupby(daily_data["date"].dt.date).agg({
            "profit": "sum",
            "total": "sum",
            "items": "sum"
        }).reset_index()
    else:
        daily_profit = filtered_df.groupby(filtered_df["date"].dt.date).agg({
            "profit": "sum",
            "total": "sum",
            "items": "sum"
        }).reset_index()
    
    daily_profit.columns = ["date", "profit", "revenue", "items"]
    
    daily_profit["profit"] = daily_profit["profit"].astype(float)
    daily_profit["revenue"] = daily_profit["revenue"].astype(float)
    daily_profit["items"] = daily_profit["items"].astype(float)
    daily_profit["margin"] = daily_profit.apply(
        lambda x: (x["profit"] / x["revenue"] * 100) if x["revenue"] > 0 else 0, axis=1
    )
    
    if not daily_profit.empty and len(daily_profit) > 1:
        try:
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=daily_profit["date"],
                y=daily_profit["profit"],
                name="Profit",
                marker_color="green",
                yaxis="y"
            ))
            
            fig.add_trace(go.Scatter(
                x=daily_profit["date"],
                y=daily_profit["revenue"],
                name="Revenue",
                mode="lines+markers",
                line=dict(color="blue", width=2),
                yaxis="y"
            ))
            
            if daily_profit["margin"].notna().any():
                fig.add_trace(go.Scatter(
                    x=daily_profit["date"],
                    y=daily_profit["margin"],
                    name="Margin %",
                    mode="lines+markers",
                    line=dict(color="red", width=2, dash="dash"),
                    yaxis="y2"
                ))
                
                fig.update_layout(
                    yaxis2=dict(
                        title="Margin (%)",
                        overlaying="y",
                        side="right",
                        range=[0, 100]
                    )
                )
            
            fig.update_layout(
                title="Daily Profit, Revenue, and Margin Trend",
                xaxis_title="Date",
                yaxis=dict(title="Amount ($)", side="left"),
                height=400,
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not display profit trend: {str(e)}")
    else:
        st.info("Not enough data to show profit trend")
    
    st.markdown("---")
    
    # ==============================
    # PROFIT MARGIN HEATMAP
    # ==============================
    st.markdown("## Profit Margin Heatmap")
    
    if len(daily_profit) >= 7:
        try:
            daily_profit["day_of_week"] = daily_profit["date"].apply(lambda x: x.weekday())
            daily_profit["week"] = daily_profit["date"].apply(lambda x: x.isocalendar().week)
            daily_profit["week_label"] = daily_profit["date"].apply(
                lambda x: f"Week {x.isocalendar().week}"
            )
            
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            daily_profit["day_name"] = daily_profit["day_of_week"].apply(lambda x: day_names[x])
            
            heatmap_data = daily_profit.pivot_table(
                values="margin",
                index="week_label",
                columns="day_name",
                aggfunc="mean"
            )
            
            for day in day_names:
                if day not in heatmap_data.columns:
                    heatmap_data[day] = 0
            
            heatmap_data = heatmap_data[day_names]
            heatmap_data = heatmap_data.astype(float)
            
            fig = px.imshow(
                heatmap_data,
                title="Profit Margin Heatmap by Week and Day",
                labels=dict(x="Day of Week", y="Week", color="Margin %"),
                color_continuous_scale="RdYlGn",
                aspect="auto",
                text_auto=True
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.info(f"Could not generate heatmap: {str(e)}")
    else:
        st.info("Need at least 7 days of data for heatmap visualization")
    
    st.markdown("---")
    
    # ==============================
    # LOSS LEADER IDENTIFICATION
    # ==============================
    st.markdown("## Loss Leaders (Negative Margin Products)")
    
    product_margin_all = filtered_df.groupby("name").agg({
        "profit": "sum",
        "total": "sum",
        "items": "sum"
    }).reset_index()
    
    product_margin_all["profit"] = product_margin_all["profit"].astype(float)
    product_margin_all["total"] = product_margin_all["total"].astype(float)
    product_margin_all["items"] = product_margin_all["items"].astype(float)
    product_margin_all["margin"] = product_margin_all.apply(
        lambda x: (x["profit"] / x["total"] * 100) if x["total"] > 0 else 0, axis=1
    )
    
    loss_leaders = product_margin_all[product_margin_all["profit"] < 0].sort_values("profit")
    
    if not loss_leaders.empty:
        st.warning(f"Found {len(loss_leaders)} products with negative profit margins")
        
        try:
            fig = px.bar(
                loss_leaders,
                x="profit",
                y="name",
                orientation='h',
                title="Loss Leaders (Negative Profit Products)",
                color="profit",
                color_continuous_scale="Reds_r",
                text="profit"
            )
            fig.update_traces(texttemplate="-$%{text:.2f}", textposition="outside")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass
        
        st.dataframe(
            loss_leaders[["name", "profit", "total", "items", "margin"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": "Product",
                "profit": st.column_config.NumberColumn("Loss", format="-$%.2f"),
                "total": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                "items": "Units Sold",
                "margin": st.column_config.NumberColumn("Margin", format="%.1f%%")
            }
        )
        
        st.info("Consider reviewing pricing or discontinuing these products")
    else:
        st.success("No loss leaders found - all products have positive profit margins")
    
    st.markdown("---")
    
    # ==============================
    # PROFIT OPTIMIZATION RECOMMENDATIONS
    # ==============================
    st.markdown("## Profit Optimization Recommendations")
    
    try:
        avg_margin = safe_float(product_margin_all["margin"].mean())
        high_margin_products = product_margin_all[product_margin_all["margin"] > avg_margin * 1.5].head(5)
        
        recommendations = []
        
        if not high_margin_products.empty:
            names = high_margin_products["name"].head(3).tolist()
            avg_high_margin = safe_float(high_margin_products["margin"].head(3).mean())
            recommendations.append(
                f"High Margin Products: Consider promoting {', '.join(names)} "
                f"with average margin of {avg_high_margin:.1f}%"
            )
        
        if not loss_leaders.empty:
            recommendations.append(
                f"Loss Leaders: {len(loss_leaders)} products have negative margins. "
                f"Consider price adjustments or discontinuing them."
            )
        
        if "payment_method" in filtered_df.columns:
            payment_profit_filtered = filtered_df.groupby("payment_method")["profit"].sum()
            payment_profit_filtered = payment_profit_filtered.astype(float)
            if not payment_profit_filtered.empty:
                best_payment = payment_profit_filtered.idxmax()
                if best_payment:
                    recommendations.append(
                        f"Best Payment Method: {best_payment} generates the highest profit. "
                        f"Consider encouraging customers to use this method."
                    )
        
        if len(product_margin_all) > 3:
            try:
                revenue_quantile = safe_float(product_margin_all["total"].quantile(0.75))
                high_revenue_low_margin = product_margin_all[
                    (product_margin_all["total"] > revenue_quantile) &
                    (product_margin_all["margin"] < avg_margin * 0.5)
                ].head(3)
                
                if not high_revenue_low_margin.empty:
                    names = high_revenue_low_margin["name"].tolist()
                    recommendations.append(
                        f"Optimization Opportunity: {', '.join(names)} "
                        f"have high revenue but low margins. Consider cost reduction or price increase."
                    )
            except Exception:
                pass
        
        if recommendations:
            for rec in recommendations:
                st.info(rec)
        else:
            st.success("No specific profit optimization recommendations at this time")
    except Exception as e:
        st.info("Could not generate recommendations at this time")
    
    # ==============================
    # EXPORT DATA
    # ==============================
    st.markdown("---")
    st.markdown("## Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        summary_data = {
            "Metric": ["Total Revenue", "Total Profit", "Profit Margin", "Total Transactions", "Average Transaction"],
            "Value": [
                f"${total_revenue:,.2f}",
                f"${total_profit:,.2f}",
                f"{profit_margin:.1f}%",
                total_transactions,
                f"${avg_transaction:.2f}"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        
        csv_summary = summary_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Summary (CSV)",
            data=csv_summary,
            file_name=f"profit_summary_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col2:
        detail_data = filtered_df[["date", "name", "total", "profit", "payment_method", "receipt_no"]].copy()
        detail_data["date"] = detail_data["date"].dt.strftime("%Y-%m-%d")
        detail_data["total"] = detail_data["total"].astype(float)
        detail_data["profit"] = detail_data["profit"].astype(float)
        
        csv_detail = detail_data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Detailed Data (CSV)",
            data=csv_detail,
            file_name=f"profit_details_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    profit_center_analysis()