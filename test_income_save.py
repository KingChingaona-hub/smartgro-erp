# test_income_save.py
from backend.core.db_adapter import record_income, load_income, get_total_income

print("=" * 60)
print("TESTING INCOME SAVE AFTER FIX")
print("=" * 60)

# Record a test income
print("\n1. Recording test income...")
success = record_income(
    income_source="Test After Fix",
    description="Test income after fixing ID column",
    amount=150.75,
    user="Admin"
)
print(f"   Success: {success}")

# Load and check
print("\n2. Loading income records...")
df = load_income()
print(f"   Total records: {len(df)}")

if not df.empty:
    print("\n3. Latest income records:")
    print(df.tail(5))
    
    total = get_total_income()
    print(f"\n4. Total income: ${total:,.2f}")
    
    # Show branch info
    if 'branch_id' in df.columns:
        branches = df['branch_id'].value_counts()
        print(f"\n5. Income by branch:")
        for branch, count in branches.items():
            print(f"   {branch}: {count} records")
else:
    print("   No records found!")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)