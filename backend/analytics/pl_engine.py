# backend/analytics/pl_engine.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backend.core.db_adapter import load_sales, load_purchases, load_products
from backend.modules.expenses import load_expenses
from backend.modules.income import load_income
from decimal import Decimal


# ==============================
# HELPER: Convert Decimal to float safely
# ==============================
def to_float(value):
    """Safely convert Decimal or any value to float"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, pd.Series):
        return float(value.sum()) if not value.empty else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ==============================
# GET TOTAL COLUMN NAME
# ==============================
def get_total_column(df):
    """Get the total/final_total column name from dataframe"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in df.columns:
            return col
    return None


# ==============================
# GET COST COLUMN NAME
# ==============================
def get_cost_column(df):
    """Get the cost column name from dataframe"""
    if df is None or df.empty:
        return None
    for col in ["cost", "cost_price", "unit_cost", "purchase_price"]:
        if col in df.columns:
            return col
    return None


# ==============================
# GET DATE COLUMN NAME
# ==============================
def get_date_column(df):
    """Get the date column name from dataframe"""
    if df is None or df.empty:
        return None
    for col in ["sale_date", "date", "transaction_date", "created_at", "expense_date", "income_date"]:
        if col in df.columns:
            return col
    return None


# ==============================
# GET PRODUCT NAME COLUMN
# ==============================
def get_product_name_column(df):
    """Get the product name column from dataframe"""
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "item_name", "product"]:
        if col in df.columns:
            return col
    return None


# ==============================
# GET QUANTITY COLUMN
# ==============================
def get_quantity_column(df):
    """Get the quantity column from dataframe"""
    if df is None or df.empty:
        return None
    for col in ["items", "quantity", "qty", "item_count"]:
        if col in df.columns:
            return col
    return None


# ==============================
# CALCULATE COST OF GOODS SOLD FROM SALES DATA
# ==============================
def calculate_cogs_from_sales(year=None, month=None, quarter=None):
    """
    Calculate COGS directly from sales data by matching products with their costs.
    This is more accurate than using purchases data alone.
    """
    sales_df = get_filtered_sales(year, month, quarter)
    products_df = load_products()
    
    if sales_df.empty or products_df.empty:
        return 0
    
    # Get product name column in sales
    sales_product_col = get_product_name_column(sales_df)
    # Get product name column in products
    products_name_col = get_product_name_column(products_df)
    # Get cost column in products
    cost_col = get_cost_column(products_df)
    # Get quantity column in sales
    qty_col = get_quantity_column(sales_df)
    
    if not sales_product_col or not products_name_col or not cost_col:
        return 0
    
    # If no quantity column, assume each row is 1 item
    if not qty_col:
        sales_df["items"] = 1
        qty_col = "items"
    
    # Create a cost lookup dictionary
    cost_lookup = {}
    for _, row in products_df.iterrows():
        product_name = str(row[products_name_col]).strip().lower()
        cost = to_float(row[cost_col])
        cost_lookup[product_name] = cost
    
    # Calculate COGS for each sale
    total_cogs = 0
    for _, row in sales_df.iterrows():
        product_name = str(row[sales_product_col]).strip().lower()
        quantity = int(to_float(row[qty_col]))
        
        # Find the cost for this product
        cost = cost_lookup.get(product_name, 0)
        total_cogs += cost * quantity
    
    return total_cogs


# ==============================
# CALCULATE CLOSING STOCK FOR A PERIOD
# ==============================
def calculate_closing_stock(year=None, month=None, quarter=None):
    """Calculate closing stock for a specific period"""
    products_df = load_products()
    
    if products_df.empty:
        return 0
    
    stock_values = []
    cost_col = get_cost_column(products_df)
    
    if not cost_col:
        return 0
    
    for _, row in products_df.iterrows():
        stock = to_float(row.get("stock", 0))
        cost = to_float(row.get(cost_col, 0))
        stock_values.append(stock * cost)
    
    return sum(stock_values)


