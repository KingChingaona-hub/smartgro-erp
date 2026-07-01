import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import logging

from backend.core.db_adapter import (
    load_sales,
    load_products,
    save_products,
    get_current_branch,
    save_sales
)
from backend.modules.cash_register import record_cash_movement

# ==============================
# LOGGING SETUP
# ==============================
logger = logging.getLogger(__name__)

# ==============================
# CONSTANTS & CONFIGURATION
# ==============================
DATA_DIR = Path("data")
RETURNS_FILE = DATA_DIR / "returns.csv"
REFUNDS_FILE = DATA_DIR / "refunds.csv"
STORE_CREDIT_FILE = DATA_DIR / "store_credit.csv"
STOCK_MOVEMENT_FILE = DATA_DIR / "stock_movements.csv"
WRITE_OFF_FILE = DATA_DIR / "write_offs.csv"

RETURN_PERIOD_DAYS = 30
ALLOWED_RETURN_ROLES = {"owner", "manager", "admin"}

RETURN_COLUMNS = [
    "return_id", "receipt_no", "return_date", "customer_name", "customer_phone",
    "product_barcode", "product_name", "quantity_returned", "refund_amount",
    "return_reason", "condition", "status", "refund_method", "store_credit_id",
    "processed_by", "processed_date", "branch_id", "shift_id", "notes"
]

REFUND_COLUMNS = [
    "refund_id", "return_id", "receipt_no", "refund_date", "customer_name",
    "amount", "refund_method", "reference_no", "processed_by", "branch_id", "notes"
]

STORE_CREDIT_COLUMNS = [
    "credit_id", "customer_name", "customer_phone", "amount", "remaining_balance",
    "issued_date", "expiry_date", "status", "issued_by", "branch_id", "used_transactions", "notes"
]

STOCK_MOVEMENT_COLUMNS = [
    "movement_id", "product_barcode", "product_name", "quantity", "movement_type",
    "reference", "reason", "created_by", "created_date", "branch_id"
]

WRITE_OFF_COLUMNS = [
    "write_off_id", "product_barcode", "product_name", "quantity", "reason",
    "reference", "created_by", "created_date", "branch_id", "notes"
]


# ==============================
# FILE OPERATIONS
# ==============================
def init_files():
    """Initialize all required CSV files"""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        
        if not RETURNS_FILE.exists():
            pd.DataFrame(columns=RETURN_COLUMNS).to_csv(RETURNS_FILE, index=False)
        
        if not REFUNDS_FILE.exists():
            pd.DataFrame(columns=REFUND_COLUMNS).to_csv(REFUNDS_FILE, index=False)
        
        if not STORE_CREDIT_FILE.exists():
            pd.DataFrame(columns=STORE_CREDIT_COLUMNS).to_csv(STORE_CREDIT_FILE, index=False)
        
        if not STOCK_MOVEMENT_FILE.exists():
            pd.DataFrame(columns=STOCK_MOVEMENT_COLUMNS).to_csv(STOCK_MOVEMENT_FILE, index=False)
        
        if not WRITE_OFF_FILE.exists():
            pd.DataFrame(columns=WRITE_OFF_COLUMNS).to_csv(WRITE_OFF_FILE, index=False)
            
    except Exception as e:
        logger.error(f"Error initializing files: {e}")
        raise


def load_returns():
    """Load returns data"""
    init_files()
    try:
        return pd.read_csv(RETURNS_FILE)
    except:
        return pd.DataFrame(columns=RETURN_COLUMNS)


def save_returns(df):
    """Save returns data"""
    try:
        df.to_csv(RETURNS_FILE, index=False)
        return True
    except Exception as e:
        logger.error(f"Error saving returns: {e}")
        return False


def load_refunds():
    """Load refunds data"""
    init_files()
    try:
        return pd.read_csv(REFUNDS_FILE)
    except:
        return pd.DataFrame(columns=REFUND_COLUMNS)


def save_refunds(df):
    """Save refunds data"""
    try:
        df.to_csv(REFUNDS_FILE, index=False)
        return True
    except Exception as e:
        logger.error(f"Error saving refunds: {e}")
        return False


def load_store_credit():
    """Load store credit data"""
    init_files()
    try:
        df = pd.read_csv(STORE_CREDIT_FILE)
        if "notes" not in df.columns:
            df["notes"] = ""
        return df
    except:
        return pd.DataFrame(columns=STORE_CREDIT_COLUMNS)


def save_store_credit(df):
    """Save store credit data"""
    try:
        df.to_csv(STORE_CREDIT_FILE, index=False)
        return True
    except Exception as e:
        logger.error(f"Error saving store credit: {e}")
        return False


def load_stock_movements():
    """Load stock movements data"""
    init_files()
    try:
        return pd.read_csv(STOCK_MOVEMENT_FILE)
    except:
        return pd.DataFrame(columns=STOCK_MOVEMENT_COLUMNS)


def save_stock_movements(df):
    """Save stock movements data"""
    try:
        df.to_csv(STOCK_MOVEMENT_FILE, index=False)
        return True
    except Exception as e:
        logger.error(f"Error saving stock movements: {e}")
        return False


def load_write_offs():
    """Load write-offs data"""
    init_files()
    try:
        return pd.read_csv(WRITE_OFF_FILE)
    except:
        return pd.DataFrame(columns=WRITE_OFF_COLUMNS)


def save_write_offs(df):
    """Save write-offs data"""
    try:
        df.to_csv(WRITE_OFF_FILE, index=False)
        return True
    except Exception as e:
        logger.error(f"Error saving write-offs: {e}")
        return False


# ==============================
# CORE BUSINESS LOGIC
# ==============================
def get_already_returned_quantity(receipt_no, barcode):
    """Get total already returned quantity for a product"""
    try:
        returns_df = load_returns()
        if returns_df.empty:
            return 0
        
        filtered = returns_df[
            (returns_df["receipt_no"].astype(str) == str(receipt_no)) &
            (returns_df["product_barcode"].astype(str) == str(barcode))
        ]
        
        return filtered["quantity_returned"].sum() if not filtered.empty else 0
    except:
        return 0


