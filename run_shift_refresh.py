# run_shift_refresh.py
# Run this script once to refresh all shift data with actual values
# Place this file in your project root: C:\Users\user\Desktop\SmartGro_System\

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import datetime
from decimal import Decimal

# Import from your existing db_adapter
from backend.core.db_adapter import (
    load_shifts, 
    save_shifts, 
    load_sales, 
    load_cash,
    get_current_branch,
    load_db_config,
    get_db_cursor
)


def to_float(value):
    """
    Safely convert a value to float.
    Handles Decimal, int, str, and None types.
    """
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def refresh_shift_data(shift_id=None):
    """
    Refresh shift data by recalculating from sales and cash tables.
    
    Args:
        shift_id: Optional specific shift ID to refresh. If None, refreshes all shifts.
    
    Returns:
        Tuple of (success, message)
    """
    print("\n🔄 Loading shifts...")
    shifts_df = load_shifts()
    
    if shifts_df.empty:
        print("❌ No shifts found in database")
        return False, "No shifts found"
    
    print(f"📊 Found {len(shifts_df)} shifts total")
    
    # Filter if specific shift_id provided
    if shift_id:
        mask = shifts_df["shift_id"] == shift_id
        if not mask.any():
            return False, f"Shift {shift_id} not found"
        indices = [shifts_df[mask].index[0]]
        print(f"🎯 Refreshing specific shift: {shift_id}")
    else:
        indices = shifts_df.index.tolist()
        print(f"🔄 Refreshing all {len(indices)} shifts...")
    
    refreshed = 0
    skipped = 0
    errors = []
    
    for i in indices:
        shift = shifts_df.loc[i]
        shift_id_val = shift["shift_id"]
        branch_id = shift.get("branch_id", get_current_branch())
        status = shift.get("status", "UNKNOWN")
        
        # Skip if shift is already closed and has data
        if status == "CLOSED" and shift.get("total_revenue", 0) > 0:
            print(f"⏭️  Skipping shift {shift_id_val} - already has data")
            skipped += 1
            continue
        
        print(f"\n📝 Processing shift: {shift_id_val} ({status})...")
        
        try:
            # Get sales for this shift
            sales_df = load_sales(branch_id)
            if not sales_df.empty and "shift_id" in sales_df.columns:
                shift_sales = sales_df[sales_df["shift_id"] == shift_id_val]
            else:
                shift_sales = pd.DataFrame()
            
            # Get cash entries for this shift
            cash_df = load_cash(branch_id)
            if not cash_df.empty and "shift_id" in cash_df.columns:
                shift_cash = cash_df[cash_df["shift_id"] == shift_id_val]
            else:
                shift_cash = pd.DataFrame()
            
            # Calculate metrics
            revenue = 0
            profit = 0
            transactions = 0
            cash_sales = 0
            credit_sales = 0
            debt_payments = 0
            expenses = 0
            
            # Calculate from sales
            if not shift_sales.empty:
                if "final_total" in shift_sales.columns:
                    revenue = to_float(shift_sales["final_total"].sum())
                elif "total" in shift_sales.columns:
                    revenue = to_float(shift_sales["total"].sum())
                
                if "profit" in shift_sales.columns:
                    profit = to_float(shift_sales["profit"].sum())
                
                transactions = len(shift_sales)
                print(f"   📊 Sales: {transactions} transactions, Revenue: ${revenue:.2f}, Profit: ${profit:.2f}")
            
            # Calculate from cash
            if not shift_cash.empty and "type" in shift_cash.columns:
                cash_sales = to_float(shift_cash[shift_cash["type"] == "CASH_SALE"]["amount"].sum())
                credit_sales = to_float(shift_cash[shift_cash["type"] == "CREDIT_SALE"]["amount"].sum())
                debt_payments = to_float(shift_cash[shift_cash["type"] == "DEBT_PAYMENT"]["amount"].sum())
                expenses = to_float(shift_cash[shift_cash["type"] == "EXPENSE"]["amount"].sum())
                print(f"   💰 Cash: Cash Sales=${cash_sales:.2f}, Credit Sales=${credit_sales:.2f}, Debt Payments=${debt_payments:.2f}, Expenses=${expenses:.2f}")
            
            # Update shift data
            old_revenue = to_float(shift.get("total_revenue", 0))
            old_profit = to_float(shift.get("profit", 0))
            old_transactions = int(shift.get("transactions", 0))
            
            # Only update if we have new data or if old data is zero
            if revenue > 0 or old_revenue == 0:
                shifts_df.at[i, "total_revenue"] = revenue
            if profit > 0 or old_profit == 0:
                shifts_df.at[i, "profit"] = profit
            if transactions > 0 or old_transactions == 0:
                shifts_df.at[i, "transactions"] = transactions
            
            shifts_df.at[i, "cash_sales"] = cash_sales
            shifts_df.at[i, "credit_sales"] = credit_sales
            shifts_df.at[i, "debt_payments"] = debt_payments
            shifts_df.at[i, "expenses"] = expenses
            
            # Calculate variance
            opening_cash = to_float(shifts_df.at[i, "opening_cash"])
            closing_cash = to_float(shifts_df.at[i, "closing_cash"])
            expected_cash = opening_cash + cash_sales + debt_payments - expenses
            variance = closing_cash - expected_cash if closing_cash > 0 else 0
            shifts_df.at[i, "variance"] = variance
            
            refreshed += 1
            print(f"   ✅ Updated: Revenue=${revenue:.2f}, Profit=${profit:.2f}, Variance=${variance:.2f}")
            
        except Exception as e:
            error_msg = f"Error processing shift {shift_id_val}: {str(e)}"
            print(f"   ❌ {error_msg}")
            errors.append(error_msg)
    
    # Save all changes
    if refreshed > 0:
        print(f"\n💾 Saving {refreshed} updated shifts...")
        save_shifts(shifts_df)
        print("✅ Save successful!")
    else:
        print(f"\n⏭️  No shifts were updated (skipped: {skipped})")
    
    # Summary
    print("\n" + "=" * 50)
    print("REFRESH SUMMARY")
    print("=" * 50)
    print(f"Total shifts processed: {len(indices)}")
    print(f"✅ Refreshed: {refreshed}")
    print(f"⏭️  Skipped: {skipped}")
    if errors:
        print(f"❌ Errors: {len(errors)}")
        for err in errors[:5]:  # Show first 5 errors
            print(f"   - {err}")
    print("=" * 50)
    
    return True, f"Refreshed {refreshed} shifts successfully"


