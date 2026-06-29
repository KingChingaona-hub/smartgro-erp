# backend/utils/utils.py - COMPLETE FIXED VERSION
import hashlib
import json
import urllib.parse
import re
from pathlib import Path
from datetime import datetime

# ==============================
# PASSWORD HASHING - FIXED
# ==============================
def hash_password(password):
    """
    Hash password using SHA-256 with proper UTF-8 encoding.
    This ensures consistent hashing across all platforms.
    """
    if not password:
        return ""
    # Use UTF-8 encoding explicitly for consistency
    return hashlib.sha256(str(password).encode('utf-8')).hexdigest()


# ==============================
# CURRENCY FORMATTER
# ==============================
def format_currency(amount, currency="ZWL", rates=None):
    if rates is None:
        return f"{amount:.2f}"

    symbol = rates.get(currency, {}).get("symbol", "Z$")
    
    if currency != "ZWL":
        rate = rates.get(currency, {}).get("rate", 1)
        amount = amount * rate

    return f"{symbol}{amount:,.2f}"


# ==============================
# JSON HELPERS
# ==============================
def load_json(file_path, default_data):
    if not Path(file_path).exists():
        with open(file_path, "w") as f:
            json.dump(default_data, f, indent=2)
        return default_data
    
    with open(file_path, "r") as f:
        return json.load(f)


def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def check_stock_available(products_df, cart):
    for item in cart:
        product = products_df[products_df["barcode"] == item["barcode"]]
        if product.empty:
            return False, f"Product not found: {item['name']}"
        available_stock = int(product.iloc[0]["stock"])
        if item["qty"] > available_stock:
            return False, f"Insufficient stock for {item['name']} (Available: {available_stock})"
    return True, "OK"


# ==============================
# WHATSAPP INTEGRATION HELPER FUNCTIONS
# ==============================

def format_phone_for_whatsapp(phone):
    """Format Zimbabwe phone number for WhatsApp"""
    if not phone:
        return None
    
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', str(phone))
    
    # Convert to international format
    if cleaned.startswith('0'):
        cleaned = '263' + cleaned[1:]
    elif cleaned.startswith('+263'):
        cleaned = cleaned[1:]
    elif not cleaned.startswith('263') and len(cleaned) == 9:
        cleaned = '263' + cleaned
    
    # Validate length
    if len(cleaned) == 12 and cleaned.startswith('263'):
        return cleaned
    
    return None


def generate_whatsapp_receipt(cart, subtotal, receipt_no, payment_method, 
                               customer_name, final_total, discount_amount=0, 
                               tax_amount=0, cash_received=0, change=0):
    """Generate WhatsApp-friendly receipt text"""
    
    receipt = f"🏪 *AZIEL INVESTMENTS*\n"
    receipt += f"📋 *Receipt:* {receipt_no}\n"
    receipt += f"📅 *Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    receipt += f"👤 *Customer:* {customer_name}\n"
    receipt += f"💳 *Payment:* {payment_method}\n"
    receipt += "─" * 25 + "\n"
    receipt += "*ITEMS:*\n"
    
    for item in cart:
        receipt += f"• {item['name'][:20]} x{item['qty']} = ${item['total']:.2f}\n"
    
    receipt += "─" * 25 + "\n"
    receipt += f"💰 *TOTAL:* ${final_total:.2f}\n"
    
    if discount_amount > 0:
        receipt += f"🎁 *Discount:* -${discount_amount:.2f}\n"
    
    if cash_received > 0:
        receipt += f"💵 *Cash Tendered:* ${cash_received:.2f}\n"
        receipt += f"🔄 *Change:* ${change:.2f}\n"
    
    receipt += "\n✅ *Thank you for shopping with us!*\n"
    receipt += f"📞 *Contact:* +263 78 290 5853\n"
    receipt += "─" * 25 + "\n"
    receipt += "*SmartGro ERP - Zimbabwe*"
    
    return receipt


def generate_whatsapp_payment_reminder(customer_name, amount, due_date, days_overdue=0):
    """Generate payment reminder message"""
    
    if days_overdue <= 0:
        reminder = f"🔔 *Payment Reminder*\n\n"
        reminder += f"Dear {customer_name},\n\n"
        reminder += f"Your payment of *${amount:.2f}* is due on *{due_date}*.\n\n"
        reminder += f"Please make your payment on time to avoid service interruption.\n\n"
        reminder += f"Thank you for your cooperation!\n\n"
        reminder += f"📞 Contact: +263 78 290 5853"
    else:
        reminder = f"⚠️ *OVERDUE PAYMENT NOTICE* ⚠️\n\n"
        reminder += f"Dear {customer_name},\n\n"
        reminder += f"Your payment of *${amount:.2f}* is now *{days_overdue} days overdue*.\n\n"
        reminder += f"Please make immediate payment to avoid service interruption.\n\n"
        reminder += f"📞 Contact: +263 78 290 5853"
    
    return reminder


def generate_whatsapp_promotion(message, discount_code=None):
    """Generate promotional message"""
    
    promo = f"🎉 *AZIEL INVESTMENTS SPECIAL OFFER* 🎉\n\n"
    promo += f"{message}\n\n"
    
    if discount_code:
        promo += f"🔑 *Discount Code:* {discount_code}\n"
    
    promo += f"\n✅ *Valid at all branches*\n"
    promo += f"📞 *Contact:* +263 78 290 5853"
    
    return promo


def get_whatsapp_link(phone, message):
    """Generate WhatsApp share link"""
    formatted_phone = format_phone_for_whatsapp(phone)
    if not formatted_phone:
        return None
    
    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/{formatted_phone}?text={encoded_message}"