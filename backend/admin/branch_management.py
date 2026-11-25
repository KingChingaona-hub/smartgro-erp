# backend/admin/branch_management.py
# UPDATED: Added Package Tiers, Dynamic Branch Passwords, Code Editing, and Auto-Deactivation of Users.

import streamlit as st
import pandas as pd
from datetime import datetime

from backend.core.db_adapter import (
    load_branches,
    save_branches,
    get_db_cursor,
    load_users,      # ADDED: Needed to deactivate users
    save_users       # ADDED: Needed to save user changes
)

# ==============================================================
# BRANCH-SCOPED TABLES
# ==============================================================
BRANCH_SCOPED_TABLES = [
    "products", "sales", "customers", "customer_transactions",
    "debtors", "debtor_payments", "expenses", "income", "purchases",
    "cash_register", "shifts", "shift_definitions", "suppliers",
    "loyalty_points", "loyalty_redemptions", "expense_budget",
    "recurring_expenses", "petty_cash", "bank_deposits", "returns", "refunds",
]

# ==============================================================
# DATA HELPERS
# ==============================================================
def _branch_row_counts(branch_id):
    counts = {}
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return counts
            for table in BRANCH_SCOPED_TABLES:
                try:
                    cur.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE branch_id = %s", (branch_id,))
                    row = cur.fetchone()
                    if row is None:
                        continue
                    count = row["c"] if isinstance(row, dict) else row[0]
                    counts[table] = int(count or 0)
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue
    except Exception as e:
        print(f"[branch_management] row count error: {e}")
    return counts

def _total_rows(counts):
    return sum(counts.values())

def _format_counts_table(counts):
    if not counts:
        return pd.DataFrame(columns=["Table", "Rows"])
    rows = [{"Table": t, "Rows": c} for t, c in counts.items() if c > 0]
    if not rows:
        return pd.DataFrame(columns=["Table", "Rows"])
    return pd.DataFrame(rows).sort_values("Rows", ascending=False).reset_index(drop=True)

def _reassign_branch_data(source_branch_id, target_branch_id):
    if source_branch_id == target_branch_id:
        return False, "Source and target branches must be different"

    moved = {}
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed"
            for table in BRANCH_SCOPED_TABLES:
                try:
                    cur.execute(f"UPDATE {table} SET branch_id = %s WHERE branch_id = %s", (target_branch_id, source_branch_id))
                    moved[table] = cur.rowcount or 0
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue
            conn.commit()
        parts = [f"{t}: {n}" for t, n in moved.items() if n > 0]
        msg = f"Reassigned {sum(moved.values())} rows to {target_branch_id}. " + ", ".join(parts) if parts else f"No rows needed reassignment to {target_branch_id}."
        return True, msg
    except Exception as e:
        return False, f"Error reassigning data: {str(e)}"

def _safe_delete_branch(branch_id, allow_orphan=False):
    if branch_id == "HO":
        return False, "Head Office cannot be deleted"
    counts = _branch_row_counts(branch_id)
    total = _total_rows(counts)
    if total > 0 and not allow_orphan:
        return False, f"Branch {branch_id} still has {total} row(s). Reassign or clear them first."
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed"
            cur.execute("DELETE FROM branches WHERE branch_id = %s", (branch_id,))
            conn.commit()
        return True, f"Branch {branch_id} deleted."
    except Exception as e:
        return False, f"Error deleting branch: {str(e)}"

