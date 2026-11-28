import streamlit as st
from datetime import datetime

# ==============================
# SAFE IMPORT (PDF OPTIONAL)
# ==============================
try:
    from reportlab.lib.pagesizes import letter, mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from io import BytesIO
    PDF_AVAILABLE = True
except:
    PDF_AVAILABLE = False


# ==============================
# BRANCH HEADER RESOLVER
# ==============================
_DEFAULT_BRANCH_NAME = "Aziel Investments"
_DEFAULT_BRANCH_ADDR = "Retreat Park, Harare"
_DEFAULT_BRANCH_PHONE = "0782905853 / 0776067967"
_DEFAULT_BRANCH_EMAIL = "info@azielinvestments.co.zw"


def _get_session_branch():
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _resolve_branch_header(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    name = _DEFAULT_BRANCH_NAME
    address = _DEFAULT_BRANCH_ADDR
    phone = _DEFAULT_BRANCH_PHONE  # LOCKED: Always uses 0782905853
    email = _DEFAULT_BRANCH_EMAIL

    try:
        from backend.core.db_adapter import load_branches
        df = load_branches()
        if df is not None and not df.empty and "branch_id" in df.columns:
            match = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                for src, key in (
                    ("branch_name", "name"),
                    ("address", "address"),
                    # ("phone", "phone"),  <-- REMOVED SO DB CANNOT OVERWRITE PHONE
                    ("email", "email"),
                ):
                    if src in row and row[src]:
                        val = str(row[src]).strip()
                        if val:
                            if key == "name":
                                name = val if "aziel" in val.lower() else f"Aziel Investments - {val}"
                            elif key == "address":
                                address = val
                            elif key == "email":
                                email = val
    except Exception:
        pass

    return name, address, phone, email


# ==============================
# PROFESSIONAL RECEIPT GENERATOR
# ==============================
def generate_receipt(
    cart,
    total_amount,
    receipt_no,
    payment_method="CASH",
    customer_name="Walk-in",
    discount_amount=0,
    tax_amount=0,
    cash_received=0,
    change=0,
    final_total=0,
    branch_id=None,
):
    branch_name, branch_address, branch_phone, branch_email = _resolve_branch_header(branch_id)

    receipt = []

    # HEADER SECTION
    receipt.append("=" * 52)
    receipt.append("              AZIEL INVESTMENTS")
    receipt.append("         'Your Business, Our Priority'")
    receipt.append("             Smart Retail ERP System")
    receipt.append("-" * 52)
    receipt.append(f"Receipt No : {receipt_no}")
    receipt.append(f"Date       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    receipt.append(f"Cashier    : {st.session_state.get('username', 'System')}")
    receipt.append(f"Customer   : {customer_name}")
    receipt.append(f"Payment    : {payment_method}")
    receipt.append("=" * 52)

    # TABLE HEADER
    receipt.append("")
    receipt.append("QTY  ITEM                       PRICE       TOTAL")
    receipt.append("-" * 52)

    # ITEMS SECTION
    for item in cart:
        name = item['name'][:26]
        qty = float(item['qty'])
        price = float(item['price'])
        total = float(item['total'])

        if qty % 1 == 0:
            qty_str = f"{int(qty):<4}"
        else:
            qty_str = f"{qty:<4.2f}"

        receipt.append(f"{qty_str} {name:<26} ${price:>7.2f} ${total:>8.2f}")

    receipt.append("-" * 52)

    # SUMMARY SECTION
    receipt.append(f"{'SUBTOTAL:':>42} ${total_amount:>7.2f}")

    if discount_amount > 0:
        receipt.append(f"{'DISCOUNT:':>42} -${discount_amount:>6.2f}")

    if tax_amount > 0:
        receipt.append(f"{'TAX:':>42} +${tax_amount:>6.2f}")

    receipt.append("-" * 52)
    receipt.append(f"{'FINAL TOTAL:':>42} ${final_total:>7.2f}")

    if payment_method == "CASH":
        receipt.append(f"{'AMOUNT TENDERED:':>42} ${cash_received:>7.2f}")
        receipt.append(f"{'CHANGE:':>42} ${change:>7.2f}")

    # FOOTER SECTION
    receipt.append("=" * 52)
    receipt.append("        THANK YOU FOR SHOPPING WITH US!")
    receipt.append("        'Your Business, Our Priority'")
    receipt.append("-" * 52)
    receipt.append(f"  Branch: {branch_name}")
    receipt.append(f"  Contacts: {branch_phone}")
    receipt.append(f"  Email: {branch_email}")
    receipt.append("=" * 52)

    return "\n".join(receipt)


# ==============================
# ENHANCED RECEIPT WITH BRANDING
# ==============================
def generate_premium_receipt(
    cart,
    total_amount,
    receipt_no,
    payment_method="CASH",
    customer_name="Walk-in",
    customer_phone="",
    discount_amount=0,
    discount_percent=0,
    tax_amount=0,
    tax_percent=0,
    cash_received=0,
    change=0,
    final_total=0,
    loyalty_points_earned=0,
    loyalty_points_used=0,
    branch_id=None,
):
    branch_name, branch_address, branch_phone, branch_email = _resolve_branch_header(branch_id)

    receipt = []

    # HEADER WITH BRANDING
    receipt.append("")
    receipt.append("╔════════════════════════════════════════════════════╗")
    receipt.append("║                                                    ║")
    receipt.append("║                AZIEL INVESTMENTS                   ║")
    receipt.append("║           'Your Business, Our Priority'            ║")
    receipt.append("║                                                    ║")
    receipt.append("║              Smart Retail ERP System               ║")
    receipt.append("║                                                    ║")
    receipt.append("╠════════════════════════════════════════════════════╣")
    receipt.append(f"║ Receipt No : {receipt_no:<36}║")
    receipt.append(f"║ Date       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<36}║")
    receipt.append(f"║ Cashier    : {st.session_state.get('username', 'System'):<36}║")
    receipt.append(f"║ Customer   : {customer_name:<36}║")
    if customer_phone:
        receipt.append(f"║ Phone      : {customer_phone:<36}║")
    receipt.append(f"║ Payment    : {payment_method:<36}║")
    receipt.append("╠════════════════════════════════════════════════════╣")

    # ITEMS TABLE
    receipt.append("║                                                    ║")
    receipt.append("║  QTY  ITEM                      PRICE      TOTAL   ║")
    receipt.append("║  ──────────────────────────────────────────────── ║")

    for item in cart:
        name = item['name'][:24]
        qty = float(item['qty'])
        price = float(item['price'])
        total = float(item['total'])

        if qty % 1 == 0:
            qty_str = f"{int(qty):<3}"
        else:
            qty_str = f"{qty:<5.2f}"

        receipt.append(f"║  {qty_str} {name:<24} ${price:>6.2f}   ${total:>7.2f} ║")

    receipt.append("║  ──────────────────────────────────────────────── ║")

    # TOTALS
    receipt.append(f"║  {'SUBTOTAL:':<39} ${total_amount:>7.2f} ║")

    if discount_amount > 0:
        if discount_percent > 0:
            receipt.append(f"║  {'DISCOUNT (' + str(discount_percent) + '%):':<39} -${discount_amount:>6.2f} ║")
        else:
            receipt.append(f"║  {'DISCOUNT:':<39} -${discount_amount:>6.2f} ║")

    if tax_amount > 0:
        if tax_percent > 0:
            receipt.append(f"║  {'TAX (' + str(tax_percent) + '%):':<39} +${tax_amount:>6.2f} ║")
        else:
            receipt.append(f"║  {'TAX:':<39} +${tax_amount:>6.2f} ║")

    receipt.append("║  ──────────────────────────────────────────────── ║")
    receipt.append(f"║  {'FINAL TOTAL:':<39} ${final_total:>7.2f} ║")

    if payment_method == "CASH":
        receipt.append(f"║  {'AMOUNT TENDERED:':<39} ${cash_received:>7.2f} ║")
        receipt.append(f"║  {'CHANGE:':<39} ${change:>7.2f} ║")

    # LOYALTY POINTS
    if loyalty_points_earned > 0:
        receipt.append("╠════════════════════════════════════════════════════╣")
        receipt.append(f"║  * LOYALTY POINTS EARNED: {loyalty_points_earned:<23}║")

    if loyalty_points_used > 0:
        receipt.append(f"║  * POINTS REDEEMED: {loyalty_points_used:<28}║")

    # FOOTER
    receipt.append("╠════════════════════════════════════════════════════╣")
    receipt.append("║                                                    ║")
    receipt.append("║          THANK YOU FOR SHOPPING WITH US!           ║")
    receipt.append("║                                                    ║")
    receipt.append("║          'Your Business, Our Priority'             ║")
    receipt.append("║                                                    ║")
    receipt.append(f"║  {branch_name[:48]:<50}║")
    receipt.append(f"║  Contacts: {branch_phone[:36]:<36}║")
    receipt.append(f"║  Email: {branch_email[:39]:<39}║")
    receipt.append("║                                                    ║")
    receipt.append("╚════════════════════════════════════════════════════╝")
    receipt.append("")

    return "\n".join(receipt)


# ==============================
# SIMPLE THERMAL RECEIPT (For 58mm printers)
# ==============================
def generate_thermal_receipt(
    cart,
    total_amount,
    receipt_no,
    payment_method="CASH",
    customer_name="Walk-in",
    final_total=0,
    branch_id=None,
):
    branch_name, branch_address, branch_phone, branch_email = _resolve_branch_header(branch_id)

    receipt = []

    # Header
    receipt.append("")
    receipt.append("     AZIEL INVESTMENTS")
    receipt.append(" 'Your Business, Our Priority'")
    receipt.append("-" * 34)
    receipt.append(f" Receipt: {receipt_no}")
    receipt.append(f" Date: {datetime.now().strftime('%d/%m/%y %H:%M')}")
    receipt.append(f" Cashier: {st.session_state.get('username', 'System')[:12]}")
    receipt.append(f" Customer: {customer_name[:20]}")
    receipt.append("-" * 34)

    # Items
    receipt.append(" QTY ITEM           PRICE")
    for item in cart:
        name = item['name'][:12]
        qty = float(item['qty'])
        price = float(item['price'])
        total = float(item['total'])

        if qty % 1 == 0:
            qty_str = f"{int(qty):>2}"
        else:
            qty_str = f"{qty:>4.1f}"

        receipt.append(f" {qty_str}  {name:<12} ${price:>5.2f}")
        receipt.append(f"                    ${total:>7.2f}")

    receipt.append("-" * 34)
    receipt.append(f" TOTAL: ${final_total:>8.2f}")

    if payment_method == "CASH":
        receipt.append("-" * 34)

    receipt.append("")
    receipt.append("  THANK YOU FOR SHOPPING!")
    receipt.append(" 'Your Business, Our Priority'")
    receipt.append(f" Contacts: {branch_phone[:20]}")
    receipt.append("=" * 34)
    receipt.append("")

    return "\n".join(receipt)


# ==============================
# DEBT PAYMENT RECEIPT
# ==============================
def generate_debt_payment_receipt(
    customer_name,
    receipt_no,
    amount_paid,
    previous_balance,
    new_balance,
    cash_tendered=0,
    change=0,
    note="",
    branch_id=None,
):
    branch_name, branch_address, branch_phone, branch_email = _resolve_branch_header(branch_id)

    receipt = []

    receipt.append("=" * 52)
    receipt.append("              AZIEL INVESTMENTS")
    receipt.append("         'Your Business, Our Priority'")
    receipt.append("            DEBT PAYMENT RECEIPT")
    receipt.append("-" * 52)
    receipt.append(f"Receipt No : {receipt_no}")
    receipt.append(f"Date       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    receipt.append(f"Cashier    : {st.session_state.get('username', 'System')}")
    receipt.append("-" * 52)
    receipt.append(f"Customer   : {customer_name}")
    receipt.append("-" * 52)
    receipt.append(f"{'Previous Balance:':<32} ${previous_balance:>10,.2f}")
    receipt.append(f"{'Amount Paid:':<32} ${amount_paid:>10,.2f}")

    if cash_tendered > 0 and cash_tendered >= amount_paid:
        receipt.append(f"{'Cash Tendered:':<32} ${cash_tendered:>10,.2f}")
        receipt.append(f"{'Change:':<32} ${change:>10,.2f}")

    receipt.append("-" * 52)
    receipt.append(f"{'New Balance:':<32} ${new_balance:>10,.2f}")
    receipt.append("=" * 52)

    if new_balance <= 0:
        receipt.append("       FULLY PAID - THANK YOU!")
    else:
        receipt.append(f"   Remaining balance: ${new_balance:,.2f}")

    receipt.append("=" * 52)
    if note:
        receipt.append(f"Note: {note}")
    receipt.append("  THANK YOU FOR YOUR PAYMENT!")
    receipt.append(" 'Your Business, Our Priority'")
    receipt.append(f" {branch_name}")
    receipt.append(f" Contacts: {branch_phone}")
    receipt.append("=" * 52)

    return "\n".join(receipt)


# ==============================
# PDF RECEIPT GENERATOR
# ==============================
def generate_receipt_pdf(receipt_text):
    if not PDF_AVAILABLE:
        return None

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(80*mm, 200*mm))

    y = 260
    for line in receipt_text.split("\n"):
        if y < 20:
            c.showPage()
            y = 260
        c.drawString(5*mm, y, line[:42])
        y -= 5

    c.save()
    buffer.seek(0)

    return buffer


# ==============================
# HTML RECEIPT FOR PRINTING
# ==============================
def generate_html_receipt(
    cart,
    total_amount,
    receipt_no,
    payment_method="CASH",
    customer_name="Walk-in",
    discount_amount=0,
    tax_amount=0,
    final_total=0,
    cash_received=0,
    change=0,
    branch_id=None,
):
    branch_name, branch_address, branch_phone, branch_email = _resolve_branch_header(branch_id)

    items_html = ""
    for item in cart:
        qty = float(item['qty'])
        if qty % 1 == 0:
            qty_str = f"{int(qty)}"
        else:
            qty_str = f"{qty:.2f}"

        items_html += f"""
        <tr>
            <td style="text-align:center">{qty_str}</td>
            <td>{item['name'][:30]}</td>
            <td style="text-align:right">${item['price']:.2f}</td>
            <td style="text-align:right">${item['total']:.2f}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Aziel Investments - Receipt {receipt_no}</title>
        <style>
            @page {{ size: 80mm auto; margin: 0mm; }}
            body {{
                font-family: 'Courier New', monospace;
                font-size: 10pt; margin: 0; padding: 5mm; width: 80mm;
            }}
            .receipt {{ width: 100%; }}
            .header {{ text-align: center; margin-bottom: 10px; }}
            .header h1 {{ font-size: 14pt; margin: 0; }}
            .header h2 {{ font-size: 10pt; margin: 0; color: #555; font-style: italic; }}
            .divider {{ border-top: 1px dashed #000; margin: 5px 0; }}
            .items-table {{ width: 100%; border-collapse: collapse; }}
            .items-table th {{ text-align: left; border-bottom: 1px solid #000; padding: 3px 0; }}
            .items-table td {{ padding: 2px 0; }}
            .totals {{ text-align: right; margin-top: 10px; }}
            .footer {{ text-align: center; margin-top: 15px; font-size: 9pt; }}
            .motto {{ font-weight: bold; margin: 5px 0; }}
            @media print {{
                body {{ margin: 0; padding: 2mm; }}
                .no-print {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                <h1>AZIEL INVESTMENTS</h1>
                <h2>'Your Business, Our Priority'</h2>
                <div class="divider"></div>
                <p>Receipt: {receipt_no}<br>
                Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                Cashier: {st.session_state.get('username', 'System')}<br>
                Customer: {customer_name}<br>
                Payment: {payment_method}</p>
                <div class="divider"></div>
            </div>

            <table class="items-table">
                <thead>
                    <tr>
                        <th style="width:15%">Qty</th>
                        <th style="width:50%">Item</th>
                        <th style="width:17%">Price</th>
                        <th style="width:18%">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
            </table>

            <div class="divider"></div>

            <div class="totals">
                <p>Subtotal: ${total_amount:.2f}</p>
                {f'<p>Discount: -${discount_amount:.2f}</p>' if discount_amount > 0 else ''}
                {f'<p>Tax: +${tax_amount:.2f}</p>' if tax_amount > 0 else ''}
                <p><strong>TOTAL: ${final_total:.2f}</strong></p>
                {f'<p>Cash Tendered: ${cash_received:.2f}</p>' if cash_received > 0 else ''}
                {f'<p>Change: ${change:.2f}</p>' if change > 0 else ''}
            </div>

            <div class="divider"></div>

            <div class="footer">
                <p>THANK YOU FOR SHOPPING WITH US!</p>
                <p class="motto">'Your Business, Our Priority'</p>
                <p>{branch_name}<br>
                Contacts: {branch_phone}<br>
                Email: {branch_email}</p>
            </div>
        </div>

        <div class="no-print" style="text-align:center; margin-top:20px;">
            <button onclick="window.print()">Print Receipt</button>
        </div>
    </body>
    </html>
    """

    return html


# ==============================
# MAIN RECEIPT FUNCTION (Backward compatible)
# ==============================
def generate_receipt_standard(cart, subtotal, receipt_no, payment_method, customer_display,
                               discount_amount, tax_amount, cash_received, change, final_total):
    """Standard receipt generation - backward compatible"""
    return generate_receipt(
        cart=cart,
        total_amount=subtotal,
        receipt_no=receipt_no,
        payment_method=payment_method,
        customer_name=customer_display,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        cash_received=cash_received,
        change=change,
        final_total=final_total
    )


# ==============================
# ALIAS FOR BACKWARD COMPATIBILITY
# ==============================
# This keeps existing POS code working
generate_receipt_standard = generate_receipt