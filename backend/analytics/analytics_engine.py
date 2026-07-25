import pandas as pd

# ==============================
# SAFE NORMALIZER (FIXED)
# ==============================
def normalize_sales(df: pd.DataFrame):

    if df is None or df.empty:
        return pd.DataFrame(columns=["barcode", "name", "items", "total", "profit"])

    df = df.copy()

    # required fields
    required_cols = ["barcode", "name", "items", "total", "profit"]

    for col in required_cols:
        if col not in df.columns:
            df[col] = 0

    # force numeric
    df["items"] = pd.to_numeric(df["items"], errors="coerce").fillna(0)
    df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)
    df["profit"] = pd.to_numeric(df["profit"], errors="coerce").fillna(0)

    # FIX: remove duplicate receipt-level inflation issue
    df = df[df["items"] > 0]

    return df


# ==============================
# REVENUE (FIXED LOGIC)
# ==============================
def get_revenue(df):
    df = normalize_sales(df)

    # FIX: avoid duplicated receipt totals
    return df["total"].sum()


# ==============================
# PROFIT
# ==============================
def get_profit(df):
    df = normalize_sales(df)
    return df["profit"].sum()


# ==============================
# ITEMS SOLD
# ==============================
def get_items_sold(df):
    df = normalize_sales(df)
    return df["items"].sum()


# ==============================
# TOP PRODUCTS (FIXED)
# ==============================
def get_top_products(df, top_n=5):

    df = normalize_sales(df)

    if df.empty:
        return pd.DataFrame(columns=["barcode", "name", "items"])

    grouped = (
        df.groupby(["barcode", "name"], as_index=False)
        .agg({
            "items": "sum",
            "total": "sum",
            "profit": "sum"
        })
        .sort_values("items", ascending=False)
        .head(top_n)
    )

    return grouped


# ==============================
# CASH HELPERS
# ==============================
def get_cash_expected(opening_cash, cash_sales):
    return opening_cash + cash_sales


def get_cash_variance(actual_cash, expected_cash):
    return actual_cash - expected_cash


# ==============================
# DAILY SUMMARY (FIXED)
# ==============================
def get_daily_summary(df, opening_cash=0, actual_cash=0):

    df = normalize_sales(df)

    revenue = get_revenue(df)
    profit = get_profit(df)
    items = get_items_sold(df)

    expected_cash = get_cash_expected(opening_cash, revenue)
    variance = get_cash_variance(actual_cash, expected_cash)

    return {
        "revenue": revenue,
        "profit": profit,
        "items": items,
        "cash_expected": expected_cash,
        "variance": variance
    }