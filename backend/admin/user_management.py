# backend/admin/user_management.py
# User Management — fully branch-aware, with branch existence checks.

import streamlit as st
import pandas as pd
from datetime import datetime
import random
import string
import re
import secrets

from backend.core.db_adapter import load_users, save_users, load_branches
from backend.core.auth import hash_password, ROLES, init_users, check_login
from backend.utils.phone_utils import validate_zimbabwe_phone, format_phone_display


def _branches_available():
    """Return a DataFrame of branches (or empty), with a stable branch_id column."""
    try:
        df = load_branches()
        if df is None or df.empty:
            return pd.DataFrame(columns=["branch_id", "branch_name"])
        if "branch_id" not in df.columns:
            return pd.DataFrame(columns=["branch_id", "branch_name"])
        return df
    except Exception:
        return pd.DataFrame(columns=["branch_id", "branch_name"])


def _branch_id_exists(branches_df, branch_id):
    """Case-insensitive check that a branch_id is present in the branches table."""
    if not branch_id or branches_df is None or branches_df.empty:
        return False
    ids = branches_df["branch_id"].astype(str).str.upper().tolist()
    return str(branch_id).upper() in ids


def _branch_label_map(branches_df):
    """Return {branch_id: 'Name (ID)'} for nicer dropdowns."""
    if branches_df is None or branches_df.empty:
        return {}
    out = {}
    for _, r in branches_df.iterrows():
        bid = str(r["branch_id"])
        name = str(r.get("branch_name", bid))
        out[bid] = f"{name} ({bid})"
    return out


