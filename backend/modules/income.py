# backend/modules/income.py - FIXED with better data protection
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
import shutil
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================
# PATH
# ==============================
DATA_DIR = Path("data")
INCOME_FILE = DATA_DIR / "income.csv"
INCOME_BACKUP_FILE = DATA_DIR / "income_backup.csv"
INCOME_EMERGENCY_BACKUP = DATA_DIR / "income_emergency_backup.csv"


# ==============================
# INIT - FIXED TO NEVER OVERWRITE
# ==============================
def init_income():
    """Initialize income file only if it doesn't exist - NEVER OVERWRITE"""
    DATA_DIR.mkdir(exist_ok=True)

    # Only create income file if it doesn't exist
    if not INCOME_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "income_source",
            "description",
            "amount",
            "user"
        ])
        df.to_csv(INCOME_FILE, index=False)
        logger.info(f"Created new income file: {INCOME_FILE}")
    else:
        # Log that file exists but DO NOT modify it
        file_size = INCOME_FILE.stat().st_size
        logger.info(f"Income file already exists: {INCOME_FILE} ({file_size} bytes)")
        
        # If file exists but is empty, it might be corrupted
        if file_size == 0:
            logger.warning(f"Income file is empty ({file_size} bytes). Checking backup...")
            # Try to recover from backup
            if INCOME_BACKUP_FILE.exists() and INCOME_BACKUP_FILE.stat().st_size > 0:
                try:
                    shutil.copy2(INCOME_BACKUP_FILE, INCOME_FILE)
                    logger.info(f"Recovered income file from backup")
                except Exception as e:
                    logger.error(f"Failed to recover from backup: {e}")
            else:
                logger.warning("No backup available to recover")


# ==============================
# LOAD - FIXED TO PRESERVE DATA
# ==============================
def load_income():
    """Load income data - NEVER DELETES DATA"""
    init_income()

    try:
        if not INCOME_FILE.exists():
            logger.warning(f"Income file not found: {INCOME_FILE}")
            return pd.DataFrame(columns=[
                "date", "income_source", "description", "amount", "user"
            ])
        
        # Check if file is empty
        if INCOME_FILE.stat().st_size == 0:
            logger.warning("Income file is empty")
            return pd.DataFrame(columns=[
                "date", "income_source", "description", "amount", "user"
            ])
        
        # Read the file
        try:
            df = pd.read_csv(INCOME_FILE)
        except pd.errors.EmptyDataError:
            logger.warning("Income file is empty (EmptyDataError)")
            return pd.DataFrame(columns=[
                "date", "income_source", "description", "amount", "user"
            ])
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            # Try to read with different encoding
            try:
                df = pd.read_csv(INCOME_FILE, encoding='utf-8', engine='python')
            except:
                try:
                    df = pd.read_csv(INCOME_FILE, encoding='latin-1')
                except:
                    logger.error("Cannot read income file")
                    return pd.DataFrame(columns=[
                        "date", "income_source", "description", "amount", "user"
                    ])
        
        logger.info(f"Loaded {len(df)} income records from CSV")
        
        if df.empty:
            logger.info("Income file is empty")
            return df
        
        # Ensure required columns exist
        required_cols = ["date", "income_source", "description", "amount", "user"]
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"Missing column: {col}, adding with default values")
                df[col] = "" if col != "amount" else 0
        
        # Convert date to datetime - preserve original data
        if "date" in df.columns:
            # Try to convert, but don't drop invalid dates
            try:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            except Exception as e:
                logger.warning(f"Date conversion error: {e}")
                # Keep as is if conversion fails
                pass
            
            # Log how many invalid dates were found
            invalid_dates = df["date"].isna().sum() if "date" in df.columns else 0
            if invalid_dates > 0:
                logger.warning(f"Found {invalid_dates} rows with invalid dates, keeping them as NaT")
        
        # Convert amount to float - preserve original data
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        
        # Ensure string columns are strings
        for col in ["income_source", "description", "user"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
            else:
                df[col] = ""
        
        logger.info(f"Successfully loaded {len(df)} income records")
        if not df.empty:
            if "date" in df.columns:
                try:
                    logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")
                except:
                    pass
            logger.info(f"Total income: ${df['amount'].sum():,.2f}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading income: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=[
            "date", "income_source", "description", "amount", "user"
        ])


