# backend/scripts/remove_duplicate_products.py - Updated with branch handling

def remove_duplicates_from_database_by_name(dry_run=False):
    """
    Remove duplicate products from Neon database by NAME
    """
    try:
        # Load products from database
        df = load_products()
        
        if df.empty:
            return False, "No products found in database.", None
        
        original_count = len(df)
        print(f"Total products in database: {original_count}")
        
        # Check for branch_id - if it exists, keep it
        branch_col = None
        if "branch_id" in df.columns:
            branch_col = "branch_id"
            print(f"Branch column found: {branch_col}")
            # Get current branch from session state or use default
            from backend.core.db_adapter import get_current_branch
            current_branch = get_current_branch()
            print(f"Current branch: {current_branch}")
            # Filter to current branch if needed
            df_branch = df[df[branch_col] == current_branch]
            print(f"Products for current branch: {len(df_branch)}")
        else:
            df_branch = df
        
        if df_branch.empty:
            return False, f"No products found for branch: {current_branch}", None
        
        # Check for name column
        if "name" not in df_branch.columns:
            return False, "No 'name' column found in products table!", None
        
        # Create a normalized name column for comparison (lowercase, stripped)
        df_branch["name_normalized"] = df_branch["name"].str.lower().str.strip()
        
        # Find duplicates by normalized name
        duplicate_names = df_branch[df_branch["name_normalized"].duplicated(keep=False)]["name_normalized"].unique()
        print(f"Duplicate names found: {len(duplicate_names)}")
        
        if len(duplicate_names) == 0:
            return True, "No duplicates found!", df_branch
        
        # Show duplicates before removal
        print("\nDuplicate products found:")
        for name in duplicate_names:
            dup_rows = df_branch[df_branch["name_normalized"] == name]
            print(f"  '{name}': {len(dup_rows)} duplicates")
            for idx, row in dup_rows.iterrows():
                print(f"    - Index: {idx}, Name: {row['name']}, Barcode: {row.get('barcode', 'N/A')}, Stock: {row.get('stock', 0)}")
        
        if dry_run:
            return True, f"DRY RUN: Would remove {len(duplicate_names)} duplicate groups.", df_branch
        
        # Remove duplicates - KEEP FIRST OCCURRENCE based on name
        df_clean = df_branch.drop_duplicates(subset=["name_normalized"], keep="first")
        new_count = len(df_clean)
        removed_count = len(df_branch) - new_count
        
        print(f"New rows after removal: {new_count}")
        print(f"Removed rows: {removed_count}")
        
        # Remove the temporary normalized column before saving
        df_clean = df_clean.drop(columns=["name_normalized"])
        
        # Reset index to ensure clean save
        df_clean = df_clean.reset_index(drop=True)
        
        # Debug: Show what we're about to save
        print(f"\nSaving {len(df_clean)} products to database...")
        print(f"Columns being saved: {df_clean.columns.tolist()}")
        
        # Save to database
        save_success = save_products(df_clean, current_branch)
        
        if save_success:
            # Verify by reloading
            df_verify = load_products()
            verify_count = len(df_verify)
            print(f"Verification - products in database after save: {verify_count}")
            
            if verify_count == new_count:
                return True, f"Successfully removed {removed_count} duplicate products by name. {new_count} products remain.", df_clean
            else:
                return False, f"Save appeared successful but count mismatch. Expected {new_count}, got {verify_count}", None
        else:
            return False, "Failed to save cleaned products to database!", None
            
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return False, f"Error: {str(e)}", None