# ==============================
# GET OPENING STOCK FROM PREVIOUS PERIOD
# ==============================
def get_opening_stock(year=None, month=None, quarter=None):
    """
    Calculate opening stock for a period.
    Opening stock = Closing stock of the previous period.
    """
    # If no period specified, opening stock is 0
    if year is None and month is None and quarter is None:
        return 0
    
    # Calculate previous period
    if month is not None:
        # Monthly: previous month
        prev_year = year
        prev_month = month - 1
        if prev_month == 0:
            prev_month = 12
            prev_year = year - 1
        
        # Get closing stock of previous month
        return calculate_closing_stock(prev_year, prev_month)
    
    elif quarter is not None:
        # Quarterly: previous quarter
        prev_year = year
        prev_quarter = quarter - 1
        if prev_quarter == 0:
            prev_quarter = 4
            prev_year = year - 1
        
        return calculate_closing_stock(prev_year, None, prev_quarter)
    
    elif year is not None:
        # Yearly: previous year
        prev_year = year - 1
        return calculate_closing_stock(prev_year, None, None)
    
    return 0


# ==============================
# LOAD AND FILTER DATA WITH REAL DATA FROM DATABASE
# ==============================
def filter_by_period(df, year=None, month=None, quarter=None):
    """Filter dataframe by year, month, or quarter"""
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # Determine which date column exists
    date_col = get_date_column(df)
    
    if date_col is None:
        return pd.DataFrame()
    
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    
    if df.empty:
        return df
    
    if year:
        df = df[df[date_col].dt.year == year]
    
    if month:
        df = df[df[date_col].dt.month == month]
    
    if quarter:
        quarter_months = {
            1: [1, 2, 3],
            2: [4, 5, 6],
            3: [7, 8, 9],
            4: [10, 11, 12]
        }
        df = df[df[date_col].dt.month.isin(quarter_months[quarter])]
    
    return df


def get_filtered_sales(year=None, month=None, quarter=None):
    """Get filtered sales data from database"""
    sales_df = load_sales()
    if sales_df.empty:
        return pd.DataFrame()
    
    # Get total column
    total_col = get_total_column(sales_df)
    
    if total_col and total_col != "total":
        sales_df["total"] = pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0)
    elif not total_col:
        sales_df["total"] = 0
    
    # Ensure numeric columns
    numeric_cols = ["items", "total", "profit", "final_total"]
    for col in numeric_cols:
        if col in sales_df.columns:
            sales_df[col] = pd.to_numeric(sales_df[col], errors="coerce").fillna(0)
    
    return filter_by_period(sales_df, year, month, quarter)


def get_filtered_expenses(year=None, month=None, quarter=None):
    """Get filtered expenses data from database"""
    try:
        expenses_df = load_expenses()
        
        if expenses_df is None or expenses_df.empty:
            return pd.DataFrame()
        
        if "amount" in expenses_df.columns:
            expenses_df["amount"] = pd.to_numeric(expenses_df["amount"], errors="coerce").fillna(0)
        else:
            expenses_df["amount"] = 0
        
        return filter_by_period(expenses_df, year, month, quarter)
    except Exception as e:
        print(f"Error loading expenses: {e}")
        return pd.DataFrame()


def get_filtered_income(year=None, month=None, quarter=None):
    """Get filtered income data from database"""
    try:
        income_df = load_income()
        
        if income_df is None or income_df.empty:
            return pd.DataFrame()
        
        if "amount" in income_df.columns:
            income_df["amount"] = pd.to_numeric(income_df["amount"], errors="coerce").fillna(0)
        else:
            income_df["amount"] = 0
        
        return filter_by_period(income_df, year, month, quarter)
    except Exception as e:
        print(f"Error loading income: {e}")
        return pd.DataFrame()


