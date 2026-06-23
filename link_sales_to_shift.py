# link_sales_to_shifts.py
# Run this script to link all existing sales to shifts
# Place this file in your project root: C:\Users\user\Desktop\SmartGro_System\

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import datetime
from backend.core.db_adapter import (
    load_shifts,
    load_sales,
    save_sales,
    load_cash,
    get_current_branch,
    to_float
)


def get_shift_for_sale(sale_date, shifts_df):
    """
    Find the appropriate shift for a sale based on its date.
    Returns the shift_id if found, else None.
    """
    if shifts_df.empty:
        return None
    
    # Convert sale_date to datetime if it's a string
    if isinstance(sale_date, str):
        try:
            sale_date = pd.to_datetime(sale_date)
        except:
            return None
    
    # Find shifts that were active around this sale time
    for _, shift in shifts_df.iterrows():
        shift_start = shift.get('start_time')
        shift_end = shift.get('end_time')
        
        if shift_start is None:
            continue
            
        # Convert to datetime if needed
        if isinstance(shift_start, str):
            shift_start = pd.to_datetime(shift_start)
        if shift_end and isinstance(shift_end, str):
            shift_end = pd.to_datetime(shift_end)
        
        # Check if sale date falls within this shift's timeframe
        if shift_end is None:
            # Active shift (no end time)
            if sale_date >= shift_start:
                return shift['shift_id']
        else:
            # Closed shift
            if shift_start <= sale_date <= shift_end:
                return shift['shift_id']
    
    # If no exact match, find the closest shift (most recent before sale)
    valid_shifts = shifts_df[shifts_df['start_time'].notna()]
    if not valid_shifts.empty:
        valid_shifts = valid_shifts.copy()
        valid_shifts['start_time'] = pd.to_datetime(valid_shifts['start_time'])
        valid_shifts = valid_shifts[valid_shifts['start_time'] <= sale_date]
        
        if not valid_shifts.empty:
            valid_shifts = valid_shifts.sort_values('start_time', ascending=False)
            return valid_shifts.iloc[0]['shift_id']
    
    return None


