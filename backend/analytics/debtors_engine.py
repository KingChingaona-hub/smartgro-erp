import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta

# ==============================
# FILE SETUP
# ==============================
DATA_DIR = Path("data")
DEBTORS_FILE = DATA_DIR / "debtors.csv"
DEBTOR_PAYMENTS_FILE = DATA_DIR / "debtor_payments.csv"
DEBTOR_ITEMS_FILE = DATA_DIR / "debtor_items.csv"
DEBTOR_REMINDERS_FILE = DATA_DIR / "debtor_reminders.csv"
CASH_FILE = DATA_DIR / "cash_register.csv"


# ==============================
# INIT FILES
# ==============================
def init_debtors():
    """Initialize all debtors files"""
    if not DEBTORS_FILE.exists():
        df = pd.DataFrame(columns=[
            "debt_id",
            "date_borrowed",
            "customer_name",
            "phone",
            "total_amount",
            "amount_paid",
            "balance",
            "expected_repayment_date",
            "repayment_date",
            "status",
            "risk_level",
            "provision_bad_debt",
            "bad_debt",
            "notes"
        ])
        df.to_csv(DEBTORS_FILE, index=False)

    if not DEBTOR_PAYMENTS_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "debt_id",
            "customer_name",
            "amount_paid",
            "balance_after",
            "note",
            "receipt_no"
        ])
        df.to_csv(DEBTOR_PAYMENTS_FILE, index=False)

    if not DEBTOR_ITEMS_FILE.exists():
        df = pd.DataFrame(columns=[
            "debt_id",
            "customer_name",
            "barcode",
            "product_name",
            "quantity",
            "unit_price",
            "total_price"
        ])
        df.to_csv(DEBTOR_ITEMS_FILE, index=False)

    if not DEBTOR_REMINDERS_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "debt_id",
            "customer_name",
            "reminder_type",
            "message",
            "sent",
            "response"
        ])
        df.to_csv(DEBTOR_REMINDERS_FILE, index=False)


# ==============================
# HELPER FUNCTION FOR SAFE STRING CONVERSION
# ==============================
def safe_str(value):
    """Safely convert any value to string for startswith check"""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


# ==============================
# LOAD / SAVE FUNCTIONS
# ==============================
def load_debtors():
    init_debtors()
    df = pd.read_csv(DEBTORS_FILE)
    
    # Ensure numeric columns
    numeric_cols = ["total_amount", "amount_paid", "balance", "provision_bad_debt", "bad_debt"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0
    
    # Add missing columns if they don't exist (for backward compatibility)
    if "credit_limit" not in df.columns:
        df["credit_limit"] = 0
    
    if "payment_plan" not in df.columns:
        df["payment_plan"] = ""
    
    if "installment_amount" not in df.columns:
        df["installment_amount"] = 0
    
    if "installment_frequency" not in df.columns:
        df["installment_frequency"] = ""
    
    if "next_payment_date" not in df.columns:
        df["next_payment_date"] = ""
    
    return df


def save_debtors(df):
    df.to_csv(DEBTORS_FILE, index=False)


def load_debtor_items():
    init_debtors()
    if DEBTOR_ITEMS_FILE.exists():
        return pd.read_csv(DEBTOR_ITEMS_FILE)
    return pd.DataFrame(columns=["debt_id", "customer_name", "barcode", "product_name", "quantity", "unit_price", "total_price"])


def save_debtor_items(df):
    df.to_csv(DEBTOR_ITEMS_FILE, index=False)


def load_payments():
    init_debtors()
    return pd.read_csv(DEBTOR_PAYMENTS_FILE)


def load_reminders():
    init_debtors()
    return pd.read_csv(DEBTOR_REMINDERS_FILE)


# ==============================
# CASH MOVEMENT HELPER
# ==============================
def record_cash_movement(amount, receipt_no, payment_method="CASH", shift_id=""):
    """Record cash movement from debt payments"""
    try:
        if not CASH_FILE.exists():
            df = pd.DataFrame(columns=["date", "type", "amount", "receipt_no", "customer_name", "note", "shift_id"])
            df.to_csv(CASH_FILE, index=False)
        else:
            df = pd.read_csv(CASH_FILE)
        
        new_row = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "DEBT_PAYMENT",
            "amount": float(amount),
            "receipt_no": receipt_no,
            "customer_name": receipt_no.split("-")[1] if "-" in receipt_no else "",
            "note": "Debt payment",
            "shift_id": shift_id
        }
        
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(CASH_FILE, index=False)
        return True
    except Exception as e:
        print(f"Cash recording error: {e}")
        return False