def find_sale_by_receipt(receipt_no):
    """Find a sale by receipt number"""
    try:
        sales_df = load_sales()
        if sales_df.empty:
            return None
        
        receipt_no = str(receipt_no).strip()
        
        if "receipt_no" not in sales_df.columns:
            return None
        
        matches = sales_df[sales_df["receipt_no"] == receipt_no]
        if not matches.empty:
            return matches
        
        matches = sales_df[sales_df["receipt_no"].astype(str).str.strip() == receipt_no]
        if not matches.empty:
            return matches
        
        return None
    except:
        return None


def get_sale_items(receipt_no):
    """Get all items from a sale grouped by product with return history"""
    try:
        sales_df = load_sales()
        receipt_no = str(receipt_no).strip()
        
        sale_rows = sales_df[sales_df["receipt_no"] == receipt_no]
        if sale_rows.empty:
            sale_rows = sales_df[sales_df["receipt_no"].astype(str).str.strip() == receipt_no]
        
        if sale_rows.empty:
            return []
        
        grouped = {}
        for _, row in sale_rows.iterrows():
            barcode = str(row.get("barcode", ""))
            name = str(row.get("product_name", row.get("name", "Unknown")))
            qty = int(row.get("items", 1))
            total = float(row.get("total", 0))
            price = total / qty if qty > 0 else 0
            
            already_returned = get_already_returned_quantity(receipt_no, barcode)
            available_qty = qty - already_returned
            
            key = barcode if barcode else name
            if key in grouped:
                grouped[key]["quantity"] += qty
                grouped[key]["available"] += available_qty
                grouped[key]["total"] += total
            else:
                grouped[key] = {
                    "name": name,
                    "barcode": barcode,
                    "quantity": qty,
                    "available": available_qty,
                    "price": price,
                    "total": total,
                    "already_returned": already_returned
                }
        
        return list(grouped.values())
    except:
        return []


def check_return_period(sale_date_str):
    """Check if return is within allowed period"""
    try:
        if not sale_date_str:
            return True, "No sale date found"
        
        sale_date = pd.to_datetime(sale_date_str)
        days_diff = (datetime.now() - sale_date).days
        
        if days_diff > RETURN_PERIOD_DAYS:
            return False, f"Return period expired ({days_diff} days, limit {RETURN_PERIOD_DAYS} days)"
        
        return True, f"Within return period ({days_diff} days)"
    except:
        return True, "Could not verify return period"


def record_stock_movement(barcode, name, quantity, movement_type, reference, reason, branch_id):
    """Record stock movement for audit trail"""
    try:
        movements_df = load_stock_movements()
        
        movement_id = f"MOV{len(movements_df)+1:08d}"
        
        new_movement = pd.DataFrame([{
            "movement_id": movement_id,
            "product_barcode": str(barcode),
            "product_name": str(name),
            "quantity": quantity,
            "movement_type": movement_type,
            "reference": str(reference),
            "reason": str(reason),
            "created_by": st.session_state.get("username", "system"),
            "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "branch_id": str(branch_id)
        }])
        
        movements_df = pd.concat([movements_df, new_movement], ignore_index=True)
        save_stock_movements(movements_df)
        return True
    except:
        return False


def record_write_off(barcode, name, quantity, reason, reference, branch_id, notes=""):
    """Record a write-off for damaged/expired items"""
    try:
        write_offs_df = load_write_offs()
        
        write_off_id = f"WO{len(write_offs_df)+1:08d}"
        
        new_write_off = pd.DataFrame([{
            "write_off_id": write_off_id,
            "product_barcode": str(barcode),
            "product_name": str(name),
            "quantity": quantity,
            "reason": reason,
            "reference": str(reference),
            "created_by": st.session_state.get("username", "system"),
            "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "branch_id": str(branch_id),
            "notes": notes
        }])
        
        write_offs_df = pd.concat([write_offs_df, new_write_off], ignore_index=True)
        save_write_offs(write_offs_df)
        return True
    except:
        return False


def generate_return_id():
    """Generate unique return ID using UUID"""
    return f"RET-{uuid.uuid4().hex[:8].upper()}"