def link_sales_to_shifts():
    """
    Link all sales without shift_id to their appropriate shifts.
    """
    print("=" * 70)
    print("   LINKING SALES TO SHIFTS")
    print("=" * 70)
    
    # Load data
    print("\n📂 Loading data...")
    shifts_df = load_shifts()
    sales_df = load_sales()
    cash_df = load_cash()
    
    if sales_df.empty:
        print("❌ No sales found in database")
        return False, "No sales found"
    
    if shifts_df.empty:
        print("❌ No shifts found. Please start a shift first.")
        return False, "No shifts found"
    
    print(f"📊 Found {len(sales_df)} sales and {len(shifts_df)} shifts")
    
    # Check for shift_id column
    if 'shift_id' not in sales_df.columns:
        print("❌ No shift_id column in sales table")
        return False, "No shift_id column"
    
    # Find sales without shift_id
    no_shift_sales = sales_df[
        sales_df['shift_id'].isna() | 
        (sales_df['shift_id'] == '') | 
        (sales_df['shift_id'] == 'None') |
        (sales_df['shift_id'] == 'null')
    ]
    
    if no_shift_sales.empty:
        print("✅ All sales already have shift_id")
        print(f"   Total sales: {len(sales_df)}")
        return True, "All sales already linked"
    
    print(f"\n🔍 Found {len(no_shift_sales)} sales without shift_id")
    
    # Display sample of sales without shift_id
    print("\n📋 Sample of sales without shift_id:")
    sample_cols = ['receipt_no', 'sale_date', 'product_name', 'final_total']
    available_cols = [col for col in sample_cols if col in no_shift_sales.columns]
    if available_cols:
        print(no_shift_sales[available_cols].head(10).to_string(index=False))
    
    # Get active shifts
    active_shifts = shifts_df[shifts_df['status'] == 'OPEN']
    closed_shifts = shifts_df[shifts_df['status'] == 'CLOSED']
    
    print(f"\n📊 Shift status:")
    print(f"   Active shifts: {len(active_shifts)}")
    print(f"   Closed shifts: {len(closed_shifts)}")
    
    # Link each sale to a shift
    print("\n🔄 Linking sales to shifts...")
    
    linked_count = 0
    active_shift_id = None
    
    # Get active shift if available
    if not active_shifts.empty:
        active_shift_id = active_shifts.iloc[0]['shift_id']
        print(f"   Active shift found: {active_shift_id}")
    
    # Process each sale without shift_id
    for idx in no_shift_sales.index:
        sale = no_shift_sales.loc[idx]
        sale_date = sale.get('sale_date')
        
        # Try to find the right shift
        shift_id = None
        
        # First, try active shift
        if active_shift_id:
            shift_id = active_shift_id
        
        # If no active shift, try to find based on date
        if not shift_id and sale_date:
            shift_id = get_shift_for_sale(sale_date, shifts_df)
        
        # If still no shift, use the most recent shift
        if not shift_id:
            sorted_shifts = shifts_df.sort_values('start_time', ascending=False)
            if not sorted_shifts.empty:
                shift_id = sorted_shifts.iloc[0]['shift_id']
                print(f"   ⚠️ Using most recent shift {shift_id} for sale {sale.get('receipt_no', 'N/A')}")
        
        if shift_id:
            sales_df.at[idx, 'shift_id'] = str(shift_id)
            linked_count += 1
        else:
            print(f"   ⚠️ Could not find shift for sale {sale.get('receipt_no', 'N/A')}")
    
    # Save updated sales
    if linked_count > 0:
        print(f"\n💾 Saving {linked_count} updated sales...")
        save_sales(sales_df)
        print("✅ Save successful!")
    else:
        print("\n⚠️ No sales were linked")
    
    # Verify the update
    print("\n🔍 Verifying update...")
    verify_df = load_sales()
    if not verify_df.empty and 'shift_id' in verify_df.columns:
        has_shift = verify_df['shift_id'].notna().sum()
        no_shift = len(verify_df) - has_shift
        print(f"   Sales with shift_id: {has_shift}")
        print(f"   Sales without shift_id: {no_shift}")
        if no_shift == 0:
            print("   ✅ All sales now have shift_id!")
        else:
            print(f"   ⚠️ Still {no_shift} sales without shift_id")
    
    print("\n" + "=" * 70)
    print(f"✅ Successfully linked {linked_count} sales to shifts")
    print("=" * 70)
    print("\n📌 Next steps:")
    print("   1. Run: python run_shift_refresh.py")
    print("   2. Restart your Streamlit app")
    print("   3. Check Shift Summary and History pages")
    
    return True, f"Linked {linked_count} sales to shifts"


