# backend/analytics/pl_engine.py

import pandas as pd
import json
from datetime import datetime, timedelta
import streamlit as st

from backend.core.db_adapter import get_db_connection


def get_sales_data(year=None, month=None, quarter=None):
    """Get sales data from the new sales table structure"""
    conn = get_db_connection()
    
    try:
        # Build query with filters
        query = "SELECT * FROM sales WHERE 1=1"
        params = []
        
        if year:
            query += " AND strftime('%Y', sale_date) = ?"
            params.append(str(year))
        
        if month:
            query += " AND strftime('%m', sale_date) = ?"
            params.append(f"{month:02d}")
        
        if quarter:
            # Quarter mapping: Q1 = Jan-Mar, Q2 = Apr-Jun, Q3 = Jul-Sep, Q4 = Oct-Dec
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3
            query += " AND strftime('%m', sale_date) BETWEEN ? AND ?"
            params.extend([f"{start_month:02d}", f"{end_month:02d}"])
        
        sales_df = pd.read_sql_query(query, conn, params=params)
        return sales_df
        
    except Exception as e:
        st.error(f"Error loading sales data: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_expenses_data(year=None, month=None, quarter=None):
    """Get expenses data"""
    conn = get_db_connection()
    
    try:
        query = "SELECT * FROM expenses WHERE 1=1"
        params = []
        
        if year:
            query += " AND strftime('%Y', expense_date) = ?"
            params.append(str(year))
        
        if month:
            query += " AND strftime('%m', expense_date) = ?"
            params.append(f"{month:02d}")
        
        if quarter:
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3
            query += " AND strftime('%m', expense_date) BETWEEN ? AND ?"
            params.extend([f"{start_month:02d}", f"{end_month:02d}"])
        
        expenses_df = pd.read_sql_query(query, conn, params=params)
        return expenses_df
        
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()


def profit_loss_account(year=None, month=None, quarter=None):
    """
    Generate Profit & Loss Account
    Uses the new sales table structure (one row per receipt)
    """
    
    # Get sales data
    sales_df = get_sales_data(year, month, quarter)
    
    # Calculate sales metrics
    total_sales = sales_df['final_total'].sum() if not sales_df.empty else 0
    total_transactions = len(sales_df) if not sales_df.empty else 0
    
    # Get COGS from sales items
    total_cogs = 0
    total_items_sold = 0
    
    if not sales_df.empty:
        for _, sale in sales_df.iterrows():
            try:
                items = json.loads(sale['items_json'])
                for item in items:
                    # Use cost from product database if available
                    cost = item.get('cost', 0) * float(item.get('qty', 0))
                    total_cogs += cost
                    total_items_sold += float(item.get('qty', 0))
            except:
                pass
    
    # Get expenses data
    expenses_df = get_expenses_data(year, month, quarter)
    
    # Categorize expenses
    operating_expenses = 0
    other_expenses = 0
    tax_expense = 0
    
    if not expenses_df.empty:
        for _, exp in expenses_df.iterrows():
            category = exp.get('category', 'Other').lower()
            amount = exp.get('amount', 0)
            
            if category in ['rent', 'salaries', 'utilities', 'insurance', 'maintenance', 'marketing', 'supplies']:
                operating_expenses += amount
            elif category in ['tax', 'income_tax']:
                tax_expense += amount
            else:
                other_expenses += amount
    
    # Calculate Profit & Loss
    gross_profit = total_sales - total_cogs
    gross_margin = (gross_profit / total_sales * 100) if total_sales > 0 else 0
    
    net_profit_before_tax = gross_profit - operating_expenses - other_expenses
    net_profit = net_profit_before_tax - tax_expense
    net_margin = (net_profit / total_sales * 100) if total_sales > 0 else 0
    
    # Return P&L data
    return {
        # Sales
        "sales": total_sales,
        "sales_returns": 0,  # Not tracked in current system
        "net_sales": total_sales,
        
        # COGS
        "opening_stock": 0,  # Not tracked in current system
        "purchases": 0,  # Not tracked in current system
        "purchase_returns": 0,
        "net_purchases": 0,
        "closing_stock": 0,
        "cogs": total_cogs,
        
        # Profit
        "gross_profit": gross_profit,
        "gross_margin": gross_margin,
        
        # Expenses
        "operating_expenses": operating_expenses,
        "other_income": 0,  # Not tracked in current system
        "other_expenses": other_expenses,
        "tax": tax_expense,
        
        # Net
        "net_profit_before_tax": net_profit_before_tax,
        "net_profit": net_profit,
        "net_margin": net_margin,
        
        # Additional metrics
        "transactions": total_transactions,
        "items_sold": total_items_sold,
        "avg_transaction": total_sales / total_transactions if total_transactions > 0 else 0
    }


def monthly_comparison(year):
    """Compare monthly performance for a given year"""
    monthly_data = []
    
    for month in range(1, 13):
        pl = profit_loss_account(year=year, month=month)
        
        monthly_data.append({
            "month": month,
            "sales": pl["net_sales"],
            "profit": pl["net_profit"],
            "transactions": pl["transactions"],
            "avg_transaction": pl["avg_transaction"]
        })
    
    return pd.DataFrame(monthly_data)


def yearly_comparison(year_a, year_b):
    """Compare two years' performance"""
    pl_a = profit_loss_account(year=year_a)
    pl_b = profit_loss_account(year=year_b)
    
    sales_growth = ((pl_b["net_sales"] - pl_a["net_sales"]) / pl_a["net_sales"] * 100) if pl_a["net_sales"] > 0 else 0
    profit_growth = ((pl_b["net_profit"] - pl_a["net_profit"]) / abs(pl_a["net_profit"]) * 100) if pl_a["net_profit"] != 0 else 0
    
    return {
        "sales_year1": pl_a["net_sales"],
        "sales_year2": pl_b["net_sales"],
        "profit_year1": pl_a["net_profit"],
        "profit_year2": pl_b["net_profit"],
        "expenses_year1": pl_a["operating_expenses"],
        "expenses_year2": pl_b["operating_expenses"],
        "sales_growth": sales_growth,
        "profit_growth": profit_growth
    }


def get_financial_ratios(year=None, month=None, quarter=None):
    """Calculate key financial ratios"""
    pl = profit_loss_account(year, month, quarter)
    
    # Get inventory data for turnover ratio
    conn = get_db_connection()
    inventory_value = 0
    
    try:
        # Get total inventory value
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(stock * cost) FROM products")
        result = cursor.fetchone()
        inventory_value = result[0] if result[0] else 0
    except:
        pass
    finally:
        conn.close()
    
    # Calculate ratios
    gross_margin = pl["gross_margin"]
    net_margin = pl["net_margin"]
    
    # Inventory turnover (based on COGS / Average Inventory)
    inventory_turnover = (pl["cogs"] / inventory_value) if inventory_value > 0 else 0
    
    # Profitability status
    if pl["net_profit"] > 0 and gross_margin > 30:
        status = "Good"
    elif pl["net_profit"] > 0 and gross_margin > 15:
        status = "Fair"
    elif pl["net_profit"] > 0:
        status = "Needs Improvement"
    else:
        status = "Critical"
    
    return {
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "inventory_turnover": inventory_turnover,
        "profitability_status": status,
        "return_on_sales": net_margin,
        "expense_ratio": (pl["operating_expenses"] / pl["net_sales"] * 100) if pl["net_sales"] > 0 else 0
    }


def break_even_analysis(year=None, month=None, quarter=None):
    """Calculate break-even point"""
    pl = profit_loss_account(year, month, quarter)
    
    # Estimate fixed vs variable costs
    # For simplicity, treat operating expenses as fixed and COGS as variable
    fixed_costs = pl["operating_expenses"]
    variable_costs = pl["cogs"]
    
    if pl["net_sales"] > 0:
        variable_ratio = variable_costs / pl["net_sales"]
        contribution_margin = 1 - variable_ratio
        
        if contribution_margin > 0:
            break_even_sales = fixed_costs / contribution_margin
        else:
            break_even_sales = float('inf')
    else:
        break_even_sales = 0
    
    margin_of_safety = pl["net_sales"] - break_even_sales
    margin_of_safety_ratio = (margin_of_safety / pl["net_sales"] * 100) if pl["net_sales"] > 0 else 0
    
    return {
        "break_even_sales": break_even_sales,
        "margin_of_safety": margin_of_safety,
        "margin_of_safety_ratio": margin_of_safety_ratio,
        "fixed_costs": fixed_costs,
        "variable_costs": variable_costs,
        "variable_ratio": variable_ratio if pl["net_sales"] > 0 else 0
    }


def cash_flow_statement(year=None, month=None, quarter=None):
    """Generate cash flow statement"""
    pl = profit_loss_account(year, month, quarter)
    
    # Get beginning cash balance
    conn = get_db_connection()
    beginning_cash = 0
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM cash_transactions WHERE type='opening_balance'")
        result = cursor.fetchone()
        beginning_cash = result[0] if result[0] else 0
    except:
        pass
    finally:
        conn.close()
    
    # Operating cash flow (simplified)
    net_cash_operating = pl["net_profit"] + 0  # Add depreciation if tracked
    
    # Investing cash flow (placeholder)
    net_cash_investing = 0
    
    # Financing cash flow (placeholder)
    net_cash_financing = 0
    
    # Calculate ending cash
    net_cash_flow = net_cash_operating + net_cash_investing + net_cash_financing
    ending_cash = beginning_cash + net_cash_flow
    
    return {
        "beginning_cash": beginning_cash,
        "net_profit": pl["net_profit"],
        "depreciation": 0,  # Not tracked
        "changes_inventory": 0,  # Not tracked
        "net_cash_operating": net_cash_operating,
        "net_cash_investing": net_cash_investing,
        "net_cash_financing": net_cash_financing,
        "net_cash_flow": net_cash_flow,
        "ending_cash": ending_cash
    }


def financial_forecast(months=6):
    """Generate financial forecast"""
    # Get historical data for trend analysis
    sales_history = []
    
    for month in range(1, 13):
        pl = profit_loss_account(year=datetime.now().year, month=month)
        sales_history.append(pl["net_sales"])
    
    forecast = []
    
    if sales_history and any(sales_history):
        # Calculate average growth from last 3 months
        recent_sales = [s for s in sales_history[-3:] if s > 0]
        
        if recent_sales:
            avg_sales = sum(recent_sales) / len(recent_sales)
            growth_rate = 0.05  # Default 5% growth
        else:
            avg_sales = 1000  # Default if no data
            growth_rate = 0.05
    else:
        avg_sales = 1000
        growth_rate = 0.05
    
    # Generate forecast
    current_sales = avg_sales
    
    for i in range(months):
        month_name = (datetime.now() + timedelta(days=30 * (i + 1))).strftime("%b %Y")
        
        # Add some seasonality
        seasonality = 1 + 0.1 * (i % 3 == 0)  # Every 3 months boost
        projected_sales = current_sales * (1 + growth_rate) * seasonality
        projected_profit = projected_sales * 0.15  # Assume 15% profit margin
        
        # Confidence intervals
        confidence_upper = projected_sales * 1.2
        confidence_lower = projected_sales * 0.8
        
        forecast.append({
            "month": month_name,
            "projected_sales": projected_sales,
            "projected_profit": projected_profit,
            "confidence_upper": confidence_upper,
            "confidence_lower": confidence_lower
        })
        
        current_sales = projected_sales
    
    return forecast


def balance_sheet():
    """Generate balance sheet"""
    conn = get_db_connection()
    
    # Get cash balance
    cash = 0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM cash_transactions")
        result = cursor.fetchone()
        cash = result[0] if result[0] else 0
    except:
        pass
    
    # Get inventory value
    inventory = 0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(stock * cost) FROM products")
        result = cursor.fetchone()
        inventory = result[0] if result[0] else 0
    except:
        pass
    
    # Accounts receivable (from credit sales)
    accounts_receivable = 0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(balance) FROM debtors WHERE balance > 0")
        result = cursor.fetchone()
        accounts_receivable = result[0] if result[0] else 0
    except:
        pass
    
    # Accounts payable (placeholder)
    accounts_payable = 0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE paid = 0")
        result = cursor.fetchone()
        accounts_payable = result[0] if result[0] else 0
    except:
        pass
    
    # Calculate totals
    total_current_assets = cash + inventory + accounts_receivable
    net_fixed_assets = 0  # Simplified
    total_assets = total_current_assets + net_fixed_assets
    
    total_current_liabilities = accounts_payable
    short_term_debt = 0
    long_term_debt = 0
    total_liabilities = total_current_liabilities + long_term_debt
    
    # Owner's equity = Assets - Liabilities
    owners_equity = total_assets - total_liabilities
    
    return {
        "cash": cash,
        "inventory": inventory,
        "accounts_receivable": accounts_receivable,
        "total_current_assets": total_current_assets,
        "equipment": 0,
        "accumulated_depreciation": 0,
        "net_fixed_assets": net_fixed_assets,
        "total_assets": total_assets,
        "accounts_payable": accounts_payable,
        "short_term_debt": short_term_debt,
        "total_current_liabilities": total_current_liabilities,
        "long_term_debt": long_term_debt,
        "total_liabilities": total_liabilities,
        "owners_equity": owners_equity,
        "total_liabilities_equity": total_liabilities + owners_equity
    }


def get_profit_center_report():
    """Get profit center report for dashboard"""
    # Get date range from session state
    start_date = st.session_state.get('analytics_start_date', None)
    end_date = st.session_state.get('analytics_end_date', None)
    
    # Get sales data for period
    conn = get_db_connection()
    
    try:
        query = "SELECT * FROM sales WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date(sale_date) >= date(?)"
            params.append(str(start_date))
        
        if end_date:
            query += " AND date(sale_date) <= date(?)"
            params.append(str(end_date))
        
        sales_df = pd.read_sql_query(query, conn, params=params)
        
        if sales_df.empty:
            return {
                "total_revenue": 0,
                "total_cost": 0,
                "total_profit": 0,
                "profit_margin": 0,
                "avg_transaction": 0,
                "total_transactions": 0,
                "revenue_by_category": {},
                "revenue_by_payment": {},
                "profit_by_product": {},
                "daily_revenue": {},
                "top_products": {}
            }
        
        # Calculate metrics
        total_revenue = sales_df['final_total'].sum()
        total_transactions = len(sales_df)
        avg_transaction = total_revenue / total_transactions if total_transactions > 0 else 0
        
        # Get product costs
        products_df = pd.read_sql_query("SELECT barcode, cost, name, category FROM products", conn)
        product_costs = {row['barcode']: row for _, row in products_df.iterrows()}
        
        # Calculate costs and breakdowns
        total_cost = 0
        category_revenue = {}
        payment_revenue = {}
        product_profits = {}
        top_products = {}
        daily_revenue = {}
        
        for _, sale in sales_df.iterrows():
            payment_method = sale['payment_method']
            payment_revenue[payment_method] = payment_revenue.get(payment_method, 0) + sale['final_total']
            
            sale_date = sale['sale_date']
            if isinstance(sale_date, str):
                sale_date = datetime.fromisoformat(sale_date).date()
            else:
                sale_date = sale_date.date()
            
            daily_revenue[sale_date] = daily_revenue.get(sale_date, 0) + sale['final_total']
            
            try:
                items = json.loads(sale['items_json'])
                sale_cost = 0
                
                for item in items:
                    barcode = item.get('barcode', '')
                    qty = float(item.get('qty', 0))
                    revenue = float(item.get('total', 0))
                    
                    product = product_costs.get(barcode)
                    cost_per_unit = product['cost'] if product else 0
                    item_cost = cost_per_unit * qty
                    sale_cost += item_cost
                    
                    product_name = product['name'] if product else item.get('name', 'Unknown')
                    product_category = product['category'] if product else 'Unknown'
                    
                    # Track product profit
                    if product_name not in product_profits:
                        product_profits[product_name] = {
                            'revenue': 0,
                            'cost': 0,
                            'profit': 0,
                            'quantity': 0,
                            'category': product_category
                        }
                    
                    product_profits[product_name]['revenue'] += revenue
                    product_profits[product_name]['cost'] += item_cost
                    product_profits[product_name]['profit'] += revenue - item_cost
                    product_profits[product_name]['quantity'] += qty
                    
                    # Track top products
                    if product_name not in top_products:
                        top_products[product_name] = {'revenue': 0, 'quantity': 0}
                    top_products[product_name]['revenue'] += revenue
                    top_products[product_name]['quantity'] += qty
                    
                    # Track category revenue
                    category_revenue[product_category] = category_revenue.get(product_category, 0) + revenue
                
                total_cost += sale_cost
                
            except:
                pass
        
        total_profit = total_revenue - total_cost
        profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Sort and limit top products
        sorted_top_products = sorted(top_products.items(), key=lambda x: x[1]['revenue'], reverse=True)[:10]
        
        return {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_profit": total_profit,
            "profit_margin": profit_margin,
            "avg_transaction": avg_transaction,
            "total_transactions": total_transactions,
            "revenue_by_category": category_revenue,
            "revenue_by_payment": payment_revenue,
            "profit_by_product": product_profits,
            "daily_revenue": daily_revenue,
            "top_products": dict(sorted_top_products)
        }
        
    except Exception as e:
        st.error(f"Error in profit center report: {str(e)}")
        return {
            "total_revenue": 0,
            "total_cost": 0,
            "total_profit": 0,
            "profit_margin": 0,
            "avg_transaction": 0,
            "total_transactions": 0,
            "revenue_by_category": {},
            "revenue_by_payment": {},
            "profit_by_product": {},
            "daily_revenue": {},
            "top_products": {}
        }
    finally:
        conn.close()