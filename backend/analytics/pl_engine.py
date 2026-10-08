# backend/analytics/pl_engine.py
# Branch-aware P&L engine.
#
# Branch scoping rules:
#   branch_id = None            -> resolve from session (current user's branch)
#   branch_id = "HO" / "NAT"..  -> that single branch
#   branch_id = "__ALL__"       -> aggregate across ALL branches (owner only)
#
# Every public function accepts branch_id and threads it through every
# underlying load_* call. Return shapes are preserved for backwards
# compatibility with reports_engine, business_advisor_engine, and
# automated_insights.

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal

from backend.core.db_adapter import (
    load_sales,
    load_purchases,
    load_products,
    load_branches,
)
from backend.modules.expenses import load_expenses
from backend.modules.income import load_income


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    """
    Resolve the effective branch for a query.

    - Explicit branch code is honoured.
    - ALL_BRANCHES sentinel is honoured (means company-wide).
    - None falls back to the current session's branch.
    """
    if branch_id is not None:
        return branch_id
    try:
        import streamlit as st
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
    """
    Call a loader with the correct branch scope.

    - If __ALL__: no branch_id passed, so the loader returns all rows
      (loaders default to the session branch otherwise, so we must pass
      an explicit 'all' path. Because db_adapter has no all-branch mode,
      we call the loader once per branch and concat.)
    - Otherwise: pass branch_id through.
    """
    if _is_all_branches(branch_id):
        try:
            branches_df = load_branches()
        except Exception:
            branches_df = pd.DataFrame()

        if branches_df is None or branches_df.empty or "branch_id" not in branches_df.columns:
            # fall back to a single call; better than nothing
            try:
                return loader(**kwargs)
            except Exception:
                return pd.DataFrame()

        frames = []
        for bid in branches_df["branch_id"].astype(str).tolist():
            try:
                df = loader(branch_id=bid, **kwargs)
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception:
                continue
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    # Single-branch path
    try:
        return loader(branch_id=branch_id, **kwargs)
    except TypeError:
        # Loader doesn't accept branch_id - fall back
        try:
            return loader(**kwargs)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ==============================
# HELPERS
# ==============================
def to_float(value):
    """Safely convert Decimal or any value to float."""
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


def get_total_column(df):
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in df.columns:
            return col
    return None


def get_cost_column(df):
    if df is None or df.empty:
        return None
    for col in ["cost", "cost_price", "unit_cost", "purchase_price"]:
        if col in df.columns:
            return col
    return None


def get_date_column(df):
    if df is None or df.empty:
        return None
    for col in [
        "sale_date", "date", "transaction_date", "created_at",
        "expense_date", "income_date",
    ]:
        if col in df.columns:
            return col
    return None


def get_product_name_column(df):
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "item_name", "product"]:
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


def _reinsert_branch_id(df, branch_id):
    """Ensure df carries a branch_id column so _enforce_branch stays usable."""
    if df is None or df.empty:
        return df
    if "branch_id" not in df.columns and not _is_all_branches(branch_id):
        df = df.copy()
        df["branch_id"] = branch_id
    return df


# ==============================
# PERIOD FILTERING
# ==============================
def filter_by_period(df, year=None, month=None, quarter=None):
    """Filter dataframe by year, month, or quarter. Preserves branch_id."""
    if df is None or df.empty:
        return df

    df = df.copy()
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
        quarter_months = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}
        df = df[df[date_col].dt.month.isin(quarter_months[quarter])]

    return df


# ==============================
# SCOPED LOADERS
# ==============================
def get_filtered_sales(branch_id=None, year=None, month=None, quarter=None):
    """Get branch-scoped sales data, optionally filtered by period."""
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)

    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    total_col = get_total_column(sales_df)
    if total_col and total_col != "total":
        sales_df["total"] = pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0)
    elif not total_col:
        sales_df["total"] = 0

    for col in ["items", "total", "profit", "final_total"]:
        if col in sales_df.columns:
            sales_df[col] = pd.to_numeric(sales_df[col], errors="coerce").fillna(0)

    sales_df = _reinsert_branch_id(sales_df, branch_id)

    return filter_by_period(sales_df, year, month, quarter)


