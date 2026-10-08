# backend/admin/branch_management.py

import streamlit as st
import pandas as pd
from datetime import datetime

from backend.core.db_adapter import (
    load_branches,
    save_branches,
    get_db_cursor,
)


# ==============================================================
# BRANCH-SCOPED TABLES
# These are the tables that carry a `branch_id` column. The
# deletion safety check inspects all of them.
# ==============================================================
BRANCH_SCOPED_TABLES = [
    "products",
    "sales",
    "customers",
    "customer_transactions",
    "debtors",
    "debtor_payments",
    "expenses",
    "income",
    "purchases",
    "cash_register",
    "shifts",
    "shift_definitions",
    "suppliers",
    "loyalty_points",
    "loyalty_redemptions",
    "expense_budget",
    "recurring_expenses",
    "petty_cash",
    "bank_deposits",
    "returns",
    "refunds",
]


# ==============================================================
# DATA HELPERS
# ==============================================================
def _branch_row_counts(branch_id):
    """
    Return a dict {table_name: row_count} for the given branch.
    Only tables that actually exist in the DB are included.
    """
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
                    # psycopg2 returns dict for RealDictCursor
                    count = row["c"] if isinstance(row, dict) else row[0]
                    counts[table] = int(count or 0)
                except Exception:
                    # Table doesn't exist or has no branch_id column — skip
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
    """Turn the counts dict into a tidy DataFrame for display."""
    if not counts:
        return pd.DataFrame(columns=["Table", "Rows"])
    rows = [{"Table": t, "Rows": c} for t, c in counts.items() if c > 0]
    if not rows:
        return pd.DataFrame(columns=["Table", "Rows"])
    return pd.DataFrame(rows).sort_values("Rows", ascending=False).reset_index(drop=True)


def _reassign_branch_data(source_branch_id, target_branch_id):
    """
    Move every row of every branch-scoped table from source to target.
    Runs in one transaction. Returns (success, message).
    """
    if source_branch_id == target_branch_id:
        return False, "Source and target branches must be different"

    moved = {}
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed"

            for table in BRANCH_SCOPED_TABLES:
                try:
                    cur.execute(
                        f"UPDATE {table} SET branch_id = %s WHERE branch_id = %s",
                        (target_branch_id, source_branch_id),
                    )
                    moved[table] = cur.rowcount or 0
                except Exception:
                    # Table doesn't exist or no branch_id column — skip
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue

            conn.commit()

        # Summarise what was moved
        parts = [f"{t}: {n}" for t, n in moved.items() if n > 0]
        if parts:
            msg = f"Reassigned {sum(moved.values())} rows to {target_branch_id}. " + ", ".join(parts)
        else:
            msg = f"No rows needed reassignment to {target_branch_id}."

        return True, msg
    except Exception as e:
        print(f"[branch_management] reassign error: {e}")
        return False, f"Error reassigning data: {str(e)}"


def _safe_delete_branch(branch_id, allow_orphan=False):
    """
    Delete a branch row from the branches table.
    If allow_orphan is False and the branch has data, deletion is refused.
    Returns (success, message).
    """
    if branch_id == "HO":
        return False, "Head Office cannot be deleted"

    counts = _branch_row_counts(branch_id)
    total = _total_rows(counts)

    if total > 0 and not allow_orphan:
        return False, (
            f"Branch {branch_id} still has {total} row(s) across "
            f"{len([c for c in counts.values() if c > 0])} table(s). "
            f"Reassign or clear them first, or use Reassign & Delete."
        )

    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed"

            cur.execute("DELETE FROM branches WHERE branch_id = %s", (branch_id,))
            conn.commit()

        return True, f"Branch {branch_id} deleted."
    except Exception as e:
        print(f"[branch_management] delete error: {e}")
        return False, f"Error deleting branch: {str(e)}"