# ==============================
# CREATE DEBT WITH ITEMS (FIXED)
# ==============================
def create_debt_with_items(customer_name, phone, items_list, total_amount, expected_date, notes="", credit_limit=0, payment_plan="", installment_amount=0, installment_frequency="", next_payment_date=""):
    """Create debt with multiple items - STOCK IS DEDUCTED"""
    
    from backend.core.database import load_products, save_products
    
    df = load_debtors()
    items_df = load_debtor_items()
    products_df = load_products()
    
    # Generate unique debt ID
    debt_id = f"DEBT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # DEDUCT STOCK FOR EACH ITEM (CREDIT SALE)
    stock_errors = []
    for item in items_list:
        barcode = safe_str(item.get("barcode", ""))
        
        if not barcode.startswith("MANUAL"):
            product = products_df[products_df["barcode"].astype(str) == barcode]
            if not product.empty:
                idx = product.index[0]
                current_stock = int(products_df.at[idx, "stock"])
                if current_stock >= item["quantity"]:
                    products_df.at[idx, "stock"] = current_stock - item["quantity"]
                else:
                    stock_errors.append(f"{item['name']}: Only {current_stock} available")
    
    if stock_errors:
        return False, "Stock insufficient: " + ", ".join(stock_errors)
    
    # Save updated stock
    save_products(products_df)
    
    # Create debt record
    new_row = {
        "debt_id": debt_id,
        "date_borrowed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": customer_name,
        "phone": phone,
        "total_amount": float(total_amount),
        "amount_paid": 0.0,
        "balance": float(total_amount),
        "credit_limit": float(credit_limit),
        "expected_repayment_date": expected_date,
        "repayment_date": "",
        "status": "NOT PAID",
        "risk_level": "LOW",
        "payment_plan": payment_plan,
        "installment_amount": float(installment_amount),
        "installment_frequency": installment_frequency,
        "next_payment_date": next_payment_date,
        "provision_bad_debt": float(total_amount) * 0.05,
        "bad_debt": 0.0,
        "notes": notes
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_debtors(df)
    
    # Save items for this debt
    for item in items_list:
        barcode = safe_str(item.get("barcode", "MANUAL"))
        item_row = {
            "debt_id": debt_id,
            "customer_name": customer_name,
            "barcode": barcode,
            "product_name": item["name"],
            "quantity": item["quantity"],
            "unit_price": item["price"],
            "total_price": item["price"] * item["quantity"]
        }
        items_df = pd.concat([items_df, pd.DataFrame([item_row])], ignore_index=True)
    
    save_debtor_items(items_df)
    
    # Also record as credit sale in cash register
    from backend.modules.cash_register import record_credit_sale
    record_credit_sale(
        amount=total_amount,
        receipt_no=debt_id,
        customer_name=customer_name,
        shift_id=""
    )
    
    return True, debt_id


# ==============================
# LEGACY CREATE DEBT (For backward compatibility)
# ==============================
def create_debt(customer_name, phone, items, total_amount, expected_date):
    """Legacy function - kept for compatibility"""
    items_list = [{
        "barcode": "MANUAL",
        "name": str(items),
        "quantity": 1,
        "price": float(total_amount)
    }]
    success, debt_id = create_debt_with_items(customer_name, phone, items_list, total_amount, expected_date, "", 0, "", 0, "", "")
    return debt_id if success else None


# ==============================
# GET DEBT ITEMS
# ==============================
def get_debt_items(debt_id):
    """Get all items for a specific debt"""
    items_df = load_debtor_items()
    return items_df[items_df["debt_id"] == debt_id]


# ==============================
# RECORD DEBT PAYMENT
# ==============================
def record_debt_payment(customer_name, amount, shift_id="", receipt_no=None):
    df = load_debtors()
    payments = load_payments()

    match = df[df["customer_name"] == customer_name]

    if match.empty:
        return False

    i = match.index[0]
    amount = float(amount)
    old_balance = float(df.at[i, "balance"])
    debt_id = df.at[i, "debt_id"]

    # Prevent overpayment
    if amount > old_balance:
        amount = old_balance

    df.at[i, "amount_paid"] += amount
    df.at[i, "balance"] -= amount

    # Payment log
    if receipt_no is None:
        receipt_no = f"PAY-{debt_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    new_payment = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "debt_id": debt_id,
        "customer_name": customer_name,
        "amount_paid": amount,
        "balance_after": df.at[i, "balance"],
        "note": "Debt repayment",
        "receipt_no": receipt_no
    }
    payments = pd.concat([payments, pd.DataFrame([new_payment])], ignore_index=True)

    # Mark as paid if balance is zero
    if df.at[i, "balance"] <= 0:
        df.at[i, "balance"] = 0
        df.at[i, "status"] = "PAID"
        df.at[i, "repayment_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update next payment date if on payment plan
    if "installment_amount" in df.columns and df.at[i, "installment_amount"] > 0 and df.at[i, "balance"] > 0:
        freq = df.at[i, "installment_frequency"]
        next_date = datetime.now()
        if freq == "Weekly":
            next_date = next_date + timedelta(days=7)
        elif freq == "Monthly":
            next_date = next_date + timedelta(days=30)
        df.at[i, "next_payment_date"] = next_date.strftime("%Y-%m-%d")

    # Record payment in cash register
    record_cash_movement(
        amount=amount,
        receipt_no=receipt_no,
        payment_method="CASH",
        shift_id=shift_id
    )

    save_debtors(df)
    payments.to_csv(DEBTOR_PAYMENTS_FILE, index=False)

    return True


# ==============================
# UPDATE CREDIT LIMIT
# ==============================
def update_credit_limit(customer_name, new_limit):
    df = load_debtors()
    match = df[df["customer_name"] == customer_name]
    
    if not match.empty:
        idx = match.index[0]
        df.at[idx, "credit_limit"] = float(new_limit)
        save_debtors(df)
        return True
    return False


# ==============================
# GET OVERDUE DEBTORS
# ==============================
def get_overdue_debtors():
    df = load_debtors()

    if df.empty:
        return df

    df["expected_repayment_date"] = pd.to_datetime(df["expected_repayment_date"], errors="coerce")
    now = pd.Timestamp.now()

    overdue = df[
        (df["status"] == "NOT PAID") &
        (df["expected_repayment_date"] < now) &
        (df["balance"] > 0)
    ]
    
    # Add days overdue column
    overdue["days_overdue"] = (now - overdue["expected_repayment_date"]).dt.days

    return overdue


# ==============================
# UPDATE RISK LEVELS (FIXED - Safe column handling)
# ==============================
def update_risk_levels():
    df = load_debtors()
    now = pd.Timestamp.now()

    for i in df.index:
        balance = float(df.at[i, "balance"])
        expected = pd.to_datetime(df.at[i, "expected_repayment_date"], errors="coerce")
        days_overdue = (now - expected).days if not pd.isna(expected) else 0
        
        # Safe credit limit check (column may not exist in old data)
        credit_limit = 0
        if "credit_limit" in df.columns:
            credit_limit = float(df.at[i, "credit_limit"]) if not pd.isna(df.at[i, "credit_limit"]) else 0
        
        credit_usage = (balance / credit_limit * 100) if credit_limit > 0 else 0

        if balance <= 0:
            risk = "NONE"
        elif days_overdue <= 0:
            if credit_usage > 80:
                risk = "MEDIUM"
            else:
                risk = "LOW"
        elif days_overdue <= 15:
            risk = "MEDIUM"
        elif days_overdue <= 45:
            risk = "HIGH"
        else:
            risk = "CRITICAL"

        df.at[i, "risk_level"] = risk

    save_debtors(df)
    return df


# ==============================
# CREDIT SCORE (FIXED - Safe column handling)
# ==============================
def get_credit_score():
    df = load_debtors()
    update_risk_levels()

    if df.empty:
        return df

    now = pd.Timestamp.now()

    def calculate_score(row):
        if row["balance"] <= 0:
            return 100

        expected = pd.to_datetime(row["expected_repayment_date"], errors="coerce")
        if pd.isna(expected):
            return 50

        days_overdue = (now - expected).days
        
        # Base score
        if days_overdue <= 0:
            score = 80
        elif days_overdue <= 15:
            score = 60
        elif days_overdue <= 45:
            score = 30
        else:
            score = 10
        
        # Adjust for credit limit usage (safe check)
        if "credit_limit" in df.columns:
            credit_limit = row["credit_limit"] if not pd.isna(row["credit_limit"]) else 0
            if credit_limit > 0:
                usage = (row["balance"] / credit_limit) * 100
                if usage > 90:
                    score -= 20
                elif usage > 70:
                    score -= 10
        
        return max(0, min(100, score))

    df["credit_score"] = df.apply(calculate_score, axis=1)
    return df.sort_values("credit_score", ascending=True)


# ==============================
# BLOCKED CUSTOMERS
# ==============================
def get_blocked_customers(threshold=30):
    df = get_credit_score()
    if df.empty:
        return df
    return df[df["credit_score"] <= threshold]


# ==============================
# DEBT AGING REPORT
# ==============================
def get_debt_aging():
    df = load_debtors()
    update_risk_levels()

    if df.empty:
        return df

    df["expected_repayment_date"] = pd.to_datetime(df["expected_repayment_date"], errors="coerce")
    now = pd.Timestamp.now()

    def aging_bucket(row):
        if row["balance"] <= 0:
            return "Paid"

        if pd.isna(row["expected_repayment_date"]):
            return "Unscheduled"

        days = (now - row["expected_repayment_date"]).days

        if days <= 0:
            return "Current"
        elif days <= 30:
            return "1-30 Days Overdue"
        elif days <= 60:
            return "31-60 Days Overdue"
        elif days <= 90:
            return "61-90 Days Overdue"
        return "90+ Days (Critical)"

    df["aging_bucket"] = df.apply(aging_bucket, axis=1)
    return df


# ==============================
# GET AGING SUMMARY
# ==============================
def get_aging_summary():
    df = get_debt_aging()
    
    if df.empty:
        return {
            "current": 0,
            "days_1_30": 0,
            "days_31_60": 0,
            "days_61_90": 0,
            "days_90_plus": 0,
            "total_outstanding": 0
        }
    
    summary = {
        "current": df[df["aging_bucket"] == "Current"]["balance"].sum(),
        "days_1_30": df[df["aging_bucket"] == "1-30 Days Overdue"]["balance"].sum(),
        "days_31_60": df[df["aging_bucket"] == "31-60 Days Overdue"]["balance"].sum(),
        "days_61_90": df[df["aging_bucket"] == "61-90 Days Overdue"]["balance"].sum(),
        "days_90_plus": df[df["aging_bucket"] == "90+ Days (Critical)"]["balance"].sum(),
        "total_outstanding": df["balance"].sum()
    }
    
    return summary


# ==============================
# GENERATE REMINDER MESSAGES
# ==============================
def generate_reminders():
    """Generate reminder messages for overdue debtors"""
    overdue = get_overdue_debtors()
    reminders = []
    
    for _, row in overdue.iterrows():
        days = row["days_overdue"] if "days_overdue" in row else 0
        balance = row["balance"]
        
        if days <= 7:
            message = f"🔔 Gentle Reminder: Your payment of ${balance:.2f} is due."
        elif days <= 30:
            message = f"⚠️ Payment Reminder: ${balance:.2f} is now {days} days overdue."
        elif days <= 60:
            message = f"🚨 URGENT: ${balance:.2f} is {days} days overdue. Please pay immediately."
        else:
            message = f"⛔ FINAL NOTICE: ${balance:.2f} is {days} days overdue. Account may be blocked."
        
        reminders.append({
            "customer_name": row["customer_name"],
            "phone": row["phone"],
            "balance": balance,
            "days_overdue": days,
            "message": message,
            "debt_id": str(row["debt_id"])
        })
    
    return reminders


# ==============================
# GET CUSTOMER DEBT SUMMARY
# ==============================
def get_customer_debt_summary(customer_name):
    """Get complete debt summary for a customer"""
    debts = load_debtors()
    items = load_debtor_items()
    
    customer_debts = debts[debts["customer_name"] == customer_name]
    
    if customer_debts.empty:
        return None
    
    # Safe credit limit access
    credit_limit = 0
    if "credit_limit" in customer_debts.columns and not customer_debts.empty:
        credit_limit = customer_debts["credit_limit"].iloc[0] if not pd.isna(customer_debts["credit_limit"].iloc[0]) else 0
    
    summary = {
        "customer_name": customer_name,
        "total_borrowed": customer_debts["total_amount"].sum(),
        "total_paid": customer_debts["amount_paid"].sum(),
        "outstanding": customer_debts["balance"].sum(),
        "active_debts": len(customer_debts[customer_debts["status"] == "NOT PAID"]),
        "credit_limit": credit_limit,
        "credit_available": max(0, credit_limit - customer_debts["balance"].sum()),
        "items": []
    }
    
    # Get items for all customer debts
    for debt_id in customer_debts["debt_id"]:
        debt_items = items[items["debt_id"] == debt_id]
        for _, item in debt_items.iterrows():
            summary["items"].append({
                "debt_id": debt_id,
                "product": item["product_name"],
                "quantity": item["quantity"],
                "price": item["unit_price"],
                "total": item["total_price"]
            })
    
    return summary


# ==============================
# RECOVERABLE DEBT CALCULATION
# ==============================
def get_recoverable_debt():
    """Calculate estimated recoverable debt based on aging"""
    aging_summary = get_aging_summary()
    
    # Recovery rates by aging bucket
    recovery_rates = {
        "current": 0.95,      # 95% recovery
        "days_1_30": 0.85,    # 85% recovery
        "days_31_60": 0.70,   # 70% recovery
        "days_61_90": 0.50,   # 50% recovery
        "days_90_plus": 0.20  # 20% recovery
    }
    
    expected_recovery = (
        aging_summary["current"] * recovery_rates["current"] +
        aging_summary["days_1_30"] * recovery_rates["days_1_30"] +
        aging_summary["days_31_60"] * recovery_rates["days_31_60"] +
        aging_summary["days_61_90"] * recovery_rates["days_61_90"] +
        aging_summary["days_90_plus"] * recovery_rates["days_90_plus"]
    )
    
    expected_loss = aging_summary["total_outstanding"] - expected_recovery
    
    return {
        "total_outstanding": aging_summary["total_outstanding"],
        "expected_recovery": expected_recovery,
        "expected_loss": expected_loss,
        "recovery_rate": (expected_recovery / aging_summary["total_outstanding"] * 100) if aging_summary["total_outstanding"] > 0 else 0
    }