def get_filtered_expenses(branch_id=None, year=None, month=None, quarter=None):
    """Get branch-scoped expenses, optionally filtered by period."""
    branch_id = _resolve_branch(branch_id)

    try:
        if _is_all_branches(branch_id):
            expenses_df = _load_scoped(load_expenses, branch_id)
        else:
            expenses_df = load_expenses(branch_id=branch_id)
    except Exception as e:
        print(f"[pl_engine] load_expenses failed: {e}")
        return pd.DataFrame()

    if expenses_df is None or expenses_df.empty:
        return pd.DataFrame()

    if "amount" in expenses_df.columns:
        expenses_df["amount"] = pd.to_numeric(expenses_df["amount"], errors="coerce").fillna(0)
    else:
        expenses_df["amount"] = 0

    expenses_df = _reinsert_branch_id(expenses_df, branch_id)

    return filter_by_period(expenses_df, year, month, quarter)


def get_filtered_income(branch_id=None, year=None, month=None, quarter=None):
    """Get branch-scoped income, optionally filtered by period."""
    branch_id = _resolve_branch(branch_id)

    try:
        if _is_all_branches(branch_id):
            income_df = _load_scoped(load_income, branch_id)
        else:
            income_df = load_income(branch_id=branch_id)
    except Exception as e:
        print(f"[pl_engine] load_income failed: {e}")
        return pd.DataFrame()

    if income_df is None or income_df.empty:
        return pd.DataFrame()

    if "amount" in income_df.columns:
        income_df["amount"] = pd.to_numeric(income_df["amount"], errors="coerce").fillna(0)
    else:
        income_df["amount"] = 0

    income_df = _reinsert_branch_id(income_df, branch_id)

    return filter_by_period(income_df, year, month, quarter)


def get_filtered_purchases(branch_id=None, year=None, month=None, quarter=None):
    """Get branch-scoped purchases, optionally filtered by period."""
    branch_id = _resolve_branch(branch_id)

    try:
        purchases_df = _load_scoped(load_purchases, branch_id)
    except Exception as e:
        print(f"[pl_engine] load_purchases failed: {e}")
        return pd.DataFrame()

    if purchases_df is None or purchases_df.empty:
        return pd.DataFrame()

    if "total_cost" in purchases_df.columns:
        purchases_df["total_cost"] = pd.to_numeric(
            purchases_df["total_cost"], errors="coerce"
        ).fillna(0)

    purchases_df = _reinsert_branch_id(purchases_df, branch_id)

    return filter_by_period(purchases_df, year, month, quarter)


# ==============================
# COGS FROM SALES
# ==============================
def calculate_cogs_from_sales(branch_id=None, year=None, month=None, quarter=None):
    """
    COGS calculated by matching each sale's product to its cost in the
    SAME BRANCH's product catalogue.
    """
    branch_id = _resolve_branch(branch_id)

    sales_df = get_filtered_sales(branch_id, year, month, quarter)
    products_df = _load_scoped(load_products, branch_id)

    if sales_df is None or sales_df.empty or products_df is None or products_df.empty:
        return 0

    sales_product_col = get_product_name_column(sales_df)
    products_name_col = get_product_name_column(products_df)
    cost_col = get_cost_column(products_df)
    qty_col = get_quantity_column(sales_df)

    if not sales_product_col or not products_name_col or not cost_col:
        return 0

    if not qty_col:
        sales_df = sales_df.copy()
        sales_df["items"] = 1
        qty_col = "items"

    # ---- Build cost lookup, keyed by (branch_id, product_name) when possible ----
    cost_lookup = {}
    has_branch_col = "branch_id" in products_df.columns
    for _, row in products_df.iterrows():
        name = str(row[products_name_col]).strip().lower()
        cost = to_float(row[cost_col])
        if has_branch_col:
            bid = str(row["branch_id"]).upper()
            cost_lookup[(bid, name)] = cost
        else:
            cost_lookup[name] = cost

    # ---- Lookup per sale ----
    has_sales_branch = "branch_id" in sales_df.columns
    total_cogs = 0.0
    for _, row in sales_df.iterrows():
        name = str(row[sales_product_col]).strip().lower()
        qty = int(to_float(row[qty_col]))
        if has_sales_branch:
            bid = str(row["branch_id"]).upper()
            cost = cost_lookup.get((bid, name), 0.0)
        else:
            cost = cost_lookup.get(name, 0.0)
        total_cogs += cost * qty

    return total_cogs


