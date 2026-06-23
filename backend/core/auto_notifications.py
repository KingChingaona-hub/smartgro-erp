import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import json
import threading
import time

from backend.core.db_adapter import load_products
from backend.integrations.email_reports import send_email, get_email_config

# ==============================
# ALERT TRACKING SYSTEM
# ==============================
ALERT_HISTORY_FILE = Path("data/low_stock_alert_history.json")
NOTIFICATION_SETTINGS_FILE = Path("data/auto_notification_settings.json")

def load_alert_history():
    """Load history of sent low stock alerts"""
    if not ALERT_HISTORY_FILE.exists():
        return {
            "last_alert_time": None,
            "alerted_items": {},  # barcode: {alerted_at, last_notified}
            "alert_count": 0
        }
    with open(ALERT_HISTORY_FILE, "r") as f:
        return json.load(f)

def save_alert_history(history):
    """Save alert history"""
    with open(ALERT_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, default=str)

def load_notification_settings():
    """Load auto-notification settings"""
    if not NOTIFICATION_SETTINGS_FILE.exists():
        return {
            "auto_notify_enabled": True,
            "check_interval_minutes": 30,
            "send_immediate_alerts": True,
            "daily_digest_enabled": True,
            "digest_time": "08:00",
            "last_digest_sent": None,
            "min_stock_threshold_override": None  # Uses product reorder_level by default
        }
    with open(NOTIFICATION_SETTINGS_FILE, "r") as f:
        return json.load(f)

