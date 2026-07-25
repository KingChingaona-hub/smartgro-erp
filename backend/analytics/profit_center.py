import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import get_db_connection, load_products


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


def load_sales_from_new_table(start_date=None, end_date=None):
    """Load sales from the new sales table structure (one row per receipt)"""
    conn = get_db_connection()
    
    try:
        # Check if the new sales table exists
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='sales'
        """)
        
        if not cursor.fetchone():
            return pd.DataFrame()
        
        # Build query with date filters
        query = """
            SELECT 
                id,
                receipt_no,
                customer_name,
                customer_phone,
                payment_method,
                subtotal,
                discount_amount,
                discount_type,
                discount_value,
                tax_amount,
                tax_rate,
                final_total,
                cash_received,
                change_amount,
                items_json,
                item_count,
                shift_id,
                cashier,
                branch_id,
                points_earned,
                points_used,
                sale_date,
                created_at
            FROM sales
            WHERE 1=1
        """
        params = []
        
        if start_date:
            query += " AND date(sale_date) >= date(?)"
            params.append(str(start_date))
        
        if end_date:
            query += " AND date(sale_date) <= date(?)"
            params.append(str(end_date))
        
        query += " ORDER BY sale_date DESC"
        
        sales_df = pd.read_sql_query(query, conn, params=params)
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Parse items_json to extract product names and individual items
        expanded_rows = []
        
        for _, sale in sales_df.iterrows():
            try:
                items = json.loads(sale['items_json'])
                
                # If there are items, create one row per item but keep receipt-level data
                for item in items:
                    expanded_row = {
                        'receipt_no': sale['receipt_no'],
                        'customer_name': sale['customer_name'],
                        'customer_phone': sale['customer_phone'],
                        'payment_method': sale['payment_method'],
                        'final_total': sale['final_total'],
                        'subtotal': sale['subtotal'],
                        'discount_amount': sale['discount_amount'],
                        'tax_amount': sale['tax_amount'],
                        'cash_received': sale['cash_received'],
                        'change_amount': sale['change_amount'],
                        'shift_id': sale['shift_id'],
                        'cashier': sale['cashier'],
                        'branch_id': sale['branch_id'],
                        'sale_date': sale['sale_date'],
                        'created_at': sale['created_at'],
                        'item_name': item.get('name', 'Unknown'),
                        'item_barcode': item.get('barcode', ''),
                        'item_qty': float(item.get('qty', 0)),
                        'item_price': float(item.get('price', 0)),
                        'item_total': float(item.get('total', 0)),
                        'item_cost': float(item.get('cost', 0)),
                        'item_profit': float(item.get('total', 0)) - float(item.get('cost', 0)) * float(item.get('qty', 0))
                    }
                    expanded_rows.append(expanded_row)
                    
            except json.JSONDecodeError:
                # If items_json is not valid JSON, skip
                pass
            except Exception as e:
                print(f"Error processing sale {sale.get('receipt_no', 'unknown')}: {str(e)}")
        
        if not expanded_rows:
            return pd.DataFrame()
        
        result_df = pd.DataFrame(expanded_rows)
        
        # Convert date column
        result_df['sale_date'] = pd.to_datetime(result_df['sale_date'], errors='coerce')
        result_df = result_df.dropna(subset=['sale_date'])
        
        # Rename columns for consistency with old code
        result_df.rename(columns={
            'sale_date': 'date',
            'item_name': 'name',
            'item_total': 'total',
            'item_profit': 'profit',
            'item_qty': 'items'
        }, inplace=True)
        
        return result_df
        
    except Exception as e:
        st.error(f"Error loading sales data: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()


def profit_center_analysis():
    """Main profit center analysis dashboard - FIXED to use new sales table"""
    
    st.title("Profit Center Analysis")
    st.caption("Analyze profitability by product, category, payment method, and time")
    
    # ==============================
    # SIDEBAR FILTERS
    # ==============================
    st.sidebar.header("Filters")
    
    # Get date range from data
    sales_df = load_sales_from_new_table()
    
    if sales_df.empty:
        st.warning("No sales data available for profit analysis")
        st.info("Make sure you have processed sales using the POS system with the new sales table structure.")
        return
    
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
    # KEY METRICS
    # ==============================
    st.markdown("## Key Profit Metrics")
    
    # Calculate metrics from the expanded data
    total_revenue = safe_float(filtered_df["total"].sum())
    total_profit = safe_float(filtered_df["profit"].sum())
    total_items = safe_int(filtered_df["items"].sum())
    total_transactions = filtered_df["receipt_no"].nunique() if "receipt_no" in filtered_df.columns else len(filtered_df)
    
    # Calculate profit margin
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Average transaction value (based on final_total per receipt)
    receipt_totals = filtered_df.groupby("receipt_no")["final_total"].first() if "receipt_no" in filtered_df.columns else filtered_df.groupby("receipt_no")["total"].sum()
    avg_transaction = receipt_totals.mean() if not receipt_totals.empty else 0
    
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
    # PROFIT BY PRODUCT
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
        
        # Convert to float
        product_profit["profit"] = product_profit["profit"].astype(float)
        product_profit["total"] = product_profit["total"].astype(float)
        product_profit["items"] = product_profit["items"].astype(float)
        
        # Calculate margin safely
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
        
        payment_profit = filtered_df.groupby("payment_method").agg({
            "profit": "sum",
            "total": "sum",
            "receipt_no": "nunique" if "receipt_no" in filtered_df.columns else "count"
        }).reset_index()
        
        # Convert to float
        payment_profit["profit"] = payment_profit["profit"].astype(float)
        payment_profit["total"] = payment_profit["total"].astype(float)
        
        if "receipt_no" not in filtered_df.columns:
            payment_profit["receipt_no"] = 1
        
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
    
    # Group by date
    daily_profit = filtered_df.groupby(filtered_df["date"].dt.date).agg({
        "profit": "sum",
        "total": "sum",
        "items": "sum"
    }).reset_index()
    daily_profit.columns = ["date", "profit", "revenue", "items"]
    
    # Convert to float
    daily_profit["profit"] = daily_profit["profit"].astype(float)
    daily_profit["revenue"] = daily_profit["revenue"].astype(float)
    daily_profit["items"] = daily_profit["items"].astype(float)
    daily_profit["margin"] = daily_profit.apply(
        lambda x: (x["profit"] / x["revenue"] * 100) if x["revenue"] > 0 else 0, axis=1
    )
    
    if not daily_profit.empty and len(daily_profit) > 1:
        try:
            # Create figure with dual y-axis
            fig = go.Figure()
            
            # Add profit bar chart
            fig.add_trace(go.Bar(
                x=daily_profit["date"],
                y=daily_profit["profit"],
                name="Profit",
                marker_color="green",
                yaxis="y"
            ))
            
            # Add revenue line
            fig.add_trace(go.Scatter(
                x=daily_profit["date"],
                y=daily_profit["revenue"],
                name="Revenue",
                mode="lines+markers",
                line=dict(color="blue", width=2),
                yaxis="y"
            ))
            
            # Add margin line on secondary axis (only if data exists)
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
    # LOSS LEADER IDENTIFICATION
    # ==============================
    st.markdown("## Loss Leaders (Negative Margin Products)")
    
    product_margin_all = filtered_df.groupby("name").agg({
        "profit": "sum",
        "total": "sum",
        "items": "sum"
    }).reset_index()
    
    # Convert to float
    product_margin_all["profit"] = product_margin_all["profit"].astype(float)
    product_margin_all["total"] = product_margin_all["total"].astype(float)
    product_margin_all["items"] = product_margin_all["items"].astype(float)
    product_margin_all["margin"] = product_margin_all.apply(
        lambda x: (x["profit"] / x["total"] * 100) if x["total"] > 0 else 0, axis=1
    )
    
    # Identify products with negative profit
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
        # Calculate key metrics for recommendations
        avg_margin = safe_float(product_margin_all["margin"].mean())
        high_margin_products = product_margin_all[product_margin_all["margin"] > avg_margin * 1.5].head(5)
        
        recommendations = []
        
        if not high_margin_products.empty:
            names = high_margin_products["name"].head(3).tolist()
            avg_high_margin = safe_float(high_margin_products["margin"].head(3).mean())
            recommendations.append(
                f"**High Margin Products**: Consider promoting {', '.join(names)} "
                f"with average margin of {avg_high_margin:.1f}%"
            )
        
        if not loss_leaders.empty:
            recommendations.append(
                f"**Loss Leaders**: {len(loss_leaders)} products have negative margins. "
                f"Consider price adjustments or discontinuing them."
            )
        
        # Check payment method profitability
        if "payment_method" in filtered_df.columns:
            payment_profit_filtered = filtered_df.groupby("payment_method")["profit"].sum()
            payment_profit_filtered = payment_profit_filtered.astype(float)
            if not payment_profit_filtered.empty:
                best_payment = payment_profit_filtered.idxmax()
                if best_payment:
                    recommendations.append(
                        f"**Best Payment Method**: {best_payment} generates the highest profit. "
                        f"Consider encouraging customers to use this method."
                    )
        
        # Check if there are products with high revenue but low margin
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
                        f"**Optimization Opportunity**: {', '.join(names)} "
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
        # Summary export
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
        # Detailed export - ensure all columns are properly formatted
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