def process_return(receipt_no, items, reason, condition, refund_method, notes=""):
    """Process a return - main business logic"""
    try:
        init_files()
        
        role = st.session_state.get("role", "cashier")
        if role not in ALLOWED_RETURN_ROLES:
            return False, "Unauthorized: Only managers and owners can process returns", [], 0
        
        sales_df = load_sales()
        products_df = load_products()
        returns_df = load_returns()
        refunds_df = load_refunds()
        current_branch = get_current_branch()
        shift_id = st.session_state.get("shift_id", "")
        
        receipt_no = str(receipt_no).strip()
        
        original_sale = find_sale_by_receipt(receipt_no)
        if original_sale is None or original_sale.empty:
            return False, "Receipt not found", [], 0
        
        sale_row = original_sale.iloc[0]
        customer_name = sale_row.get("customer", sale_row.get("customer_name", "Walk-in Customer"))
        customer_phone = sale_row.get("customer_phone", sale_row.get("phone", ""))
        sale_date = sale_row.get("date", sale_row.get("sale_date", ""))
        
        is_valid, period_msg = check_return_period(sale_date)
        if not is_valid:
            return False, period_msg, [], 0
        
        total_refund = 0
        return_ids = []
        returned_products = []
        
        for item in items:
            qty = int(item["quantity"])
            price = float(item["price"])
            refund_amount = qty * price
            total_refund += refund_amount
            
            barcode = str(item.get("barcode", ""))
            name = str(item.get("name", ""))
            
            already_returned = get_already_returned_quantity(receipt_no, barcode)
            available_qty = int(item.get("available", qty))
            
            if qty > available_qty:
                return False, f"Only {available_qty} units of {name} available for return", [], 0
            
            returned_products.append({
                "barcode": barcode,
                "name": name,
                "quantity": qty,
                "price": price
            })
            
            return_id = generate_return_id()
            return_ids.append(return_id)
            
            new_return = pd.DataFrame([{
                "return_id": return_id,
                "receipt_no": receipt_no,
                "return_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "customer_name": str(customer_name),
                "customer_phone": str(customer_phone),
                "product_barcode": barcode,
                "product_name": name,
                "quantity_returned": qty,
                "refund_amount": refund_amount,
                "return_reason": reason,
                "condition": condition,
                "status": "COMPLETED",
                "refund_method": refund_method,
                "store_credit_id": "",
                "processed_by": st.session_state.get("username", "system"),
                "processed_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "branch_id": str(current_branch),
                "shift_id": str(shift_id),
                "notes": notes
            }])
            
            returns_df = pd.concat([returns_df, new_return], ignore_index=True)
            
            # ============================================================
            # STOCK HANDLING BASED ON CONDITION
            # ============================================================
            product_idx = products_df[products_df["barcode"].astype(str) == barcode].index
            
            if len(product_idx) > 0:
                current_stock = float(products_df.loc[product_idx[0], "stock"])
                
                # WRITE-OFF: For expired or damaged items - DO NOT add back to stock
                if condition.lower() in ["expired", "damaged", "broken", "faulty", "write-off"]:
                    # Record as write-off, stock remains unchanged
                    record_write_off(
                        barcode=barcode,
                        name=name,
                        quantity=qty,
                        reason=f"Return - {condition}",
                        reference=receipt_no,
                        branch_id=current_branch,
                        notes=f"Returned as {condition} from receipt {receipt_no}"
                    )
                    movement_type = "WRITE_OFF"
                    stock_reason = f"Write-off: {condition} from receipt {receipt_no}"
                    
                elif condition.lower() in ["new", "unused", "like new"]:
                    products_df.loc[product_idx[0], "stock"] = current_stock + qty
                    movement_type = "RETURN_STOCK"
                    stock_reason = f"Returned from receipt {receipt_no} - Condition: {condition}"
                    
                else:
                    products_df.loc[product_idx[0], "stock"] = current_stock + qty
                    movement_type = "RETURN_STOCK"
                    stock_reason = f"Returned from receipt {receipt_no} - Condition: {condition}"
                
                # Record stock movement
                record_stock_movement(
                    barcode=barcode,
                    name=name,
                    quantity=qty,
                    movement_type=movement_type,
                    reference=receipt_no,
                    reason=stock_reason,
                    branch_id=current_branch
                )
        
        # Create negative sale entry
        if returned_products:
            return_receipt = f"RET-{receipt_no}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            for product in returned_products:
                return_sale = pd.DataFrame([{
                    "branch_id": str(current_branch),
                    "sale_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "receipt_no": return_receipt,
                    "barcode": product["barcode"],
                    "product_name": product["name"],
                    "items": -product["quantity"],
                    "total": -(product["price"] * product["quantity"]),
                    "profit": 0,
                    "payment_method": refund_method,
                    "customer_name": str(customer_name),
                    "customer_phone": str(customer_phone),
                    "final_total": -total_refund,
                    "shift_id": str(shift_id),
                    "cashier": st.session_state.get("username", "system"),
                    "return_id": ",".join(return_ids)
                }])
                sales_df = pd.concat([sales_df, return_sale], ignore_index=True)
        
        # Handle refund
        if refund_method == "STORE_CREDIT":
            existing_credit = check_existing_store_credit(customer_phone, customer_name)
            
            if existing_credit:
                credit_id = update_store_credit(existing_credit, total_refund)
                credit_msg = f"Updated existing credit {credit_id} (+${total_refund:.2f})"
            else:
                credit_id = create_store_credit(customer_name, customer_phone, total_refund)
                credit_msg = f"Created new credit {credit_id} for ${total_refund:.2f}"
            
            for rid in return_ids:
                returns_df.loc[returns_df["return_id"] == rid, "store_credit_id"] = credit_id
            
            st.info(f"💳 {credit_msg}")
            
        else:
            refund_id = f"REF{len(refunds_df)+1:08d}"
            new_refund = pd.DataFrame([{
                "refund_id": refund_id,
                "return_id": ",".join(return_ids),
                "receipt_no": receipt_no,
                "refund_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "customer_name": str(customer_name),
                "amount": total_refund,
                "refund_method": refund_method,
                "reference_no": f"REF-{receipt_no}",
                "processed_by": st.session_state.get("username", "system"),
                "branch_id": str(current_branch),
                "notes": notes
            }])
            refunds_df = pd.concat([refunds_df, new_refund], ignore_index=True)
            
            if refund_method == "CASH":
                try:
                    record_cash_movement(-total_refund, f"REFUND-{receipt_no}", "REFUND", shift_id)
                except:
                    pass
        
        save_products(products_df)
        save_sales(sales_df)
        save_returns(returns_df)
        save_refunds(refunds_df)
        
        summary = "Return processed successfully!\n\n"
        summary += f"📋 Receipt: {receipt_no}\n"
        summary += f"👤 Customer: {customer_name}\n"
        summary += f"💰 Total Refund: ${total_refund:.2f}\n"
        summary += f"📦 Refund Method: {refund_method}\n\n"
        
        written_off = [p for p in returned_products if any(
            item.get("condition", "").lower() in ["expired", "damaged", "broken", "faulty", "write-off"]
            for item in items if item.get("barcode") == p["barcode"]
        )]
        
        if written_off:
            summary += "⚠️ WRITE-OFF ITEMS (Not returned to stock):\n"
            for p in written_off:
                summary += f"   • {p['name']}: {p['quantity']} units - {condition}\n"
        
        return True, summary, returned_products, total_refund
        
    except Exception as e:
        logger.error(f"Error processing return: {e}")
        return False, f"Error processing return: {str(e)}", [], 0


# ==============================
# STORE CREDIT FUNCTIONS
# ==============================
def check_existing_store_credit(phone, name):
    """Check if customer already has active store credit"""
    try:
        credits_df = load_store_credit()
        if credits_df.empty:
            return None
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        active = credits_df[
            (credits_df["customer_phone"].astype(str) == str(phone)) &
            (credits_df["status"] == "ACTIVE") &
            (credits_df["expiry_date"] >= today)
        ]
        
        if not active.empty:
            return active.iloc[0]["credit_id"]
        
        return None
    except:
        return None