def save_notification_settings(settings):
    """Save notification settings"""
    with open(NOTIFICATION_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

def get_low_stock_items():
    """Get all items that need reordering"""
    products_df = load_products()
    
    if products_df.empty:
        return pd.DataFrame()
    
    # Get items below reorder level
    low_stock = products_df[products_df["stock"] <= products_df["reorder_level"]].copy()
    
    # Categorize urgency
    def get_urgency(row):
        if row["stock"] == 0:
            return "CRITICAL"
        elif row["stock"] <= row["reorder_level"] * 0.3:
            return "HIGH"
        elif row["stock"] <= row["reorder_level"] * 0.6:
            return "MEDIUM"
        else:
            return "LOW"
    
    if not low_stock.empty:
        low_stock["urgency"] = low_stock.apply(get_urgency, axis=1)
        low_stock["suggested_order"] = (low_stock["reorder_level"] * 2) - low_stock["stock"]
        low_stock["suggested_order"] = low_stock["suggested_order"].apply(lambda x: max(5, int(x)))
        if "cost" in low_stock.columns:
            low_stock["estimated_cost"] = low_stock["suggested_order"] * low_stock["cost"]
    
    return low_stock

def generate_enhanced_low_stock_report(low_stock_df):
    """Generate a detailed low stock report with urgency levels"""
    
    if low_stock_df.empty:
        return None
    
    critical = low_stock_df[low_stock_df["urgency"] == "CRITICAL"]
    high = low_stock_df[low_stock_df["urgency"] == "HIGH"]
    medium = low_stock_df[low_stock_df["urgency"] == "MEDIUM"]
    low = low_stock_df[low_stock_df["urgency"] == "LOW"]
    
    report = f"""
{'='*60}
AZIEL INVESTMENTS - LOW STOCK ALERT SYSTEM
{'='*60}

Alert Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'─'*40}
SUMMARY
{'─'*40}
• CRITICAL (Out of Stock): {len(critical)} items
• HIGH Urgency: {len(high)} items  
• MEDIUM Urgency: {len(medium)} items
• LOW Urgency: {len(low)} items
• TOTAL: {len(low_stock_df)} items needing attention

"""
    
    if not critical.empty:
        report += f"""
{'─'*40}
🚨 CRITICAL - OUT OF STOCK (IMMEDIATE ACTION REQUIRED)
{'─'*40}
"""
        for _, item in critical.iterrows():
            report += f"• {item['name']} - STOCK: 0 | Reorder at: {item['reorder_level']}\n"
    
    if not high.empty:
        report += f"""
{'─'*40}
⚠️ HIGH URGENCY (Reorder Immediately)
{'─'*40}
"""
        for _, item in high.iterrows():
            suggested = int(item['suggested_order'])
            report += f"• {item['name']} - Stock: {int(item['stock'])} | Reorder: {item['reorder_level']} | Suggested: {suggested}"
            if "estimated_cost" in item:
                report += f" (${item['estimated_cost']:.2f})"
            report += "\n"
    
    if not medium.empty:
        report += f"""
{'─'*40}
📦 MEDIUM URGENCY (Plan Reorder)
{'─'*40}
"""
        for _, item in medium.head(10).iterrows():
            report += f"• {item['name']} - Stock: {int(item['stock'])} | Reorder at: {item['reorder_level']}\n"
        if len(medium) > 10:
            report += f"... and {len(medium) - 10} more items\n"
    
    if not low.empty:
        report += f"""
{'─'*40}
✅ LOW URGENCY (Monitor)
{'─'*40}
"""
        for _, item in low.head(5).iterrows():
            report += f"• {item['name']} - Stock: {int(item['stock'])} | Reorder at: {item['reorder_level']}\n"
        if len(low) > 5:
            report += f"... and {len(low) - 5} more items\n"
    
    # Calculate total estimated cost
    if "estimated_cost" in low_stock_df.columns:
        total_cost = low_stock_df["estimated_cost"].sum()
        report += f"""
{'─'*40}
💰 FINANCIAL IMPACT
{'─'*40}
Total estimated reorder cost: ${total_cost:,.2f}

"""
    
    report += f"""
{'─'*40}
RECOMMENDED ACTIONS
{'─'*40}
1. IMMEDIATE: Place orders for CRITICAL and HIGH urgency items
2. TODAY: Review MEDIUM urgency items for ordering
3. WEEKLY: Monitor LOW urgency items

{'='*60}
SmartGro ERP System - Automated Stock Monitor
Contact: +263 78 290 5853
{'='*60}
"""
    
    return report

def check_and_send_low_stock_alerts(force=False):
    """
    Check stock levels and send alerts if needed
    Returns: (bool, message, new_items_found)
    """
    
    settings = load_notification_settings()
    if not settings["auto_notify_enabled"] and not force:
        return False, "Auto-notifications are disabled", False
    
    # Get current low stock items
    low_stock_df = get_low_stock_items()
    
    if low_stock_df.empty:
        return False, "No low stock items found", False
    
    # Load alert history
    history = load_alert_history()
    
    # Get current low stock barcodes
    current_low_barcodes = set(low_stock_df["barcode"].astype(str).tolist())
    
    # Get previously alerted barcodes
    previously_alerted = set(history.get("alerted_items", {}).keys())
    
    # Find NEW items that weren't alerted before
    new_items = current_low_barcodes - previously_alerted
    
    # Also check if existing items got worse (stock decreased significantly)
    worsened_items = []
    for barcode in previously_alerted & current_low_barcodes:
        current_stock = low_stock_df[low_stock_df["barcode"].astype(str) == barcode]["stock"].iloc[0]
        last_stock = history["alerted_items"].get(barcode, {}).get("last_stock", 999)
        if current_stock < last_stock * 0.5:  # Stock dropped by 50%
            worsened_items.append(barcode)
    
    # Check if enough time has passed since last alert (prevent spam)
    last_alert_time = history.get("last_alert_time")
    if last_alert_time:
        last_alert = datetime.fromisoformat(last_alert_time) if isinstance(last_alert_time, str) else last_alert_time
        minutes_since_last = (datetime.now() - last_alert).total_seconds() / 60
    else:
        minutes_since_last = 999
    
    # Determine if we should send an alert
    should_send = force or new_items or worsened_items
    
    # For digest mode, send even without new items after interval
    if settings["daily_digest_enabled"] and not should_send:
        last_digest = history.get("last_digest_sent")
        if last_digest:
            last_digest_date = datetime.fromisoformat(last_digest) if isinstance(last_digest, str) else last_digest
            if (datetime.now() - last_digest_date).days >= 1:
                should_send = True
    
    # Rate limiting: Don't send more than every 30 minutes for immediate alerts
    if settings["send_immediate_alerts"] and new_items and minutes_since_last < settings["check_interval_minutes"]:
        if not force:
            return False, f"Alert suppressed. Last alert was {minutes_since_last:.0f} minutes ago.", False
    
    if not should_send and not force:
        return False, "No new low stock items detected", False
    
    # Generate enhanced report
    report = generate_enhanced_low_stock_report(low_stock_df)
    
    if not report:
        return False, "No report generated", False
    
    # Determine subject line
    critical_count = len(low_stock_df[low_stock_df["urgency"] == "CRITICAL"])
    total_count = len(low_stock_df)
    
    if critical_count > 0:
        subject = f"🚨 URGENT: {critical_count} items OUT OF STOCK + {total_count - critical_count} low items"
    elif new_items:
        subject = f"⚠️ NEW Low Stock Alert: {len(new_items)} new items need attention"
    else:
        subject = f"📦 Low Stock Summary: {total_count} items need reordering"
    
    # Send email to all recipients
    config = get_email_config()
    recipients = config.get("recipient_emails", [])
    
    if not recipients:
        return False, "No recipient emails configured", False
    
    success_count = 0
    for recipient in recipients:
        if recipient and recipient.strip():
            success, message = send_email(
                recipient.strip(),
                subject,
                report
            )
            if success:
                success_count += 1
    
    if success_count > 0:
        # Update alert history
        current_time = datetime.now().isoformat()
        
        # Update history for all current low stock items
        for _, item in low_stock_df.iterrows():
            barcode = str(item["barcode"])
            if barcode not in history["alerted_items"]:
                history["alerted_items"][barcode] = {}
            history["alerted_items"][barcode]["alerted_at"] = current_time
            history["alerted_items"][barcode]["last_stock"] = int(item["stock"])
            history["alerted_items"][barcode]["last_notified"] = current_time
        
        history["last_alert_time"] = current_time
        history["alert_count"] = history.get("alert_count", 0) + 1
        
        if settings["daily_digest_enabled"]:
            history["last_digest_sent"] = current_time
        
        save_alert_history(history)
        
        new_count = len(new_items)
        worsened_count = len(worsened_items)
        return True, f"Alert sent to {success_count} recipient(s). New: {new_count}, Worsened: {worsened_count}", new_count > 0
    
    return False, "Failed to send alert", False


def get_alert_summary():
    """Get summary of alert history for dashboard display"""
    history = load_alert_history()
    
    low_stock_df = get_low_stock_items()
    
    return {
        "total_alerts_sent": history.get("alert_count", 0),
        "last_alert_time": history.get("last_alert_time"),
        "current_low_stock_count": len(low_stock_df),
        "critical_count": len(low_stock_df[low_stock_df["urgency"] == "CRITICAL"]) if not low_stock_df.empty else 0,
        "alerted_items_count": len(history.get("alerted_items", {})),
        "auto_notifications_enabled": load_notification_settings()["auto_notify_enabled"]
    }


def run_auto_monitor():
    """
    Background function to run stock monitoring
    This would be called by a scheduler in production
    """
    settings = load_notification_settings()
    
    while True:
        try:
            check_and_send_low_stock_alerts()
            time.sleep(settings["check_interval_minutes"] * 60)
        except Exception as e:
            print(f"Auto monitor error: {e}")
            time.sleep(60)