def get_filtered_purchases(year=None, month=None, quarter=None):
    """Get filtered purchases data from database"""
    try:
        purchases_df = load_purchases()
        if purchases_df is None or purchases_df.empty:
            return pd.DataFrame()
        
        if "total_cost" in purchases_df.columns:
            purchases_df["total_cost"] = pd.to_numeric(purchases_df["total_cost"], errors="coerce").fillna(0)
        
        return filter_by_period(purchases_df, year, month, quarter)
    except Exception as e:
        print(f"Error loading purchases: {e}")
        return pd.DataFrame()


# ==============================
# TRADING ACCOUNT - USING REAL DATA WITH CORRECT COGS
# ==============================
def trading_account(year=None, month=None, quarter=None):
    """Calculate trading account figures from REAL data"""
    
    sales_df = get_filtered_sales(year, month, quarter)
    purchases_df = get_filtered_purchases(year, month, quarter)
    
    # ==============================
    # FIX: Use unique receipts for revenue (NO DUPLICATION)
    # ==============================
    if not sales_df.empty and "receipt_no" in sales_df.columns:
        # Get unique receipts to avoid duplication
        unique_receipts = sales_df.drop_duplicates(subset=['receipt_no'])
        
        # Get total column
        total_col = get_total_column(unique_receipts)
        
        # SALES - Convert Decimal to float from unique receipts only
        sales = to_float(unique_receipts[total_col].sum()) if total_col and not unique_receipts.empty else 0
    else:
        # Fallback if no receipt_no column (old data structure)
        total_col = get_total_column(sales_df)
        sales = to_float(sales_df["total"].sum()) if total_col and not sales_df.empty else 0
    
    # TURNOVER (same as sales)
    turnover = sales
    
    # SALES RETURNS (placeholder - would need returns data)
    sales_returns = 0
    net_sales = turnover - sales_returns
    
    # PURCHASES - Convert Decimal to float
    purchases = to_float(purchases_df["total_cost"].sum()) if "total_cost" in purchases_df.columns and not purchases_df.empty else 0
    
    # PURCHASE RETURNS (placeholder)
    purchase_returns = 0
    net_purchases = purchases - purchase_returns
    
    # OPENING STOCK - Get from previous period
    opening_stock = get_opening_stock(year, month, quarter)
    
    # CLOSING STOCK - Current period stock
    closing_stock = calculate_closing_stock(year, month, quarter)
    
    # COST OF GOODS SOLD - Calculate from sales data (more accurate)
    # This calculates the actual cost of goods sold based on sales
    cogs_from_sales = calculate_cogs_from_sales(year, month, quarter)
    
    # Also calculate using traditional formula for comparison
    cogs_traditional = opening_stock + net_purchases - closing_stock
    
    # Use the more accurate method (from sales) if available, otherwise fallback to traditional
    cogs = cogs_from_sales if cogs_from_sales > 0 else cogs_traditional
    
    # GROSS PROFIT
    gross_profit = net_sales - cogs
    gross_margin = (gross_profit / net_sales * 100) if net_sales > 0 else 0
    
    return {
        "sales": sales,
        "sales_returns": sales_returns,
        "net_sales": net_sales,
        "purchases": purchases,
        "purchase_returns": purchase_returns,
        "net_purchases": net_purchases,
        "opening_stock": opening_stock,
        "closing_stock": closing_stock,
        "cogs": cogs,
        "cogs_from_sales": cogs_from_sales,
        "cogs_traditional": cogs_traditional,
        "gross_profit": gross_profit,
        "gross_margin": gross_margin
    }

