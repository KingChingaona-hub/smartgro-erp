import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import uuid

# ALL IMPORTS FIXED - Using db_adapter instead of database
from backend.core.db_adapter import (
    load_sales,
    load_products,
    save_products,
    load_customers,
    save_customers,
    get_current_branch
)
from backend.modules.cash_register import record_cash_movement

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
BRANCH_DATA_DIR = Path("branch_data")
RETURNS_FILE = DATA_DIR / "returns.csv"
REFUNDS_FILE = DATA_DIR / "refunds.csv"
STORE_CREDIT_FILE = DATA_DIR / "store_credit.csv"
WARRANTY_FILE = DATA_DIR / "warranty_registrations.csv"


# ==============================
# HELPER: Convert Scientific Notation
# ==============================
def convert_scientific_to_normal(value):
    """Convert scientific notation back to normal number string"""
    try:
        value_str = str(value).strip()
        if 'E' in value_str.upper():
            float_val = float(value_str)
            if float_val.is_integer():
                return str(int(float_val))
            else:
                return str(float_val)
        return value_str
    except:
        return str(value)


# ==============================
# INITIALIZATION
# ==============================
def init_returns_files():
    """Initialize returns-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Returns file
    if not RETURNS_FILE.exists():
        df = pd.DataFrame(columns=[
            "return_id",
            "receipt_no",
            "sale_id",
            "return_date",
            "customer_name",
            "customer_phone",
            "product_barcode",
            "product_name",
            "quantity_returned",
            "refund_amount",
            "return_reason",
            "condition",
            "status",
            "refund_method",
            "store_credit_id",
            "processed_by",
            "processed_date",
            "notes",
            "branch_code"
        ])
        df.to_csv(RETURNS_FILE, index=False)
    
    # Refunds file
    if not REFUNDS_FILE.exists():
        df = pd.DataFrame(columns=[
            "refund_id",
            "return_id",
            "receipt_no",
            "refund_date",
            "customer_name",
            "amount",
            "refund_method",
            "reference_no",
            "processed_by",
            "notes",
            "branch_code"
        ])
        df.to_csv(REFUNDS_FILE, index=False)
    
    # Store credit file
    if not STORE_CREDIT_FILE.exists():
        df = pd.DataFrame(columns=[
            "credit_id",
            "customer_name",
            "customer_phone",
            "amount",
            "remaining_balance",
            "issued_date",
            "expiry_date",
            "status",
            "issued_by",
            "used_transactions",
            "branch_code"
        ])
        df.to_csv(STORE_CREDIT_FILE, index=False)
    
    # Warranty file
    if not WARRANTY_FILE.exists():
        df = pd.DataFrame(columns=[
            "warranty_id",
            "receipt_no",
            "customer_name",
            "customer_phone",
            "product_barcode",
            "product_name",
            "purchase_date",
            "warranty_months",
            "expiry_date",
            "status",
            "claimed_date",
            "notes",
            "branch_code"
        ])
        df.to_csv(WARRANTY_FILE, index=False)


def load_returns():
    """Load all returns"""
    init_returns_files()
    df = pd.read_csv(RETURNS_FILE)
    if "receipt_no" in df.columns:
        df["receipt_no"] = df["receipt_no"].astype(str).apply(convert_scientific_to_normal)
    if "branch_code" in df.columns and not df.empty:
        current_branch = get_current_branch()
        df = df[df["branch_code"] == current_branch]
    return df


def save_returns(df):
    """Save returns to file"""
    if "branch_code" not in df.columns:
        df["branch_code"] = get_current_branch()
    else:
        df["branch_code"] = get_current_branch()
    df.to_csv(RETURNS_FILE, index=False)


def load_refunds():
    """Load all refunds"""
    init_returns_files()
    df = pd.read_csv(REFUNDS_FILE)
    if "branch_code" in df.columns and not df.empty:
        current_branch = get_current_branch()
        df = df[df["branch_code"] == current_branch]
    return df


def save_refunds(df):
    """Save refunds to file"""
    if "branch_code" not in df.columns:
        df["branch_code"] = get_current_branch()
    else:
        df["branch_code"] = get_current_branch()
    df.to_csv(REFUNDS_FILE, index=False)


def load_store_credit():
    """Load all store credit records"""
    init_returns_files()
    df = pd.read_csv(STORE_CREDIT_FILE)
    if "branch_code" in df.columns and not df.empty:
        current_branch = get_current_branch()
        df = df[df["branch_code"] == current_branch]
    return df


def save_store_credit(df):
    """Save store credit records"""
    if "branch_code" not in df.columns:
        df["branch_code"] = get_current_branch()
    else:
        df["branch_code"] = get_current_branch()
    df.to_csv(STORE_CREDIT_FILE, index=False)


def load_warranties():
    """Load all warranty registrations"""
    init_returns_files()
    df = pd.read_csv(WARRANTY_FILE)
    if "branch_code" in df.columns and not df.empty:
        current_branch = get_current_branch()
        df = df[df["branch_code"] == current_branch]
    return df


def save_warranties(df):
    """Save warranty registrations"""
    if "branch_code" not in df.columns:
        df["branch_code"] = get_current_branch()
    else:
        df["branch_code"] = get_current_branch()
    df.to_csv(WARRANTY_FILE, index=False)


def get_current_branch():
    """Get current branch from session state"""
    from backend.core.db_adapter import get_current_branch as db_get_branch
    return db_get_branch()


# ==============================
# RECEIPT SEARCH - FIXED
# ==============================
def search_sale_by_receipt(receipt_no):
    """
    Search for a sale by receipt number.
    Handles both string and numeric receipt numbers.
    """
    sales_df = load_sales()
    
    if sales_df.empty:
        return None
    
    # Convert search term to string
    search_term = str(receipt_no).strip()
    
    # Try to convert to int for numeric comparison
    search_int = None
    try:
        search_int = int(float(search_term))
    except:
        pass
    
    if "receipt_no" not in sales_df.columns:
        return None
    
    # Try exact string match (receipt_no is already string from load_sales)
    matches = sales_df[sales_df["receipt_no"] == search_term]
    if not matches.empty:
        return matches
    
    # Try numeric comparison
    if search_int is not None:
        matches = sales_df[sales_df["receipt_no"] == str(search_int)]
        if not matches.empty:
            return matches
    
    # Try partial match
    matches = sales_df[sales_df["receipt_no"].str.contains(search_term, na=False)]
    if not matches.empty:
        return matches
    
    # Try without .0 suffix
    search_clean = search_term.replace('.0', '')
    if search_clean != search_term:
        matches = sales_df[sales_df["receipt_no"].str.contains(search_clean, na=False)]
        if not matches.empty:
            return matches
    
    return None


def get_sale_items(sale_row):
    """Extract items from a single sale row"""
    items = []
    
    # Check if this row already has product info
    if "barcode" in sale_row.index and ("product_name" in sale_row.index or "name" in sale_row.index):
        name_col = "product_name" if "product_name" in sale_row.index else "name"
        qty = int(sale_row.get("items", 1))
        total = float(sale_row.get("total", 0))
        price = total / qty if qty > 0 else 0
        
        return [{
            "name": str(sale_row[name_col]),
            "barcode": str(sale_row.get("barcode", "")),
            "quantity": qty,
            "price": price,
            "total": total
        }]
    
    # Try to parse items from string
    if "items" in sale_row.index:
        items_data = sale_row["items"]
        if isinstance(items_data, str):
            try:
                items = eval(items_data)
            except:
                try:
                    items = json.loads(items_data)
                except:
                    return []
        elif isinstance(items_data, list):
            items = items_data
        elif isinstance(items_data, dict):
            items = [items_data]
    
    # Format items
    formatted_items = []
    for item in items:
        formatted_item = {
            "name": item.get("name", item.get("product_name", item.get("product", "Unknown"))),
            "barcode": str(item.get("barcode", item.get("product_barcode", item.get("sku", "")))),
            "quantity": int(item.get("quantity", item.get("qty", 1))),
            "price": float(item.get("price", item.get("unit_price", 0))),
            "total": float(item.get("total", item.get("subtotal", 0)))
        }
        formatted_items.append(formatted_item)
    
    return formatted_items


def get_sales_items_grouped(sale_row):
    """Get all items from a sale, grouped by product"""
    
    receipt_no = sale_row.get("receipt_no")
    if not receipt_no:
        return get_sale_items(sale_row)
    
    sales_df = load_sales()
    receipt_no_str = str(receipt_no).strip()
    
    # Find all rows with this receipt number
    all_sale_rows = sales_df[sales_df["receipt_no"] == receipt_no_str]
    
    # If no match, try numeric
    if all_sale_rows.empty:
        try:
            receipt_int = int(receipt_no_str)
            all_sale_rows = sales_df[sales_df["receipt_no"] == str(receipt_int)]
        except:
            pass
    
    # If still no match, try contains
    if all_sale_rows.empty:
        all_sale_rows = sales_df[sales_df["receipt_no"].str.contains(receipt_no_str, na=False)]
    
    # If we have multiple rows, group them
    if len(all_sale_rows) > 1:
        grouped = {}
        for _, row in all_sale_rows.iterrows():
            barcode = str(row.get("barcode", ""))
            name = str(row.get("product_name", row.get("name", "Unknown")))
            qty = int(row.get("items", 1))
            total = float(row.get("total", 0))
            price = total / qty if qty > 0 else 0
            
            key = barcode if barcode else name
            if key in grouped:
                grouped[key]["quantity"] += qty
                grouped[key]["total"] += total
            else:
                grouped[key] = {
                    "name": name,
                    "barcode": barcode,
                    "quantity": qty,
                    "price": price,
                    "total": total
                }
        
        return list(grouped.values())
    else:
        # Single row or no rows
        return get_sale_items(sale_row)


# ==============================
# RETURN FUNCTIONS
# ==============================
def process_return(receipt_no, items_to_return, return_reason, condition, refund_method, notes=""):
    """Process a return and update inventory AND sales"""
    sales_df = load_sales()
    products_df = load_products()
    returns_df = load_returns()
    refunds_df = load_refunds()
    current_branch = get_current_branch()
    
    receipt_no_str = str(receipt_no).strip()
    
    original_sale = search_sale_by_receipt(receipt_no_str)
    
    if original_sale is None or original_sale.empty:
        return False, f"Receipt '{receipt_no_str}' not found. Please check the receipt number."
    
    sale_row = original_sale.iloc[0]
    customer_name = sale_row.get("customer", sale_row.get("customer_name", "Walk-in Customer"))
    if pd.isna(customer_name) or customer_name == "":
        customer_name = "Walk-in Customer"
    
    customer_phone = sale_row.get("customer_phone", sale_row.get("phone", ""))
    if pd.isna(customer_phone):
        customer_phone = ""
    
    sale_id = sale_row.get("sale_id", sale_row.get("id", receipt_no_str))
    
    sale_date_str = sale_row.get("date", sale_row.get("sale_date", ""))
    if sale_date_str:
        try:
            sale_date = pd.to_datetime(sale_date_str)
            if datetime.now() - sale_date > timedelta(days=30):
                return False, f"Return period has expired (30 days limit). Sale was on {sale_date.strftime('%Y-%m-%d')}"
        except:
            pass
    
    sale_items = get_sales_items_grouped(sale_row)
    
    if not sale_items:
        return False, "Could not parse items from the original sale."
    
    total_refund = 0
    store_credit_id = None
    return_ids = []
    
    # Track which products were returned for stock update
    returned_products = []
    
    for return_item in items_to_return:
        matching_item = None
        for item in sale_items:
            if str(item.get("barcode", "")) == str(return_item.get("barcode", "")) or item.get("name") == return_item.get("name"):
                matching_item = item
                break
        
        if not matching_item:
            continue
        
        return_qty = min(int(return_item["quantity"]), int(matching_item["quantity"]))
        refund_amount = float(matching_item["price"]) * return_qty
        total_refund += refund_amount
        
        # Track returned product
        returned_products.append({
            "barcode": str(return_item.get("barcode", "")),
            "name": str(return_item.get("name", "")),
            "quantity": return_qty,
            "price": float(matching_item["price"])
        })
        
        return_id = f"RET{len(returns_df)+1:06d}"
        return_ids.append(return_id)
        
        new_return = pd.DataFrame([{
            "return_id": return_id,
            "receipt_no": receipt_no_str,
            "sale_id": str(sale_id),
            "return_date": datetime.now().isoformat(),
            "customer_name": str(customer_name),
            "customer_phone": str(customer_phone),
            "product_barcode": str(return_item.get("barcode", "")),
            "product_name": str(return_item.get("name", "")),
            "quantity_returned": return_qty,
            "refund_amount": refund_amount,
            "return_reason": return_reason,
            "condition": condition,
            "status": "COMPLETED",
            "refund_method": refund_method,
            "store_credit_id": None,
            "processed_by": st.session_state.get("username", "system"),
            "processed_date": datetime.now().isoformat(),
            "notes": notes,
            "branch_code": current_branch
        }])
        
        returns_df = pd.concat([returns_df, new_return], ignore_index=True)
        
        # ============================================================
        # UPDATE STOCK - ADD RETURNED QUANTITY BACK TO INVENTORY
        # ============================================================
        product_barcode = str(return_item.get("barcode", ""))
        if product_barcode:
            # Find product by barcode
            product_idx = products_df[products_df["barcode"].astype(str) == product_barcode].index
            if len(product_idx) > 0:
                current_stock = float(products_df.loc[product_idx[0], "stock"])
                products_df.loc[product_idx[0], "stock"] = current_stock + return_qty
                print(f"✅ Stock updated: {return_item.get('name')} +{return_qty} (was {current_stock}, now {current_stock + return_qty})")
            else:
                # Try by product name
                product_idx = products_df[products_df["name"].astype(str).str.lower() == str(return_item.get("name", "")).lower()].index
                if len(product_idx) > 0:
                    current_stock = float(products_df.loc[product_idx[0], "stock"])
                    products_df.loc[product_idx[0], "stock"] = current_stock + return_qty
                    print(f"✅ Stock updated (by name): {return_item.get('name')} +{return_qty}")
    
    # ============================================================
    # UPDATE SALES - ADD RETURN AS NEGATIVE SALE (RETURN ENTRY)
    # ============================================================
    if returned_products:
        return_receipt_no = f"RET-{receipt_no_str}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        for product in returned_products:
            # Create a negative sale entry to reflect the return
            return_sale = pd.DataFrame([{
                "branch_id": current_branch,
                "sale_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "receipt_no": return_receipt_no,
                "barcode": product["barcode"],
                "product_name": product["name"],
                "items": -product["quantity"],  # Negative quantity for return
                "total": -(product["price"] * product["quantity"]),  # Negative total
                "profit": 0,  # No profit on return
                "payment_method": refund_method,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "final_total": -total_refund,  # Negative final total
                "shift_id": st.session_state.get("shift_id", ""),
                "cashier": st.session_state.get("username", "system"),
                "return_id": ",".join(return_ids)
            }])
            
            # Append to sales dataframe
            sales_df = pd.concat([sales_df, return_sale], ignore_index=True)
            print(f"✅ Return sale recorded: {product['name']} -{product['quantity']} units")
    
    # Handle refund
    if refund_method == "STORE_CREDIT":
        store_credit_id = create_store_credit(customer_name, customer_phone, total_refund)
        for return_id in return_ids:
            returns_df.loc[returns_df["return_id"] == return_id, "store_credit_id"] = store_credit_id
    else:
        refund_id = f"REF{len(refunds_df)+1:06d}"
        new_refund = pd.DataFrame([{
            "refund_id": refund_id,
            "return_id": ",".join(return_ids),
            "receipt_no": receipt_no_str,
            "refund_date": datetime.now().isoformat(),
            "customer_name": str(customer_name),
            "amount": total_refund,
            "refund_method": refund_method,
            "reference_no": f"REF-{receipt_no_str}",
            "processed_by": st.session_state.get("username", "system"),
            "notes": notes,
            "branch_code": current_branch
        }])
        refunds_df = pd.concat([refunds_df, new_refund], ignore_index=True)
        
        if refund_method == "CASH":
            try:
                record_cash_movement(-total_refund, f"REFUND-{receipt_no_str}", "REFUND", st.session_state.get("shift_id", ""))
            except:
                pass
    
    # ============================================================
    # SAVE ALL CHANGES
    # ============================================================
    save_products(products_df)
    save_sales(sales_df)  # Save updated sales with return entries
    save_returns(returns_df)
    save_refunds(refunds_df)
    
    # ============================================================
    # RETURN SUMMARY
    # ============================================================
    summary = f"""
    ✅ Return processed successfully!
    
    📋 Return Summary:
    • Receipt: {receipt_no_str}
    • Customer: {customer_name}
    • Items Returned: {len(returned_products)}
    • Refund Amount: ${total_refund:.2f}
    • Refund Method: {refund_method}
    
    📦 Stock Updated:
    """
    for p in returned_products:
        summary += f"   • {p['name']}: +{p['quantity']} units (back in stock)\n"
    
    summary += f"\n📊 Sales Updated: Return entry recorded with negative sale"
    
    return True, summary

def create_store_credit(customer_name, customer_phone, amount, expiry_days=365):
    """Create store credit for customer"""
    
    credits_df = load_store_credit()
    current_branch = get_current_branch()
    
    credit_id = f"SC{len(credits_df)+1:06d}"
    
    new_credit = pd.DataFrame([{
        "credit_id": credit_id,
        "customer_name": str(customer_name),
        "customer_phone": str(customer_phone),
        "amount": float(amount),
        "remaining_balance": float(amount),
        "issued_date": datetime.now().isoformat(),
        "expiry_date": (datetime.now() + timedelta(days=expiry_days)).isoformat(),
        "status": "ACTIVE",
        "issued_by": st.session_state.get("username", "system"),
        "used_transactions": "",
        "branch_code": current_branch
    }])
    
    credits_df = pd.concat([credits_df, new_credit], ignore_index=True)
    save_store_credit(credits_df)
    
    return credit_id


def use_store_credit(customer_phone, amount, receipt_no):
    """Use store credit for a purchase"""
    
    credits_df = load_store_credit()
    
    active_credits = credits_df[
        (credits_df["customer_phone"].astype(str) == str(customer_phone)) & 
        (credits_df["status"] == "ACTIVE") &
        (credits_df["remaining_balance"] > 0)
    ]
    
    if active_credits.empty:
        return False, 0, "No active store credit found"
    
    credit = active_credits.sort_values("issued_date").iloc[0]
    idx = credit.name
    
    used_amount = min(float(amount), float(credit["remaining_balance"]))
    new_balance = float(credit["remaining_balance"]) - used_amount
    
    credits_df.loc[idx, "remaining_balance"] = new_balance
    if new_balance <= 0:
        credits_df.loc[idx, "status"] = "USED"
    
    used_transactions = credit["used_transactions"]
    if pd.isna(used_transactions) or used_transactions == "":
        used_transactions = receipt_no
    else:
        used_transactions += f",{receipt_no}"
    credits_df.loc[idx, "used_transactions"] = used_transactions
    
    save_store_credit(credits_df)
    
    return True, used_amount, f"Used ${used_amount:.2f} from store credit"


def get_customer_store_credit(customer_phone):
    """Get total store credit available for customer"""
    
    credits_df = load_store_credit()
    
    active_credits = credits_df[
        (credits_df["customer_phone"].astype(str) == str(customer_phone)) & 
        (credits_df["status"] == "ACTIVE") &
        (credits_df["remaining_balance"] > 0)
    ]
    
    total_credit = active_credits["remaining_balance"].sum()
    
    return float(total_credit) if not pd.isna(total_credit) else 0


def register_warranty(receipt_no, product_barcode, product_name, customer_name, customer_phone, warranty_months=12):
    """Register a product warranty"""
    warranties_df = load_warranties()
    current_branch = get_current_branch()
    
    sale = search_sale_by_receipt(receipt_no)
    if sale is not None and not sale.empty:
        date_col = None
        for col in ["date", "sale_date", "timestamp", "created_at"]:
            if col in sale.columns:
                date_col = col
                break
        if date_col:
            try:
                purchase_date = pd.to_datetime(sale.iloc[0][date_col])
            except:
                purchase_date = datetime.now()
        else:
            purchase_date = datetime.now()
    else:
        purchase_date = datetime.now()
    
    warranty_id = f"WAR{len(warranties_df)+1:06d}"
    expiry_date = purchase_date + timedelta(days=warranty_months * 30)
    
    new_warranty = pd.DataFrame([{
        "warranty_id": warranty_id,
        "receipt_no": str(receipt_no),
        "customer_name": str(customer_name),
        "customer_phone": str(customer_phone),
        "product_barcode": str(product_barcode),
        "product_name": str(product_name),
        "purchase_date": purchase_date.isoformat(),
        "warranty_months": warranty_months,
        "expiry_date": expiry_date.isoformat(),
        "status": "ACTIVE",
        "claimed_date": "",
        "notes": "",
        "branch_code": current_branch
    }])
    
    warranties_df = pd.concat([warranties_df, new_warranty], ignore_index=True)
    save_warranties(warranties_df)
    
    return warranty_id


def check_warranty(product_barcode, customer_phone=None):
    """Check if product is under warranty"""
    
    warranties_df = load_warranties()
    
    filtered = warranties_df[warranties_df["product_barcode"].astype(str) == str(product_barcode)]
    
    if customer_phone:
        filtered = filtered[filtered["customer_phone"].astype(str) == str(customer_phone)]
    
    if filtered.empty:
        return None
    
    warranty = filtered.iloc[0]
    expiry_date = pd.to_datetime(warranty["expiry_date"])
    
    if datetime.now() > expiry_date:
        return {"status": "EXPIRED", "expiry_date": expiry_date}
    
    days_left = (expiry_date - datetime.now()).days
    
    return {
        "status": "ACTIVE",
        "warranty_id": warranty["warranty_id"],
        "expiry_date": expiry_date,
        "days_left": days_left,
        "warranty_months": warranty["warranty_months"]
    }


def get_return_summary():
    """Get summary of returns"""
    
    returns_df = load_returns()
    
    if returns_df.empty:
        return {
            "total_returns": 0,
            "total_refund_amount": 0,
            "pending_returns": 0,
            "completed_returns": 0,
            "avg_return_value": 0
        }
    
    total_returns = len(returns_df)
    total_refund = returns_df["refund_amount"].sum()
    pending = len(returns_df[returns_df["status"] == "PENDING"])
    completed = len(returns_df[returns_df["status"] == "COMPLETED"])
    
    return {
        "total_returns": total_returns,
        "total_refund_amount": total_refund,
        "pending_returns": pending,
        "completed_returns": completed,
        "avg_return_value": total_refund / total_returns if total_returns > 0 else 0
    }


def get_sample_receipts():
    """Get sample receipts for testing"""
    sales_df = load_sales()
    if sales_df.empty:
        return []
    
    if "receipt_no" in sales_df.columns:
        receipts = sales_df["receipt_no"].tail(10).tolist()
        return receipts
    return []


# ==============================
# RETURNS DASHBOARD
# ==============================
def returns_management_dashboard():
    """Returns and Refunds Management Dashboard"""
    
    st.title("🔄 Returns & Refunds Management")
    st.caption("Process customer returns, manage store credit, and track warranties")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only managers and owners can process returns.")
        return
    
    init_returns_files()
    
    sample_receipts = get_sample_receipts()
    if sample_receipts:
        with st.expander("📋 Recent Receipt Numbers (for testing)"):
            st.write("Try these receipt numbers:")
            for r in sample_receipts[:5]:
                st.code(f"• {r}")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔄 Process Return",
        "💰 Store Credit",
        "📋 Warranty Check",
        "📊 Return Analytics",
        "📜 Return History"
    ])
    
    with tab1:
        st.markdown("## 🔄 Process Customer Return")
        st.caption("Enter the receipt number to find the original sale")
        
        receipt_no = st.text_input(
            "Receipt Number", 
            placeholder="Enter receipt number from original sale (e.g., 20260615095601)", 
            key="receipt_search"
        )
        
        col1, col2 = st.columns([3, 1])
        with col2:
            search_clicked = st.button("🔍 Search Receipt", use_container_width=True)
        
        if receipt_no and search_clicked:
            sales_df = load_sales()
            
            original_sale = search_sale_by_receipt(receipt_no)
            
            if original_sale is None or original_sale.empty:
                st.error(f"❌ Receipt '{receipt_no}' not found.")
                
                if not sales_df.empty and "receipt_no" in sales_df.columns:
                    st.info("Available receipt numbers in system:")
                    recent = sales_df["receipt_no"].tail(5).tolist()
                    for r in recent:
                        st.code(f"• {r}")
            else:
                sale_row = original_sale.iloc[0]
                
                customer_name = sale_row.get("customer", sale_row.get("customer_name", "Walk-in Customer"))
                if pd.isna(customer_name) or customer_name == "":
                    customer_name = "Walk-in Customer"
                
                customer_phone = sale_row.get("customer_phone", sale_row.get("phone", ""))
                if pd.isna(customer_phone):
                    customer_phone = ""
                
                sale_date = sale_row.get("date", sale_row.get("sale_date", "Unknown"))
                
                st.success(f"✅ Sale found for receipt: {receipt_no}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**Customer:** {customer_name}")
                with col2:
                    st.info(f"**Phone:** {customer_phone}")
                with col3:
                    st.info(f"**Date:** {str(sale_date)[:16] if sale_date != 'Unknown' else 'Unknown'}")
                
                st.markdown("### Items from Original Sale")
                
                sale_items = get_sales_items_grouped(sale_row)
                
                if not sale_items:
                    st.error("Could not parse items from this sale.")
                else:
                    items_df = pd.DataFrame(sale_items)
                    display_df = items_df[["name", "quantity", "price", "total"]].copy()
                    display_df.columns = ["Product", "Quantity", "Price", "Total"]
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    st.markdown("### Select Items to Return")
                    
                    return_items = []
                    for idx, item in enumerate(sale_items):
                        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                        with col1:
                            st.write(f"**{item['name']}**")
                        with col2:
                            st.write(f"Qty: {item['quantity']}")
                        with col3:
                            st.write(f"Price: ${item['price']:.2f}")
                        with col4:
                            return_qty = st.number_input(
                                "Return",
                                min_value=0,
                                max_value=item['quantity'],
                                value=0,
                                key=f"return_qty_{idx}",
                                step=1,
                                label_visibility="collapsed"
                            )
                            if return_qty > 0:
                                st.write(f"Refund: ${return_qty * item['price']:.2f}")
                        
                        if return_qty > 0:
                            return_items.append({
                                "barcode": item.get("barcode", ""),
                                "name": item['name'],
                                "quantity": return_qty,
                                "price": item['price']
                            })
                    
                    if return_items:
                        st.markdown("---")
                        st.markdown("### Return Details")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            return_reason = st.selectbox(
                                "Return Reason",
                                ["Damaged Product", "Wrong Item", "Changed Mind", "Defective", "Expired", "Other"]
                            )
                            condition = st.selectbox(
                                "Product Condition",
                                ["New/Unused", "Like New", "Used - Good", "Used - Fair", "Damaged"]
                            )
                        
                        with col2:
                            refund_method = st.selectbox(
                                "Refund Method",
                                ["CASH", "STORE_CREDIT", "CARD", "ECOCASH"]
                            )
                            notes = st.text_area("Notes", placeholder="Additional information...")
                        
                        total_refund = sum(item['quantity'] * item['price'] for item in return_items)
                        st.info(f"💰 **Total Refund Amount: ${total_refund:.2f}**")
                        
                        if refund_method == "STORE_CREDIT":
                            st.info("💳 Store credit will be issued to customer for future purchases")
                        
                        if st.button("✅ Process Return", type="primary", use_container_width=True):
                            with st.spinner("Processing return..."):
                                success, message = process_return(
                                    receipt_no=receipt_no,
                                    items_to_return=return_items,
                                    return_reason=return_reason,
                                    condition=condition,
                                    refund_method=refund_method,
                                    notes=notes
                                )
                                
                                if success:
                                    st.success(f"✅ {message}")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                    else:
                        st.warning("Please select at least one item to return")
        else:
            st.info("🔍 Enter a receipt number and click 'Search Receipt' to begin processing a return")
    
    with tab2:
        st.markdown("## 💳 Store Credit Management")
        st.caption("Issue and manage store credit for customers")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Issue Store Credit")
            
            credit_customer = st.text_input("Customer Name", key="credit_name")
            credit_phone = st.text_input("Customer Phone", key="credit_phone")
            credit_amount = st.number_input("Credit Amount ($)", min_value=0.01, step=10.0, key="credit_amount")
            credit_expiry = st.number_input("Expiry (days)", min_value=1, max_value=730, value=365, key="credit_expiry")
            credit_notes = st.text_area("Notes", key="credit_notes")
            
            if st.button("💰 Issue Store Credit", type="primary", use_container_width=True):
                if credit_customer and credit_phone and credit_amount > 0:
                    credit_id = create_store_credit(credit_customer, credit_phone, credit_amount, credit_expiry)
                    st.success(f"✅ Store credit issued! ID: {credit_id}")
                    st.rerun()
                else:
                    st.error("Please fill all required fields")
        
        with col2:
            st.markdown("### Check Store Credit Balance")
            
            check_phone = st.text_input("Customer Phone", key="check_credit_phone")
            
            if check_phone:
                balance = get_customer_store_credit(check_phone)
                
                if balance > 0:
                    st.success(f"💰 Available Store Credit: **${balance:.2f}**")
                    
                    credits_df = load_store_credit()
                    customer_credits = credits_df[
                        (credits_df["customer_phone"].astype(str) == str(check_phone)) & 
                        (credits_df["status"] == "ACTIVE") &
                        (credits_df["remaining_balance"] > 0)
                    ]
                    
                    if not customer_credits.empty:
                        st.markdown("#### Credit Details")
                        for _, credit in customer_credits.iterrows():
                            try:
                                expiry = pd.to_datetime(credit["expiry_date"])
                                days_left = (expiry - datetime.now()).days
                                st.write(f"• ${credit['remaining_balance']:.2f} - Expires in {days_left} days")
                            except:
                                st.write(f"• ${credit['remaining_balance']:.2f}")
                else:
                    st.info("No store credit found for this customer")
        
        st.markdown("---")
        st.markdown("### 📋 Store Credit History")
        
        credits_df = load_store_credit()
        if not credits_df.empty:
            st.dataframe(
                credits_df[["credit_id", "customer_name", "customer_phone", "amount", "remaining_balance", "status", "issued_date"]].head(20),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No store credit records found")
    
    with tab3:
        st.markdown("## 📋 Warranty Management")
        st.caption("Register warranties and check product warranty status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Register Warranty")
            
            war_receipt = st.text_input("Receipt Number", key="war_receipt")
            war_product = st.text_input("Product Barcode", key="war_product")
            war_name = st.text_input("Product Name", key="war_name")
            war_customer = st.text_input("Customer Name", key="war_customer")
            war_phone = st.text_input("Customer Phone", key="war_phone")
            war_months = st.number_input("Warranty Period (months)", min_value=1, max_value=60, value=12, key="war_months")
            
            if st.button("📝 Register Warranty", type="primary", use_container_width=True):
                if war_receipt and war_product and war_name and war_customer:
                    warranty_id = register_warranty(
                        receipt_no=war_receipt,
                        product_barcode=war_product,
                        product_name=war_name,
                        customer_name=war_customer,
                        customer_phone=war_phone,
                        warranty_months=war_months
                    )
                    st.success(f"✅ Warranty registered! ID: {warranty_id}")
                    st.rerun()
                else:
                    st.error("Please fill all required fields")
        
        with col2:
            st.markdown("### Check Warranty Status")
            
            check_product = st.text_input("Product Barcode", key="check_warranty_product")
            check_customer = st.text_input("Customer Phone (optional)", key="check_warranty_customer")
            
            if st.button("🔍 Check Warranty", use_container_width=True):
                if check_product:
                    warranty_status = check_warranty(check_product, check_customer if check_customer else None)
                    
                    if warranty_status:
                        if warranty_status["status"] == "ACTIVE":
                            st.success(f"✅ Product is under warranty!")
                            st.write(f"**Warranty ID:** {warranty_status['warranty_id']}")
                            st.write(f"**Expires:** {warranty_status['expiry_date'].strftime('%Y-%m-%d')}")
                            st.write(f"**Days Left:** {warranty_status['days_left']} days")
                        else:
                            st.error(f"❌ Warranty expired on {warranty_status['expiry_date'].strftime('%Y-%m-%d')}")
                    else:
                        st.warning("No warranty found for this product")
                else:
                    st.error("Please enter product barcode")
        
        st.markdown("---")
        st.markdown("### 📋 Active Warranties")
        
        warranties_df = load_warranties()
        if not warranties_df.empty:
            warranties_df["expiry_date"] = pd.to_datetime(warranties_df["expiry_date"])
            active_warranties = warranties_df[warranties_df["expiry_date"] >= datetime.now()]
            
            if not active_warranties.empty:
                st.dataframe(
                    active_warranties[["warranty_id", "product_name", "customer_name", "purchase_date", "expiry_date"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No active warranties")
        else:
            st.info("No warranty records found")
    
    with tab4:
        st.markdown("## 📊 Return Analytics")
        
        summary = get_return_summary()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📦 Total Returns", summary["total_returns"])
        with col2:
            st.metric("💰 Total Refunded", f"${summary['total_refund_amount']:,.2f}")
        with col3:
            st.metric("⏳ Pending", summary["pending_returns"])
        with col4:
            st.metric("📊 Avg Return", f"${summary['avg_return_value']:.2f}")
        
        st.markdown("---")
        
        returns_df = load_returns()
        
        if not returns_df.empty:
            st.markdown("### Returns by Reason")
            
            reason_counts = returns_df["return_reason"].value_counts().reset_index()
            reason_counts.columns = ["Reason", "Count"]
            
            fig_reason = px.pie(
                reason_counts,
                values="Count",
                names="Reason",
                title="Return Reasons Distribution",
                hole=0.3
            )
            st.plotly_chart(fig_reason, use_container_width=True)
            
            st.markdown("### Returns Over Time")
            
            returns_df["return_date"] = pd.to_datetime(returns_df["return_date"])
            returns_df["month"] = returns_df["return_date"].dt.strftime("%Y-%m")
            
            monthly_returns = returns_df.groupby("month").agg({
                "return_id": "count",
                "refund_amount": "sum"
            }).reset_index()
            monthly_returns.columns = ["Month", "Returns Count", "Refund Amount"]
            
            fig_trend = px.line(
                monthly_returns,
                x="Month",
                y="Refund Amount",
                title="Monthly Refund Amount",
                markers=True
            )
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.markdown("### Top Returned Products")
            
            top_products = returns_df.groupby("product_name").agg({
                "quantity_returned": "sum",
                "refund_amount": "sum"
            }).nlargest(10, "quantity_returned").reset_index()
            
            st.dataframe(
                top_products,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "refund_amount": st.column_config.NumberColumn("Refund Amount", format="$%.2f")
                }
            )
        else:
            st.info("No return data available")
    
    with tab5:
        st.markdown("## 📜 Return History")
        
        returns_df = load_returns()
        
        if not returns_df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                status_filter = st.selectbox("Filter by Status", ["All", "PENDING", "APPROVED", "COMPLETED", "REJECTED"])
            
            with col2:
                date_filter = st.date_input("Filter by Date", value=None)
            
            filtered_df = returns_df.copy()
            
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df["status"] == status_filter]
            
            if date_filter:
                filtered_df["return_date_dt"] = pd.to_datetime(filtered_df["return_date"]).dt.date
                filtered_df = filtered_df[filtered_df["return_date_dt"] == date_filter]
            
            st.dataframe(
                filtered_df[["return_id", "receipt_no", "return_date", "customer_name", "product_name", "quantity_returned", "refund_amount", "return_reason", "status"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "refund_amount": st.column_config.NumberColumn("Refund Amount", format="$%.2f")
                }
            )
            
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Returns Data (CSV)",
                data=csv,
                file_name=f"returns_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No return records found")


# ==============================
# POS INTEGRATION: STORE CREDIT AT CHECKOUT
# ==============================
def apply_store_credit_to_cart(customer_phone, cart_total):
    """Function to integrate store credit with POS"""
    
    available_credit = get_customer_store_credit(customer_phone)
    
    if available_credit <= 0:
        return 0, "No store credit available"
    
    use_credit = st.checkbox(f"💳 Apply Store Credit (${available_credit:.2f} available)")
    
    if use_credit:
        amount_to_use = min(available_credit, cart_total)
        st.success(f"✅ Applying ${amount_to_use:.2f} from store credit")
        return amount_to_use, f"Store credit applied: ${amount_to_use:.2f}"
    
    return 0, ""


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    returns_management_dashboard()