def create_store_credit(customer_name, customer_phone, amount, expiry_days=365, notes=""):
    """Create store credit for customer"""
    try:
        credits_df = load_store_credit()
        current_branch = get_current_branch()
        
        credit_id = f"SC{len(credits_df)+1:06d}"
        
        new_credit = pd.DataFrame([{
            "credit_id": credit_id,
            "customer_name": str(customer_name),
            "customer_phone": str(customer_phone),
            "amount": float(amount),
            "remaining_balance": float(amount),
            "issued_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d"),
            "status": "ACTIVE",
            "issued_by": st.session_state.get("username", "system"),
            "branch_id": str(current_branch),
            "used_transactions": "",
            "notes": notes
        }])
        
        credits_df = pd.concat([credits_df, new_credit], ignore_index=True)
        save_store_credit(credits_df)
        
        return credit_id
    except:
        return None


def update_store_credit(credit_id, additional_amount):
    """Update existing store credit with additional amount"""
    try:
        credits_df = load_store_credit()
        idx = credits_df[credits_df["credit_id"] == credit_id].index
        
        if len(idx) > 0:
            current_balance = float(credits_df.loc[idx[0], "remaining_balance"])
            current_amount = float(credits_df.loc[idx[0], "amount"])
            
            credits_df.loc[idx[0], "amount"] = current_amount + float(additional_amount)
            credits_df.loc[idx[0], "remaining_balance"] = current_balance + float(additional_amount)
            credits_df.loc[idx[0], "issued_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            save_store_credit(credits_df)
            return credit_id
        
        return None
    except:
        return None


def get_customer_store_credit(phone):
    """Get available store credit for a customer (checks expiry)"""
    try:
        credits_df = load_store_credit()
        if credits_df.empty:
            return 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        active = credits_df[
            (credits_df["customer_phone"].astype(str) == str(phone)) &
            (credits_df["status"] == "ACTIVE") &
            (credits_df["remaining_balance"] > 0) &
            (credits_df["expiry_date"] >= today)
        ]
        
        return active["remaining_balance"].sum() if not active.empty else 0
    except:
        return 0


def use_store_credit(phone, amount, receipt_no, notes=""):
    """Use store credit for a purchase"""
    try:
        credits_df = load_store_credit()
        
        active_credits = credits_df[
            (credits_df["customer_phone"].astype(str) == str(phone)) &
            (credits_df["status"] == "ACTIVE") &
            (credits_df["remaining_balance"] > 0)
        ].sort_values("expiry_date")
        
        if active_credits.empty:
            return False, 0, "No active store credit found"
        
        total_used = 0
        remaining_to_use = float(amount)
        
        for idx, credit in active_credits.iterrows():
            if remaining_to_use <= 0:
                break
            
            current_balance = float(credit["remaining_balance"])
            
            if remaining_to_use >= current_balance:
                credits_df.loc[idx, "remaining_balance"] = 0
                credits_df.loc[idx, "status"] = "USED"
                total_used += current_balance
                remaining_to_use -= current_balance
                
                used_trans = str(credit["used_transactions"])
                if used_trans and used_trans != "nan":
                    credits_df.loc[idx, "used_transactions"] = f"{used_trans}, {receipt_no}"
                else:
                    credits_df.loc[idx, "used_transactions"] = receipt_no
            else:
                new_balance = current_balance - remaining_to_use
                credits_df.loc[idx, "remaining_balance"] = new_balance
                total_used += remaining_to_use
                remaining_to_use = 0
                
                used_trans = str(credit["used_transactions"])
                if used_trans and used_trans != "nan":
                    credits_df.loc[idx, "used_transactions"] = f"{used_trans}, {receipt_no}"
                else:
                    credits_df.loc[idx, "used_transactions"] = receipt_no
        
        if total_used > 0:
            save_store_credit(credits_df)
            return True, total_used, f"Used ${total_used:.2f} from store credit"
        else:
            return False, 0, "Could not use store credit"
            
    except Exception as e:
        logger.error(f"Error using store credit: {e}")
        return False, 0, f"Error: {str(e)}"


def edit_store_credit(credit_id, amount, balance, expiry_date, status, notes):
    """Edit store credit details"""
    try:
        credits_df = load_store_credit()
        idx = credits_df[credits_df["credit_id"] == credit_id].index
        
        if len(idx) > 0:
            credits_df.loc[idx[0], "amount"] = float(amount)
            credits_df.loc[idx[0], "remaining_balance"] = float(balance)
            credits_df.loc[idx[0], "expiry_date"] = expiry_date
            credits_df.loc[idx[0], "status"] = status
            credits_df.loc[idx[0], "notes"] = notes
            
            save_store_credit(credits_df)
            return True, "Credit updated successfully"
        
        return False, "Credit not found"
    except Exception as e:
        logger.error(f"Error editing store credit: {e}")
        return False, f"Error: {str(e)}"


def delete_store_credit(credit_id):
    """Delete store credit"""
    try:
        credits_df = load_store_credit()
        credits_df = credits_df[credits_df["credit_id"] != credit_id]
        save_store_credit(credits_df)
        return True, "Credit deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting store credit: {e}")
        return False, f"Error: {str(e)}"


def get_return_stats():
    """Get return statistics"""
    try:
        returns_df = load_returns()
        
        if returns_df.empty:
            return {"total": 0, "refund_amount": 0, "completed": 0, "pending": 0, "avg_value": 0}
        
        total = len(returns_df)
        refund = returns_df["refund_amount"].sum() if "refund_amount" in returns_df.columns else 0
        
        return {
            "total": total,
            "refund_amount": refund,
            "completed": total,
            "pending": 0,
            "avg_value": refund / total if total > 0 else 0
        }
    except:
        return {"total": 0, "refund_amount": 0, "completed": 0, "pending": 0, "avg_value": 0}


def get_write_off_stats():
    """Get write-off statistics"""
    try:
        write_offs_df = load_write_offs()
        
        if write_offs_df.empty:
            return {"total": 0, "items": 0}
        
        return {
            "total": len(write_offs_df),
            "items": write_offs_df["quantity"].sum() if "quantity" in write_offs_df.columns else 0
        }
    except:
        return {"total": 0, "items": 0}