# ==============================
# SAVE - FIXED WITH MULTIPLE BACKUPS
# ==============================
def save_income(df):
    """Save income data with multiple backups - NEVER DELETES"""
    try:
        if df is None:
            logger.warning("Attempted to save None dataframe")
            return False
        
        # If df is empty, don't save - prevent data loss
        if df.empty:
            logger.warning("Attempted to save empty dataframe - skipping to prevent data loss")
            return False
        
        # Create multiple backups before saving
        if INCOME_FILE.exists() and INCOME_FILE.stat().st_size > 0:
            try:
                # Create a timestamped backup
                backup_filename = f"income_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                backup_path = DATA_DIR / backup_filename
                shutil.copy2(INCOME_FILE, backup_path)
                logger.info(f"Created timestamped backup: {backup_path}")
                
                # Keep the latest backup
                shutil.copy2(INCOME_FILE, INCOME_BACKUP_FILE)
                logger.info(f"Updated latest backup: {INCOME_BACKUP_FILE}")
                
                # Create emergency backup
                shutil.copy2(INCOME_FILE, INCOME_EMERGENCY_BACKUP)
                logger.info(f"Updated emergency backup: {INCOME_EMERGENCY_BACKUP}")
                
            except Exception as e:
                logger.warning(f"Could not create backups: {e}")
        
        # Ensure date is in string format for saving
        if "date" in df.columns and not df.empty:
            df = df.copy()
            # Convert datetime to string if needed
            if pd.api.types.is_datetime64_any_dtype(df["date"]):
                df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
            # For any NaT values, use current timestamp
            df["date"] = df["date"].fillna(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # Save to file
        df.to_csv(INCOME_FILE, index=False)
        logger.info(f"Saved {len(df)} income records to CSV")
        
        # Verify save was successful
        if INCOME_FILE.exists() and INCOME_FILE.stat().st_size > 0:
            logger.info(f"File size after save: {INCOME_FILE.stat().st_size} bytes")
            return True
        else:
            logger.error("File save failed - file is empty or missing")
            return False
            
    except Exception as e:
        logger.error(f"Error saving income: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==============================
# RECORD INCOME - FIXED
# ==============================
def record_income(income_source, description, amount, user="System"):
    """Record new income - APPENDS to existing data"""
    try:
        # Load existing income
        df = load_income()
        
        # If df is empty, create new dataframe with columns
        if df is None or df.empty:
            df = pd.DataFrame(columns=[
                "date", "income_source", "description", "amount", "user"
            ])

        try:
            amount_float = float(amount)
        except (ValueError, TypeError):
            amount_float = 0.0

        new_row = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "income_source": income_source,
            "description": description,
            "amount": amount_float,
            "user": user
        }

        # Append new row
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save with backup
        success = save_income(df)

        if success:
            logger.info(f"Income recorded: ${amount_float:.2f} - {description}")
            return True, f"Income recorded: ${amount_float:.2f} - {description}"
        else:
            return False, "Failed to save income"
            
    except Exception as e:
        logger.error(f"Error recording income: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Error: {str(e)}"


# ==============================
# DELETE INCOME - FIXED
# ==============================
def delete_income_by_id(date_str, income_source, amount, description=""):
    """Delete an income record by its unique combination of fields."""
    try:
        df = load_income()
        
        if df.empty:
            return False
        
        # Create backup before deletion
        if INCOME_FILE.exists() and INCOME_FILE.stat().st_size > 0:
            try:
                shutil.copy2(INCOME_FILE, INCOME_BACKUP_FILE)
                shutil.copy2(INCOME_FILE, INCOME_EMERGENCY_BACKUP)
                logger.info(f"Created backups before deletion")
            except Exception as e:
                logger.warning(f"Could not create backup: {e}")
        
        # Convert date string to match format in dataframe
        df["date_short"] = df["date"].str[:16]
        search_date = date_str[:16]
        
        # Find matching records
        mask = (
            (df["date_short"] == search_date) & 
            (df["income_source"] == income_source) & 
            (abs(df["amount"] - float(amount)) < 0.01)
        )
        
        if description:
            mask = mask & (df["description"].str.contains(description[:20], case=False, na=False))
        
        matching_indices = df[mask].index.tolist()
        
        if not matching_indices:
            # Try a more lenient match
            mask_lenient = (
                (df["date_short"] == search_date) & 
                (df["income_source"] == income_source) & 
                (abs(df["amount"] - float(amount)) < 0.01)
            )
            matching_indices = df[mask_lenient].index.tolist()
            
            if not matching_indices:
                logger.warning(f"No matching income record found for {search_date} - {income_source} - ${amount}")
                return False
        
        # Delete the first matching record
        df = df.drop(matching_indices[0])
        df = df.drop(columns=["date_short"], errors="ignore")
        df = df.reset_index(drop=True)
        save_income(df)
        
        logger.info(f"Deleted income: {date_str} - {income_source} - ${amount}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting income by ID: {e}")
        return False


# ==============================
# DELETE INCOME BY INDEX (Legacy)
# ==============================
def delete_income(index):
    """Delete an income record by index"""
    try:
        df = load_income()
        
        if index in df.index:
            # Create backup before deletion
            if INCOME_FILE.exists() and INCOME_FILE.stat().st_size > 0:
                try:
                    shutil.copy2(INCOME_FILE, INCOME_BACKUP_FILE)
                except:
                    pass
            
            record = df.loc[index]
            logger.info(f"Deleting income: {record['date']} - {record['income_source']} - ${record['amount']}")
            
            df = df.drop(index)
            df = df.reset_index(drop=True)
            save_income(df)
            return True
        else:
            logger.warning(f"Index {index} not found in income dataframe")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting income: {e}")
        return False


# ==============================
# MONTHLY TOTAL
# ==============================
def get_monthly_income(month=None):
    """Get total income for a specific month"""
    df = load_income()

    if df.empty:
        return 0

    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

        if month:
            df = df[df["date"].dt.strftime("%Y-%m") == month]
        else:
            current_month = datetime.now().strftime("%Y-%m")
            df = df[df["date"].dt.strftime("%Y-%m") == current_month]

        return df["amount"].sum()
    except Exception as e:
        logger.error(f"Error calculating monthly income: {e}")
        return 0


# ==============================
# GET INCOME BY SOURCE
# ==============================
def get_income_by_source(month=None):
    """Get income grouped by source"""
    df = load_income()
    
    if df.empty:
        return pd.DataFrame()
    
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        
        if month:
            df = df[df["date"].dt.strftime("%Y-%m") == month]
        else:
            current_month = datetime.now().strftime("%Y-%m")
            df = df[df["date"].dt.strftime("%Y-%m") == current_month]
        
        if df.empty:
            return pd.DataFrame()
        
        source_summary = df.groupby("income_source")["amount"].sum().reset_index()
        source_summary = source_summary.sort_values("amount", ascending=False)
        
        return source_summary
    except Exception as e:
        logger.error(f"Error getting income by source: {e}")
        return pd.DataFrame()


# ==============================
# GET INCOME TREND
# ==============================
def get_income_trend(months=12):
    """Get monthly income trend"""
    df = load_income()
    
    if df.empty:
        return pd.DataFrame()
    
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        
        if df.empty:
            return pd.DataFrame()
        
        df["month"] = df["date"].dt.strftime("%Y-%m")
        
        monthly_trend = df.groupby("month")["amount"].sum().reset_index()
        monthly_trend = monthly_trend.sort_values("month").tail(months)
        monthly_trend.columns = ["Month", "Total Income"]
        
        return monthly_trend
    except Exception as e:
        logger.error(f"Error getting income trend: {e}")
        return pd.DataFrame()


# ==============================
# GET TOTAL INCOME
# ==============================
def get_total_income():
    """Get total income all time"""
    df = load_income()
    return df["amount"].sum() if not df.empty else 0


# ==============================
# RECOVER INCOME FROM BACKUP
# ==============================
def recover_from_backup():
    """Recover income from backup file"""
    # Try emergency backup first
    if INCOME_EMERGENCY_BACKUP.exists() and INCOME_EMERGENCY_BACKUP.stat().st_size > 0:
        try:
            df = pd.read_csv(INCOME_EMERGENCY_BACKUP)
            if not df.empty:
                save_income(df)
                logger.info(f"Recovered {len(df)} income records from emergency backup")
                return True, f"Recovered {len(df)} income records from emergency backup"
        except Exception as e:
            logger.error(f"Emergency backup recovery failed: {e}")
    
    # Try regular backup
    if INCOME_BACKUP_FILE.exists() and INCOME_BACKUP_FILE.stat().st_size > 0:
        try:
            df = pd.read_csv(INCOME_BACKUP_FILE)
            if not df.empty:
                save_income(df)
                logger.info(f"Recovered {len(df)} income records from backup")
                return True, f"Recovered {len(df)} income records from backup"
        except Exception as e:
            logger.error(f"Backup recovery failed: {e}")
    
    return False, "No backup available"


# ==============================
# DEBUG FUNCTION
# ==============================
def debug_income_file():
    """Debug function to check income file contents"""
    try:
        if INCOME_FILE.exists():
            file_size = INCOME_FILE.stat().st_size
            print(f"File exists: {INCOME_FILE}")
            print(f"File size: {file_size} bytes")
            
            if file_size == 0:
                print("File is empty!")
                # Check if backup exists
                if INCOME_BACKUP_FILE.exists() and INCOME_BACKUP_FILE.stat().st_size > 0:
                    print(f"Backup exists with size: {INCOME_BACKUP_FILE.stat().st_size} bytes")
                return
            
            with open(INCOME_FILE, 'r') as f:
                lines = f.readlines()
                print(f"Number of lines: {len(lines)}")
                if len(lines) > 1:
                    print("Header:", lines[0].strip())
                    print("First data row:", lines[1].strip())
                    print(f"Total data rows: {len(lines) - 1}")
                    if len(lines) > 2:
                        print("Last data row:", lines[-1].strip())
                else:
                    print("File has only header or is empty")
        else:
            print(f"File does not exist: {INCOME_FILE}")
            
        # Check backups
        if INCOME_BACKUP_FILE.exists():
            backup_size = INCOME_BACKUP_FILE.stat().st_size
            print(f"\nBackup file exists: {INCOME_BACKUP_FILE}")
            print(f"Backup size: {backup_size} bytes")
        
        if INCOME_EMERGENCY_BACKUP.exists():
            emergency_size = INCOME_EMERGENCY_BACKUP.stat().st_size
            print(f"\nEmergency backup exists: {INCOME_EMERGENCY_BACKUP}")
            print(f"Emergency backup size: {emergency_size} bytes")
            
    except Exception as e:
        print(f"Debug error: {e}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    debug_income_file()
    
    df = load_income()
    print(f"\nLoaded {len(df)} income records")
    if not df.empty:
        print("Sample records:")
        print(df.head(5))
        print(f"\nTotal income: ${df['amount'].sum():,.2f}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")