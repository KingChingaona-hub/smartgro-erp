# backend/core/auto_notifications.py
# Branch-aware automatic low-stock alerts.
#
# Every product read is scoped to a specific branch. The alert history and
# auto-notification settings are stored per branch, so HO's alert cadence
# cannot suppress NAT's alert, and NAT's "last alerted" items cannot mask
# HO's genuinely new low-stock items.

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import json
import threading
import time

from backend.core.db_adapter import (
    load_products,
    get_current_branch,
    load_branches,
)
from backend.integrations.email_reports import send_email, get_email_config


# ==============================
# FILE PATHS - BRANCH AWARE
# ==============================
DATA_DIR = Path("data")


def get_branch_alert_history_file(branch_id=None):
    """Per-branch low-stock alert history file."""
    if branch_id is None:
        branch_id = get_current_branch()
    branch_id = str(branch_id).strip().upper() or "HO"
    return DATA_DIR / f"low_stock_alert_history_{branch_id.lower()}.json"


def get_branch_notification_settings_file(branch_id=None):
    """Per-branch auto-notification settings file."""
    if branch_id is None:
        branch_id = get_current_branch()
    branch_id = str(branch_id).strip().upper() or "HO"
    return DATA_DIR / f"auto_notification_settings_{branch_id.lower()}.json"


# ==============================
# BRANCH HELPERS
# ==============================
def _resolve_branch(branch_id=None):
    """Fallback to session branch if none was explicitly passed."""
    if branch_id is None:
        branch_id = get_current_branch()
    if not branch_id:
        branch_id = "HO"
    return str(branch_id).strip().upper()


def _branch_display_name(branch_id):
    """Human-readable branch label for email subject lines and report headers."""
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                name = row.get("branch_name", "")
                if name:
                    return f"{name} ({branch_id})"
    except Exception:
        pass
    return str(branch_id)


# ==============================
# ALERT HISTORY (PER BRANCH)
# ==============================
def load_alert_history(branch_id=None):
    """Load history of sent low stock alerts for the given branch."""
    branch_id = _resolve_branch(branch_id)
    path = get_branch_alert_history_file(branch_id)

    if not path.exists():
        return {
            "branch_id": branch_id,
            "last_alert_time": None,
            "alerted_items": {},   # barcode: {alerted_at, last_notified, last_stock}
            "alert_count": 0,
            "last_digest_sent": None,
        }

    try:
        with open(path, "r") as f:
            data = json.load(f)
        data.setdefault("branch_id", branch_id)
        data.setdefault("alerted_items", {})
        data.setdefault("alert_count", 0)
        return data
    except Exception:
        return {
            "branch_id": branch_id,
            "last_alert_time": None,
            "alerted_items": {},
            "alert_count": 0,
            "last_digest_sent": None,
        }


def save_alert_history(history, branch_id=None):
    """Save alert history for the given branch."""
    branch_id = _resolve_branch(branch_id)
    path = get_branch_alert_history_file(branch_id)
    path.parent.mkdir(exist_ok=True)
    history["branch_id"] = branch_id
    with open(path, "w") as f:
        json.dump(history, f, indent=2, default=str)


# ==============================
# NOTIFICATION SETTINGS (PER BRANCH)
# ==============================
def load_notification_settings(branch_id=None):
    """Load auto-notification settings for the given branch."""
    branch_id = _resolve_branch(branch_id)
    path = get_branch_notification_settings_file(branch_id)

    if not path.exists():
        defaults = {
            "branch_id": branch_id,
            "auto_notify_enabled": True,
            "check_interval_minutes": 30,
            "send_immediate_alerts": True,
            "daily_digest_enabled": True,
            "digest_time": "08:00",
            "last_digest_sent": None,
            "min_stock_threshold_override": None,
        }
        path.parent.mkdir(exist_ok=True)
        try:
            with open(path, "w") as f:
                json.dump(defaults, f, indent=2)
        except Exception:
            pass
        return defaults

    try:
        with open(path, "r") as f:
            data = json.load(f)
        data.setdefault("branch_id", branch_id)
        return data
    except Exception:
        return {
            "branch_id": branch_id,
            "auto_notify_enabled": True,
            "check_interval_minutes": 30,
            "send_immediate_alerts": True,
            "daily_digest_enabled": True,
            "digest_time": "08:00",
            "last_digest_sent": None,
            "min_stock_threshold_override": None,
        }