def _branch_name_for(branches_df, branch_id):
    if branches_df is None or branches_df.empty:
        return branch_id
    match = branches_df[branches_df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
    if match.empty:
        return branch_id
    return match.iloc[0].get("branch_name", branch_id)


def user_management_page():
    """User Management Page."""

    st.title("User Management")
    st.caption("Manage system users - Add, Edit, Delete, and Change Passwords")

    # Only owner can access
    if st.session_state.get("role") != "owner":
        st.error("Access Denied. Only system owner can access this page.")
        return

    # ==============================
    # SESSION STATE
    # ==============================
    if "um_initialized" not in st.session_state:
        st.session_state.um_initialized = False
    if "um_message" not in st.session_state:
        st.session_state.um_message = ""
    if "um_message_type" not in st.session_state:
        st.session_state.um_message_type = ""
    if "um_loading" not in st.session_state:
        st.session_state.um_loading = False
    if "um_force_refresh" not in st.session_state:
        st.session_state.um_force_refresh = False
    if "um_audit_log" not in st.session_state:
        st.session_state.um_audit_log = []
    if "user_created" not in st.session_state:
        st.session_state.user_created = False
    if "user_created_name" not in st.session_state:
        st.session_state.user_created_name = ""
    if "user_updated" not in st.session_state:
        st.session_state.user_updated = False
    if "user_updated_name" not in st.session_state:
        st.session_state.user_updated_name = ""

    def log_audit(action, details=""):
        st.session_state.um_audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "user": st.session_state.get("username", "system"),
            "action": action,
            "details": details,
            "branch": st.session_state.get("current_branch_code")
                      or st.session_state.get("user_branch", "HO"),
        })

    # ==============================
    # LOAD USERS + BRANCHES
    # ==============================
    try:
        if st.session_state.um_force_refresh:
            st.cache_data.clear()
            st.session_state.um_force_refresh = False

        users_df = load_users()
        branches_df = _branches_available()

        if users_df.empty and not st.session_state.um_initialized:
            st.warning("No users found in the system.")

            if st.button("Create Default Users", type="primary", use_container_width=True):
                st.session_state.um_loading = True
                with st.spinner("Creating default users..."):
                    users_df = init_users()
                    if not users_df.empty:
                        st.session_state.um_message = "Default users created successfully!"
                        st.session_state.um_message_type = "success"
                        st.session_state.um_initialized = True
                        st.session_state.um_force_refresh = True
                        log_audit("CREATE_DEFAULT_USERS", "Created default users")
                    else:
                        st.session_state.um_message = "Failed to create default users."
                        st.session_state.um_message_type = "error"
                    st.session_state.um_loading = False
            return
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return

    if not users_df.empty:
        st.session_state.um_initialized = True

    # Ensure required columns exist
    required_cols = [
        "username", "password", "role", "branch_id", "full_name",
        "phone", "whatsapp", "active", "last_login", "mobile_enabled",
        "two_factor_enabled", "force_password_change",
    ]
    for col in required_cols:
        if col not in users_df.columns:
            if col in ["active", "mobile_enabled", "two_factor_enabled", "force_password_change"]:
                users_df[col] = False
            elif col == "last_login":
                users_df[col] = ""
            else:
                users_df[col] = ""

    # ==============================
    # MESSAGES
    # ==============================
    if st.session_state.um_message:
        if st.session_state.um_message_type == "success":
            st.success(st.session_state.um_message)
        elif st.session_state.um_message_type == "error":
            st.error(st.session_state.um_message)
        else:
            st.info(st.session_state.um_message)
        st.session_state.um_message = ""
        st.session_state.um_message_type = ""

    if st.session_state.user_updated:
        st.success(f"User '{st.session_state.user_updated_name}' updated successfully!")
        st.session_state.user_updated = False
        st.session_state.user_updated_name = ""

    # ==============================
    # WARN IF BRANCHES ARE MISSING
    # ==============================
    if branches_df.empty:
        st.warning(
            "No branches configured. Please add at least one branch in "
            "**Branch Management** before creating users."
        )

    # ==============================
    # METRICS
    # ==============================
    st.markdown("## User Metrics")

    total_users = len(users_df)
    active_users = len(users_df[users_df["active"] == True])
    inactive_users = total_users - active_users
    owners = len(users_df[users_df["role"] == "owner"])
    managers = len(users_df[users_df["role"] == "manager"])
    cashiers = len(users_df[users_df["role"] == "cashier"])
    viewers = len(users_df[users_df["role"] == "viewer"])
    mobile_users = len(users_df[users_df["mobile_enabled"] == True])

    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
    with col1:
        st.metric("Total", total_users)
    with col2:
        st.metric("Active", active_users)
    with col3:
        st.metric("Inactive", inactive_users)
    with col4:
        st.metric("Owners", owners)
    with col5:
        st.metric("Managers", managers)
    with col6:
        st.metric("Cashiers", cashiers)
    with col7:
        st.metric("Viewers", viewers)
    with col8:
        st.metric("Mobile", mobile_users)

    # ==============================
    # PER-BRANCH USER SUMMARY
    # ==============================
    with st.expander("👥 Users per branch", expanded=False):
        if not branches_df.empty:
            rows = []
            for _, br in branches_df.iterrows():
                bid = br["branch_id"]
                count_total = int((users_df["branch_id"].astype(str).str.upper() == str(bid).upper()).sum())
                count_active = int((
                    (users_df["branch_id"].astype(str).str.upper() == str(bid).upper())
                    & (users_df["active"] == True)
                ).sum())
                rows.append({
                    "Branch": br.get("branch_name", bid),
                    "Code": bid,
                    "Total users": count_total,
                    "Active users": count_active,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No branches configured.")

    st.markdown("---")

    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Users",
        "Add User",
        "Edit User",
        "Password",
        "Delete/Deactivate",
        "Audit Log",
    ])

    # ==============================
    # TAB 1: USERS
    # ==============================
    with tab1:
        st.subheader("User List")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            search = st.text_input("Search", placeholder="Name, username, phone...")
        with col2:
            role_filter = st.selectbox("Filter Role", ["All"] + list(ROLES.keys()))
        with col3:
            status_filter = st.selectbox("Filter Status", ["All", "Active", "Inactive"])
        with col4:
            # Branch dropdown with friendly labels
            branch_labels = _branch_label_map(branches_df)
            branch_options = ["All"] + list(branch_labels.values())
            branch_choice = st.selectbox("Filter Branch", branch_options, key="um_branch_filter")
            branch_filter_id = None
            if branch_choice != "All":
                # Reverse-lookup the id from the label
                for bid, label in branch_labels.items():
                    if label == branch_choice:
                        branch_filter_id = bid
                        break

        filtered_df = users_df.copy()

        if search:
            s = search.lower()
            filtered_df = filtered_df[
                filtered_df["username"].str.lower().str.contains(s, na=False)
                | filtered_df["full_name"].str.lower().str.contains(s, na=False)
                | filtered_df["phone"].astype(str).str.contains(s, na=False)
                | filtered_df.get("whatsapp", pd.Series(dtype=str)).astype(str).str.contains(s, na=False)
            ]

        if role_filter != "All":
            filtered_df = filtered_df[filtered_df["role"] == role_filter]

        if status_filter == "Active":
            filtered_df = filtered_df[filtered_df["active"] == True]
        elif status_filter == "Inactive":
            filtered_df = filtered_df[filtered_df["active"] == False]

        if branch_filter_id:
            filtered_df = filtered_df[
                filtered_df["branch_id"].astype(str).str.upper() == str(branch_filter_id).upper()
            ]

        st.caption(f"Showing {len(filtered_df)} of {len(users_df)} users")

        if not filtered_df.empty:
            display_df = filtered_df[[
                "username", "full_name", "role", "branch_id", "phone",
                "whatsapp", "active", "mobile_enabled",
                "two_factor_enabled", "last_login",
            ]].copy()

            display_df["active"] = display_df["active"].apply(lambda x: "Active" if x else "Inactive")
            display_df["mobile_enabled"] = display_df["mobile_enabled"].apply(lambda x: "Yes" if x else "No")
            display_df["two_factor_enabled"] = display_df["two_factor_enabled"].apply(lambda x: "Yes" if x else "No")
            display_df["phone"] = display_df["phone"].apply(lambda x: format_phone_display(x) if x else "-")
            display_df["whatsapp"] = display_df["whatsapp"].apply(lambda x: format_phone_display(x) if x else "-")
            display_df["last_login"] = display_df["last_login"].fillna("Never")

            # Rename branch_id → Branch (Name)
            display_df["branch_id"] = display_df["branch_id"].apply(
                lambda bid: _branch_name_for(branches_df, bid)
            )
            display_df = display_df.rename(columns={"branch_id": "branch"})

            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ==============================
    # TAB 2: ADD USER
    # ==============================
    with tab2:
        st.subheader("Add New User")
        st.caption("Create a new user account with proper validation")

        if st.session_state.user_created:
            st.success(f"User '{st.session_state.user_created_name}' created successfully!")
            st.balloons()
            st.session_state.user_created = False
            st.session_state.user_created_name = ""

        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                new_username = st.text_input("Username *", placeholder="Enter unique username").strip()
                new_password = st.text_input("Password *", type="password", placeholder="Enter password (min 8 characters)")
                show_password = st.checkbox("Show password")
                if show_password and new_password:
                    st.code(new_password)
                new_full_name = st.text_input("Full Name *", placeholder="Enter full name").strip()
                new_phone = st.text_input("Phone Number", placeholder="0782905853", help="Zimbabwe phone number")

            with col2:
                new_role = st.selectbox("Role *", list(ROLES.keys()))

                # ---- Branch dropdown with friendly labels and validated ids ----
                if not branches_df.empty:
                    branch_labels = _branch_label_map(branches_df)
                    branch_labels_list = list(branch_labels.values())
                    branch_ids_list = list(branch_labels.keys())
                    default_branch = st.session_state.get("current_branch_code") \
                                    or st.session_state.get("user_branch") \
                                    or branch_ids_list[0]
                    default_idx = branch_ids_list.index(default_branch) if default_branch in branch_ids_list else 0
                    chosen_label = st.selectbox(
                        "Branch *",
                        branch_labels_list,
                        index=default_idx,
                        key="um_add_branch",
                    )
                    new_branch = branch_ids_list[branch_labels_list.index(chosen_label)]
                else:
                    new_branch = "HO"
                    st.warning("No branches found. Add a branch first.")

                new_whatsapp = st.text_input("WhatsApp", placeholder="0782905853", help="Zimbabwe WhatsApp number")
                new_mobile = st.checkbox("Enable Mobile Access")
                new_2fa = st.checkbox("Enable 2FA")
                new_active = st.checkbox("Active", value=True)
                new_force_password = st.checkbox("Force Password Change on Next Login", value=True)

            submitted = st.form_submit_button("Create User", type="primary", use_container_width=True)

            if submitted:
                current_users = load_users()
                errors = []
                warnings = []
                standardized_phone = ""
                standardized_whatsapp = ""

                # ---- Username validation ----
                if not new_username:
                    errors.append("Username is required")
                elif len(new_username) < 3:
                    errors.append("Username must be at least 3 characters")
                elif not re.match(r'^[a-zA-Z0-9_]+$', new_username):
                    errors.append("Username can only contain letters, numbers, and underscores")
                elif not current_users.empty and new_username in current_users["username"].values:
                    errors.append(f"Username '{new_username}' already exists!")

                # ---- Password validation ----
                if not new_password:
                    errors.append("Password is required")
                elif len(new_password) < 8:
                    errors.append("Password must be at least 8 characters")
                else:
                    strength = 0
                    if len(new_password) >= 8: strength += 1
                    if re.search(r'[A-Z]', new_password): strength += 1
                    if re.search(r'[a-z]', new_password): strength += 1
                    if re.search(r'[0-9]', new_password): strength += 1
                    if re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', new_password): strength += 1
                    if strength <= 2:
                        warnings.append(
                            "Password is weak. Consider using a stronger password "
                            "with uppercase, lowercase, numbers, and special characters."
                        )

                if not new_full_name:
                    errors.append("Full name is required")

                # ---- Branch existence validation ----
                if not _branch_id_exists(branches_df, new_branch):
                    errors.append(
                        f"Branch '{new_branch}' does not exist. "
                        f"Choose a branch from the dropdown."
                    )

                # ---- Phone validation ----
                if new_phone:
                    valid, standardized_phone, msg = validate_zimbabwe_phone(new_phone)
                    if not valid:
                        errors.append(f"Phone: {msg}")
                    elif not current_users.empty and "phone" in current_users.columns \
                            and standardized_phone in current_users["phone"].values:
                        errors.append(
                            f"Phone number {format_phone_display(standardized_phone)} "
                            f"already in use by another user"
                        )

                # ---- WhatsApp validation ----
                if new_whatsapp:
                    valid, standardized_whatsapp, msg = validate_zimbabwe_phone(new_whatsapp)
                    if not valid:
                        errors.append(f"WhatsApp: {msg}")
                    elif "whatsapp" in current_users.columns \
                            and standardized_whatsapp in current_users["whatsapp"].values:
                        errors.append(
                            f"WhatsApp number {format_phone_display(standardized_whatsapp)} "
                            f"already in use by another user"
                        )

                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    for w in warnings:
                        st.warning(w)

                    try:
                        hashed_pw = hash_password(new_password)

                        new_user_data = {
                            "username": new_username,
                            "password": hashed_pw,
                            "role": new_role,
                            "branch_id": new_branch,
                            "full_name": new_full_name,
                            "phone": standardized_phone if new_phone else "",
                            "whatsapp": standardized_whatsapp if new_whatsapp else "",
                            "active": new_active,
                            "mobile_enabled": new_mobile,
                            "two_factor_enabled": new_2fa,
                            "force_password_change": new_force_password,
                            "last_login": "",
                            "last_mobile_login": "",
                            "device_info": "",
                            "session_token": "",
                            "receive_alerts": True,
                        }

                        new_user = pd.DataFrame([new_user_data])
                        fresh_users = load_users()
                        updated_users = (
                            new_user if fresh_users.empty
                            else pd.concat([fresh_users, new_user], ignore_index=True)
                        )

                        save_users(updated_users)

                        log_audit("USER_CREATED", f"Created user: {new_username} ({new_role}) @ {new_branch}")

                        st.session_state.user_created = True
                        st.session_state.user_created_name = new_username
                        st.session_state.um_force_refresh = True
                        st.success(f"User '{new_username}' created successfully!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error creating user: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())

    # ==============================
    # TAB 3: EDIT USER
    # ==============================
    with tab3:
        st.subheader("Edit User")

        if users_df.empty:
            st.info("No users found")
        else:
            user_list = users_df["username"].tolist()
            edit_user = st.selectbox("Select User to Edit", user_list)

            if edit_user:
                user_data = users_df[users_df["username"] == edit_user].iloc[0]

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**Username:** {edit_user}")
                with col2:
                    st.info(f"**Current Role:** {user_data.get('role', 'N/A')}")
                with col3:
                    status = "Active" if user_data.get("active", True) else "Inactive"
                    st.info(f"**Current Status:** {status}")

                st.markdown("---")

                with st.form("edit_user_form"):
                    col1, col2 = st.columns(2)

                    with col1:
                        edit_full_name = st.text_input("Full Name", value=user_data.get("full_name", ""))
                        edit_phone = st.text_input("Phone", value=user_data.get("phone", ""))
                        edit_whatsapp = st.text_input("WhatsApp", value=user_data.get("whatsapp", ""))

                    with col2:
                        role_list = list(ROLES.keys())
                        edit_role = st.selectbox(
                            "Role",
                            role_list,
                            index=role_list.index(user_data.get("role", "cashier")) if user_data.get("role") in role_list else 0,
                        )

                        # ---- Branch dropdown ----
                        if not branches_df.empty:
                            branch_labels = _branch_label_map(branches_df)
                            branch_labels_list = list(branch_labels.values())
                            branch_ids_list = list(branch_labels.keys())

                            current_branch = str(user_data.get("branch_id", "")).upper()
                            current_idx = 0
                            for i, bid in enumerate(branch_ids_list):
                                if str(bid).upper() == current_branch:
                                    current_idx = i
                                    break

                            chosen_label = st.selectbox(
                                "Branch",
                                branch_labels_list,
                                index=current_idx,
                                key="um_edit_branch",
                            )
                            edit_branch = branch_ids_list[branch_labels_list.index(chosen_label)]
                        else:
                            edit_branch = "HO"
                            st.warning("No branches configured.")

                        edit_mobile = st.checkbox("Mobile Access", value=user_data.get("mobile_enabled", False))
                        edit_2fa = st.checkbox("2FA Enabled", value=user_data.get("two_factor_enabled", False))
                        edit_active = st.checkbox("Active", value=user_data.get("active", True))
                        edit_force_password = st.checkbox("Force Password Change", value=user_data.get("force_password_change", False))

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Save Changes", type="primary", use_container_width=True):
                            try:
                                current_users = load_users()
                                mask = current_users["username"] == edit_user
                                if not mask.any():
                                    st.error(f"User '{edit_user}' not found")
                                    st.stop()
                                idx = current_users[mask].index[0]

                                # Branch existence check
                                if not _branch_id_exists(branches_df, edit_branch):
                                    st.error(
                                        f"Branch '{edit_branch}' does not exist. "
                                        f"Choose a branch from the dropdown."
                                    )
                                    st.stop()

                                # Phone validation
                                if edit_phone:
                                    valid, standardized_phone, msg = validate_zimbabwe_phone(edit_phone)
                                    if not valid:
                                        st.error(f"Phone: {msg}")
                                        st.stop()
                                    phone_exists = False
                                    if "phone" in current_users.columns:
                                        for i, row in current_users.iterrows():
                                            if i != idx and row.get("phone") == standardized_phone:
                                                phone_exists = True
                                                break
                                    if phone_exists:
                                        st.error(
                                            f"Phone number {format_phone_display(standardized_phone)} "
                                            f"already in use by another user"
                                        )
                                        st.stop()
                                    current_users.loc[idx, "phone"] = standardized_phone
                                else:
                                    current_users.loc[idx, "phone"] = ""

                                # WhatsApp validation
                                if edit_whatsapp:
                                    valid, standardized_whatsapp, msg = validate_zimbabwe_phone(edit_whatsapp)
                                    if not valid:
                                        st.error(f"WhatsApp: {msg}")
                                        st.stop()
                                    wa_exists = False
                                    if "whatsapp" in current_users.columns:
                                        for i, row in current_users.iterrows():
                                            if i != idx and row.get("whatsapp") == standardized_whatsapp:
                                                wa_exists = True
                                                break
                                    if wa_exists:
                                        st.error(
                                            f"WhatsApp number {format_phone_display(standardized_whatsapp)} "
                                            f"already in use by another user"
                                        )
                                        st.stop()
                                    current_users.loc[idx, "whatsapp"] = standardized_whatsapp
                                else:
                                    current_users.loc[idx, "whatsapp"] = ""

                                # Update other fields
                                current_users.loc[idx, "full_name"] = edit_full_name
                                current_users.loc[idx, "role"] = edit_role
                                current_users.loc[idx, "branch_id"] = edit_branch
                                current_users.loc[idx, "mobile_enabled"] = edit_mobile
                                current_users.loc[idx, "two_factor_enabled"] = edit_2fa
                                current_users.loc[idx, "active"] = edit_active
                                current_users.loc[idx, "force_password_change"] = edit_force_password

                                save_users(current_users)
                                log_audit("USER_UPDATED", f"Updated user: {edit_user}")

                                st.session_state.user_updated = True
                                st.session_state.user_updated_name = edit_user
                                st.session_state.um_force_refresh = True
                                st.success(f"User '{edit_user}' updated successfully!")
                                st.rerun()

                            except Exception as e:
                                st.error(f"Error updating user: {str(e)}")

                    with col2:
                        if st.form_submit_button("Cancel", use_container_width=True):
                            st.rerun()

    # ==============================
    # TAB 4: PASSWORD
    # ==============================
    with tab4:
        st.subheader("Password Management")

        if users_df.empty:
            st.info("No users found")
        else:
            password_user = st.selectbox(
                "Select User", users_df["username"].tolist(), key="password_user"
            )

            if password_user:
                user_data = users_df[users_df["username"] == password_user].iloc[0]

                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"User: {password_user} ({user_data.get('role', 'N/A')})")
                with col2:
                    st.info(f"Status: {'Active' if user_data.get('active', True) else 'Inactive'}")

                with st.form("password_form"):
                    new_password = st.text_input("New Password", type="password", placeholder="Enter new password (min 8 characters)")
                    confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm new password")
                    force_change = st.checkbox(
                        "Force password change on next login",
                        value=user_data.get("force_password_change", False),
                    )

                    if new_password:
                        strength = 0
                        if len(new_password) >= 8: strength += 1
                        if re.search(r'[A-Z]', new_password): strength += 1
                        if re.search(r'[a-z]', new_password): strength += 1
                        if re.search(r'[0-9]', new_password): strength += 1
                        if re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', new_password): strength += 1
                        st.progress(strength / 5)
                        strength_text = ["Very Weak", "Weak", "Medium", "Strong", "Very Strong"][strength - 1] if strength > 0 else "Very Weak"
                        st.caption(f"Strength: {strength_text}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Change Password", type="primary", use_container_width=True):
                            if not new_password:
                                st.error("Please enter a new password")
                            elif len(new_password) < 8:
                                st.error("Password must be at least 8 characters")
                            elif new_password != confirm_password:
                                st.error("Passwords do not match")
                            else:
                                try:
                                    current_users = load_users()
                                    hashed_pw = hash_password(new_password)
                                    idx = current_users[current_users["username"] == password_user].index[0]
                                    current_users.loc[idx, "password"] = hashed_pw
                                    current_users.loc[idx, "force_password_change"] = force_change
                                    save_users(current_users)
                                    log_audit("PASSWORD_CHANGED", f"Changed password for: {password_user}")
                                    st.session_state.um_force_refresh = True
                                    st.success(f"Password for '{password_user}' changed successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error changing password: {str(e)}")

                    with col2:
                        if st.form_submit_button("Generate Random Password", use_container_width=True):
                            try:
                                characters = string.ascii_letters + string.digits + "!@#$%^&*"
                                random_password = ''.join(random.choice(characters) for _ in range(12))
                                current_users = load_users()
                                hashed_pw = hash_password(random_password)
                                idx = current_users[current_users["username"] == password_user].index[0]
                                current_users.loc[idx, "password"] = hashed_pw
                                current_users.loc[idx, "force_password_change"] = True
                                save_users(current_users)
                                st.success(f"Password for '{password_user}' changed to:")
                                st.code(random_password)
                                st.info("Please provide this password to the user. They can change it later.")
                                log_audit("PASSWORD_RESET", f"Generated new password for: {password_user}")
                                st.session_state.um_force_refresh = True
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error generating password: {str(e)}")

    # ==============================
    # TAB 5: DELETE / DEACTIVATE
    # ==============================
    with tab5:
        st.subheader("Delete or Deactivate User")

        if users_df.empty:
            st.info("No users found")
        else:
            current_user = st.session_state.get("username", "")
            user_options = [u for u in users_df["username"].tolist() if u != current_user]

            if not user_options:
                st.info("No other users to manage.")
            else:
                delete_user = st.selectbox("Select User to Manage", user_options, key="delete_user")

                if delete_user:
                    user_data = users_df[users_df["username"] == delete_user].iloc[0]

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"**Username:** {delete_user}")
                    with col2:
                        st.info(f"**Role:** {str(user_data['role']).upper()}")
                    with col3:
                        status = "Active" if user_data.get("active", True) else "Inactive"
                        st.info(f"**Status:** {status}")

                    st.markdown("---")

                    col1, col2 = st.columns(2)

                    with col1:
                        current_status = user_data.get("active", True)
                        status_text = "Deactivate" if current_status else "Activate"
                        if st.button(f"{status_text} User", use_container_width=True):
                            try:
                                current_users = load_users()
                                idx = current_users[current_users["username"] == delete_user].index[0]
                                current_users.loc[idx, "active"] = not current_status
                                save_users(current_users)
                                new_status = "deactivated" if not current_status else "activated"
                                log_audit(f"USER_{new_status.upper()}", f"{new_status} user: {delete_user}")
                                st.session_state.um_force_refresh = True
                                st.success(f"User '{delete_user}' {new_status} successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating user: {str(e)}")

                    with col2:
                        if st.button("Delete User Permanently", use_container_width=True):
                            if delete_user in ["admin"]:
                                st.error("Cannot delete the admin user!")
                            elif user_data.get("role") == "owner" and \
                                    len(users_df[users_df["role"] == "owner"]) <= 1:
                                st.error("Cannot delete the last owner!")
                            else:
                                # ---- Block deletion if this user is the last
                                #      active user in their branch ----
                                target_branch = user_data.get("branch_id", "")
                                if target_branch:
                                    same_branch_active = users_df[
                                        (users_df["branch_id"] == target_branch)
                                        & (users_df["active"] == True)
                                        & (users_df["username"] != delete_user)
                                    ]
                                    is_only_active_in_branch = (
                                        user_data.get("active", True) is True
                                        and same_branch_active.empty
                                    )
                                else:
                                    is_only_active_in_branch = False

                                if is_only_active_in_branch:
                                    st.error(
                                        f"Cannot delete **{delete_user}** — they are the "
                                        f"only active user in branch **{_branch_name_for(branches_df, target_branch)}**. "
                                        f"Add or activate another user in this branch first."
                                    )
                                else:
                                    st.warning(
                                        f"This will permanently delete user '{delete_user}'. "
                                        f"This action CANNOT be undone."
                                    )
                                    confirm = st.checkbox(
                                        "I understand this action CANNOT be undone",
                                        key=f"confirm_delete_{delete_user}",
                                    )
                                    if confirm:
                                        try:
                                            current_users = load_users()
                                            current_users = current_users[
                                                current_users["username"] != delete_user
                                            ]
                                            save_users(current_users)
                                            log_audit("USER_DELETED", f"Deleted user: {delete_user}")
                                            st.session_state.um_force_refresh = True
                                            st.success(f"User '{delete_user}' deleted permanently!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error deleting user: {str(e)}")

    # ==============================
    # TAB 6: AUDIT LOG
    # ==============================
    with tab6:
        st.subheader("Audit Log")
        st.caption("Track all user management actions")

        if st.session_state.um_audit_log:
            audit_df = pd.DataFrame(st.session_state.um_audit_log)
            audit_df["timestamp"] = pd.to_datetime(audit_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(audit_df, use_container_width=True, hide_index=True)

            csv = audit_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export Audit Log (CSV)",
                data=csv,
                file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("No audit logs recorded yet")

    # ==============================
    # REFRESH
    # ==============================
    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.um_force_refresh = True
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    user_management_page()