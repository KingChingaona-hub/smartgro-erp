import pandas as pd
from datetime import datetime
from backend.analytics.debtors_engine import load_debtors


def get_overdue_messages():
    """Generate notification messages for overdue debtors"""
    
    df = load_debtors()
    
    if df.empty:
        return pd.DataFrame()
    
    df["expected_repayment_date"] = pd.to_datetime(
        df["expected_repayment_date"],
        errors="coerce"
    )
    
    now = pd.Timestamp.now()
    messages = []
    
    for _, row in df.iterrows():
        if row["balance"] <= 0:
            continue
        
        if pd.isna(row["expected_repayment_date"]):
            continue
        
        days_overdue = (now - row["expected_repayment_date"]).days
        
        if days_overdue > 0:
            # Different message based on severity
            if days_overdue <= 7:
                severity = "Gentle Reminder"
                emoji = "🔔"
            elif days_overdue <= 30:
                severity = "Follow Up"
                emoji = "⚠️"
            elif days_overdue <= 60:
                severity = "URGENT"
                emoji = "🚨"
            else:
                severity = "FINAL NOTICE"
                emoji = "⛔"
            
            messages.append({
                "customer": row["customer_name"],
                "phone": row["phone"],
                "balance": f"${row['balance']:.2f}",
                "days_overdue": days_overdue,
                "severity": severity,
                "debt_id": row["debt_id"],
                "message": (
                    f"{emoji} {severity}: Dear {row['customer_name']}, "
                    f"your outstanding balance of ${row['balance']:.2f} "
                    f"is overdue by {days_overdue} days. "
                    f"Please make payment immediately to avoid service interruption."
                )
            })
    
    # Sort by days overdue (most urgent first)
    messages_df = pd.DataFrame(messages)
    if not messages_df.empty:
        messages_df = messages_df.sort_values("days_overdue", ascending=False)
    
    return messages_df