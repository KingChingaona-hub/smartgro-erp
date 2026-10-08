import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
import json

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
# SESSION BRANCH HELPERS
# ==============================
def _get_session_branch():
    """
    Return the authoritative branch for the current session.
    Prefers `current_branch_code` (set by the branch-selection screen)
    over `user_branch` (which may be a stale default).
    """
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _scoped(df, branch_id):
    """
    Filter a debtors-family DataFrame to a single branch.
    Back-fills a branch_id column if it is missing so legacy rows are
    treated as belonging to the session branch.
    """
    if df is None:
        return pd.DataFrame()
    if df.empty:
        return df
    if "branch_id" not in df.columns:
        df = df.copy()
        df["branch_id"] = str(branch_id)
        return df
    return df[
        df["branch_id"].astype(str).str.upper() == str(branch_id).upper()
    ].copy()


# ==============================
# INIT FILES
# ==============================
def init_debtors():
    """Initialize all debtors files (branch-aware schema)"""
    DATA_DIR.mkdir(exist_ok=True)

    if not DEBTORS_FILE.exists():
        df = pd.DataFrame(columns=[
            "debt_id",
            "branch_id",
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
            "notes",
            "credit_limit",
            "payment_plan",
            "installment_amount",
            "installment_frequency",
            "next_payment_date",
            "payment_history"  # Added for tracking part payments
        ])
        df.to_csv(DEBTORS_FILE, index=False)
    else:
        # Back-fill branch_id on legacy file
        try:
            existing = pd.read_csv(DEBTORS_FILE)
            if "branch_id" not in existing.columns:
                existing["branch_id"] = ""
                existing.to_csv(DEBTORS_FILE, index=False)
        except Exception:
            pass

    if not DEBTOR_PAYMENTS_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "debt_id",
            "branch_id",
            "customer_name",
            "amount_paid",
            "balance_after",
            "note",
            "receipt_no",
            "payment_method"
        ])
        df.to_csv(DEBTOR_PAYMENTS_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(DEBTOR_PAYMENTS_FILE)
            if "branch_id" not in existing.columns:
                existing["branch_id"] = ""
                existing.to_csv(DEBTOR_PAYMENTS_FILE, index=False)
        except Exception:
            pass

    if not DEBTOR_ITEMS_FILE.exists():
        df = pd.DataFrame(columns=[
            "debt_id",
            "branch_id",
            "customer_name",
            "barcode",
            "product_name",
            "quantity",
            "unit_price",
            "total_price",
            "type"  # "inventory" or "non_inventory"
        ])
        df.to_csv(DEBTOR_ITEMS_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(DEBTOR_ITEMS_FILE)
            if "branch_id" not in existing.columns:
                existing["branch_id"] = ""
                existing.to_csv(DEBTOR_ITEMS_FILE, index=False)
        except Exception:
            pass

    if not DEBTOR_REMINDERS_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "debt_id",
            "branch_id",
            "customer_name",
            "reminder_type",
            "message",
            "sent",
            "response"
        ])
        df.to_csv(DEBTOR_REMINDERS_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(DEBTOR_REMINDERS_FILE)
            if "branch_id" not in existing.columns:
                existing["branch_id"] = ""
                existing.to_csv(DEBTOR_REMINDERS_FILE, index=False)
        except Exception:
            pass


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


def to_float(value):
    """Safely convert to float"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ==============================
# LOAD / SAVE FUNCTIONS (branch-scoped)
# ==============================
def load_debtors(branch_id=None):
    """Load debtors from CSV file (branch-scoped)."""
    if branch_id is None:
        branch_id = _get_session_branch()

    init_debtors()

    if not DEBTORS_FILE.exists():
        return pd.DataFrame(columns=[
            "debt_id", "branch_id", "date_borrowed", "customer_name", "phone",
            "total_amount", "amount_paid", "balance", "expected_repayment_date",
            "repayment_date", "status", "risk_level", "provision_bad_debt",
            "bad_debt", "notes", "credit_limit", "payment_plan",
            "installment_amount", "installment_frequency", "next_payment_date",
            "payment_history"
        ])

    try:
        df = pd.read_csv(DEBTORS_FILE)

        # Ensure numeric columns
        numeric_cols = ["total_amount", "amount_paid", "balance", "provision_bad_debt", "bad_debt", "credit_limit", "installment_amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0

        # Add missing columns if they don't exist
        for col in ["credit_limit", "payment_plan", "installment_amount", "installment_frequency", "next_payment_date", "payment_history"]:
            if col not in df.columns:
                if col in ["payment_plan", "installment_frequency", "next_payment_date"]:
                    df[col] = ""
                elif col == "payment_history":
                    df[col] = ""  # Store as JSON string
                else:
                    df[col] = 0

        if "branch_id" not in df.columns:
            df["branch_id"] = ""

        return _scoped(df, branch_id)
    except Exception as e:
        print(f"Error loading debtors: {e}")
        return pd.DataFrame(columns=[
            "debt_id", "branch_id", "date_borrowed", "customer_name", "phone",
            "total_amount", "amount_paid", "balance", "expected_repayment_date",
            "repayment_date", "status", "risk_level", "provision_bad_debt",
            "bad_debt", "notes", "credit_limit", "payment_plan",
            "installment_amount", "installment_frequency", "next_payment_date",
            "payment_history"
        ])


def save_debtors(df, branch_id=None):
    """
    Save debtors to CSV file (branch-scoped).

    Merge-back behaviour: only the incoming branch's rows are replaced.
    Other branches' rows in the shared CSV are preserved.
    """
    if branch_id is None:
        branch_id = _get_session_branch()

    init_debtors()

    try:
        full_df = pd.read_csv(DEBTORS_FILE)
        if "branch_id" not in full_df.columns:
            full_df["branch_id"] = ""
    except Exception:
        full_df = pd.DataFrame()

    if df is None:
        df = pd.DataFrame()
    df = df.copy()
    if "branch_id" not in df.columns:
        df["branch_id"] = str(branch_id)

    # Drop this branch's old rows from the full frame, then append the new ones
    if not full_df.empty and "branch_id" in full_df.columns:
        full_df = full_df[
            full_df["branch_id"].astype(str).str.upper() != str(branch_id).upper()
        ]

    merged = pd.concat([full_df, df], ignore_index=True)
    if "debt_id" in merged.columns:
        merged = merged.drop_duplicates(subset=["debt_id"], keep="last")
    merged.to_csv(DEBTORS_FILE, index=False)


def load_debtor_items(branch_id=None):
    """Load debtor items (branch-scoped)."""
    if branch_id is None:
        branch_id = _get_session_branch()

    init_debtors()
    if DEBTOR_ITEMS_FILE.exists():
        try:
            df = pd.read_csv(DEBTOR_ITEMS_FILE)
            # Add type column if missing
            if "type" not in df.columns:
                df["type"] = "inventory"
            if "branch_id" not in df.columns:
                df["branch_id"] = ""
            return _scoped(df, branch_id)
        except:
            return pd.DataFrame(columns=["debt_id", "branch_id", "customer_name", "barcode", "product_name", "quantity", "unit_price", "total_price", "type"])
    return pd.DataFrame(columns=["debt_id", "branch_id", "customer_name", "barcode", "product_name", "quantity", "unit_price", "total_price", "type"])


def save_debtor_items(df, branch_id=None):
    """Save debtor items (branch-scoped, merge-back)."""
    if branch_id is None:
        branch_id = _get_session_branch()

    init_debtors()

    try:
        full_df = pd.read_csv(DEBTOR_ITEMS_FILE)
        if "branch_id" not in full_df.columns:
            full_df["branch_id"] = ""
    except Exception:
        full_df = pd.DataFrame()

    if df is None:
        df = pd.DataFrame()
    df = df.copy()
    if "branch_id" not in df.columns:
        df["branch_id"] = str(branch_id)

    if not full_df.empty and "branch_id" in full_df.columns:
        full_df = full_df[
            full_df["branch_id"].astype(str).str.upper() != str(branch_id).upper()
        ]

    merged = pd.concat([full_df, df], ignore_index=True)
    merged.to_csv(DEBTOR_ITEMS_FILE, index=False)


def load_payments(branch_id=None):
    """Load debtor payments (branch-scoped)."""
    if branch_id is None:
        branch_id = _get_session_branch()

    init_debtors()
    if DEBTOR_PAYMENTS_FILE.exists():
        try:
            df = pd.read_csv(DEBTOR_PAYMENTS_FILE)
            if "branch_id" not in df.columns:
                df["branch_id"] = ""
            return _scoped(df, branch_id)
        except:
            return pd.DataFrame(columns=["date", "debt_id", "branch_id", "customer_name", "amount_paid", "balance_after", "note", "receipt_no", "payment_method"])
    return pd.DataFrame(columns=["date", "debt_id", "branch_id", "customer_name", "amount_paid", "balance_after", "note", "receipt_no", "payment_method"])


def load_reminders(branch_id=None):
    """Load debtor reminders (branch-scoped)."""
    if branch_id is None:
        branch_id = _get_session_branch()

    init_debtors()
    if DEBTOR_REMINDERS_FILE.exists():
        try:
            df = pd.read_csv(DEBTOR_REMINDERS_FILE)
            if "branch_id" not in df.columns:
                df["branch_id"] = ""
            return _scoped(df, branch_id)
        except:
            return pd.DataFrame(columns=["date", "debt_id", "branch_id", "customer_name", "reminder_type", "message", "sent", "response"])
    return pd.DataFrame(columns=["date", "debt_id", "branch_id", "customer_name", "reminder_type", "message", "sent", "response"])


# ==============================
# CASH MOVEMENT HELPER
# ==============================
def record_cash_movement(amount, receipt_no, payment_method="CASH", shift_id="", branch_id=None):
    """Record cash movement from debt payments (branch-scoped)."""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        CASH_FILE.parent.mkdir(exist_ok=True)

        if not CASH_FILE.exists():
            df = pd.DataFrame(columns=["date", "branch_id", "type", "amount", "receipt_no", "customer_name", "note", "shift_id"])
            df.to_csv(CASH_FILE, index=False)
        else:
            df = pd.read_csv(CASH_FILE)
            if "branch_id" not in df.columns:
                df["branch_id"] = ""

        new_row = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "branch_id": str(branch_id),
            "type": "DEBT_PAYMENT",
            "amount": float(amount),
            "receipt_no": receipt_no,
            "customer_name": "",
            "note": f"Debt payment - {payment_method}",
            "shift_id": shift_id
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(CASH_FILE, index=False)
        return True
    except Exception as e:
        print(f"Cash recording error: {e}")
        return False


# ==============================
# CREATE DEBT WITH ITEMS (branch-scoped)
# ==============================
def create_debt_with_items(customer_name, phone, items_list, total_amount, expected_date, notes="", credit_limit=0, payment_plan="", installment_amount=0, installment_frequency="", next_payment_date="", branch_id=None):
    """Create debt with multiple items - STOCK IS DEDUCTED for inventory items only (branch-scoped)"""

    if branch_id is None:
        branch_id = _get_session_branch()

    try:
        from backend.core.db_adapter import load_products, save_products
    except ImportError:
        # Fallback if db_adapter not available
        def load_products(branch_id=None):
            try:
                from backend.core.db_adapter import load_products as lp
                return lp(branch_id=branch_id)
            except:
                return pd.DataFrame(columns=["barcode", "name", "stock", "price"])

        def save_products(df, branch_id=None):
            try:
                from backend.core.db_adapter import save_products as sp
                sp(df, branch_id=branch_id)
            except:
                pass

    df = load_debtors(branch_id=branch_id)
    items_df = load_debtor_items(branch_id=branch_id)
    products_df = load_products(branch_id=branch_id)

    # Generate unique debt ID
    debt_id = f"DEBT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # DEDUCT STOCK ONLY FOR INVENTORY ITEMS (non-inventory items don't affect stock)
    stock_errors = []
    for item in items_list:
        item_type = item.get("type", "inventory")
        barcode = safe_str(item.get("barcode", ""))

        # Only deduct stock for inventory items
        if item_type == "inventory" and not barcode.startswith("MANUAL"):
            if not products_df.empty and "barcode" in products_df.columns:
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
    try:
        save_products(products_df, branch_id=branch_id)
    except:
        pass

    # Create debt record
    new_row = {
        "debt_id": debt_id,
        "branch_id": str(branch_id),
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
        "notes": notes,
        "payment_history": ""  # Initialize empty payment history
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_debtors(df, branch_id=branch_id)

    # Save items for this debt
    for item in items_list:
        item_type = item.get("type", "inventory")
        barcode = safe_str(item.get("barcode", "MANUAL"))
        item_row = {
            "debt_id": debt_id,
            "branch_id": str(branch_id),
            "customer_name": customer_name,
            "barcode": barcode,
            "product_name": item["name"],
            "quantity": int(item["quantity"]),
            "unit_price": float(item["price"]),
            "total_price": float(item["price"]) * int(item["quantity"]),
            "type": item_type
        }
        items_df = pd.concat([items_df, pd.DataFrame([item_row])], ignore_index=True)

    save_debtor_items(items_df, branch_id=branch_id)

    # Also record as credit sale in cash register
    try:
        from backend.modules.cash_register import record_credit_sale
        try:
            record_credit_sale(
                amount=total_amount,
                receipt_no=debt_id,
                customer_name=customer_name,
                shift_id="",
                branch_id=branch_id,
            )
        except TypeError:
            record_credit_sale(
                amount=total_amount,
                receipt_no=debt_id,
                customer_name=customer_name,
                shift_id=""
            )
    except:
        pass

    return True, debt_id


# ==============================
# LEGACY CREATE DEBT
# ==============================
def create_debt(customer_name, phone, items, total_amount, expected_date, branch_id=None):
    """Legacy function - kept for compatibility"""
    items_list = [{
        "barcode": "MANUAL",
        "name": str(items),
        "quantity": 1,
        "price": float(total_amount),
        "type": "non_inventory"
    }]
    success, debt_id = create_debt_with_items(customer_name, phone, items_list, total_amount, expected_date, "", 0, "", 0, "", "", branch_id=branch_id)
    return debt_id if success else None


# ==============================
# GET DEBT ITEMS
# ==============================
def get_debt_items(debt_id, branch_id=None):
    """Get all items for a specific debt (branch-scoped)."""
    items_df = load_debtor_items(branch_id=branch_id)
    if items_df.empty or "debt_id" not in items_df.columns:
        return pd.DataFrame(columns=["debt_id", "branch_id", "customer_name", "barcode", "product_name", "quantity", "unit_price", "total_price", "type"])
    result = items_df[items_df["debt_id"] == debt_id]
    if "type" not in result.columns:
        result["type"] = "inventory"
    return result


# ==============================
# RECORD DEBT PAYMENT (Supports Part Payments, branch-scoped)
# ==============================
def record_debt_payment(customer_name, amount, shift_id="", receipt_no=None, payment_method="CASH", branch_id=None):
    """Record a debt payment - supports part payments (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_debtors(branch_id=branch_id)
    payments = load_payments(branch_id=branch_id)

    # Get all debts for this customer with outstanding balance
    customer_debts = df[df["customer_name"] == customer_name]

    if customer_debts.empty:
        return False

    amount = float(amount)
    remaining_to_allocate = amount

    # Sort debts by oldest first (or by expected repayment date)
    customer_debts = customer_debts.sort_values("expected_repayment_date")

    payment_history = []

    for idx in customer_debts.index:
        if remaining_to_allocate <= 0:
            break

        debt_id = df.at[idx, "debt_id"]
        current_balance = float(df.at[idx, "balance"])

        if current_balance <= 0:
            continue

        # Determine payment amount for this debt
        if remaining_to_allocate >= current_balance:
            payment_amount = current_balance
        else:
            payment_amount = remaining_to_allocate

        # Update debt
        df.at[idx, "amount_paid"] += payment_amount
        df.at[idx, "balance"] -= payment_amount

        remaining_to_allocate -= payment_amount

        # Record payment
        if receipt_no is None:
            receipt_no = f"PAY-{debt_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        new_payment = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "debt_id": debt_id,
            "branch_id": str(branch_id),
            "customer_name": customer_name,
            "amount_paid": payment_amount,
            "balance_after": df.at[idx, "balance"],
            "note": f"Part payment - {payment_method}",
            "receipt_no": receipt_no,
            "payment_method": payment_method
        }
        payments = pd.concat([payments, pd.DataFrame([new_payment])], ignore_index=True)

        # Add to payment history
        payment_history.append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "debt_id": debt_id,
            "amount": payment_amount,
            "balance_after": df.at[idx, "balance"]
        })

        # Mark as PAID if balance is zero
        if df.at[idx, "balance"] <= 0:
            df.at[idx, "balance"] = 0
            df.at[idx, "status"] = "PAID"
            df.at[idx, "repayment_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            df.at[idx, "status"] = "PARTIAL"

        # Update next payment date if on payment plan
        if df.at[idx, "installment_amount"] > 0 and df.at[idx, "balance"] > 0:
            freq = df.at[idx, "installment_frequency"]
            next_date = datetime.now()
            if freq == "Weekly":
                next_date = next_date + timedelta(days=7)
            elif freq == "Monthly":
                next_date = next_date + timedelta(days=30)
            df.at[idx, "next_payment_date"] = next_date.strftime("%Y-%m-%d")

    # Save updated data (branch-scoped merge-back)
    save_debtors(df, branch_id=branch_id)

    # Merge payments back into the shared CSV
    try:
        full_payments = pd.read_csv(DEBTOR_PAYMENTS_FILE)
        if "branch_id" not in full_payments.columns:
            full_payments["branch_id"] = ""
    except Exception:
        full_payments = pd.DataFrame()
    if not full_payments.empty and "branch_id" in full_payments.columns:
        full_payments = full_payments[
            full_payments["branch_id"].astype(str).str.upper() != str(branch_id).upper()
        ]
    merged_payments = pd.concat([full_payments, payments], ignore_index=True)
    merged_payments.to_csv(DEBTOR_PAYMENTS_FILE, index=False)

    # Record cash movement
    if payment_method == "CASH":
        record_cash_movement(
            amount=amount,
            receipt_no=receipt_no,
            payment_method="CASH",
            shift_id=shift_id,
            branch_id=branch_id,
        )

    return True


# ==============================
# UPDATE CREDIT LIMIT
# ==============================
def update_credit_limit(customer_name, new_limit, branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_debtors(branch_id=branch_id)
    match = df[df["customer_name"] == customer_name]

    if not match.empty:
        idx = match.index[0]
        df.at[idx, "credit_limit"] = float(new_limit)
        save_debtors(df, branch_id=branch_id)
        return True
    return False


# ==============================
# GET OVERDUE DEBTORS
# ==============================
def get_overdue_debtors(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_debtors(branch_id=branch_id)

    if df.empty:
        return df

    df["expected_repayment_date"] = pd.to_datetime(df["expected_repayment_date"], errors="coerce")
    now = pd.Timestamp.now()

    overdue = df[
        (df["status"].isin(["NOT PAID", "PARTIAL"])) &
        (df["expected_repayment_date"] < now) &
        (df["balance"] > 0)
    ]

    if not overdue.empty:
        overdue["days_overdue"] = (now - overdue["expected_repayment_date"]).dt.days

    return overdue


# ==============================
# UPDATE RISK LEVELS
# ==============================
def update_risk_levels(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_debtors(branch_id=branch_id)

    if df.empty:
        return df

    now = pd.Timestamp.now()

    for i in df.index:
        balance = float(df.at[i, "balance"])
        expected = pd.to_datetime(df.at[i, "expected_repayment_date"], errors="coerce")
        days_overdue = (now - expected).days if not pd.isna(expected) else 0

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

    save_debtors(df, branch_id=branch_id)
    return df


# ==============================
# CREDIT SCORE
# ==============================
def get_credit_score(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_debtors(branch_id=branch_id)
    update_risk_levels(branch_id=branch_id)

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

        # Adjust for credit limit usage
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
def get_blocked_customers(threshold=30, branch_id=None):
    df = get_credit_score(branch_id=branch_id)
    if df.empty:
        return df
    return df[df["credit_score"] <= threshold]


# ==============================
# DEBT AGING REPORT
# ==============================
def get_debt_aging(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_debtors(branch_id=branch_id)
    update_risk_levels(branch_id=branch_id)

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
def get_aging_summary(branch_id=None):
    df = get_debt_aging(branch_id=branch_id)

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
def generate_reminders(branch_id=None):
    """Generate reminder messages for overdue debtors (branch-scoped)"""
    overdue = get_overdue_debtors(branch_id=branch_id)
    reminders = []

    if overdue.empty:
        return reminders

    for _, row in overdue.iterrows():
        days = row.get("days_overdue", 0)
        balance = row["balance"]

        if days <= 7:
            message = f"Gentle Reminder: Your payment of ${balance:.2f} is due."
        elif days <= 30:
            message = f"Payment Reminder: ${balance:.2f} is now {days} days overdue."
        elif days <= 60:
            message = f"URGENT: ${balance:.2f} is {days} days overdue. Please pay immediately."
        else:
            message = f"FINAL NOTICE: ${balance:.2f} is {days} days overdue. Account may be blocked."

        reminders.append({
            "customer_name": row["customer_name"],
            "phone": row["phone"],
            "balance": balance,
            "days_overdue": days,
            "message": message,
            "debt_id": str(row["debt_id"]),
            "expected_repayment_date": row["expected_repayment_date"]
        })

    return reminders


# ==============================
# GET CUSTOMER DEBT SUMMARY
# ==============================
def get_customer_debt_summary(customer_name, branch_id=None):
    """Get complete debt summary for a customer (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()

    debts = load_debtors(branch_id=branch_id)
    items = load_debtor_items(branch_id=branch_id)

    customer_debts = debts[debts["customer_name"] == customer_name]

    if customer_debts.empty:
        return None

    credit_limit = 0
    if "credit_limit" in customer_debts.columns and not customer_debts.empty:
        credit_limit = customer_debts["credit_limit"].iloc[0] if not pd.isna(customer_debts["credit_limit"].iloc[0]) else 0

    summary = {
        "customer_name": customer_name,
        "total_borrowed": customer_debts["total_amount"].sum(),
        "total_paid": customer_debts["amount_paid"].sum(),
        "outstanding": customer_debts["balance"].sum(),
        "active_debts": len(customer_debts[customer_debts["status"].isin(["NOT PAID", "PARTIAL"])]),
        "credit_limit": credit_limit,
        "credit_available": max(0, credit_limit - customer_debts["balance"].sum()),
        "items": []
    }

    # Get items for all customer debts
    if not items.empty and "debt_id" in items.columns:
        for debt_id in customer_debts["debt_id"]:
            debt_items = items[items["debt_id"] == debt_id]
            for _, item in debt_items.iterrows():
                summary["items"].append({
                    "debt_id": debt_id,
                    "product": item["product_name"],
                    "quantity": item["quantity"],
                    "price": item["unit_price"],
                    "total": item["total_price"],
                    "type": item.get("type", "inventory")
                })

    # Add payment history
    payments = load_payments(branch_id=branch_id)
    if not payments.empty:
        customer_payments = payments[payments["customer_name"] == customer_name]
        summary["payment_history"] = customer_payments.to_dict('records')
    else:
        summary["payment_history"] = []

    return summary


# ==============================
# RECOVERABLE DEBT CALCULATION
# ==============================
def get_recoverable_debt(branch_id=None):
    """Calculate estimated recoverable debt based on aging (branch-scoped)"""
    aging_summary = get_aging_summary(branch_id=branch_id)

    # Recovery rates by aging bucket
    recovery_rates = {
        "current": 0.95,
        "days_1_30": 0.85,
        "days_31_60": 0.70,
        "days_61_90": 0.50,
        "days_90_plus": 0.20
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