# ==============================================================
# MAIN PAGE
# ==============================================================
def branch_management_page():
    """Branch Management Page — Add, Edit, Delete with safety checks."""

    st.title("Branch Management")
    st.caption("Manage your business branches — Add, Edit, or Delete branches")

    # Security check
    if st.session_state.get("role") != "owner":
        st.error("Access Denied. Only system owner can access branch management.")
        return

    # ==========================================================
    # SESSION STATE
    # ==========================================================
    for key, default in [
        ("bm_message", ""),
        ("bm_message_type", ""),
        ("bm_force_refresh", False),
        ("bm_branch_created", False),
        ("bm_branch_updated", False),
        ("bm_branch_deleted", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ==========================================================
    # LOAD BRANCHES
    # ==========================================================
    if st.session_state.bm_force_refresh:
        st.cache_data.clear()
        st.session_state.bm_force_refresh = False

    df = load_branches()

    required_columns = ["branch_id", "branch_name", "location", "level", "active"]
    for col in required_columns:
        if col not in df.columns:
            if col == "active":
                df[col] = True
            elif col == "level":
                df[col] = 1
            else:
                df[col] = ""

    save_branches(df)

    # ==========================================================
    # MESSAGES
    # ==========================================================
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
    # EXISTING BRANCHES (with data summary)
    # ==========================================================
    st.subheader("Existing Branches")

    if not df.empty:
        display_df = df.copy()
        display_df["active"] = display_df["active"].apply(lambda x: "Active" if x else "Inactive")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Branches", len(df))
        with col2:
            st.metric("Active Branches", len(df[df["active"] == "Active"]))
        with col3:
            st.metric("Total Levels", df["level"].nunique())
    else:
        st.info("No branches available. Add your first branch below.")

    st.markdown("---")

    # ==========================================================
    # DATA SUMMARY PER BRANCH
    # ==========================================================
    with st.expander("📊 Data summary per branch", expanded=False):
        st.caption(
            "Shows how many rows each branch has across all branch-scoped tables. "
            "A branch with zero rows can be deleted safely. A branch with rows "
            "must be reassigned before deletion."
        )
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
                    "Branch": br["branch_name"],
                    "Code": bid,
                    "Total rows": total,
                    "Busiest table": f"{busiest[0]} ({busiest[1]})" if busiest[0] else "—",
                })
            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("---")

    # ==========================================================
    # ADD BRANCH
    # ==========================================================
    st.subheader("Add New Branch")

    with st.form("add_branch_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            new_branch_id = st.text_input(
                "Branch Code *",
                placeholder="e.g., BR004 or HO",
                help="Unique branch identifier",
            )
            new_branch_name = st.text_input(
                "Branch Name *",
                placeholder="e.g., Harare City Centre",
            )
            new_location = st.text_input(
                "Location",
                placeholder="e.g., Harare, Bulawayo, Mutare",
            )

        with col2:
            new_level = st.selectbox(
                "Branch Level", [1, 2, 3, 4, 5, 6],
                help="1=Head Office, 2=National, 3=Provincial, 4=District, 5=Village, 6=Other",
            )
            new_active = st.checkbox("Active Branch", value=True)

        submitted = st.form_submit_button("Add Branch", type="primary", use_container_width=True)

        if submitted:
            if new_branch_id.strip() == "":
                st.session_state.bm_message = "Branch Code is required"
                st.session_state.bm_message_type = "error"
            elif new_branch_name.strip() == "":
                st.session_state.bm_message = "Branch Name is required"
                st.session_state.bm_message_type = "error"
            elif new_branch_id.upper() in df["branch_id"].astype(str).str.upper().tolist():
                st.session_state.bm_message = f"Branch Code '{new_branch_id.upper()}' already exists!"
                st.session_state.bm_message_type = "error"
            else:
                try:
                    new_branch = pd.DataFrame([{
                        "branch_id": new_branch_id.strip().upper(),
                        "branch_name": new_branch_name.strip(),
                        "location": new_location.strip(),
                        "level": new_level,
                        "active": new_active,
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
                    st.session_state.bm_message = f"Error adding branch: {str(e)}"
                    st.session_state.bm_message_type = "error"

    st.markdown("---")

    # ==========================================================
    # EDIT BRANCH
    # ==========================================================
    st.subheader("Update / Edit Branch")

    if df.empty:
        st.info("No branches available to update. Add a branch first.")
    else:
        branch_names = df["branch_name"].tolist()
        selected_branch_name = st.selectbox(
            "Select Branch to Update", branch_names, key="update_branch_select"
        )

        if selected_branch_name:
            row = df[df["branch_name"] == selected_branch_name].iloc[0]

            with st.form("update_branch_form"):
                col1, col2 = st.columns(2)

                with col1:
                    st.text_input("Branch Code", value=row["branch_id"], disabled=True,
                                  help="Branch code cannot be changed")
                    update_branch_name = st.text_input("Branch Name", value=row["branch_name"])
                    update_location = st.text_input("Location", value=row["location"])

                with col2:
                    update_level = st.selectbox(
                        "Level", [1, 2, 3, 4, 5, 6],
                        index=int(row["level"]) - 1 if int(row["level"]) <= 6 else 0,
                    )
                    update_active = st.checkbox("Active", value=bool(row["active"]))

                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    if st.form_submit_button("Save Changes", type="primary", use_container_width=True):
                        if not update_branch_name.strip():
                            st.session_state.bm_message = "Branch Name is required"
                            st.session_state.bm_message_type = "error"
                        else:
                            try:
                                current_df = load_branches()
                                idx = current_df[current_df["branch_name"] == selected_branch_name].index[0]
                                current_df.at[idx, "branch_name"] = update_branch_name
                                current_df.at[idx, "location"] = update_location
                                current_df.at[idx, "level"] = update_level
                                current_df.at[idx, "active"] = update_active

                                save_branches(current_df)

                                st.session_state.bm_message = f"Branch '{update_branch_name}' updated successfully!"
                                st.session_state.bm_message_type = "success"
                                st.session_state.bm_branch_updated = True
                                st.session_state.bm_force_refresh = True
                                st.rerun()
                            except Exception as e:
                                st.session_state.bm_message = f"Error updating branch: {str(e)}"
                                st.session_state.bm_message_type = "error"

                with col_btn2:
                    # DELETION IS NOT DONE HERE — see the dedicated section below
                    st.caption("To delete a branch, use the **Delete Branch** section below.")

    st.markdown("---")

    # ==========================================================
    # DELETE BRANCH  (with safety checks + reassign flow)
    # ==========================================================
    st.subheader("Delete Branch")
    st.caption(
        "A branch can only be deleted when it has no data. "
        "If it has data, you can either reassign it to another branch, "
        "or explicitly override and leave the data orphaned."
    )

    if df.empty or len(df) <= 1:
        st.info("Cannot delete the only remaining branch. Add another branch first.")
    else:
        deletable_branches = df[df["branch_id"].astype(str).str.upper() != "HO"]

        if deletable_branches.empty:
            st.info("No deletable branches (Head Office cannot be deleted).")
        else:
            branch_options = [
                f"{r['branch_name']} ({r['branch_id']})"
                for _, r in deletable_branches.iterrows()
            ]
            selected_delete_label = st.selectbox(
                "Select Branch to Delete", branch_options, key="delete_branch_select"
            )

            idx = branch_options.index(selected_delete_label)
            target_row = deletable_branches.iloc[idx]
            target_id = target_row["branch_id"]

            # -------- Show what would be affected --------
            st.markdown(f"### Data in **{target_row['branch_name']}** ({target_id})")
            counts = _branch_row_counts(target_id)
            total_rows = _total_rows(counts)

            if total_rows == 0:
                st.success("This branch has no data. It can be deleted safely.")
            else:
                st.warning(
                    f"This branch has **{total_rows}** row(s) across "
                    f"{len([c for c in counts.values() if c > 0])} table(s). "
                    f"Deleting it without reassigning will orphan these rows."
                )
                st.dataframe(
                    _format_counts_table(counts),
                    use_container_width=True,
                    hide_index=True,
                )

            st.markdown("---")

            # -------- Option 1: Reassign then delete --------
            if total_rows > 0:
                st.markdown("#### Option A — Reassign all data to another branch, then delete")

                other_branches = df[df["branch_id"] != target_id]
                reassign_options = [
                    f"{r['branch_name']} ({r['branch_id']})"
                    for _, r in other_branches.iterrows()
                ]
                reassign_label = st.selectbox(
                    "Reassign data to",
                    reassign_options,
                    key="reassign_target_select",
                )
                reassign_id = other_branches.iloc[reassign_options.index(reassign_label)]["branch_id"]

                st.info(
                    f"All rows in **{target_row['branch_name']}** will be moved to "
                    f"**{reassign_label}** and then the branch will be deleted. "
                    f"This cannot be undone."
                )

                confirm_reassign = st.checkbox(
                    "I understand the data will be moved and the branch will be deleted",
                    key="confirm_reassign",
                )

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
                                st.error(
                                    f"Data moved, but branch row could not be deleted: {msg2}"
                                )

                st.markdown("---")

            # -------- Option 2: Straight delete (only safe when empty) --------
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

            # -------- Option 3: Force delete (override, leaves orphans) --------
            if total_rows > 0:
                with st.expander("⚠️ Option B — Force delete (leave data orphaned)", expanded=False):
                    st.error(
                        "This will remove the branch row from the branches table. "
                        f"The {total_rows} orphaned rows remain in the database but will "
                        "no longer be reachable from any login. This is not recommended."
                    )
                    force_confirm = st.text_input(
                        f"Type the branch code **{target_id}** to confirm",
                        key="force_delete_confirm",
                    )
                    if st.button("Force Delete Branch", use_container_width=True, key="force_delete_btn"):
                        if force_confirm.strip().upper() != str(target_id).upper():
                            st.error("Confirmation text does not match the branch code.")
                        else:
                            ok, msg = _safe_delete_branch(target_id, allow_orphan=True)
                            if ok:
                                st.session_state.bm_message = (
                                    f"Branch {target_id} force-deleted. "
                                    f"{total_rows} rows remain orphaned in the database."
                                )
                                st.session_state.bm_message_type = "info"
                                st.session_state.bm_branch_deleted = True
                                st.session_state.bm_force_refresh = True
                                st.rerun()
                            else:
                                st.error(msg)

    st.markdown("---")

    # ==========================================================
    # REFRESH
    # ==========================================================
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.bm_force_refresh = True
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    branch_management_page()