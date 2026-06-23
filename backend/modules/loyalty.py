import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# ==============================
# FILE SETUP
# ==============================
DATA_DIR = Path("data")
LOYALTY_FILE = DATA_DIR / "loyalty_points.csv"
LOYALTY_REDEMPTIONS_FILE = DATA_DIR / "loyalty_redemptions.csv"


# ==============================
# INIT LOYALTY FILES
# ==============================
def init_loyalty_files():
    """Initialize loyalty points files"""
    
    if not LOYALTY_FILE.exists():
        df = pd.DataFrame(columns=[
            "customer_name",
            "phone",
            "points",
            "tier",
            "total_spent",
            "total_orders",
            "last_visit",
            "birthday",
            "joined_date"
        ])
        df.to_csv(LOYALTY_FILE, index=False)
    
    if not LOYALTY_REDEMPTIONS_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "customer_name",
            "points_used",
            "discount_amount",
            "receipt_no"
        ])
        df.to_csv(LOYALTY_REDEMPTIONS_FILE, index=False)


# ==============================
# LOAD/SAVE FUNCTIONS
# ==============================
def load_loyalty():
    init_loyalty_files()
    return pd.read_csv(LOYALTY_FILE)


def save_loyalty(df):
    df.to_csv(LOYALTY_FILE, index=False)


def load_redemptions():
    init_loyalty_files()
    return pd.read_csv(LOYALTY_REDEMPTIONS_FILE)


# ==============================
# TIER DETERMINATION
# ==============================
def get_tier(total_spent):
    """Determine customer tier based on total spending"""
    if total_spent >= 5000:
        return "👑 PLATINUM"
    elif total_spent >= 2000:
        return "🥇 GOLD"
    elif total_spent >= 500:
        return "🥈 SILVER"
    else:
        return "🥉 BRONZE"


# ==============================
# TIER BENEFITS
# ==============================
def get_tier_benefits(tier):
    """Return benefits for each tier"""
    benefits = {
        "🥉 BRONZE": {
            "points_multiplier": 1,
            "discount": 0,
            "birthday_bonus": 50,
            "free_delivery": False
        },
        "🥈 SILVER": {
            "points_multiplier": 1.2,
            "discount": 5,
            "birthday_bonus": 100,
            "free_delivery": False
        },
        "🥇 GOLD": {
            "points_multiplier": 1.5,
            "discount": 10,
            "birthday_bonus": 200,
            "free_delivery": True
        },
        "👑 PLATINUM": {
            "points_multiplier": 2,
            "discount": 15,
            "birthday_bonus": 500,
            "free_delivery": True
        }
    }
    return benefits.get(tier, benefits["🥉 BRONZE"])


# ==============================
# ADD LOYALTY POINTS
# ==============================
def add_loyalty_points(customer_name, phone, amount_spent, receipt_no):
    """Add loyalty points to customer account"""
    
    df = load_loyalty()
    
    # Check if customer exists
    customer = df[df["phone"] == phone]
    
    if not customer.empty:
        idx = customer.index[0]
        current_points = df.at[idx, "points"]
        current_spent = df.at[idx, "total_spent"]
        current_orders = df.at[idx, "total_orders"]
        current_tier = df.at[idx, "tier"]
        
        # Calculate points earned (1 point per $1 spent, multiplied by tier)
        tier_benefits = get_tier_benefits(current_tier)
        points_earned = int(amount_spent * tier_benefits["points_multiplier"])
        
        # Update customer
        df.at[idx, "points"] = current_points + points_earned
        df.at[idx, "total_spent"] = current_spent + amount_spent
        df.at[idx, "total_orders"] = current_orders + 1
        df.at[idx, "last_visit"] = datetime.now().strftime("%Y-%m-%d")
        
        # Update tier based on new spending
        new_tier = get_tier(df.at[idx, "total_spent"])
        df.at[idx, "tier"] = new_tier
        
    else:
        # New customer
        points_earned = int(amount_spent)  # Base points for new customer
        
        new_customer = pd.DataFrame([{
            "customer_name": customer_name,
            "phone": phone,
            "points": points_earned + 50,  # Signup bonus
            "tier": "🥉 BRONZE",
            "total_spent": amount_spent,
            "total_orders": 1,
            "last_visit": datetime.now().strftime("%Y-%m-%d"),
            "birthday": "",
            "joined_date": datetime.now().strftime("%Y-%m-%d")
        }])
        df = pd.concat([df, new_customer], ignore_index=True)
    
    save_loyalty(df)
    return points_earned


# ==============================
# REDEEM LOYALTY POINTS
# ==============================
def redeem_points(customer_phone, points_to_redeem, receipt_no):
    """Redeem loyalty points for discount"""
    
    df = load_loyalty()
    redemptions = load_redemptions()
    
    customer = df[df["phone"] == customer_phone]
    
    if customer.empty:
        return False, 0, "Customer not found"
    
    idx = customer.index[0]
    current_points = df.at[idx, "points"]
    
    if points_to_redeem > current_points:
        return False, 0, f"Insufficient points. You have {current_points} points"
    
    # Calculate discount (100 points = $1 discount)
    discount = points_to_redeem / 100
    
    # Deduct points
    df.at[idx, "points"] = current_points - points_to_redeem
    save_loyalty(df)
    
    # Record redemption
    new_redemption = pd.DataFrame([{
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": df.at[idx, "customer_name"],
        "points_used": points_to_redeem,
        "discount_amount": discount,
        "receipt_no": receipt_no
    }])
    redemptions = pd.concat([redemptions, new_redemption], ignore_index=True)
    redemptions.to_csv(LOYALTY_REDEMPTIONS_FILE, index=False)
    
    return True, discount, f"Successfully redeemed {points_to_redeem} points for ${discount:.2f} discount"


# ==============================
# GET CUSTOMER LOYALTY INFO
# ==============================
def get_customer_loyalty_info(phone):
    """Get loyalty information for a customer"""
    
    df = load_loyalty()
    customer = df[df["phone"] == phone]
    
    if customer.empty:
        return None
    
    row = customer.iloc[0]
    tier_benefits = get_tier_benefits(row["tier"])
    
    return {
        "customer_name": row["customer_name"],
        "phone": row["phone"],
        "points": row["points"],
        "tier": row["tier"],
        "total_spent": row["total_spent"],
        "total_orders": row["total_orders"],
        "last_visit": row["last_visit"],
        "joined_date": row["joined_date"],
        "benefits": tier_benefits,
        "points_to_next_tier": get_points_to_next_tier(row["total_spent"])
    }


def get_points_to_next_tier(total_spent):
    """Calculate points needed to reach next tier"""
    if total_spent < 500:
        return 500 - total_spent
    elif total_spent < 2000:
        return 2000 - total_spent
    elif total_spent < 5000:
        return 5000 - total_spent
    else:
        return 0


# ==============================
# GET TOP LOYALTY CUSTOMERS
# ==============================
def get_top_loyalty_customers(n=10):
    df = load_loyalty()
    if df.empty:
        return df
    return df.nlargest(n, "points")[["customer_name", "phone", "points", "tier", "total_spent"]]


# ==============================
# BIRTHDAY CUSTOMERS THIS MONTH
# ==============================
def get_birthday_customers():
    df = load_loyalty()
    if df.empty or "birthday" not in df.columns:
        return pd.DataFrame()
    
    current_month = datetime.now().month
    df["birthday_month"] = pd.to_datetime(df["birthday"], errors="coerce").dt.month
    birthday_customers = df[df["birthday_month"] == current_month]
    
    return birthday_customers[["customer_name", "phone", "points", "tier"]]