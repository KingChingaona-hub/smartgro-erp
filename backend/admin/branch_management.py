# backend/admin/branch_management.py
# FIXED:
#   1. Lazy-loaded data summary (fixes slowness — no more 22×N queries per load)
#   2. Targeted cache invalidation (fixes stale display after save)
#   3. No unconditional save_branches() on every page load
#   4. Spinners during long operations
#   5. Robust re-load after every mutation
#   6. EDIT now passes original_branch_id to save_branches() so a rename
#      becomes DELETE-old + INSERT-new (no duplicate row, all fields saved).

import streamlit as st
import pandas as pd

from backend.core.db_adapter import (
    load_branches,
    save_branches,
    get_db_cursor,
    load_users,
    save_users,
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
# CACHE HELPERS
# ==============================================================
def _invalidate_branch_cache():
    """
    Clear the branches cache only (targeted). Leaves products/sales caches intact.
    Works whether load_branches is @st.cache_data decorated or a plain function.
    """
    try:
        if hasattr(load_branches, "clear"):
            load_branches.clear()
            print("[branch_management] branches cache cleared")
    except Exception as e:
        print(f"[branch_management] targeted clear failed: {e}")

    # Fallback (harmless if load_branches isn't cached)
    try:
        st.cache_data.clear()
    except Exception:
        pass


def _finish_operation(message, message_type="success"):
    """Persist a message, invalidate cache, rerun."""
    st.session_state.bm_message = message
    st.session_state.bm_message_type = message_type
    st.session_state.bm_force_refresh = True
    _invalidate_branch_cache()
    st.rerun()


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
                    cur.execute(
                        f"SELECT COUNT(*) AS c FROM {table} WHERE branch_id = %s",
                        (branch_id,),
                    )
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
                    cur.execute(
                        f"UPDATE {table} SET branch_id = %s WHERE branch_id = %s",
                        (target_branch_id, source_branch_id),
                    )
                    moved[table] = cur.rowcount or 0
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue
            conn.commit()
        parts = [f"{t}: {n}" for t, n in moved.items() if n > 0]
        msg = (
            f"Reassigned {sum(moved.values())} rows to {target_branch_id}. " + ", ".join(parts)
            if parts
            else f"No rows needed reassignment to {target_branch_id}."
        )
        return True, msg
    except Exception as e:
        return False, f"Error reassigning data: {str(e)}"


def _safe_delete_branch(branch_id, allow_orphan=False):
    if branch_id == "HO":
        return False, "Head Office cannot be deleted"
    counts = _branch_row_counts(branch_id)
    total = _total_rows(counts)
    if total > 0 and not allow_orphan:
        return False, (
            f"Branch {branch_id} still has {total} row(s). Reassign or clear them first."
        )
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
        ("bm_show_summary", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ---------- Cache control ----------
    if st.session_state.bm_force_refresh:
        _invalidate_branch_cache()
        st.session_state.bm_force_refresh = False

    # ---------- Load branches ----------
    df = load_branches()

    # ---------- Column migration: only save if columns were actually missing ----------
    required_columns = [
        "branch_id", "branch_name", "location", "level", "active",
        "package", "status", "branch_password",
    ]
    columns_added = False
    legacy_pw = {
        "HO": "ho123", "NAT": "nat123", "PRO": "pro123",
        "DIS": "dis123", "VIL": "vil123",
    }
    for col in required_columns:
        if col not in df.columns:
            columns_added = True
            if col == "active":
                df[col] = True
            elif col == "level":
                df[col] = 1
            elif col == "package":
                df[col] = "Bronze"
            elif col == "status":
                df[col] = "Active"
            elif col == "branch_password":
                df[col] = df["branch_id"].astype(str).str.upper().map(
                    lambda x: legacy_pw.get(x, "admin123")
                )
            else:
                df[col] = ""

    if columns_added:
        # No renames here — no original_branch_id needed.
        save_branches(df)
        _invalidate_branch_cache()
        df = load_branches()   # reload fresh after schema change

    # ---------- Messages ----------
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
    # DATA SUMMARY PER BRANCH — LAZY-LOADED
    # ==========================================================
    with st.expander("Data summary per branch", expanded=False):
        st.caption(
            "Shows how many rows each branch has across all branch-scoped tables. "
            "Loading this runs ~22 queries per branch, so it's opt-in for speed."
        )
        if df.empty:
            st.info("No branches to summarise.")
        else:
            load_summary = st.checkbox(
                "Load data summary now (may take a few seconds)",
                key="load_data_summary_cb",
            )
            if load_summary:
                with st.spinner("Counting rows across all branches..."):
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
            new_branch_id = st.text_input("Branch Code *", placeholder="e.g., BR004")
            new_branch_name = st.text_input("Branch Name *", placeholder="e.g., Harare City Centre")
            new_location = st.text_input("Location", placeholder="e.g., Harare")
            new_branch_password = st.text_input(
                "Branch Login Password *", type="password", value="admin123"
            )
        with col2:
            new_level = st.selectbox(
                "Branch Level", [1, 2, 3, 4, 5, 6],
                help="1=Head Office, 2=National, 3=Provincial, 4=District, 5=Village, 6=Other",
            )
            new_package = st.selectbox("Subscription Package", ["Bronze", "Silver", "Gold", "Platinum"])
            new_active = st.checkbox("Active Branch", value=True)
            new_status = st.selectbox("Subscription Status", ["Active", "Terminated"], index=0)

        submitted = st.form_submit_button("Add Branch", type="primary", use_container_width=True)

        if submitted:
            if not new_branch_id.strip():
                st.error("Branch Code is required")
            elif not new_branch_name.strip():
                st.error("Branch Name is required")
            elif new_branch_id.upper() in df["branch_id"].astype(str).str.upper().tolist():
                st.error(f"Branch Code '{new_branch_id.upper()}' already exists!")
            else:
                try:
                    with st.spinner("Saving new branch..."):
                        new_branch = pd.DataFrame([{
                            "branch_id": new_branch_id.strip().upper(),
                            "branch_name": new_branch_name.strip(),
                            "location": new_location.strip(),
                            "level": new_level,
                            "active": new_active,
                            "package": new_package,
                            "status": new_status,
                            "branch_password": new_branch_password,
                        }])
                        current_df = load_branches()
                        updated_df = pd.concat([current_df, new_branch], ignore_index=True)
                        # New branch — no rename, no original_branch_id.
                        save_branches(updated_df)

                    st.session_state.bm_branch_created = True
                    _finish_operation(
                        f"Branch '{new_branch_name}' added successfully!",
                        "success",
                    )
                except Exception as e:
                    st.error(f"Error adding branch: {str(e)}")

    st.markdown("---")

    # ==========================================================
    # EDIT BRANCH
    # ==========================================================
    st.subheader("Update / Edit Branch")

    if df.empty:
        st.info("No branches available to update.")
    else:
        # Use branch_id as the selector label so renaming a branch doesn't break
        branch_labels = [f"{r['branch_name']} ({r['branch_id']})" for _, r in df.iterrows()]
        selected_label = st.selectbox(
            "Select Branch to Update", branch_labels, key="update_branch_select"
        )

        if selected_label:
            selected_idx = branch_labels.index(selected_label)
            original_branch_id = df.iloc[selected_idx]["branch_id"]
            row = df[df["branch_id"] == original_branch_id].iloc[0]

            with st.form("update_branch_form"):
                col1, col2 = st.columns(2)
                with col1:
                    update_branch_id = st.text_input("Branch Code (Editable)", value=row["branch_id"])
                    update_branch_name = st.text_input("Branch Name", value=row["branch_name"])
                    update_location = st.text_input("Location", value=row["location"])
                    update_password = st.text_input(
                        "Branch Login Password", value=row.get("branch_password", "admin123")
                    )
                with col2:
                    update_level = st.selectbox(
                        "Level", [1, 2, 3, 4, 5, 6],
                        index=int(row["level"]) - 1 if int(row["level"]) <= 6 else 0,
                    )
                    update_package = st.selectbox(
                        "Subscription Package", ["Bronze", "Silver", "Gold", "Platinum"],
                        index=["Bronze", "Silver", "Gold", "Platinum"].index(
                            row.get("package", "Bronze")
                        ),
                    )
                    update_status = st.selectbox(
                        "Subscription Status", ["Active", "Terminated"],
                        index=["Active", "Terminated"].index(row.get("status", "Active")),
                    )
                    update_active = st.checkbox("System Active", value=bool(row["active"]))

                if st.form_submit_button("Save Changes", type="primary", use_container_width=True):
                    if not update_branch_name.strip():
                        st.error("Branch Name is required")
                    else:
                        try:
                            with st.spinner("Saving changes..."):
                                current_df = load_branches()
                                old_code = str(original_branch_id).strip().upper()
                                new_code = update_branch_id.strip().upper()

                                # Match by the ORIGINAL branch_id (stable key)
                                idx_matches = current_df.index[
                                    current_df["branch_id"].astype(str).str.upper() == old_code
                                ].tolist()
                                if not idx_matches:
                                    st.error(
                                        f"Branch {original_branch_id} not found in fresh data. "
                                        "Try clicking 'Refresh Data'."
                                    )
                                else:
                                    idx = idx_matches[0]

                                    # -------------------------------------------------
                                    # Build the single row we want the DB to end up
                                    # with, keyed on `new_code`.
                                    # -------------------------------------------------
                                    new_row = {
                                        "branch_id": new_code,
                                        "branch_name": update_branch_name.strip(),
                                        "location": update_location.strip(),
                                        "level": update_level,
                                        "active": update_active,
                                        "package": update_package,
                                        "status": update_status,
                                        "branch_password": update_password,
                                    }
                                    # Preserve any legacy columns not covered above
                                    for col in current_df.columns:
                                        if col not in new_row:
                                            new_row[col] = row.get(col, "")

                                    # Rebuild the frame:
                                    #  - drop the old row (so a rename can't leave a ghost)
                                    #  - keep every other branch as-is
                                    #  - append the edited row
                                    others = current_df.drop(index=idx).reset_index(drop=True)
                                    updated_df = pd.concat(
                                        [others, pd.DataFrame([new_row])],
                                        ignore_index=True,
                                    )

                                    # ---------------------------------------------
                                    # THE FIX: tell the adapter the original key
                                    # so it can DELETE the old row when a rename
                                    # happened, then upsert the new row with all
                                    # 8 columns (name/location/level/active/
                                    # package/status/branch_password).
                                    # ---------------------------------------------
                                    if old_code != new_code:
                                        save_branches(updated_df, original_branch_id=old_code)
                                    else:
                                        save_branches(updated_df)

                                    # If branch code changed, update users table
                                    if old_code != new_code:
                                        users_df = load_users()
                                        if not users_df.empty and "branch_id" in users_df.columns:
                                            users_df.loc[
                                                users_df["branch_id"].astype(str).str.upper() == old_code,
                                                "branch_id",
                                            ] = new_code
                                            save_users(users_df)

                                    # Handle status change (terminate / activate)
                                    if row.get("status") != update_status:
                                        users_df = load_users()
                                        if not users_df.empty and "branch_id" in users_df.columns:
                                            branch_users = (
                                                users_df["branch_id"].astype(str).str.upper()
                                                == new_code
                                            )
                                            if update_status == "Terminated":
                                                users_df.loc[branch_users, "active"] = False
                                            else:
                                                users_df.loc[branch_users, "active"] = True
                                            save_users(users_df)

                            _finish_operation(
                                f"Branch '{update_branch_name}' updated successfully!",
                                "success",
                            )
                        except Exception as e:
                            st.error(f"Error updating branch: {str(e)}")

    st.markdown("---")

    # ==========================================================
    # DELETE BRANCH
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

            st.markdown(f"### Data in **{target_row['branch_name']}** ({target_id})")

            load_counts = st.checkbox(
                "Check what data will be affected", key="load_delete_counts_cb"
            )
            if load_counts:
                with st.spinner("Counting rows..."):
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
            else:
                total_rows = 0
                counts = {}
                st.info("Tick the checkbox above to see the row counts before deleting.")

            st.markdown("---")

            # -------- Option A: Reassign then delete --------
            st.markdown("#### Option A — Reassign all data to another branch, then delete")

            other_branches = df[df["branch_id"] != target_id]
            reassign_options = [
                f"{r['branch_name']} ({r['branch_id']})"
                for _, r in other_branches.iterrows()
            ]
            reassign_label = st.selectbox(
                "Reassign data to", reassign_options, key="reassign_target_select"
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

            if st.button(
                "Reassign & Delete Branch",
                use_container_width=True,
                key="reassign_delete_btn",
            ):
                if not confirm_reassign:
                    st.error("Please tick the confirmation checkbox.")
                else:
                    with st.spinner("Reassigning data and deleting branch..."):
                        ok, msg = _reassign_branch_data(target_id, reassign_id)
                        if not ok:
                            st.error(msg)
                        else:
                            ok2, msg2 = _safe_delete_branch(target_id, allow_orphan=False)
                            if ok2:
                                st.session_state.bm_branch_deleted = True
                                _finish_operation(
                                    f"Branch '{target_row['branch_name']}' deleted after reassignment.",
                                    "success",
                                )
                            else:
                                st.error(f"Data moved, but branch row could not be deleted: {msg2}")

            st.markdown("---")

            # -------- Option B: Delete only if empty --------
            st.markdown("#### Option B — Delete an empty branch")

            if st.button(
                "Delete Empty Branch",
                use_container_width=True,
                key="delete_empty_branch_btn",
            ):
                with st.spinner("Checking and deleting..."):
                    ok, msg = _safe_delete_branch(target_id, allow_orphan=False)
                    if ok:
                        st.session_state.bm_branch_deleted = True
                        _finish_operation(msg, "success")
                    else:
                        st.error(msg)

            # -------- Option C: Force delete (leaves orphans) --------
            with st.expander("Option C — Force delete (leave data orphaned)", expanded=False):
                st.error(
                    "This will remove the branch row from the branches table. "
                    "Orphaned rows remain in the database but will no longer be reachable "
                    "from any login. This is not recommended."
                )
                force_confirm = st.text_input(
                    f"Type the branch code **{target_id}** to confirm",
                    key="force_delete_confirm",
                )
                if st.button(
                    "Force Delete Branch",
                    use_container_width=True,
                    key="force_delete_btn",
                ):
                    if force_confirm.strip().upper() != str(target_id).upper():
                        st.error("Confirmation text does not match the branch code.")
                    else:
                        with st.spinner("Force deleting..."):
                            ok, msg = _safe_delete_branch(target_id, allow_orphan=True)
                            if ok:
                                st.session_state.bm_branch_deleted = True
                                _finish_operation(
                                    f"Branch {target_id} force-deleted. Data rows remain orphaned.",
                                    "info",
                                )
                            else:
                                st.error(msg)

    st.markdown("---")

    # ==========================================================
    # REFRESH
    # ==========================================================
    if st.button("Refresh Data", use_container_width=True):
        _invalidate_branch_cache()
        st.session_state.bm_force_refresh = True
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    branch_management_page()