# ==============================
# CLOSING / OPENING STOCK
# ==============================
def calculate_closing_stock(branch_id=None, year=None, month=None, quarter=None):
    """Closing stock value for the branch's current product catalogue."""
    branch_id = _resolve_branch(branch_id)

    products_df = _load_scoped(load_products, branch_id)
    if products_df is None or products_df.empty:
        return 0

    cost_col = get_cost_column(products_df)
    if not cost_col:
        return 0

    total = 0.0
    for _, row in products_df.iterrows():
        stock = to_float(row.get("stock", 0))
        cost = to_float(row.get(cost_col, 0))
        total += stock * cost
    return total


def get_opening_stock(branch_id=None, year=None, month=None, quarter=None):
    """
    Opening stock for a period = closing stock of the previous period.
    Period arguments decide what "previous" means.
    """
    branch_id = _resolve_branch(branch_id)

    if year is None and month is None and quarter is None:
        return 0

    if month is not None:
        prev_year = year
        prev_month = month - 1
        if prev_month == 0:
            prev_month = 12
            prev_year = year - 1
        return calculate_closing_stock(branch_id, prev_year, prev_month)

    if quarter is not None:
        prev_year = year
        prev_quarter = quarter - 1
        if prev_quarter == 0:
            prev_quarter = 4
            prev_year = year - 1
        return calculate_closing_stock(branch_id, prev_year, None, prev_quarter)

    if year is not None:
        return calculate_closing_stock(branch_id, year - 1, None, None)

    return 0


# ==============================
# TRADING ACCOUNT
# ==============================
def trading_account(branch_id=None, year=None, month=None, quarter=None):
    """
    Trading account figures for a single branch (or __ALL__).

    NOTE: the signature has been extended with branch_id as the FIRST
    argument. All existing callers that pass year/month/quarter by keyword
    continue to work; positional callers must be updated to pass branch_id
    first, or use keywords.
    """
    branch_id = _resolve_branch(branch_id)

    sales_df = get_filtered_sales(branch_id, year, month, quarter)
    purchases_df = get_filtered_purchases(branch_id, year, month, quarter)

    # ---- Sales revenue ----
    # Deduplicate by receipt_no so a multi-line receipt isn't counted
    # once per line.
    if not sales_df.empty and "receipt_no" in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=["receipt_no"])
        total_col = get_total_column(unique_receipts)
        sales = to_float(unique_receipts[total_col].sum()) if total_col else 0
    else:
        total_col = get_total_column(sales_df)
        sales = to_float(sales_df["total"].sum()) if total_col and not sales_df.empty else 0

    turnover = sales
    sales_returns = 0
    net_sales = turnover - sales_returns

    # ---- Purchases ----
    purchases = (
        to_float(purchases_df["total_cost"].sum())
        if "total_cost" in purchases_df.columns and not purchases_df.empty
        else 0
    )
    purchase_returns = 0
    net_purchases = purchases - purchase_returns

    # ---- Stock ----
    opening_stock = get_opening_stock(branch_id, year, month, quarter)
    closing_stock = calculate_closing_stock(branch_id, year, month, quarter)

    # ---- COGS ----
    cogs_from_sales = calculate_cogs_from_sales(branch_id, year, month, quarter)
    cogs_traditional = opening_stock + net_purchases - closing_stock
    cogs = cogs_from_sales if cogs_from_sales > 0 else cogs_traditional

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
        "gross_margin": gross_margin,
        "branch_id": branch_id,
    }