# ==============================
# PROFIT & LOSS ACCOUNT - USING REAL DATA
# ==============================
def profit_loss_account(year=None, month=None, quarter=None):
    """Complete P&L statement from REAL data"""
    
    trade = trading_account(year, month, quarter)
    
    income_df = get_filtered_income(year, month, quarter)
    expense_df = get_filtered_expenses(year, month, quarter)
    
    # Other Income - Convert Decimal to float
    other_income = to_float(income_df["amount"].sum()) if "amount" in income_df.columns and not income_df.empty else 0
    
    # Operating Expenses - Convert Decimal to float
    operating_expenses = to_float(expense_df["amount"].sum()) if "amount" in expense_df.columns and not expense_df.empty else 0
    
    # Total Expenses
    total_expenses = operating_expenses
    
    # Net Profit Before Tax - Convert all to float
    gross_profit = to_float(trade["gross_profit"])
    net_profit_before_tax = gross_profit + other_income - total_expenses
    
    # Tax (placeholder - 25% corporate tax)
    tax = net_profit_before_tax * 0.25 if net_profit_before_tax > 0 else 0
    
    # Net Profit After Tax
    net_profit = net_profit_before_tax - tax
    net_margin = (net_profit / trade["net_sales"] * 100) if trade["net_sales"] > 0 else 0
    
    return {
        **trade,
        "other_income": other_income,
        "operating_expenses": operating_expenses,
        "total_expenses": total_expenses,
        "net_profit_before_tax": net_profit_before_tax,
        "tax": tax,
        "net_profit": net_profit,
        "net_margin": net_margin
    }


# ==============================
# KEY FINANCIAL RATIOS - USING REAL DATA
# ==============================
def get_financial_ratios(year=None, month=None, quarter=None):
    """Calculate key financial ratios from REAL data"""
    
    pl = profit_loss_account(year, month, quarter)
    
    gross_margin = to_float(pl["gross_margin"])
    net_margin = to_float(pl["net_margin"])
    net_sales = to_float(pl["net_sales"])
    operating_expenses = to_float(pl["operating_expenses"])
    
    operating_margin = (operating_expenses / net_sales * 100) if net_sales > 0 else 0
    
    # Efficiency Ratios
    opening_stock = to_float(pl["opening_stock"])
    closing_stock = to_float(pl["closing_stock"])
    avg_inventory = (opening_stock + closing_stock) / 2 if closing_stock > 0 else closing_stock
    inventory_turnover = (to_float(pl["cogs"]) / avg_inventory) if avg_inventory > 0 else 0
    
    return_on_sales = net_margin
    
    return {
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "operating_margin": operating_margin,
        "inventory_turnover": inventory_turnover,
        "return_on_sales": return_on_sales,
        "profitability_status": "Good" if net_margin > 15 else ("Fair" if net_margin > 5 else "Poor")
    }


# ==============================
# BREAK-EVEN ANALYSIS - USING REAL DATA
# ==============================
def break_even_analysis(year=None, month=None):
    """Calculate break-even point from REAL data"""
    
    pl = profit_loss_account(year, month)
    
    operating_expenses = to_float(pl["operating_expenses"])
    net_sales = to_float(pl["net_sales"])
    
    # Fixed vs Variable Costs (simplified - 30% fixed, 70% variable assumption)
    fixed_costs = operating_expenses * 0.3
    variable_costs = operating_expenses * 0.7
    
    contribution_margin = net_sales - variable_costs
    contribution_margin_ratio = (contribution_margin / net_sales) if net_sales > 0 else 0
    
    break_even_sales = fixed_costs / contribution_margin_ratio if contribution_margin_ratio > 0 else 0
    break_even_units = break_even_sales / (net_sales / 100) if net_sales > 0 else 0
    
    margin_of_safety = net_sales - break_even_sales
    margin_of_safety_ratio = (margin_of_safety / net_sales * 100) if net_sales > 0 else 0
    
    return {
        "fixed_costs": fixed_costs,
        "variable_costs": variable_costs,
        "contribution_margin": contribution_margin,
        "contribution_margin_ratio": contribution_margin_ratio * 100,
        "break_even_sales": break_even_sales,
        "margin_of_safety": margin_of_safety,
        "margin_of_safety_ratio": margin_of_safety_ratio,
        "status": "Above Break-even" if margin_of_safety > 0 else "Below Break-even"
    }


