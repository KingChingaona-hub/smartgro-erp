# backend/core/shift_definitions.py
"""
Branch-scoped shift definitions.

Owners and managers can Add / Edit / Delete shift definitions on any branch.
Non-owners see only the definitions for their own session branch.

This module owns the `shift_definitions` table. It does NOT touch the
`shifts` table (which stores actual running/completed shift instances).

Schema (created automatically on first use):
    shift_definitions (
        id              SERIAL PRIMARY KEY,
        branch_id       VARCHAR(20) NOT NULL,
        shift_name      VARCHAR(50) NOT NULL,
        display_name    VARCHAR(100),
        start_time      TIME,
        end_time        TIME,
        active          BOOLEAN DEFAULT TRUE,
        sort_order      INTEGER DEFAULT 0,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (branch_id, shift_name)
    )
"""

import logging
from datetime import datetime
import psycopg2
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ==============================================================
# DEFAULT SHIFT TEMPLATE
# ==============================================================
DEFAULT_SHIFTS = [
    {"shift_name": "ALPHA",   "display_name": "Alpha Shift (06:00 - 12:00)",   "start_time": "06:00", "end_time": "12:00", "sort_order": 1},
    {"shift_name": "BRAVO",   "display_name": "Bravo Shift (08:00 - 14:00)",   "start_time": "08:00", "end_time": "14:00", "sort_order": 2},
    {"shift_name": "CHARLIE", "display_name": "Charlie Shift (10:00 - 16:00)", "start_time": "10:00", "end_time": "16:00", "sort_order": 3},
    {"shift_name": "DELTA",   "display_name": "Delta Shift (12:00 - 18:00)",   "start_time": "12:00", "end_time": "18:00", "sort_order": 4},
    {"shift_name": "ECHO",    "display_name": "Echo Shift (14:00 - 20:00)",    "start_time": "14:00", "end_time": "20:00", "sort_order": 5},
]


# ==============================================================
# DB HELPERS  (standalone — no circular import from db_adapter)
# ==============================================================
def _get_db_url():
    return os.environ.get("POSTGRESQL_URL") or os.environ.get("DATABASE_URL")


def _get_db_connection():
    url = _get_db_url()
    if not url:
        return None
    parsed = urlparse(url)
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        sslmode="require",
    )


def _get_session_branch():
    """Return the authoritative branch for the current session."""
    try:
        import streamlit as st
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _get_session_role():
    try:
        import streamlit as st
        return st.session_state.get("role", "cashier")
    except Exception:
        return "cashier"


def _is_multi_branch_user():
    return _get_session_role() in ("owner", "manager", "admin")