def link_cash_to_shifts():
    """
    Link cash entries without shift_id to their appropriate shifts.
    """
    print("\n" + "=" * 70)
    print("   LINKING CASH ENTRIES TO SHIFTS")
    print("=" * 70)
    
    shifts_df = load_shifts()
    cash_df = load_cash()
    
    if cash_df.empty:
        print("❌ No cash entries found")
        return False, "No cash entries found"
    
    if shifts_df.empty:
        print("❌ No shifts found")
        return False, "No shifts found"
    
    if 'shift_id' not in cash_df.columns:
        print("❌ No shift_id column in cash table")
        return False, "No shift_id column"
    
    # Find cash entries without shift_id
    no_shift_cash = cash_df[
        cash_df['shift_id'].isna() | 
        (cash_df['shift_id'] == '') | 
        (cash_df['shift_id'] == 'None')
    ]
    
    if no_shift_cash.empty:
        print("✅ All cash entries already have shift_id")
        return True, "All cash entries already linked"
    
    print(f"🔍 Found {len(no_shift_cash)} cash entries without shift_id")
    
    # Get active shift
    active_shifts = shifts_df[shifts_df['status'] == 'OPEN']
    active_shift_id = None
    if not active_shifts.empty:
        active_shift_id = active_shifts.iloc[0]['shift_id']
        print(f"   Active shift: {active_shift_id}")
    
    # Link cash entries
    linked_count = 0
    for idx in no_shift_cash.index:
        cash = no_shift_cash.loc[idx]
        
        # Try active shift first
        if active_shift_id:
            cash_df.at[idx, 'shift_id'] = str(active_shift_id)
            linked_count += 1
        else:
            # Use most recent shift
            sorted_shifts = shifts_df.sort_values('start_time', ascending=False)
            if not sorted_shifts.empty:
                cash_df.at[idx, 'shift_id'] = str(sorted_shifts.iloc[0]['shift_id'])
                linked_count += 1
    
    if linked_count > 0:
        print(f"💾 Saving {linked_count} updated cash entries...")
        # Use save_cash function
        from backend.core.db_adapter import save_cash
        save_cash(cash_df)
        print("✅ Save successful!")
    
    return True, f"Linked {linked_count} cash entries to shifts"


def refresh_shift_data(shift_id=None):
    """
    Refresh shift data by recalculating from sales and cash tables.
    """
    print("\n" + "=" * 70)
    print("   REFRESHING SHIFT DATA")
    print("=" * 70)
    
    shifts_df = load_shifts()
    
    if shifts_df.empty:
        print("❌ No shifts found")
        return False, "No shifts found"
    
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
                print(f"   📊 Sales: {transactions} transactions, Revenue: ${revenue:.2f}")
            
            # Calculate from cash
            if not shift_cash.empty and "type" in shift_cash.columns:
                cash_sales = to_float(shift_cash[shift_cash["type"] == "CASH_SALE"]["amount"].sum())
                credit_sales = to_float(shift_cash[shift_cash["type"] == "CREDIT_SALE"]["amount"].sum())
                debt_payments = to_float(shift_cash[shift_cash["type"] == "DEBT_PAYMENT"]["amount"].sum())
                expenses = to_float(shift_cash[shift_cash["type"] == "EXPENSE"]["amount"].sum())
            
            # Update shift data
            shifts_df.at[i, "total_revenue"] = revenue
            shifts_df.at[i, "profit"] = profit
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
            print(f"   ✅ Updated: Revenue=${revenue:.2f}, Profit=${profit:.2f}")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    # Save all changes
    if refreshed > 0:
        print(f"\n💾 Saving {refreshed} updated shifts...")
        from backend.core.db_adapter import save_shifts
        save_shifts(shifts_df)
        print("✅ Save successful!")
    else:
        print(f"\n⏭️  No shifts were updated (skipped: {skipped})")
    
    print("\n" + "=" * 70)
    print(f"✅ Refreshed {refreshed} shifts successfully")
    print("=" * 70)
    
    return True, f"Refreshed {refreshed} shifts"