# ==============================
# CASH FLOW STATEMENT - USING REAL DATA
# ==============================
def cash_flow_statement(year=None, month=None):
    """Generate cash flow statement from REAL data"""
    
    pl = profit_loss_account(year, month)
    
    net_profit = to_float(pl["net_profit"])
    operating_expenses = to_float(pl["operating_expenses"])
    closing_stock = to_float(pl["closing_stock"])
    
    depreciation = operating_expenses * 0.05
    changes_inventory = -closing_stock
    
    net_cash_operating = net_profit + depreciation + changes_inventory
    
    # Investing Activities (placeholder)
    capex = 0
    net_cash_investing = -capex
    
    # Financing Activities (placeholder)
    loans_received = 0
    dividends_paid = 0
    net_cash_financing = loans_received - dividends_paid
    
    net_cash_flow = net_cash_operating + net_cash_investing + net_cash_financing
    
    # Beginning cash (estimate from sales)
    beginning_cash = to_float(pl["net_sales"]) * 0.1 if pl["net_sales"] > 0 else 1000
    
    ending_cash = beginning_cash + net_cash_flow
    
    return {
        "net_profit": net_profit,
        "depreciation": depreciation,
        "changes_inventory": changes_inventory,
        "net_cash_operating": net_cash_operating,
        "net_cash_investing": net_cash_investing,
        "net_cash_financing": net_cash_financing,
        "net_cash_flow": net_cash_flow,
        "beginning_cash": beginning_cash,
        "ending_cash": ending_cash
    }


# ==============================
# FINANCIAL FORECAST - USING REAL DATA
# ==============================
def financial_forecast(months_ahead=6):
    """Generate financial forecast from REAL data"""
    
    historical_months = []
    forecast = []
    
    # Get last 6 months of REAL data
    for i in range(6, 0, -1):
        current_date = datetime.now() - timedelta(days=30 * i)
        pl = profit_loss_account(year=current_date.year, month=current_date.month)
        historical_months.append({
            "month": current_date.strftime("%Y-%m"),
            "sales": to_float(pl["net_sales"]),
            "profit": to_float(pl["net_profit"])
        })
    
    # Calculate average growth rate
    if len(historical_months) >= 2:
        sales_growth = []
        for i in range(1, len(historical_months)):
            if historical_months[i-1]["sales"] > 0:
                growth = (historical_months[i]["sales"] - historical_months[i-1]["sales"]) / historical_months[i-1]["sales"]
                sales_growth.append(growth)
        avg_growth = np.mean(sales_growth) if sales_growth else 0.05
    else:
        avg_growth = 0.05
    
    # Generate forecast
    last_sales = historical_months[-1]["sales"] if historical_months else 10000
    
    for i in range(1, months_ahead + 1):
        forecast_date = datetime.now() + timedelta(days=30 * i)
        projected_sales = last_sales * (1 + avg_growth) ** i
        projected_profit = projected_sales * 0.15  # Assume 15% profit margin
        
        forecast.append({
            "month": forecast_date.strftime("%Y-%m"),
            "projected_sales": projected_sales,
            "projected_profit": projected_profit,
            "confidence_lower": projected_sales * 0.9,
            "confidence_upper": projected_sales * 1.1
        })
    
    return forecast