# ==============================================================
# MAIN PAGE
# ==============================================================
def branch_management_page():
    st.title("Branch Management & Subscriptions")
    st.caption("Manage branches, packages, logins, and system access")

    if st.session_state.get("role") != "owner":
        st.error("Access Denied. Only system owner can access branch management.")
        return

    for key, default in [
        ("bm_message", ""), ("bm_message_type", ""), ("bm_force_refresh", False),
        ("bm_branch_created", False), ("bm_branch_updated", False), ("bm_branch_deleted", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    if st.session_state.bm_force_refresh:
        st.cache_data.clear()
        st.session_state.bm_force_refresh = False

    df = load_branches()

    # ADDED: Ensure new columns exist for backward compatibility
    required_columns = ["branch_id", "branch_name", "location", "level", "active", "package", "status", "branch_password"]
    for col in required_columns:
        if col not in df.columns:
            if col == "active":
                df[col] = True
            elif col == "level":
                df[col] = 1
            elif col == "package":
                df[col] = "Bronze"
            elif col == "status":
                df[col] = "Active"
            elif col == "branch_password":
                df[col] = "admin123" # Default password for existing branches
            else:
                df[col] = ""

    save_branches(df)

    if st.session_state.bm_message:
        if st.session_state.bm_message_type == "success":
            st.success(st.session_state.bm_message)
            if st.session_state.bm_branch_created:
                st.balloons()
                st.session_state.bm_branch_created = False
        elif st.session_state.bm_message_type == "error":
            st.error(st.session_state.bm_message)
        else:
            st.info(st.session_state.bm_message)
        st.session_state.bm_message = ""
        st.session_state.bm_message_type = ""

    # ==========================================================
    # EXISTING BRANCHES
    # ==========================================================
    st.subheader("Existing Branches")
    if not df.empty:
        display_df = df.copy()
        display_df["active"] = display_df["active"].apply(lambda x: "Yes" if x else "No")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Branches", len(df))
        with col2:
            st.metric("Active Branches", len(df[df["status"] == "Active"]))
        with col3:
            st.metric("Terminated", len(df[df["status"] == "Terminated"]))
        with col4:
            st.metric("Total Levels", df["level"].nunique())
    else:
        st.info("No branches available. Add your first branch below.")

    st.markdown("---")

    # ==========================================================
    # DATA SUMMARY PER BRANCH
    # ==========================================================
    with st.expander("📊 Data summary per branch", expanded=False):
        if df.empty:
            st.info("No branches to summarise.")
        else:
            summary_rows = []
            for _, br in df.iterrows():
                bid = br["branch_id"]
                counts = _branch_row_counts(bid)
                total = _total_rows(counts)
                busiest = max(counts.items(), key=lambda kv: kv[1]) if counts else (None, 0)
                summary_rows.append({
                    "Branch": br["branch_name"], "Code": bid, "Total rows": total,
                    "Busiest table": f"{busiest[0]} ({busiest[1]})" if busiest[0] else "—",
                })
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ==========================================================
    # ADD BRANCH
    # ==========================================================
    st.subheader("Add New Branch")

    with st.form("add_branch_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_branch_id = st.text_input("Branch Code *", placeholder="e.g., BR004")
            new_branch_name = st.text_input("Branch Name *", placeholder="e.g., Harare City Centre")
            new_location = st.text_input("Location", placeholder="e.g., Harare")
            new_branch_password = st.text_input("Branch Login Password *", type="password", value="admin123")

        with col2:
            new_level = st.selectbox("Branch Level", [1, 2, 3, 4, 5, 6], help="1=Head Office, 2=National, etc.")
            new_package = st.selectbox("Subscription Package", ["Bronze", "Silver", "Gold", "Platinum"])
            new_active = st.checkbox("Active Branch", value=True)
            new_status = st.selectbox("Subscription Status", ["Active", "Terminated"], index=0)

        submitted = st.form_submit_button("Add Branch", type="primary", use_container_width=True)
        if submitted:
            if not new_branch_id.strip(): st.error("Branch Code is required")
            elif not new_branch_name.strip(): st.error("Branch Name is required")
            elif new_branch_id.upper() in df["branch_id"].astype(str).str.upper().tolist():
                st.error(f"Branch Code '{new_branch_id.upper()}' already exists!")
            else:
                try:
                    new_branch = pd.DataFrame([{
                        "branch_id": new_branch_id.strip().upper(),
                        "branch_name": new_branch_name.strip(),
                        "location": new_location.strip(),
                        "level": new_level,
                        "active": new_active,
                        "package": new_package,
                        "status": new_status,
                        "branch_password": new_branch_password
                    }])
                    current_df = load_branches()
                    updated_df = pd.concat([current_df, new_branch], ignore_index=True)
                    save_branches(updated_df)

                    st.session_state.bm_message = f"Branch '{new_branch_name}' added successfully!"
                    st.session_state.bm_message_type = "success"
                    st.session_state.bm_branch_created = True
                    st.session_state.bm_force_refresh = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding branch: {str(e)}")

    st.markdown("---")

    # ==========================================================
    # EDIT BRANCH (Updated with Package & Status logic)
    # ==========================================================
    st.subheader("Update / Edit Branch")

    if df.empty:
        st.info("No branches available to update.")
    else:
        branch_names = df["branch_name"].tolist()
        selected_branch_name = st.selectbox("Select Branch to Update", branch_names, key="update_branch_select")

        if selected_branch_name:
            row = df[df["branch_name"] == selected_branch_name].iloc[0]
            original_branch_id = row["branch_id"]

            with st.form("update_branch_form"):
                col1, col2 = st.columns(2)
                with col1:
                    update_branch_id = st.text_input("Branch Code (Editable)", value=row["branch_id"])
                    update_branch_name = st.text_input("Branch Name", value=row["branch_name"])
                    update_location = st.text_input("Location", value=row["location"])
                    update_password = st.text_input("Branch Login Password", value=row.get("branch_password", "admin123"))

                with col2:
                    update_level = st.selectbox("Level", [1, 2, 3, 4, 5, 6], index=int(row["level"]) - 1 if int(row["level"]) <= 6 else 0)
                    update_package = st.selectbox("Subscription Package", ["Bronze", "Silver", "Gold", "Platinum"], index=["Bronze", "Silver", "Gold", "Platinum"].index(row.get("package", "Bronze")))
                    update_status = st.selectbox("Subscription Status", ["Active", "Terminated"], index=["Active", "Terminated"].index(row.get("status", "Active")))
                    update_active = st.checkbox("System Active", value=bool(row["active"]))

                if st.form_submit_button("Save Changes", type="primary", use_container_width=True):
                    if not update_branch_name.strip():
                        st.error("Branch Name is required")
                    else:
                        try:
                            current_df = load_branches()
                            idx = current_df[current_df["branch_name"] == selected_branch_name].index[0]
                            
                            # 1. Update Branch Data
                            current_df.at[idx, "branch_id"] = update_branch_id.strip().upper()
                            current_df.at[idx, "branch_name"] = update_branch_name
                            current_df.at[idx, "location"] = update_location
                            current_df.at[idx, "level"] = update_level
                            current_df.at[idx, "active"] = update_active
                            current_df.at[idx, "package"] = update_package
                            current_df.at[idx, "status"] = update_status
                            current_df.at[idx, "branch_password"] = update_password
                            
                            save_branches(current_df)

                            # 2. If Branch Code changed, update Users table
                            if original_branch_id != update_branch_id.strip().upper():
                                users_df = load_users()
                                if not users_df.empty and "branch_id" in users_df.columns:
                                    users_df.loc[users_df["branch_id"] == original_branch_id, "branch_id"] = update_branch_id.strip().upper()
                                    save_users(users_df)

                            # 3. Handle Status Change (Terminate / Activate)
                            if row.get("status") != update_status:
                                users_df = load_users()
                                if not users_df.empty and "branch_id" in users_df.columns:
                                    branch_users = users_df["branch_id"].astype(str).str.upper() == update_branch_id.strip().upper()
                                    if update_status == "Terminated":
                                        users_df.loc[branch_users, "active"] = False
                                        st.warning(f"Branch Terminated. All users for {update_branch_id} have been deactivated.")
                                    else:
                                        users_df.loc[branch_users, "active"] = True
                                        st.success(f"Branch Activated. All users for {update_branch_id} have been reactivated.")
                                    save_users(users_df)

                            st.session_state.bm_message = f"Branch '{update_branch_name}' updated successfully!"
                            st.session_state.bm_message_type = "success"
                            st.session_state.bm_branch_updated = True
                            st.session_state.bm_force_refresh = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating branch: {str(e)}")

    st.markdown("---")

    # ==========================================================
    # DELETE BRANCH
    # ==========================================================
    st.subheader("Delete Branch")
    if df.empty or len(df) <= 1:
        st.info("Cannot delete the only remaining branch.")
    else:
        deletable_branches = df[df["branch_id"].astype(str).str.upper() != "HO"]
        if deletable_branches.empty:
            st.info("No deletable branches (Head Office cannot be deleted).")
        else:
            branch_options = [f"{r['branch_name']} ({r['branch_id']})" for _, r in deletable_branches.iterrows()]
            selected_delete_label = st.selectbox("Select Branch to Delete", branch_options, key="delete_branch_select")

            idx = branch_options.index(selected_delete_label)
            target_row = deletable_branches.iloc[idx]
            target_id = target_row["branch_id"]

            st.markdown(f"### Data in **{target_row['branch_name']}** ({target_id})")
            counts = _branch_row_counts(target_id)
            total_rows = _total_rows(counts)

            if total_rows == 0:
                st.success("This branch has no data. It can be deleted safely.")
            else:
                st.warning(f"This branch has **{total_rows}** row(s). Deleting it without reassigning will orphan these rows.")
                st.dataframe(_format_counts_table(counts), use_container_width=True, hide_index=True)

            st.markdown("---")

            if total_rows > 0:
                st.markdown("#### Option A — Reassign all data to another branch, then delete")
                other_branches = df[df["branch_id"] != target_id]
                reassign_options = [f"{r['branch_name']} ({r['branch_id']})" for _, r in other_branches.iterrows()]
                reassign_label = st.selectbox("Reassign data to", reassign_options, key="reassign_target_select")
                reassign_id = other_branches.iloc[reassign_options.index(reassign_label)]["branch_id"]

                confirm_reassign = st.checkbox("I understand the data will be moved and the branch will be deleted", key="confirm_reassign")
                if st.button("Reassign & Delete Branch", use_container_width=True, key="reassign_delete_btn"):
                    if not confirm_reassign:
                        st.error("Please tick the confirmation checkbox.")
                    else:
                        ok, msg = _reassign_branch_data(target_id, reassign_id)
                        if not ok:
                            st.error(msg)
                        else:
                            st.success(msg)
                            ok2, msg2 = _safe_delete_branch(target_id, allow_orphan=False)
                            if ok2:
                                st.session_state.bm_message = f"Branch '{target_row['branch_name']}' deleted after reassignment."
                                st.session_state.bm_message_type = "success"
                                st.session_state.bm_branch_deleted = True
                                st.session_state.bm_force_refresh = True
                                st.rerun()
                            else:
                                st.error(f"Data moved, but branch row could not be deleted: {msg2}")
                st.markdown("---")

            if total_rows == 0:
                st.markdown("#### Delete this empty branch")
                if st.button("Delete Branch", use_container_width=True, key="delete_empty_branch_btn"):
                    ok, msg = _safe_delete_branch(target_id, allow_orphan=False)
                    if ok:
                        st.session_state.bm_message = msg
                        st.session_state.bm_message_type = "success"
                        st.session_state.bm_branch_deleted = True
                        st.session_state.bm_force_refresh = True
                        st.rerun()
                    else:
                        st.error(msg)

            if total_rows > 0:
                with st.expander("⚠️ Option B — Force delete (leave data orphaned)", expanded=False):
                    st.error("This will remove the branch row. Orphaned rows remain in the database but will no longer be reachable.")
                    force_confirm = st.text_input(f"Type the branch code **{target_id}** to confirm", key="force_delete_confirm")
                    if st.button("Force Delete Branch", use_container_width=True, key="force_delete_btn"):
                        if force_confirm.strip().upper() != str(target_id).upper():
                            st.error("Confirmation text does not match the branch code.")
                        else:
                            ok, msg = _safe_delete_branch(target_id, allow_orphan=True)
                            if ok:
                                st.session_state.bm_message = f"Branch {target_id} force-deleted. {total_rows} rows remain orphaned."
                                st.session_state.bm_message_type = "info"
                                st.session_state.bm_branch_deleted = True
                                st.session_state.bm_force_refresh = True
                                st.rerun()
                            else:
                                st.error(msg)

    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.bm_force_refresh = True
        st.rerun()

if __name__ == "__main__":
    branch_management_page()