# ==============================================================
# TABLE INIT
# ==============================================================
def _ensure_table_exists(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shift_definitions (
            id              SERIAL PRIMARY KEY,
            branch_id       VARCHAR(20) NOT NULL,
            shift_name      VARCHAR(50) NOT NULL,
            display_name    VARCHAR(100),
            start_time      TIME,
            end_time        TIME,
            active          BOOLEAN DEFAULT TRUE,
            sort_order      INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (branch_id, shift_name)
        )
    """)


def _seed_defaults_for_branch(cur, branch_id):
    """Insert the five default shifts for this branch if none exist."""
    cur.execute(
        "SELECT COUNT(*) FROM shift_definitions WHERE branch_id = %s",
        (branch_id,),
    )
    count = cur.fetchone()[0]
    if count > 0:
        return

    for shift in DEFAULT_SHIFTS:
        cur.execute("""
            INSERT INTO shift_definitions
                (branch_id, shift_name, display_name, start_time, end_time, active, sort_order)
            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
            ON CONFLICT (branch_id, shift_name) DO NOTHING
        """, (
            branch_id,
            shift["shift_name"],
            shift["display_name"],
            shift["start_time"],
            shift["end_time"],
            shift["sort_order"],
        ))


# ==============================================================
# PUBLIC API
# ==============================================================
def load_shift_definitions(branch_id=None, include_inactive=False):
    """
    Return shift definitions for the given branch.
    If branch_id is None, uses the session branch.
    Enforces branch isolation for non-owner/manager/admin users.
    """
    if branch_id is None:
        branch_id = _get_session_branch()

    # Non-owners can only read their own branch
    if not _is_multi_branch_user():
        branch_id = _get_session_branch()

    import pandas as pd
    conn = _get_db_connection()
    if conn is None:
        return pd.DataFrame(columns=[
            "id", "branch_id", "shift_name", "display_name",
            "start_time", "end_time", "active", "sort_order",
        ])

    try:
        cur = conn.cursor()
        _ensure_table_exists(cur)
        _seed_defaults_for_branch(cur, branch_id)
        conn.commit()

        query = """
            SELECT id, branch_id, shift_name, display_name,
                   start_time, end_time, active, sort_order
            FROM shift_definitions
            WHERE branch_id = %s
        """
        params = [branch_id]
        if not include_inactive:
            query += " AND active = TRUE"
        query += " ORDER BY sort_order, shift_name"

        cur.execute(query, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        cur.close()
        conn.close()

        if rows:
            return pd.DataFrame(rows, columns=cols)
        return pd.DataFrame(columns=cols)

    except Exception as e:
        logger.error(f"Error loading shift definitions: {e}")
        try:
            conn.close()
        except Exception:
            pass
        import pandas as pd
        return pd.DataFrame(columns=[
            "id", "branch_id", "shift_name", "display_name",
            "start_time", "end_time", "active", "sort_order",
        ])


def add_shift_definition(branch_id, shift_name, display_name="", start_time=None, end_time=None, sort_order=None):
    """
    Add a new shift definition for a specific branch.
    Owner/manager only. Returns (success, message).
    """
    if not _is_multi_branch_user():
        return False, "Only owners and managers can manage shifts"

    shift_name = str(shift_name).strip().upper()
    if not shift_name:
        return False, "Shift name is required"
    if not branch_id:
        return False, "Branch is required"

    if sort_order is None:
        sort_order = 99  # appended

    conn = _get_db_connection()
    if conn is None:
        return False, "Database connection failed"

    try:
        cur = conn.cursor()
        _ensure_table_exists(cur)

        # Reject duplicates within the same branch
        cur.execute(
            "SELECT 1 FROM shift_definitions WHERE branch_id = %s AND UPPER(shift_name) = UPPER(%s)",
            (branch_id, shift_name),
        )
        if cur.fetchone():
            cur.close()
            conn.close()
            return False, f"Shift '{shift_name}' already exists in this branch"

        cur.execute("""
            INSERT INTO shift_definitions
                (branch_id, shift_name, display_name, start_time, end_time, active, sort_order)
            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
        """, (
            branch_id,
            shift_name,
            display_name or f"{shift_name} Shift",
            start_time,
            end_time,
            sort_order,
        ))

        conn.commit()
        cur.close()
        conn.close()
        return True, f"Shift '{shift_name}' added to branch {branch_id}"

    except Exception as e:
        logger.error(f"Error adding shift definition: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False, f"Error: {str(e)}"


def update_shift_definition(definition_id, display_name=None, start_time=None, end_time=None, active=None, sort_order=None):
    """
    Update an existing shift definition by its row id.
    Owner/manager only. Returns (success, message).
    """
    if not _is_multi_branch_user():
        return False, "Only owners and managers can manage shifts"

    conn = _get_db_connection()
    if conn is None:
        return False, "Database connection failed"

    try:
        cur = conn.cursor()
        _ensure_table_exists(cur)

        # Load current row
        cur.execute("""
            SELECT branch_id, shift_name, display_name, start_time, end_time, active, sort_order
            FROM shift_definitions WHERE id = %s
        """, (definition_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return False, "Shift definition not found"

        cur_branch_id, cur_shift_name, cur_display, cur_start, cur_end, cur_active, cur_sort = row

        # Non-owners cannot edit other branches
        if not _is_multi_branch_user() and cur_branch_id != _get_session_branch():
            cur.close()
            conn.close()
            return False, "You can only manage shifts in your own branch"

        new_display = display_name if display_name is not None else cur_display
        new_start = start_time if start_time is not None else cur_start
        new_end = end_time if end_time is not None else cur_end
        new_active = active if active is not None else cur_active
        new_sort = sort_order if sort_order is not None else cur_sort

        cur.execute("""
            UPDATE shift_definitions
            SET display_name = %s,
                start_time = %s,
                end_time = %s,
                active = %s,
                sort_order = %s,
                updated_at = %s
            WHERE id = %s
        """, (
            new_display,
            new_start,
            new_end,
            new_active,
            new_sort,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            definition_id,
        ))

        conn.commit()
        cur.close()
        conn.close()
        return True, f"Shift '{cur_shift_name}' updated"

    except Exception as e:
        logger.error(f"Error updating shift definition: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False, f"Error: {str(e)}"


def delete_shift_definition(definition_id):
    """
    Soft-delete a shift definition (sets active = FALSE).
    Owner/manager only. Returns (success, message).
    """
    if not _is_multi_branch_user():
        return False, "Only owners and managers can manage shifts"

    conn = _get_db_connection()
    if conn is None:
        return False, "Database connection failed"

    try:
        cur = conn.cursor()
        _ensure_table_exists(cur)

        cur.execute(
            "SELECT branch_id, shift_name FROM shift_definitions WHERE id = %s",
            (definition_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return False, "Shift definition not found"

        branch_id, shift_name = row

        if not _is_multi_branch_user() and branch_id != _get_session_branch():
            cur.close()
            conn.close()
            return False, "You can only manage shifts in your own branch"

        cur.execute("""
            UPDATE shift_definitions
            SET active = FALSE,
                updated_at = %s
            WHERE id = %s
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            definition_id,
        ))

        conn.commit()
        cur.close()
        conn.close()
        return True, f"Shift '{shift_name}' removed"

    except Exception as e:
        logger.error(f"Error deleting shift definition: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False, f"Error: {str(e)}"


def get_shift_names_for_branch(branch_id=None):
    """Return a list of active shift names for the given (or session) branch."""
    df = load_shift_definitions(branch_id=branch_id, include_inactive=False)
    if df.empty:
        return []
    return df["shift_name"].tolist()


def get_shift_display_name_for_branch(shift_name, branch_id=None):
    """Return the display name for a shift, scoped by branch."""
    df = load_shift_definitions(branch_id=branch_id, include_inactive=False)
    if df.empty:
        return shift_name
    match = df[df["shift_name"].str.upper() == str(shift_name).upper()]
    if match.empty:
        return shift_name
    return match.iloc[0]["display_name"] or shift_name


def ensure_branch_has_defaults(branch_id):
    """
    Guarantee the given branch has at least the five default shifts.
    Safe to call from anywhere — creates the table if missing and seeds
    defaults if the branch has no rows yet.
    """
    conn = _get_db_connection()
    if conn is None:
        return False
    try:
        cur = conn.cursor()
        _ensure_table_exists(cur)
        _seed_defaults_for_branch(cur, branch_id)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error ensuring defaults: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False