# ==============================
# PROFIT & LOSS ACCOUNT
# ==============================
def profit_loss_account(branch_id=None, year=None, month=None, quarter=None):
    """
    Full P&L statement for a single branch (or __ALL__).

    Signature extended with branch_id first. Keyword callers preserved.
    """
    branch_id = _resolve_branch(branch_id)

    trade = trading_account(branch_id, year, month, quarter)

    income_df = get_filtered_income(branch_id, year, month, quarter)
    expense_df = get_filtered_expenses(branch_id, year, month, quarter)

    other_income = (
        to_float(income_df["amount"].sum())
        if "amount" in income_df.columns and not income_df.empty
        else 0
    )
    operating_expenses = (
        to_float(expense_df["amount"].sum())
        if "amount" in expense_df.columns and not expense_df.empty
        else 0
    )

    total_expenses = operating_expenses

    gross_profit = to_float(trade["gross_profit"])
    net_profit_before_tax = gross_profit + other_income - total_expenses

    tax = net_profit_before_tax * 0.25 if net_profit_before_tax > 0 else 0
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
        "net_margin": net_margin,
        "branch_id": branch_id,
    }


# ==============================
# FINANCIAL RATIOS
# ==============================
def get_financial_ratios(branch_id=None, year=None, month=None, quarter=None):
    branch_id = _resolve_branch(branch_id)

    pl = profit_loss_account(branch_id, year, month, quarter)

    gross_margin = to_float(pl["gross_margin"])
    net_margin = to_float(pl["net_margin"])
    net_sales = to_float(pl["net_sales"])
    operating_expenses = to_float(pl["operating_expenses"])

    operating_margin = (operating_expenses / net_sales * 100) if net_sales > 0 else 0

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
        "profitability_status": "Good" if net_margin > 15 else ("Fair" if net_margin > 5 else "Poor"),
    }


# ==============================
# BREAK-EVEN
# ==============================
def break_even_analysis(branch_id=None, year=None, month=None):
    branch_id = _resolve_branch(branch_id)

    pl = profit_loss_account(branch_id, year, month)

    operating_expenses = to_float(pl["operating_expenses"])
    net_sales = to_float(pl["net_sales"])

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
        "break_even_units": break_even_units,
        "margin_of_safety": margin_of_safety,
        "margin_of_safety_ratio": margin_of_safety_ratio,
        "status": "Above Break-even" if margin_of_safety > 0 else "Below Break-even",
    }


# ==============================
# CASH FLOW
# ==============================
def cash_flow_statement(branch_id=None, year=None, month=None):
    branch_id = _resolve_branch(branch_id)

    pl = profit_loss_account(branch_id, year, month)

    net_profit = to_float(pl["net_profit"])
    operating_expenses = to_float(pl["operating_expenses"])
    closing_stock = to_float(pl["closing_stock"])

    depreciation = operating_expenses * 0.05
    changes_inventory = -closing_stock

    net_cash_operating = net_profit + depreciation + changes_inventory

    capex = 0
    net_cash_investing = -capex

    loans_received = 0
    dividends_paid = 0
    net_cash_financing = loans_received - dividends_paid

    net_cash_flow = net_cash_operating + net_cash_investing + net_cash_financing

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
        "ending_cash": ending_cash,
    }