def save_notification_settings(settings, branch_id=None):
    """Save notification settings for the given branch."""
    branch_id = _resolve_branch(branch_id or settings.get("branch_id"))
    path = get_branch_notification_settings_file(branch_id)
    path.parent.mkdir(exist_ok=True)
    settings["branch_id"] = branch_id
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)


# ==============================
# LOW STOCK DETECTION (BRANCH-SCOPED)
# ==============================
def get_low_stock_items(branch_id=None):
    """
    Return all products at or below their reorder level, for the given branch.
    The scoping happens inside load_products(branch_id=...), so this never
    crosses branches.
    """
    branch_id = _resolve_branch(branch_id)

    products_df = load_products(branch_id=branch_id)

    if products_df is None or products_df.empty:
        return pd.DataFrame()

    # Ensure numeric safety on stock / reorder_level before comparison
    for col in ("stock", "reorder_level"):
        if col in products_df.columns:
            products_df[col] = pd.to_numeric(products_df[col], errors="coerce").fillna(0)

    if "reorder_level" not in products_df.columns:
        return pd.DataFrame()

    low_stock = products_df[products_df["stock"] <= products_df["reorder_level"]].copy()

    def get_urgency(row):
        stock = float(row.get("stock", 0) or 0)
        reorder = float(row.get("reorder_level", 0) or 0)
        if stock <= 0:
            return "CRITICAL"
        if reorder > 0 and stock <= reorder * 0.3:
            return "HIGH"
        if reorder > 0 and stock <= reorder * 0.6:
            return "MEDIUM"
        return "LOW"

    if not low_stock.empty:
        low_stock["urgency"] = low_stock.apply(get_urgency, axis=1)
        low_stock["suggested_order"] = (
            (low_stock["reorder_level"] * 2) - low_stock["stock"]
        ).apply(lambda x: max(5, int(x)) if pd.notna(x) else 5)

        if "cost" in low_stock.columns:
            low_stock["cost"] = pd.to_numeric(low_stock["cost"], errors="coerce").fillna(0)
            low_stock["estimated_cost"] = low_stock["suggested_order"] * low_stock["cost"]

        # Tag for downstream report headers
        low_stock["branch_id"] = branch_id

    return low_stock


# ==============================
# REPORT GENERATION (BRANCH-LABELLED)
# ==============================
def generate_enhanced_low_stock_report(low_stock_df, branch_id=None):
    """Generate a detailed low stock report with urgency levels, labelled by branch."""
    branch_id = _resolve_branch(branch_id)
    branch_label = _branch_display_name(branch_id)

    if low_stock_df is None or low_stock_df.empty:
        return None

    critical = low_stock_df[low_stock_df["urgency"] == "CRITICAL"]
    high = low_stock_df[low_stock_df["urgency"] == "HIGH"]
    medium = low_stock_df[low_stock_df["urgency"] == "MEDIUM"]
    low = low_stock_df[low_stock_df["urgency"] == "LOW"]

    report = f"""
{'='*60}
AZIEL INVESTMENTS - LOW STOCK ALERT SYSTEM
{'='*60}

Branch: {branch_label}
Alert Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'─'*40}
SUMMARY
{'─'*40}
- CRITICAL (Out of Stock): {len(critical)} items
- HIGH Urgency: {len(high)} items
- MEDIUM Urgency: {len(medium)} items
- LOW Urgency: {len(low)} items
- TOTAL: {len(low_stock_df)} items needing attention
"""

    if not critical.empty:
        report += f"""
{'─'*40}
CRITICAL - OUT OF STOCK (IMMEDIATE ACTION REQUIRED)
{'─'*40}
"""
        for _, item in critical.iterrows():
            report += f"- {item['name']} - STOCK: 0 | Reorder at: {item['reorder_level']}\n"

    if not high.empty:
        report += f"""
{'─'*40}
HIGH URGENCY (Reorder Immediately)
{'─'*40}
"""
        for _, item in high.iterrows():
            suggested = int(item["suggested_order"])
            report += (
                f"- {item['name']} - Stock: {int(item['stock'])} | "
                f"Reorder: {item['reorder_level']} | Suggested: {suggested}"
            )
            if "estimated_cost" in item:
                report += f" (${item['estimated_cost']:.2f})"
            report += "\n"

    if not medium.empty:
        report += f"""
{'─'*40}
MEDIUM URGENCY (Plan Reorder)
{'─'*40}
"""
        for _, item in medium.head(10).iterrows():
            report += f"- {item['name']} - Stock: {int(item['stock'])} | Reorder at: {item['reorder_level']}\n"
        if len(medium) > 10:
            report += f"... and {len(medium) - 10} more items\n"

    if not low.empty:
        report += f"""
{'─'*40}
LOW URGENCY (Monitor)
{'─'*40}
"""
        for _, item in low.head(5).iterrows():
            report += f"- {item['name']} - Stock: {int(item['stock'])} | Reorder at: {item['reorder_level']}\n"
        if len(low) > 5:
            report += f"... and {len(low) - 5} more items\n"

    if "estimated_cost" in low_stock_df.columns:
        total_cost = low_stock_df["estimated_cost"].sum()
        report += f"""
{'─'*40}
FINANCIAL IMPACT
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
Branch: {branch_label}
Contact: +263 78 290 5853
{'='*60}
"""

    return report