def get_sample_receipts():
    """Get sample receipt numbers for testing"""
    try:
        sales_df = load_sales()
        if sales_df.empty:
            return []
        if "receipt_no" in sales_df.columns:
            return sales_df["receipt_no"].tail(10).tolist()
        return []
    except:
        return []


# ==============================
# UI COMPONENTS
# ==============================
def render_process_return_tab():
    """Render the Process Return tab with 3-step workflow"""
    
    st.markdown("## 🔄 Process Customer Return")
    st.caption(f"Return period: {RETURN_PERIOD_DAYS} days from purchase date")
    
    # Initialize session state
    if "return_step" not in st.session_state:
        st.session_state.return_step = "search"
    if "return_receipt" not in st.session_state:
        st.session_state.return_receipt = ""
    if "return_sale_data" not in st.session_state:
        st.session_state.return_sale_data = None
    if "return_items" not in st.session_state:
        st.session_state.return_items = []
    if "return_quantities" not in st.session_state:
        st.session_state.return_quantities = {}
    if "return_search_triggered" not in st.session_state:
        st.session_state.return_search_triggered = False
    if "return_processed" not in st.session_state:
        st.session_state.return_processed = False
    if "return_result" not in st.session_state:
        st.session_state.return_result = None
    
    # ============================================================
    # STEP 1: SEARCH RECEIPT
    # ============================================================
    if st.session_state.return_step == "search":
        
        with st.form(key="search_receipt_form"):
            receipt_no = st.text_input(
                "Receipt Number",
                placeholder="Enter receipt number from original sale",
                key="return_receipt_input",
                value=st.session_state.return_receipt
            )
            
            col1, col2 = st.columns([3, 1])
            with col2:
                search_clicked = st.form_submit_button("🔍 Search Receipt", use_container_width=True)
            
            if search_clicked and receipt_no:
                original_sale = find_sale_by_receipt(receipt_no)
                
                if original_sale is None or original_sale.empty:
                    st.error(f"❌ Receipt '{receipt_no}' not found.")
                    
                    sales_df = load_sales()
                    if not sales_df.empty and "receipt_no" in sales_df.columns:
                        st.info("Available receipt numbers in system:")
                        for r in sales_df["receipt_no"].tail(5).tolist():
                            st.code(f"• {r}")
                else:
                    sale_row = original_sale.iloc[0]
                    
                    sale_date = sale_row.get("date", sale_row.get("sale_date", ""))
                    is_valid, period_msg = check_return_period(sale_date)
                    
                    if not is_valid:
                        st.error(f"⚠️ {period_msg}")
                    else:
                        st.session_state.return_receipt = receipt_no
                        st.session_state.return_sale_data = sale_row
                        st.session_state.return_step = "select"
                        st.session_state.return_search_triggered = True
            
            elif not receipt_no:
                st.info("🔍 Enter a receipt number and click 'Search Receipt'")
    
    # ============================================================
    # STEP 2: SELECT ITEMS
    # ============================================================
    elif st.session_state.return_step == "select":
        
        sale_row = st.session_state.return_sale_data
        receipt_no = st.session_state.return_receipt
        
        if sale_row is None:
            st.error("No sale data found. Please search again.")
            st.session_state.return_step = "search"
            return
        
        customer_name = sale_row.get("customer", sale_row.get("customer_name", "Walk-in Customer"))
        customer_phone = sale_row.get("customer_phone", sale_row.get("phone", ""))
        sale_date = sale_row.get("date", sale_row.get("sale_date", "Unknown"))
        
        st.success(f"✅ Sale found for receipt: {receipt_no}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"**Customer:** {customer_name}")
        with col2:
            st.info(f"**Phone:** {customer_phone}")
        with col3:
            st.info(f"**Date:** {str(sale_date)[:16] if sale_date != 'Unknown' else 'Unknown'}")
        
        st.markdown("---")
        st.markdown("### Items from Original Sale")
        
        sale_items = get_sale_items(receipt_no)
        
        if not sale_items:
            st.error("Could not parse items from this sale.")
            st.session_state.return_step = "search"
            return
        
        # Show items with availability
        display_data = []
        for item in sale_items:
            available = item.get('available', item['quantity'])
            display_data.append({
                "Product": item['name'],
                "Original Qty": item['quantity'],
                "Already Returned": item.get('already_returned', 0),
                "Available": available,
                "Price": f"${item['price']:.2f}"
            })
        
        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("### Select Items to Return")
        st.info(f"💡 Enter quantities (max: available quantity)")
        
        # Show condition options with write-off explanation
        st.markdown("**Condition Guidelines:**")
        st.caption("• **New/Unused** - Returns to stock (full refund)")
        st.caption("• **Used - Good** - Returns to stock (full refund)")
        st.caption("• **Damaged/Broken** - Written off (stock not affected, full refund)")
        st.caption("• **Expired** - Written off (stock not affected, full refund)")
        
        # Quantity selection
        selected_items = []
        has_selection = False
        
        for idx, item in enumerate(sale_items):
            available = item.get('available', item['quantity'])
            
            if available <= 0:
                st.info(f"✅ {item['name']} - Fully returned")
                continue
            
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.write(f"**{item['name']}**")
            with col2:
                st.write(f"Available: {available}")
            with col3:
                st.write(f"Price: ${item['price']:.2f}")
            with col4:
                qty_key = f"qty_{idx}_{item['barcode']}"
                current_qty = st.session_state.return_quantities.get(qty_key, 0)
                
                return_qty = st.number_input(
                    "Qty",
                    min_value=0,
                    max_value=available,
                    value=current_qty,
                    key=qty_key,
                    step=1,
                    label_visibility="collapsed"
                )
                
                st.session_state.return_quantities[qty_key] = return_qty
                
                if return_qty > 0:
                    has_selection = True
                    st.write(f"Refund: ${return_qty * item['price']:.2f}")
                    selected_items.append({
                        "barcode": item.get("barcode", ""),
                        "name": item['name'],
                        "quantity": return_qty,
                        "price": item['price'],
                        "available": available
                    })
        
        # Navigation buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⬅️ Back to Search", use_container_width=True):
                st.session_state.return_step = "search"
                st.session_state.return_quantities = {}
        
        with col2:
            if has_selection:
                if st.button("➡️ Continue to Confirm", type="primary", use_container_width=True):
                    st.session_state.return_items = selected_items
                    st.session_state.return_step = "confirm"
            else:
                st.warning("Please select at least one item to return")
    
    # ============================================================
    # STEP 3: CONFIRM & PROCESS
    # ============================================================
    elif st.session_state.return_step == "confirm":
        
        receipt_no = st.session_state.return_receipt
        sale_row = st.session_state.return_sale_data
        selected_items = st.session_state.return_items
        
        if not selected_items:
            st.error("No items selected. Please go back and select items.")
            st.session_state.return_step = "select"
            return
        
        customer_name = sale_row.get("customer", sale_row.get("customer_name", "Walk-in Customer"))
        customer_phone = sale_row.get("customer_phone", sale_row.get("phone", ""))
        
        st.success(f"✅ Confirming return for receipt: {receipt_no}")
        
        # Show selected items
        st.markdown("### Items to Return")
        items_data = []
        total_refund = 0
        for item in selected_items:
            refund = item['quantity'] * item['price']
            total_refund += refund
            items_data.append({
                "Product": item['name'],
                "Quantity": item['quantity'],
                "Price": f"${item['price']:.2f}",
                "Refund": f"${refund:.2f}"
            })
        
        st.dataframe(pd.DataFrame(items_data), use_container_width=True, hide_index=True)
        st.info(f"💰 **Total Refund Amount: ${total_refund:.2f}**")
        
        st.markdown("---")
        st.markdown("### Return Details")
        
        # Use a form to prevent double submission
        with st.form(key="process_return_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                reason = st.selectbox(
                    "Return Reason",
                    ["Damaged Product", "Wrong Item", "Changed Mind", "Defective", "Expired", "Other"],
                    key="return_reason_confirm"
                )
                condition = st.selectbox(
                    "Product Condition",
                    ["New/Unused", "Like New", "Used - Good", "Used - Fair", "Damaged", "Expired"],
                    key="return_condition_confirm"
                )
            
            with col2:
                refund_method = st.selectbox(
                    "Refund Method",
                    ["CASH", "STORE_CREDIT", "CARD", "ECOCASH"],
                    key="return_method_confirm"
                )
                notes = st.text_area("Notes", placeholder="Additional information...", key="return_notes_confirm")
            
            # Show write-off warning if applicable
            if condition.lower() in ["damaged", "expired", "broken", "faulty"]:
                st.warning(f"⚠️ **Write-Off Notice:** Items marked as '{condition}' will be written off and will NOT be added back to stock.")
            
            if refund_method == "STORE_CREDIT":
                st.info("💳 Store credit will be issued to customer")
                
                # Check existing credit
                existing = check_existing_store_credit(customer_phone, customer_name)
                if existing:
                    st.info(f"ℹ️ Customer already has store credit {existing}. This return will be added to existing credit.")
            
            # Submit button - MUST be st.form_submit_button
            submitted = st.form_submit_button("✅ CONFIRM & PROCESS RETURN", type="primary", use_container_width=True)
        
        # Back button - OUTSIDE the form
        if st.button("⬅️ Back to Selection", use_container_width=True):
            st.session_state.return_step = "select"
        
        # Process the submission - OUTSIDE the form
        if submitted:
            with st.spinner("Processing return..."):
                success, message, returned_products, refund_total = process_return(
                    receipt_no=receipt_no,
                    items=selected_items,
                    reason=reason,
                    condition=condition,
                    refund_method=refund_method,
                    notes=notes
                )
                
                if success:
                    st.success(f"✅ {message}")
                    
                    if returned_products:
                        st.markdown("### 📦 Stock Update Summary")
                        for p in returned_products:
                            is_write_off = False
                            for item in selected_items:
                                if item.get("barcode") == p["barcode"] and condition.lower() in ["damaged", "expired", "broken", "faulty"]:
                                    is_write_off = True
                                    break
                            
                            if is_write_off:
                                st.warning(f"📝 {p['name']}: {p['quantity']} units - WRITTEN OFF (not added to stock)")
                            else:
                                st.success(f"✅ {p['name']}: +{p['quantity']} units returned to stock")
                    
                    st.balloons()
                    
                    # Reset for next return
                    st.session_state.return_step = "search"
                    st.session_state.return_receipt = ""
                    st.session_state.return_sale_data = None
                    st.session_state.return_items = []
                    st.session_state.return_quantities = {}
                    st.session_state.return_processed = True
                else:
                    st.error(f"❌ {message}")


def render_store_credit_tab():
    """Render the Store Credit tab with full CRUD - Issue, Use, Edit, Delete, History"""
    
    st.markdown("## 💳 Store Credit Management")
    
    # Initialize session state for edit/delete
    if "edit_credit_id" not in st.session_state:
        st.session_state.edit_credit_id = None
    if "delete_credit_id" not in st.session_state:
        st.session_state.delete_credit_id = None
    
    # ============================================================
    # TABS FOR STORE CREDIT OPERATIONS
    # ============================================================
    credit_tab1, credit_tab2, credit_tab3, credit_tab4 = st.tabs([
        "💰 Issue Credit",
        "💳 Use Credit",
        "✏️ Manage Credits",
        "📋 Credit History"
    ])
    
    # ============================================================
    # TAB 1: ISSUE CREDIT
    # ============================================================
    with credit_tab1:
        st.markdown("### Issue New Store Credit")
        
        with st.form(key="issue_store_credit_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                customer = st.text_input("Customer Name", key="isc_name")
                phone = st.text_input("Customer Phone", key="isc_phone")
            
            with col2:
                amount = st.number_input("Credit Amount ($)", min_value=0.01, step=10.0, key="isc_amount")
                expiry = st.number_input("Expiry (days)", min_value=1, max_value=730, value=365, key="isc_expiry")
            
            notes = st.text_area("Notes", key="isc_notes")
            
            # Check if customer already has credit
            if phone:
                existing = check_existing_store_credit(phone, customer)
                if existing:
                    st.info(f"ℹ️ Customer already has active store credit. New credit will be added separately.")
            
            submitted = st.form_submit_button("💰 Issue Store Credit", type="primary", use_container_width=True)
            
            if submitted:
                if customer and phone and amount > 0:
                    credit_id = create_store_credit(customer, phone, amount, expiry, notes)
                    if credit_id:
                        st.success(f"✅ Store credit issued! ID: {credit_id} (${amount:.2f})")
                    else:
                        st.error("❌ Failed to issue store credit")
                else:
                    st.error("Please fill all required fields")
    
    # ============================================================
    # TAB 2: USE CREDIT
    # ============================================================
    with credit_tab2:
        st.markdown("### Use Store Credit")
        st.caption("Deduct store credit when customer makes a purchase")
        
        with st.form(key="use_store_credit_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                use_phone = st.text_input("Customer Phone", key="usc_phone")
                use_receipt = st.text_input("Receipt Number", key="usc_receipt", placeholder="Current sale receipt")
            
            with col2:
                use_amount = st.number_input("Amount to Use ($)", min_value=0.01, step=5.0, key="usc_amount")
                use_notes = st.text_area("Notes", key="usc_notes", placeholder="e.g., Used for purchase of items")
            
            # Show available balance
            if use_phone:
                balance = get_customer_store_credit(use_phone)
                if balance > 0:
                    st.success(f"💰 Available Store Credit: **${balance:.2f}**")
                else:
                    st.info("No active store credit found for this customer")
            
            submitted = st.form_submit_button("💳 Use Store Credit", type="primary", use_container_width=True)
            
            if submitted:
                if use_phone and use_amount > 0:
                    available = get_customer_store_credit(use_phone)
                    
                    if available <= 0:
                        st.error("❌ No store credit available for this customer")
                    elif use_amount > available:
                        st.error(f"❌ Insufficient credit. Available: ${available:.2f}")
                    else:
                        success, used_amount, message = use_store_credit(use_phone, use_amount, use_receipt, use_notes)
                        if success:
                            st.success(f"✅ {message}")
                            new_balance = get_customer_store_credit(use_phone)
                            st.info(f"💰 Remaining balance: ${new_balance:.2f}")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.error("Please enter customer phone and amount")
    
    # ============================================================
    # TAB 3: MANAGE CREDITS (Edit/Delete)
    # ============================================================
    with credit_tab3:
        st.markdown("### Manage Store Credits")
        
        credits_df = load_store_credit()
        
        if credits_df.empty:
            st.info("No store credit records found")
        else:
            search_phone = st.text_input("Search by Customer Phone", key="mng_phone", placeholder="Enter phone to filter...")
            
            filtered_df = credits_df.copy()
            if search_phone:
                filtered_df = filtered_df[filtered_df["customer_phone"].astype(str).str.contains(search_phone, na=False)]
            
            if filtered_df.empty:
                st.info("No credits found for this customer")
            else:
                active_df = filtered_df[filtered_df["status"] == "ACTIVE"]
                used_df = filtered_df[filtered_df["status"] == "USED"]
                expired_df = filtered_df[filtered_df["status"] == "EXPIRED"]
                
                if not active_df.empty:
                    st.markdown("#### 🟢 Active Credits")
                    for idx, credit in active_df.iterrows():
                        with st.expander(f"💳 {credit['credit_id']} - {credit['customer_name']} - ${credit['remaining_balance']:.2f}"):
                            col1, col2, col3 = st.columns([2, 1, 1])
                            
                            with col1:
                                st.write(f"**Phone:** {credit['customer_phone']}")
                                st.write(f"**Amount:** ${credit['amount']:.2f}")
                                st.write(f"**Remaining:** ${credit['remaining_balance']:.2f}")
                                st.write(f"**Expires:** {credit['expiry_date']}")
                                st.write(f"**Issued:** {credit['issued_date']}")
                                if credit.get("notes"):
                                    st.write(f"**Notes:** {credit['notes']}")
                            
                            with col2:
                                if st.button(f"✏️ Edit", key=f"edit_{credit['credit_id']}"):
                                    st.session_state.edit_credit_id = credit['credit_id']
                            
                            with col3:
                                if st.button(f"🗑️ Delete", key=f"del_{credit['credit_id']}"):
                                    st.session_state.delete_credit_id = credit['credit_id']
                
                if not used_df.empty:
                    st.markdown("#### 🔵 Used Credits")
                    for _, credit in used_df.iterrows():
                        with st.expander(f"🔵 {credit['credit_id']} - {credit['customer_name']} - USED"):
                            st.write(f"**Amount:** ${credit['amount']:.2f}")
                            st.write(f"**Used:** {credit['used_transactions']}")
                            if credit.get("notes"):
                                st.write(f"**Notes:** {credit['notes']}")
                
                if not expired_df.empty:
                    st.markdown("#### 🔴 Expired Credits")
                    for _, credit in expired_df.iterrows():
                        with st.expander(f"🔴 {credit['credit_id']} - {credit['customer_name']} - EXPIRED"):
                            st.write(f"**Amount:** ${credit['amount']:.2f}")
                            st.write(f"**Remaining:** ${credit['remaining_balance']:.2f}")
                            st.write(f"**Expired:** {credit['expiry_date']}")
                            if credit.get("notes"):
                                st.write(f"**Notes:** {credit['notes']}")
        
        # ============================================================
        # EDIT CREDIT MODAL
        # ============================================================
        if st.session_state.get("edit_credit_id"):
            credit_id = st.session_state.edit_credit_id
            credits_df = load_store_credit()
            credit = credits_df[credits_df["credit_id"] == credit_id]
            
            if not credit.empty:
                credit_data = credit.iloc[0]
                
                st.markdown("---")
                st.markdown(f"### ✏️ Edit Credit: {credit_id}")
                
                with st.form(key="edit_credit_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_amount = st.number_input(
                            "Total Amount ($)",
                            value=float(credit_data["amount"]),
                            min_value=0.01,
                            step=10.0,
                            key="edit_amount"
                        )
                        edit_balance = st.number_input(
                            "Remaining Balance ($)",
                            value=float(credit_data["remaining_balance"]),
                            min_value=0.0,
                            step=5.0,
                            key="edit_balance"
                        )
                    
                    with col2:
                        edit_expiry = st.date_input(
                            "Expiry Date",
                            value=pd.to_datetime(credit_data["expiry_date"]).date(),
                            key="edit_expiry"
                        )
                        edit_status = st.selectbox(
                            "Status",
                            ["ACTIVE", "USED", "EXPIRED"],
                            index=["ACTIVE", "USED", "EXPIRED"].index(credit_data["status"]),
                            key="edit_status"
                        )
                    
                    edit_notes = st.text_area("Notes", value=credit_data.get("notes", ""), key="edit_notes")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                            success, message = edit_store_credit(
                                credit_id=credit_id,
                                amount=edit_amount,
                                balance=edit_balance,
                                expiry_date=edit_expiry.strftime("%Y-%m-%d"),
                                status=edit_status,
                                notes=edit_notes
                            )
                            if success:
                                st.success(f"✅ {message}")
                                st.session_state.edit_credit_id = None
                            else:
                                st.error(f"❌ {message}")
                    
                    with col2:
                        if st.form_submit_button("❌ Cancel", use_container_width=True):
                            st.session_state.edit_credit_id = None
        
        # ============================================================
        # DELETE CREDIT CONFIRMATION
        # ============================================================
        if st.session_state.get("delete_credit_id"):
            credit_id = st.session_state.delete_credit_id
            
            st.markdown("---")
            st.warning(f"⚠️ Are you sure you want to delete credit: {credit_id}?")
            st.caption("This action cannot be undone.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Yes, Delete", type="primary", use_container_width=True):
                    success, message = delete_store_credit(credit_id)
                    if success:
                        st.success(f"✅ {message}")
                        st.session_state.delete_credit_id = None
                    else:
                        st.error(f"❌ {message}")
            
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.delete_credit_id = None
    
    # ============================================================
    # TAB 4: CREDIT HISTORY
    # ============================================================
    with credit_tab4:
        st.markdown("### 📋 Store Credit History")
        
        credits_df = load_store_credit()
        
        if credits_df.empty:
            st.info("No store credit records found")
        else:
            total_issued = credits_df["amount"].sum()
            total_remaining = credits_df["remaining_balance"].sum()
            active_count = len(credits_df[credits_df["status"] == "ACTIVE"])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💰 Total Issued", f"${total_issued:,.2f}")
            with col2:
                st.metric("💳 Available", f"${total_remaining:,.2f}")
            with col3:
                st.metric("🟢 Active Credits", active_count)
            
            st.markdown("---")
            
            display_df = credits_df[["credit_id", "customer_name", "customer_phone", "amount", "remaining_balance", "status", "issued_date", "expiry_date", "notes"]]
            st.dataframe(
                display_df.sort_values("issued_date", ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                    "remaining_balance": st.column_config.NumberColumn("Balance", format="$%.2f")
                }
            )
            
            csv = credits_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Store Credit Data (CSV)",
                data=csv,
                file_name=f"store_credit_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )


def render_return_analytics_tab():
    """Render the Return Analytics tab"""
    
    st.markdown("## 📊 Return Analytics")
    
    stats = get_return_stats()
    write_off_stats = get_write_off_stats()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📦 Total Returns", stats["total"])
    with col2:
        st.metric("💰 Total Refunded", f"${stats['refund_amount']:,.2f}")
    with col3:
        st.metric("⏳ Pending", stats["pending"])
    with col4:
        st.metric("📊 Avg Return", f"${stats['avg_value']:.2f}")
    with col5:
        st.metric("📝 Write-Offs", write_off_stats["total"])
    
    st.markdown("---")
    
    returns_df = load_returns()
    if not returns_df.empty:
        st.markdown("### 📋 Recent Returns")
        st.dataframe(
            returns_df[["return_id", "receipt_no", "customer_name", "product_name", "quantity_returned", "refund_amount", "return_date", "condition"]].head(20),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No return data available")
    
    write_offs_df = load_write_offs()
    if not write_offs_df.empty:
        st.markdown("### 📝 Write-Off Summary")
        st.dataframe(
            write_offs_df[["write_off_id", "product_name", "quantity", "reason", "created_date"]].head(20),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No write-offs recorded")


def render_return_history_tab():
    """Render the Return History tab"""
    
    st.markdown("## 📜 Return History")
    
    returns_df = load_returns()
    
    if not returns_df.empty:
        st.dataframe(
            returns_df[["return_id", "receipt_no", "return_date", "customer_name", "product_name", "quantity_returned", "refund_amount", "status", "condition"]],
            use_container_width=True,
            hide_index=True
        )
        
        csv = returns_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Returns Data (CSV)",
            data=csv,
            file_name=f"returns_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No return records found")
    
    st.markdown("---")
    st.markdown("### 📝 Write-Off History")
    
    write_offs_df = load_write_offs()
    if not write_offs_df.empty:
        st.dataframe(
            write_offs_df[["write_off_id", "product_name", "quantity", "reason", "created_date"]],
            use_container_width=True,
            hide_index=True
        )
        
        csv = write_offs_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Write-Off Data (CSV)",
            data=csv,
            file_name=f"write_offs_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No write-off records found")


# ==============================
# MAIN DASHBOARD
# ==============================
def returns_management_dashboard():
    """Main Returns and Refunds Management Dashboard"""
    
    st.title("🔄 Returns & Refunds Management")
    st.caption("Process customer returns, manage store credit, and track warranties")
    
    role = st.session_state.get("role", "cashier")
    if role not in ALLOWED_RETURN_ROLES:
        st.error("❌ Access Denied. Only managers and owners can process returns.")
        return
    
    try:
        init_files()
    except Exception as e:
        st.error(f"❌ Error initializing system: {e}")
        return
    
    sample_receipts = get_sample_receipts()
    if sample_receipts:
        with st.expander("📋 Recent Receipt Numbers (for testing)"):
            for r in sample_receipts[:5]:
                st.code(f"• {r}")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔄 Process Return",
        "💰 Store Credit",
        "📊 Return Analytics",
        "📜 Return History"
    ])
    
    with tab1:
        render_process_return_tab()
    
    with tab2:
        render_store_credit_tab()
    
    with tab3:
        render_return_analytics_tab()
    
    with tab4:
        render_return_history_tab()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    returns_management_dashboard()