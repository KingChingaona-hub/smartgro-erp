from backend.modules.expenses import recover_from_backup, debug_expenses_file, load_expenses

# First, check what files exist
debug_expenses_file()

# Try to recover from backup
success, message = recover_from_backup()
print(message)

# Check if recovery worked
df = load_expenses()
print(f"Now have {len(df)} expense records")
if not df.empty:
    print(df)