# ==============================
# MAIN CHECK & SEND (BRANCH-AWARE)
# ==============================
def check_and_send_low_stock_alerts(force=False, branch_id=None):
    """
    Check stock levels for a specific branch and send alerts if needed.

    Args:
        force: ignore rate limiting and send regardless.
        branch_id: which branch to check. Defaults to session branch.

    Returns:
        (bool success, str message, bool new_items_found)
    """
    branch_id = _resolve_branch(branch_id)
    branch_label = _branch_display_name(branch_id)

    settings = load_notification_settings(branch_id=branch_id)
    if not settings["auto_notify_enabled"] and not force:
        return False, f"Auto-notifications are disabled for {branch_label}", False

    # ---- Scoped low-stock read ----
    low_stock_df = get_low_stock_items(branch_id=branch_id)

    if low_stock_df.empty:
        return False, f"No low stock items found in {branch_label}", False

    # ---- Load this branch's alert history ----
    history = load_alert_history(branch_id=branch_id)

    current_low_barcodes = set(low_stock_df["barcode"].astype(str).tolist())
    previously_alerted = set(history.get("alerted_items", {}).keys())

    new_items = current_low_barcodes - previously_alerted

    # Check if items that were previously alerted got materially worse
    worsened_items = []
    for barcode in previously_alerted & current_low_barcodes:
        try:
            current_stock = low_stock_df[low_stock_df["barcode"].astype(str) == barcode]["stock"].iloc[0]
            last_stock = history["alerted_items"].get(barcode, {}).get("last_stock", 999)
            if current_stock < last_stock * 0.5:
                worsened_items.append(barcode)
        except Exception:
            continue

    # Rate limiting window
    last_alert_time = history.get("last_alert_time")
    if last_alert_time:
        try:
            last_alert = (
                datetime.fromisoformat(last_alert_time)
                if isinstance(last_alert_time, str)
                else last_alert_time
            )
            minutes_since_last = (datetime.now() - last_alert).total_seconds() / 60
        except Exception:
            minutes_since_last = 999
    else:
        minutes_since_last = 999

    should_send = force or bool(new_items) or bool(worsened_items)

    # Daily digest window
    if settings.get("daily_digest_enabled") and not should_send:
        last_digest = history.get("last_digest_sent")
        if last_digest:
            try:
                last_digest_dt = (
                    datetime.fromisoformat(last_digest)
                    if isinstance(last_digest, str)
                    else last_digest
                )
                if (datetime.now() - last_digest_dt).days >= 1:
                    should_send = True
            except Exception:
                pass

    # Rate limit immediate alerts
    if (
        settings.get("send_immediate_alerts")
        and new_items
        and minutes_since_last < settings.get("check_interval_minutes", 30)
        and not force
    ):
        return (
            False,
            f"Alert for {branch_label} suppressed. Last alert was {minutes_since_last:.0f} minutes ago.",
            False,
        )

    if not should_send and not force:
        return False, f"No new low stock items detected in {branch_label}", False

    # ---- Build the report ----
    report = generate_enhanced_low_stock_report(low_stock_df, branch_id=branch_id)
    if not report:
        return False, "No report generated", False

    # ---- Subject line ----
    critical_count = len(low_stock_df[low_stock_df["urgency"] == "CRITICAL"])
    total_count = len(low_stock_df)

    if critical_count > 0:
        subject = (
            f"[{branch_id}] URGENT: {critical_count} items OUT OF STOCK "
            f"+ {total_count - critical_count} low items"
        )
    elif new_items:
        subject = f"[{branch_id}] NEW Low Stock Alert: {len(new_items)} new items need attention"
    else:
        subject = f"[{branch_id}] Low Stock Summary: {total_count} items need reordering"

    # ---- Send to this branch's configured recipients ----
    config = get_email_config(branch_id=branch_id)
    recipients = config.get("recipient_emails", []) if config else []

    if not recipients:
        return False, f"No recipient emails configured for {branch_label}", False

    success_count = 0
    for recipient in recipients:
        if recipient and recipient.strip():
            success, _ = send_email(
                recipient.strip(),
                subject,
                report,
                branch_id=branch_id,
            )
            if success:
                success_count += 1

    if success_count == 0:
        return False, f"Failed to send alert for {branch_label}", False

    # ---- Update this branch's history ----
    current_time = datetime.now().isoformat()

    for _, item in low_stock_df.iterrows():
        barcode = str(item["barcode"])
        if barcode not in history["alerted_items"]:
            history["alerted_items"][barcode] = {}
        history["alerted_items"][barcode]["alerted_at"] = current_time
        history["alerted_items"][barcode]["last_stock"] = int(item["stock"])
        history["alerted_items"][barcode]["last_notified"] = current_time

    history["last_alert_time"] = current_time
    history["alert_count"] = history.get("alert_count", 0) + 1
    if settings.get("daily_digest_enabled"):
        history["last_digest_sent"] = current_time

    save_alert_history(history, branch_id=branch_id)

    return (
        True,
        f"Alert for {branch_label} sent to {success_count} recipient(s). "
        f"New: {len(new_items)}, Worsened: {len(worsened_items)}",
        len(new_items) > 0,
    )