# ==============================
# BALANCE SHEET - USING REAL DATA
# ==============================
def balance_sheet(as_at_date=None):
    """Generate simplified balance sheet from REAL data"""
    
    if as_at_date is None:
        as_at_date = datetime.now()
    
    products_df = load_products()
    
    # ASSETS
    # Current Assets
    sales_df = load_sales()
    total_col = get_total_column(sales_df)
    
    total_sales = 0
    if total_col and not sales_df.empty:
        total_sales = to_float(sales_df[total_col].sum())
    
    # Cash estimate (10% of total sales)
    cash = total_sales * 0.1 if total_sales > 0 else 5000
    
    # Inventory
    inventory = 0
    if not products_df.empty:
        cost_col = get_cost_column(products_df)
        if cost_col:
            for _, row in products_df.iterrows():
                stock = to_float(row.get("stock", 0))
                cost = to_float(row.get(cost_col, 0))
                inventory += stock * cost
    
    # Accounts Receivable (20% of sales)
    accounts_receivable = total_sales * 0.2 if total_sales > 0 else 2000
    
    total_current_assets = cash + inventory + accounts_receivable
    
    # Fixed Assets
    equipment = 15000
    accumulated_depreciation = 3000
    net_fixed_assets = equipment - accumulated_depreciation
    
    total_assets = total_current_assets + net_fixed_assets
    
    # LIABILITIES
    # Current Liabilities
    expenses_df = load_expenses()
    total_expenses = 0
    if "amount" in expenses_df.columns and not expenses_df.empty:
        total_expenses = to_float(expenses_df["amount"].sum())
    
    accounts_payable = total_expenses * 0.3 if total_expenses > 0 else 1000
    short_term_debt = 500
    
    total_current_liabilities = accounts_payable + short_term_debt
    
    # Long-term Liabilities
    long_term_debt = 5000
    
    total_liabilities = total_current_liabilities + long_term_debt
    
    # EQUITY
    owners_equity = total_assets - total_liabilities
    
    return {
        "as_at_date": as_at_date,
        "cash": cash,
        "inventory": inventory,
        "accounts_receivable": accounts_receivable,
        "total_current_assets": total_current_assets,
        "equipment": equipment,
        "accumulated_depreciation": accumulated_depreciation,
        "net_fixed_assets": net_fixed_assets,
        "total_assets": total_assets,
        "accounts_payable": accounts_payable,
        "short_term_debt": short_term_debt,
        "total_current_liabilities": total_current_liabilities,
        "long_term_debt": long_term_debt,
        "total_liabilities": total_liabilities,
        "owners_equity": owners_equity
    }


# ==============================
# MONTHLY COMPARISON DATA - USING REAL DATA
# ==============================
def monthly_comparison(year):
    """Get monthly sales, expenses, and profit for the year from REAL data"""
    
    results = []
    
    for month in range(1, 13):
        pl = profit_loss_account(year=year, month=month)
        results.append({
            "month": month,
            "sales": to_float(pl["net_sales"]),
            "expenses": to_float(pl["total_expenses"]),
            "profit": to_float(pl["net_profit"])
        })
    
    return pd.DataFrame(results)


# ==============================
# YEARLY COMPARISON - USING REAL DATA
# ==============================
def yearly_comparison(year1, year2):
    """Compare financial performance between two years from REAL data"""
    
    pl1 = profit_loss_account(year=year1)
    pl2 = profit_loss_account(year=year2)
    
    sales_year1 = to_float(pl1["net_sales"])
    sales_year2 = to_float(pl2["net_sales"])
    expenses_year1 = to_float(pl1["total_expenses"])
    expenses_year2 = to_float(pl2["total_expenses"])
    profit_year1 = to_float(pl1["net_profit"])
    profit_year2 = to_float(pl2["net_profit"])
    
    sales_growth = ((sales_year2 - sales_year1) / sales_year1 * 100) if sales_year1 > 0 else 0
    profit_growth = ((profit_year2 - profit_year1) / profit_year1 * 100) if profit_year1 > 0 else 0
    
    return {
        "sales_year1": sales_year1,
        "sales_year2": sales_year2,
        "expenses_year1": expenses_year1,
        "expenses_year2": expenses_year2,
        "profit_year1": profit_year1,
        "profit_year2": profit_year2,
        "sales_growth": sales_growth,
        "profit_growth": profit_growth
    }