def verify_updated_data():
    """Verify that the data was updated correctly"""
    print("\n🔍 Verifying updated data...")
    
    shifts_df = load_shifts()
    
    if shifts_df.empty:
        print("❌ No shifts found")
        return
    
    print(f"\n📊 Total shifts: {len(shifts_df)}")
    
    # Show closed shifts with data
    closed_shifts = shifts_df[shifts_df["status"] == "CLOSED"]
    if not closed_shifts.empty:
        print(f"\n📋 Closed Shifts ({len(closed_shifts)}):")
        display_cols = ["shift_id", "cashier_name", "total_revenue", "profit", "transactions", "variance"]
        available_cols = [col for col in display_cols if col in closed_shifts.columns]
        
        # Show only shifts with revenue > 0
        with_data = closed_shifts[closed_shifts["total_revenue"] > 0]
        if not with_data.empty:
            print("\n✅ Shifts with data:")
            print(with_data[available_cols].head(10).to_string(index=False))
        else:
            print("\n⚠️  No closed shifts have revenue data")
    
    # Show active shifts
    active_shifts = shifts_df[shifts_df["status"] == "OPEN"]
    if not active_shifts.empty:
        print(f"\n🟢 Active Shifts ({len(active_shifts)}):")
        display_cols = ["shift_id", "cashier_name", "opening_cash", "status"]
        available_cols = [col for col in display_cols if col in active_shifts.columns]
        print(active_shifts[available_cols].head(5).to_string(index=False))
    
    # Summary statistics
    print("\n📊 Summary Statistics:")
    total_revenue = shifts_df["total_revenue"].sum() if "total_revenue" in shifts_df.columns else 0
    total_profit = shifts_df["profit"].sum() if "profit" in shifts_df.columns else 0
    total_transactions = shifts_df["transactions"].sum() if "transactions" in shifts_df.columns else 0
    
    print(f"   Total Revenue: ${to_float(total_revenue):,.2f}")
    print(f"   Total Profit: ${to_float(total_profit):,.2f}")
    print(f"   Total Transactions: {int(total_transactions):,}")
    print(f"   Total Shifts: {len(shifts_df)}")


def refresh_single_shift(shift_id):
    """Refresh a single shift by ID"""
    print(f"\n🎯 Refreshing specific shift: {shift_id}")
    return refresh_shift_data(shift_id)


def refresh_all_shifts():
    """Refresh all shifts"""
    print("\n🔄 Refreshing ALL shifts...")
    return refresh_shift_data()


def refresh_today_shifts():
    """Refresh today's shifts only"""
    print("\n📅 Refreshing today's shifts...")
    
    shifts_df = load_shifts()
    if shifts_df.empty:
        return False, "No shifts found"
    
    # Get today's date
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Filter shifts that started today
    if "start_time" in shifts_df.columns:
        shifts_df["start_date"] = pd.to_datetime(shifts_df["start_time"]).dt.strftime("%Y-%m-%d")
        today_shifts = shifts_df[shifts_df["start_date"] == today]
        
        if today_shifts.empty:
            return False, "No shifts found for today"
        
        # Refresh each today's shift
        success_count = 0
        for shift_id in today_shifts["shift_id"].tolist():
            success, msg = refresh_shift_data(shift_id)
            if success:
                success_count += 1
        
        return True, f"Refreshed {success_count} today's shifts"
    
    return False, "Could not filter by date"


def main():
    """Main menu for the refresh tool"""
    print("\n" + "=" * 60)
    print("   SHIFT DATA REFRESH TOOL")
    print("=" * 60)
    print("\nThis tool will refresh shift data with actual values from sales and cash tables.")
    print("\nOptions:")
    print("  1. Refresh ALL shifts")
    print("  2. Refresh a specific shift")
    print("  3. Refresh today's shifts")
    print("  4. Verify data only (no refresh)")
    print("  5. Exit")
    
    while True:
        try:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == "1":
                success, message = refresh_all_shifts()
                print(f"\n{message}")
                if success:
                    verify_updated_data()
                break
                
            elif choice == "2":
                shift_id = input("Enter shift ID: ").strip()
                if shift_id:
                    success, message = refresh_single_shift(shift_id)
                    print(f"\n{message}")
                    if success:
                        verify_updated_data()
                else:
                    print("❌ Invalid shift ID")
                break
                
            elif choice == "3":
                success, message = refresh_today_shifts()
                print(f"\n{message}")
                if success:
                    verify_updated_data()
                break
                
            elif choice == "4":
                verify_updated_data()
                break
                
            elif choice == "5":
                print("\n👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please enter 1-5.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            break


if __name__ == "__main__":
    # Check if shift ID was passed as command line argument
    if len(sys.argv) > 1:
        shift_id = sys.argv[1]
        print(f"\n🎯 Refreshing specific shift: {shift_id}")
        success, message = refresh_single_shift(shift_id)
        print(f"\n{message}")
        if success:
            verify_updated_data()
    else:
        # Run interactive menu
        main()