# ==============================
# FORECAST
# ==============================
def financial_forecast(branch_id=None, months_ahead=6):
    branch_id = _resolve_branch(branch_id)

    historical_months = []
    for i in range(6, 0, -1):
        current_date = datetime.now() - timedelta(days=30 * i)
        pl = profit_loss_account(branch_id, year=current_date.year, month=current_date.month)
        historical_months.append({
            "month": current_date.strftime("%Y-%m"),
            "sales": to_float(pl["net_sales"]),
            "profit": to_float(pl["net_profit"]),
        })

    if len(historical_months) >= 2:
        growth = []
        for i in range(1, len(historical_months)):
            prev = historical_months[i - 1]["sales"]
            cur = historical_months[i]["sales"]
            if prev > 0:
                growth.append((cur - prev) / prev)
        avg_growth = np.mean(growth) if growth else 0.05
    else:
        avg_growth = 0.05

    last_sales = historical_months[-1]["sales"] if historical_months else 10000

    forecast = []
    for i in range(1, months_ahead + 1):
        forecast_date = datetime.now() + timedelta(days=30 * i)
        projected_sales = last_sales * (1 + avg_growth) ** i
        projected_profit = projected_sales * 0.15
        forecast.append({
            "month": forecast_date.strftime("%Y-%m"),
            "projected_sales": projected_sales,
            "projected_profit": projected_profit,
            "confidence_lower": projected_sales * 0.9,
            "confidence_upper": projected_sales * 1.1,
        })

    return forecast


# ==============================
# BALANCE SHEET
# ==============================
def balance_sheet(branch_id=None, as_at_date=None):
    branch_id = _resolve_branch(branch_id)

    if as_at_date is None:
        as_at_date = datetime.now()

    products_df = _load_scoped(load_products, branch_id)
    sales_df = get_filtered_sales(branch_id)

    total_col = get_total_column(sales_df)
    total_sales = 0
    if total_col and not sales_df.empty:
        total_sales = to_float(sales_df[total_col].sum())

    cash = total_sales * 0.1 if total_sales > 0 else 5000

    inventory = 0
    if products_df is not None and not products_df.empty:
        cost_col = get_cost_column(products_df)
        if cost_col:
            for _, row in products_df.iterrows():
                stock = to_float(row.get("stock", 0))
                cost = to_float(row.get(cost_col, 0))
                inventory += stock * cost

    accounts_receivable = total_sales * 0.2 if total_sales > 0 else 2000
    total_current_assets = cash + inventory + accounts_receivable

    equipment = 15000
    accumulated_depreciation = 3000
    net_fixed_assets = equipment - accumulated_depreciation
    total_assets = total_current_assets + net_fixed_assets

    # Scoped expenses for the branch
    expenses_df = get_filtered_expenses(branch_id)
    total_expenses = (
        to_float(expenses_df["amount"].sum())
        if "amount" in expenses_df.columns and not expenses_df.empty
        else 0
    )

    accounts_payable = total_expenses * 0.3 if total_expenses > 0 else 1000
    short_term_debt = 500
    total_current_liabilities = accounts_payable + short_term_debt
    long_term_debt = 5000
    total_liabilities = total_current_liabilities + long_term_debt
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
        "owners_equity": owners_equity,
        "branch_id": branch_id,
    }


# ==============================
# COMPARISONS
# ==============================
def monthly_comparison(branch_id=None, year=None):
    branch_id = _resolve_branch(branch_id)

    results = []
    for month in range(1, 13):
        pl = profit_loss_account(branch_id, year=year, month=month)
        results.append({
            "month": month,
            "sales": to_float(pl["net_sales"]),
            "expenses": to_float(pl["total_expenses"]),
            "profit": to_float(pl["net_profit"]),
        })
    return pd.DataFrame(results)


def yearly_comparison(branch_id=None, year1=None, year2=None):
    branch_id = _resolve_branch(branch_id)

    pl1 = profit_loss_account(branch_id, year=year1)
    pl2 = profit_loss_account(branch_id, year=year2)

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
        "profit_growth": profit_growth,
    }