# ==============================
# SUMMARY FOR DASHBOARD
# ==============================
def get_alert_summary(branch_id=None):
    """Get summary of alert history + current low-stock state for a branch."""
    branch_id = _resolve_branch(branch_id)

    history = load_alert_history(branch_id=branch_id)
    low_stock_df = get_low_stock_items(branch_id=branch_id)
    settings = load_notification_settings(branch_id=branch_id)

    return {
        "branch_id": branch_id,
        "branch_label": _branch_display_name(branch_id),
        "total_alerts_sent": history.get("alert_count", 0),
        "last_alert_time": history.get("last_alert_time"),
        "current_low_stock_count": len(low_stock_df),
        "critical_count": (
            len(low_stock_df[low_stock_df["urgency"] == "CRITICAL"])
            if not low_stock_df.empty
            else 0
        ),
        "alerted_items_count": len(history.get("alerted_items", {})),
        "auto_notifications_enabled": settings.get("auto_notify_enabled", True),
    }


# ==============================
# BACKGROUND MONITOR
# ==============================
def run_auto_monitor(branch_id=None):
    """
    Background loop that runs a stock check at the configured interval.
    If branch_id is None, the loop checks every branch on each cycle.
    """
    while True:
        try:
            if branch_id:
                settings = load_notification_settings(branch_id=branch_id)
                check_and_send_low_stock_alerts(force=False, branch_id=branch_id)
                interval = settings.get("check_interval_minutes", 30)
                time.sleep(interval * 60)
            else:
                # Multi-branch sweep
                branches = ["HO", "NAT", "PRO", "DIS", "VIL"]
                try:
                    bdf = load_branches()
                    if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
                        branches = bdf["branch_id"].astype(str).tolist()
                except Exception:
                    pass

                min_interval = 30
                for bid in branches:
                    try:
                        settings = load_notification_settings(branch_id=bid)
                        if settings.get("auto_notify_enabled", True):
                            check_and_send_low_stock_alerts(force=False, branch_id=bid)
                        min_interval = min(
                            min_interval,
                            settings.get("check_interval_minutes", 30),
                        )
                    except Exception as e:
                        print(f"[Auto-Monitor] Branch {bid} error: {e}")

                time.sleep(min_interval * 60)

        except Exception as e:
            print(f"[Auto-Monitor] Error: {e}")
            time.sleep(60)


def start_monitor_thread(branch_id=None):
    """
    Start the background monitor as a daemon thread.
    Call from app.py:
        start_monitor_thread()               # sweep all branches
        start_monitor_thread(branch_id="HO") # single branch
    Returns the thread object.
    """
    t = threading.Thread(
        target=run_auto_monitor,
        kwargs={"branch_id": branch_id},
        daemon=True,
    )
    t.start()
    return t