def main():
    """Main menu for the linking tool"""
    print("\n" + "=" * 70)
    print("   SHIFT LINKING AND DATA REFRESH TOOL")
    print("=" * 70)
    print("\nThis tool will:")
    print("  1. Link existing sales to shifts")
    print("  2. Link existing cash entries to shifts")
    print("  3. Refresh shift data with real values")
    
    print("\n" + "-" * 70)
    print("OPTIONS:")
    print("  1. Run ALL steps (Link Sales + Link Cash + Refresh)")
    print("  2. Link Sales to Shifts only")
    print("  3. Link Cash Entries to Shifts only")
    print("  4. Refresh Shift Data only")
    print("  5. Verify Data (Check what's linked)")
    print("  6. Exit")
    print("-" * 70)
    
    while True:
        try:
            choice = input("\nSelect option (1-6): ").strip()
            
            if choice == "1":
                print("\n🚀 Running ALL steps...")
                
                # Step 1: Link sales
                success1, msg1 = link_sales_to_shifts()
                print(f"\n{msg1}")
                
                # Step 2: Link cash
                success2, msg2 = link_cash_to_shifts()
                print(f"\n{msg2}")
                
                # Step 3: Refresh shifts
                success3, msg3 = refresh_shift_data()
                print(f"\n{msg3}")
                
                if success1 and success2 and success3:
                    print("\n✅ All steps completed successfully!")
                    print("\n📌 Restart your Streamlit app to see the updated data.")
                break
                
            elif choice == "2":
                success, message = link_sales_to_shifts()
                print(f"\n{message}")
                break
                
            elif choice == "3":
                success, message = link_cash_to_shifts()
                print(f"\n{message}")
                break
                
            elif choice == "4":
                success, message = refresh_shift_data()
                print(f"\n{message}")
                break
                
            elif choice == "5":
                verify_data()
                break
                
            elif choice == "6":
                print("\n👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please enter 1-6.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            break


def verify_data():
    """Verify the data linking"""
    print("\n" + "=" * 70)
    print("   DATA VERIFICATION")
    print("=" * 70)
    
    shifts_df = load_shifts()
    sales_df = load_sales()
    cash_df = load_cash()
    
    print(f"\n📊 Shifts: {len(shifts_df)}")
    if not shifts_df.empty:
        active = shifts_df[shifts_df['status'] == 'OPEN']
        closed = shifts_df[shifts_df['status'] == 'CLOSED']
        print(f"   Active: {len(active)}")
        print(f"   Closed: {len(closed)}")
    
    print(f"\n📊 Sales: {len(sales_df)}")
    if not sales_df.empty and 'shift_id' in sales_df.columns:
        has_shift = sales_df['shift_id'].notna().sum()
        no_shift = len(sales_df) - has_shift
        print(f"   With shift_id: {has_shift}")
        print(f"   Without shift_id: {no_shift}")
        
        # Show sales by shift
        if has_shift > 0:
            print(f"\n📋 Sales by shift:")
            shift_counts = sales_df['shift_id'].value_counts().head(10)
            for shift_id, count in shift_counts.items():
                print(f"   {shift_id}: {count} sales")
    
    print(f"\n📊 Cash Entries: {len(cash_df)}")
    if not cash_df.empty and 'shift_id' in cash_df.columns:
        has_shift = cash_df['shift_id'].notna().sum()
        no_shift = len(cash_df) - has_shift
        print(f"   With shift_id: {has_shift}")
        print(f"   Without shift_id: {no_shift}")
    
    # Show revenue by shift
    if not sales_df.empty and 'shift_id' in sales_df.columns and 'final_total' in sales_df.columns:
        print(f"\n💰 Revenue by shift:")
        revenue_by_shift = sales_df.groupby('shift_id')['final_total'].sum().sort_values(ascending=False).head(10)
        for shift_id, revenue in revenue_by_shift.items():
            print(f"   {shift_id}: ${revenue:,.2f}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Check if shift ID was passed as command line argument
    if len(sys.argv) > 1:
        if sys.argv[1] == "--link-sales":
            success, message = link_sales_to_shifts()
            print(f"\n{message}")
        elif sys.argv[1] == "--link-cash":
            success, message = link_cash_to_shifts()
            print(f"\n{message}")
        elif sys.argv[1] == "--refresh":
            shift_id = sys.argv[2] if len(sys.argv) > 2 else None
            success, message = refresh_shift_data(shift_id)
            print(f"\n{message}")
        elif sys.argv[1] == "--verify":
            verify_data()
        else:
            print("Usage:")
            print("  python link_sales_to_shifts.py --link-sales")
            print("  python link_sales_to_shifts.py --link-cash")
            print("  python link_sales_to_shifts.py --refresh [shift_id]")
            print("  python link_sales_to_shifts.py --verify")
    else:
        # Run interactive menu
        main()