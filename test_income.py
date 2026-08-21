# test_income.py
from backend.core.db_adapter import record_income, load_income, get_total_income
import pandas as pd

print("=" * 60)
print("TESTING INCOME RECORDING")
print("=" * 60)

# Test recording
print("\n1. Recording test income...")
success = record_income(
    income_source="Test Income",
    description="Test description",
    amount=100.50,
    user="Test User"
)
print(f"  Success: {success}")

# Load and check
print("\n2. Loading income records...")
df = load_income()
print(f"  Total records: {len(df)}")

if not df.empty:
    print("\n3. Latest records:")
    print(df.tail(5))
    
    total = get_total_income()
    print(f"\n4. Total income: ${total:,.2f}")
else:
    print("  No records found!")

print("\n" + "=" * 60)