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
    """
    Load sales from the new sales table structure (one row per receipt)
    FIXED: Separates receipt-level and item-level data to avoid revenue duplication
    """
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
        
        # ==============================
        # FIX: Separate receipt-level and item-level data
        # ==============================
        
        # 1. Create receipt-level summary (ONE row per receipt)
        receipt_rows = []
        
        # 2. Create item-level breakdown (for product analysis)
        item_rows = []
        
        for _, sale in sales_df.iterrows():
            # Receipt-level data (use this for revenue totals)
            receipt_data = {
                'receipt_no': sale['receipt_no'],
                'customer_name': sale['customer_name'],
                'customer_phone': sale['customer_phone'],
                'payment_method': sale['payment_method'],
                'final_total': float(sale['final_total']) if sale['final_total'] else 0,
                'subtotal': float(sale['subtotal']) if sale['subtotal'] else 0,
                'discount_amount': float(sale['discount_amount']) if sale['discount_amount'] else 0,
                'tax_amount': float(sale['tax_amount']) if sale['tax_amount'] else 0,
                'cash_received': float(sale['cash_received']) if sale['cash_received'] else 0,
                'change_amount': float(sale['change_amount']) if sale['change_amount'] else 0,
                'shift_id': sale['shift_id'],
                'cashier': sale['cashier'],
                'branch_id': sale['branch_id'],
                'sale_date': sale['sale_date'],
                'created_at': sale['created_at'],
                'item_count': int(sale['item_count']) if sale['item_count'] else 0,
                'points_earned': int(sale['points_earned']) if sale['points_earned'] else 0,
                'points_used': int(sale['points_used']) if sale['points_used'] else 0
            }
            receipt_rows.append(receipt_data)
            
            # Parse items_json for product-level breakdown
            try:
                items = json.loads(sale['items_json'])
                for item in items:
                    item_data = {
                        'receipt_no': sale['receipt_no'],
                        'sale_date': sale['sale_date'],
                        'payment_method': sale['payment_method'],
                        'customer_name': sale['customer_name'],
                        'name': item.get('name', 'Unknown'),
                        'barcode': item.get('barcode', ''),
                        'qty': float(item.get('qty', 0)),
                        'price': float(item.get('price', 0)),
                        'total': float(item.get('total', 0)),
                        'cost': float(item.get('cost', 0)),
                        # Calculate profit at item level
                        'profit': float(item.get('total', 0)) - (float(item.get('cost', 0)) * float(item.get('qty', 0)))
                    }
                    item_rows.append(item_data)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"Error processing items for receipt {sale.get('receipt_no', 'unknown')}: {str(e)}")
        
        # Create DataFrames
        receipts_df = pd.DataFrame(receipt_rows)
        items_df = pd.DataFrame(item_rows)
        
        if receipts_df.empty:
            return pd.DataFrame()
        
        # Convert date column
        receipts_df['sale_date'] = pd.to_datetime(receipts_df['sale_date'], errors='coerce')
        receipts_df = receipts_df.dropna(subset=['sale_date'])
        
        # Rename for consistency
        receipts_df.rename(columns={
            'sale_date': 'date',
            'final_total': 'receipt_total'
        }, inplace=True)
        
        if items_df.empty:
            # If no items, return receipt-level data only
            return receipts_df
        
        # Merge receipt-level data with item-level data
        # This creates one row per item BUT with receipt-level totals preserved separately
        merged_df = pd.merge(
            receipts_df[['receipt_no', 'date', 'receipt_total', 'payment_method', 'customer_name', 
                         'cashier', 'branch_id', 'item_count', 'subtotal', 'discount_amount', 
                         'tax_amount']],
            items_df[['receipt_no', 'name', 'barcode', 'qty', 'price', 'total', 'cost', 'profit']],
            on='receipt_no',
            how='left'
        )
        
        # Rename columns to avoid confusion
        merged_df.rename(columns={
            'total': 'item_total'  # This is the item's total
        }, inplace=True)
        
        # For backward compatibility with existing code
        # Use item-level data for product names and quantities
        # Use receipt-level data for revenue (to avoid duplication)
        merged_df['name'] = merged_df['name'].fillna('Unknown')
        merged_df['quantity'] = merged_df['qty']
        merged_df['item_price'] = merged_df['price']
        merged_df['item_total'] = merged_df['item_total'].fillna(0)
        merged_df['profit'] = merged_df['profit'].fillna(0)
        
        return merged_df
        
    except Exception as e:
        st.error(f"Error loading sales data: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()


def profit_center_analysis():
    """Main profit center analysis dashboard - FIXED for correct revenue"""
    
    st.title("Profit Center Analysis")
    st.caption("Analyze profitability by product, category, payment method, and time")
    
    # Load data
    sales_df = load_sales_from_new_table()
    
    if sales_df.empty:
        st.warning("No sales data available for profit analysis")
        st.info("Make sure you have processed sales using the POS system with the new sales table structure.")
        return
    
    # ==============================
    # SIDEBAR FILTERS
    # ==============================
    st.sidebar.header("Filters")
    
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
    
    # Payment method filter    if "payment_method" in filtered_df.columns and not filtered_df.empty:
        payment_methods = ["All"] + sorted(filtered_df["payment_method"].unique().tolist())
        selected_payment = st.sidebar.selectbox("Payment Method", payment_methods)
        
        if selected_payment != "All" and selected_payment in filtered_df["payment_method"].values:
            filtered_df = filtered_df[filtered_df["payment_method"] == selected_payment]
    
    if filtered_df.empty:
        st.warning("No data matches the selected filters")
        return
    
    # ==============================
    # KEY METRICS - Use receipt-level data
    # ==============================
    st.markdown("## Key Profit Metrics")
    
    # Get unique receipts for revenue calculation
    unique_receipts = filtered_df.drop_duplicates(subset=['receipt_no'])
    
    total_revenue = safe_float(unique_receipts['receipt_total'].sum())
    total_transactions = len(unique_receipts)
    avg_transaction = total_revenue / total_transactions if total_transactions > 0 else 0
    
    # For profit, sum item-level profits (this is correct because profit is per item)
    total_profit = safe_float(filtered_df['profit'].sum())
    
    # Profit margin
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Total items sold
    total_items = safe_int(filtered_df['qty'].sum())
    
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
    # PROFIT BY PRODUCT - Use item-level data
    # ==============================
    st.markdown("## Profit by Product")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Group by product name using item-level data
        product_profit = filtered_df.groupby("name").agg({
            "profit": "sum",
            "item_total": "sum",
            "qty": "sum"
        }).reset_index()
        
        product_profit.rename(columns={
            "item_total": "revenue",
            "qty": "quantity"
        }, inplace=True)
        
        # Convert to float
        product_profit["profit"] = product_profit["profit"].astype(float)
        product_profit["revenue"] = product_profit["revenue"].astype(float)
        product_profit["quantity"] = product_profit["quantity"].astype(float)
        
        # Calculate margin
        product_profit["margin"] = product_profit.apply(
            lambda x: (x["profit"] / x["revenue"] * 100) if x["revenue"] > 0 else 0, axis=1
        )
        
        # Sort and display top 10
        top_products = product_profit.sort_values("profit", ascending=False).head(10)
        
        if not top_products.empty:
            fig = px.bar(
                top_products,
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
    # PROFIT BY PAYMENT METHOD - Use receipt-level data
    # ==============================
    if "payment_method" in filtered_df.columns:
        st.markdown("## Profit by Payment Method")
        
        # Use unique receipts for payment method revenue
        payment_receipts = filtered_df.drop_duplicates(subset=['receipt_no', 'payment_method'])
        
        payment_profit = payment_receipts.groupby("payment_method").agg({
            "receipt_total": "sum",
            "receipt_no": "count"
        }).reset_index()
        
        payment_profit.rename(columns={
            "receipt_total": "revenue",
            "receipt_no": "transactions"
        }, inplace=True)
        
        # Add profit per payment method (from item-level data)
        payment_item_profit = filtered_df.groupby("payment_method")["profit"].sum().reset_index()
        payment_profit = pd.merge(payment_profit, payment_item_profit, on="payment_method")
        
        # Convert to float
        payment_profit["revenue"] = payment_profit["revenue"].astype(float)
        payment_profit["profit"] = payment_profit["profit"].astype(float)
        payment_profit["transactions"] = payment_profit["transactions"].astype(float)
        
        payment_profit["margin"] = payment_profit.apply(
            lambda x: (x["profit"] / x["revenue"] * 100) if x["revenue"] > 0 else 0, axis=1
        )
        payment_profit["avg_transaction"] = payment_profit.apply(
            lambda x: x["revenue"] / x["transactions"] if x["transactions"] > 0 else 0, axis=1
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
                    payment_profit[["payment_method", "profit", "revenue", "margin", "avg_transaction"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "payment_method": "Payment Method",
                        "profit": st.column_config.NumberColumn("Profit", format="$%.2f"),
                        "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                        "margin": st.column_config.NumberColumn("Margin", format="%.1f%%"),
                        "avg_transaction": st.column_config.NumberColumn("Avg Transaction", format="$%.2f")
                    }
                )
        
        st.markdown("---")
    
    # ==============================
    # PROFIT TREND OVER TIME
    # ==============================
    st.markdown("## Profit Trend Over Time")
    
    # Group by date using receipt-level data for revenue
    daily_receipts = filtered_df.drop_duplicates(subset=['date', 'receipt_no'])
    daily_revenue = daily_receipts.groupby('date').agg({
        'receipt_total': 'sum'
    }).reset_index()
    daily_revenue.columns = ['date', 'revenue']
    
    # Group by date for profit (item-level)
    daily_profit = filtered_df.groupby('date').agg({
        'profit': 'sum',
        'qty': 'sum'
    }).reset_index()
    daily_profit.columns = ['date', 'profit', 'items']
    
    # Merge revenue and profit
    daily_data = pd.merge(daily_revenue, daily_profit, on='date')
    
    # Calculate margin
    daily_data["margin"] = daily_data.apply(
        lambda x: (x["profit"] / x["revenue"] * 100) if x["revenue"] > 0 else 0, axis=1
    )
    
    if not daily_data.empty and len(daily_data) > 1:
        try:
            # Create figure with dual y-axis
            fig = go.Figure()
            
            # Add profit bar chart
            fig.add_trace(go.Bar(
                x=daily_data["date"],
                y=daily_data["profit"],
                name="Profit",
                marker_color="green",
                yaxis="y"
            ))
            
            # Add revenue line
            fig.add_trace(go.Scatter(
                x=daily_data["date"],
                y=daily_data["revenue"],
                name="Revenue",
                mode="lines+markers",
                line=dict(color="blue", width=2),
                yaxis="y"
            ))
            
            # Add margin line on secondary axis
            if daily_data["margin"].notna().any():
                fig.add_trace(go.Scatter(
                    x=daily_data["date"],
                    y=daily_data["margin"],
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
        "item_total": "sum",
        "qty": "sum"
    }).reset_index()
    
    product_margin_all.rename(columns={
        "item_total": "revenue",
        "qty": "quantity"
    }, inplace=True)
    
    # Convert to float
    product_margin_all["profit"] = product_margin_all["profit"].astype(float)
    product_margin_all["revenue"] = product_margin_all["revenue"].astype(float)
    product_margin_all["quantity"] = product_margin_all["quantity"].astype(float)
    product_margin_all["margin"] = product_margin_all.apply(
        lambda x: (x["profit"] / x["revenue"] * 100) if x["revenue"] > 0 else 0, axis=1
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
            loss_leaders[["name", "profit", "revenue", "quantity", "margin"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": "Product",
                "profit": st.column_config.NumberColumn("Loss", format="-$%.2f"),
                "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                "quantity": "Units Sold",
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
        # Detailed export - use item-level data
        if not filtered_df.empty:
            detail_data = filtered_df[["date", "name", "item_total", "profit", "payment_method", "receipt_no", "qty"]].copy()
            detail_data["date"] = detail_data["date"].dt.strftime("%Y-%m-%d")
            detail_data.rename(columns={"item_total": "revenue"}, inplace=True)
            
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