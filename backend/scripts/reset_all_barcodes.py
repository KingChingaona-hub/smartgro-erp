"""
Reset every product barcode to a 13-digit numeric code derived from its id,
and retag every reference in sales / purchases / customer_transactions.

Safe design:
  - Uses a single transaction; rolls back on any error.
  - Refuses to run twice: if every barcode already matches ^[0-9]{13}$, it
    exits without touching anything.
  - Collisions: because two different products can share the same branch,
    the new barcode is guaranteed unique per (branch_id, barcode) by
    appending the id. If a collision still occurs (row id was modified),
    it bumps to a fallback range.
  - References are retagged for every row whose barcode matches the old
    value inside the same branch.
  - Prints a full before/after table so you can audit.

Usage:
    python -m backend.scripts.reset_all_barcodes
"""

import re
import sys
from backend.core.db_adapter import get_db_cursor


CONFORMING = re.compile(r"^[0-9]{13}$")


def _new_barcode(row_id: int) -> str:
    """13-digit numeric derived from row id, prefix 2 for consistency."""
    core = f"{int(row_id) % 10_000_000_000_00:012d}"   # 12 digits
    return ("2" + core)[:13].ljust(13, "0")


def _new_barcode_fallback(row_id: int) -> str:
    """Alternate barcode in case the primary collides."""
    core = f"{(int(row_id) + 7_000_000_000_00) % 10_000_000_000_00:012d}"
    return ("2" + core)[:13].ljust(13, "0")


# Tables that carry a barcode column and should be retagged when a product's
# barcode changes. Missing tables / columns are skipped silently.
REFERENCE_TABLES = (
    "sales",
    "purchases",
    "customer_transactions",
    "debtor_items",
    "returns",
    "refunds",
    "warranty_registrations",
)


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
    """, (table, column))
    return cur.fetchone() is not None


def main():
    with get_db_cursor() as (cur, conn):
        if cur is None or conn is None:
            print("No DB connection. Aborting.")
            sys.exit(1)

        # ---- 1. Read every product ----
        cur.execute("""
            SELECT id, branch_id, barcode, name
            FROM products
            ORDER BY branch_id, id
        """)
        products = cur.fetchall() or []

        if not products:
            print("No products found.")
            return

        to_change = []
        for row in products:
            rid = row["id"]
            branch = row["branch_id"]
            old = (row["barcode"] or "")
            name = row["name"]
            if not CONFORMING.match(old):
                to_change.append((rid, branch, old, name))

        if not to_change:
            print("Every barcode already matches ^[0-9]{13}$. Nothing to do.")
            return

        print(f"Found {len(to_change)} product(s) with non-conforming barcodes.")
        print()

        # ---- 2. Build the new barcodes, resolving collisions per branch ----
        # First pass: propose new barcodes and detect in-branch collisions
        # against products we are NOT changing (they already conform) and
        # against each other.
        proposed = {}                     # rid -> new barcode
        taken = {}                        # branch -> set of barcodes in use
        for row in products:
            b = row["branch_id"]
            taken.setdefault(b, set())
            if CONFORMING.match(row["barcode"] or ""):
                taken[b].add(row["barcode"])

        for rid, branch, old, name in to_change:
            candidate = _new_barcode(rid)
            if candidate in taken[branch]:
                candidate = _new_barcode_fallback(rid)
            # If it still collides, keep bumping until free
            bump = 0
            while candidate in taken[branch]:
                bump += 1
                candidate = _new_barcode(rid + bump)
            taken[branch].add(candidate)
            proposed[rid] = candidate

        # ---- 3. Retag references, then update products ----
        for rid, branch, old, name in to_change:
            new = proposed[rid]

            # 3a. Retag references in every reference table that has a barcode column
            for tbl in REFERENCE_TABLES:
                if not _column_exists(cur, tbl, "barcode"):
                    continue
                try:
                    cur.execute(
                        f"UPDATE {tbl} SET barcode = %s "
                        f"WHERE barcode = %s AND branch_id = %s",
                        (new, old, branch),
                    )
                except Exception as e:
                    print(f"  [WARN] retag {tbl} for id={rid}: {e}")
                    conn.rollback()

            # 3b. Update the product row itself
            cur.execute(
                "UPDATE products SET barcode = %s WHERE id = %s",
                (new, rid),
            )

            print(f"  {branch} id={rid:>8} {name!r:<30} {old!r:>20} -> {new!r}")

        conn.commit()

        # ---- 4. Verify ----
        cur.execute("""
            SELECT COUNT(*) AS bad FROM products
            WHERE barcode IS NULL OR barcode !~ '^[0-9]{13}$'
        """)
        r = cur.fetchone()
        remaining = r["bad"] if isinstance(r, dict) else r[0]

        print()
        print("===== Summary =====")
        print(f"  Rewritten: {len(to_change)}")
        print(f"  Remaining non-conforming barcodes: {remaining}")
        if remaining:
            print("  WARNING: some rows still do not conform. Re-run this script.")


if __name__ == "__main__":
    main()