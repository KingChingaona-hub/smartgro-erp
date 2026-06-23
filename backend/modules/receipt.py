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
    final_total=0
):
    """Generate professional receipt with proper alignment"""
    
    receipt = []
    
    # ==============================
    # HEADER SECTION
    # ==============================
    receipt.append("=" * 48)
    receipt.append("         AZIEL INVESTMENTS")
    receipt.append("      SMART RETAIL ERP SYSTEM")
    receipt.append("-" * 48)
    receipt.append(f"Receipt No: {receipt_no}")
    receipt.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    receipt.append(f"Cashier: {st.session_state.get('username', 'System')}")
    receipt.append(f"Customer: {customer_name}")
    receipt.append(f"Payment: {payment_method}")
    receipt.append("=" * 48)
    
    # ==============================
    # TABLE HEADER (Aligned columns)
    # ==============================
    receipt.append("")
    receipt.append("QTY  ITEM                         PRICE     TOTAL")
    receipt.append("-" * 48)
    
    # ==============================
    # ITEMS SECTION (Proper alignment)
    # ==============================
    for item in cart:
        name = item['name'][:28]  # Truncate long names
        qty = int(item['qty'])
        price = float(item['price'])
        total = float(item['total'])
        
        # Format with proper spacing
        # Column widths: QTY(4) + ITEM(28) + PRICE(8) + TOTAL(8) = 48
        receipt.append(f"{qty:<4} {name:<28} ${price:>7.2f} ${total:>7.2f}")
    
    receipt.append("-" * 48)
    
    # ==============================
    # SUMMARY SECTION
    # ==============================
    receipt.append(f"{'SUBTOTAL:':>40} ${total_amount:>7.2f}")
    
    if discount_amount > 0:
        receipt.append(f"{'DISCOUNT:':>40} -${discount_amount:>7.2f}")
    
    if tax_amount > 0:
        receipt.append(f"{'TAX:':>40} +${tax_amount:>7.2f}")
    
    receipt.append("-" * 48)
    receipt.append(f"{'FINAL TOTAL:':>40} ${final_total:>7.2f}")
    
    if payment_method == "CASH":
        receipt.append(f"{'AMOUNT TENDERED:':>40} ${cash_received:>7.2f}")
        receipt.append(f"{'CHANGE:':>40} ${change:>7.2f}")
    
    # ==============================
    # FOOTER SECTION
    # ==============================
    receipt.append("=" * 48)
    receipt.append("        THANK YOU FOR SHOPPING!")
    receipt.append("-" * 48)
    receipt.append("     Aziel Investments - Retreat Park")
    receipt.append("         Contact: 0782 905 853")
    receipt.append("     Email: info@azielinvestments.co.zw")
    receipt.append("=" * 48)
    
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
    loyalty_points_used=0
):
    """Generate premium receipt with loyalty and branding"""
    
    receipt = []
    
    # ==============================
    # HEADER WITH BRANDING
    # ==============================
    receipt.append("")
    receipt.append("╔══════════════════════════════════════════════════╗")
    receipt.append("║                                                    ║")
    receipt.append("║             ╔══════════════════════╗              ║")
    receipt.append("║             ║   AZIEL INVESTMENTS   ║              ║")
    receipt.append("║             ╚══════════════════════╝              ║")
    receipt.append("║                                                    ║")
    receipt.append("║           SMART RETAIL ERP SYSTEM                  ║")
    receipt.append("║                                                    ║")
    receipt.append("╠════════════════════════════════════════════════════╣")
    receipt.append(f"║ Receipt No: {receipt_no:<37}║")
    receipt.append(f"║ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<39}║")
    receipt.append(f"║ Cashier: {st.session_state.get('username', 'System'):<37}║")
    receipt.append(f"║ Customer: {customer_name:<37}║")
    if customer_phone:
        receipt.append(f"║ Phone: {customer_phone:<40}║")
    receipt.append(f"║ Payment: {payment_method:<38}║")
    receipt.append("╠════════════════════════════════════════════════════╣")
    
    # ==============================
    # ITEMS TABLE
    # ==============================
    receipt.append("║                                                    ║")
    receipt.append("║  QTY  ITEM                     PRICE      TOTAL   ║")
    receipt.append("║  ──────────────────────────────────────────────── ║")
    
    for item in cart:
        name = item['name'][:24]
        qty = int(item['qty'])
        price = float(item['price'])
        total = float(item['total'])
        
        receipt.append(f"║  {qty:<3}  {name:<24} ${price:>6.2f}   ${total:>7.2f} ║")
    
    receipt.append("║  ──────────────────────────────────────────────── ║")
    
    # ==============================
    # TOTALS
    # ==============================
    receipt.append(f"║  {'SUBTOTAL:':<37} ${total_amount:>7.2f} ║")
    
    if discount_amount > 0:
        if discount_percent > 0:
            receipt.append(f"║  {'DISCOUNT (' + str(discount_percent) + '%):':<37} -${discount_amount:>6.2f} ║")
        else:
            receipt.append(f"║  {'DISCOUNT:':<37} -${discount_amount:>6.2f} ║")
    
    if tax_amount > 0:
        if tax_percent > 0:
            receipt.append(f"║  {'TAX (' + str(tax_percent) + '%):':<37} +${tax_amount:>6.2f} ║")
        else:
            receipt.append(f"║  {'TAX:':<37} +${tax_amount:>6.2f} ║")
    
    receipt.append("║  ──────────────────────────────────────────────── ║")
    receipt.append(f"║  {'FINAL TOTAL:':<37} ${final_total:>7.2f} ║")
    
    if payment_method == "CASH":
        receipt.append(f"║  {'AMOUNT TENDERED:':<37} ${cash_received:>7.2f} ║")
        receipt.append(f"║  {'CHANGE:':<37} ${change:>7.2f} ║")
    
    # ==============================
    # LOYALTY POINTS
    # ==============================
    if loyalty_points_earned > 0:
        receipt.append("╠════════════════════════════════════════════════════╣")
        receipt.append(f"║  ⭐ LOYALTY POINTS EARNED: {loyalty_points_earned:<21}║")
    
    if loyalty_points_used > 0:
        receipt.append(f"║  🎁 POINTS REDEEMED: {loyalty_points_used:<26}║")
    
    # ==============================
    # FOOTER
    # ==============================
    receipt.append("╠════════════════════════════════════════════════════╣")
    receipt.append("║                                                    ║")
    receipt.append("║         THANK YOU FOR SHOPPING WITH US!            ║")
    receipt.append("║                                                    ║")
    receipt.append("║  🏪 Aziel Investments - Retreat Park, Harare       ║")
    receipt.append("║  📞 Contact: 0782 905 853                          ║")
    receipt.append("║  📧 Email: info@azielinvestments.co.zw             ║")
    receipt.append("║  🌐 Web: www.azielinvestments.co.zw                ║")
    receipt.append("║                                                    ║")
    receipt.append("║     Follow us on social media for updates!         ║")
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
    final_total=0
):
    """Generate receipt optimized for 58mm thermal printers"""
    
    receipt = []
    
    # Header
    receipt.append("")
    receipt.append(" AZIEL INVESTMENTS")
    receipt.append(" Smart Retail ERP")
    receipt.append("-" * 32)
    receipt.append(f" Receipt: {receipt_no}")
    receipt.append(f" Date: {datetime.now().strftime('%d/%m/%y %H:%M')}")
    receipt.append(f" Cashier: {st.session_state.get('username', 'System')[:12]}")
    receipt.append(f" Customer: {customer_name[:20]}")
    receipt.append("-" * 32)
    
    # Items
    receipt.append(" QTY ITEM          PRICE")
    for item in cart:
        name = item['name'][:12]
        qty = int(item['qty'])
        price = float(item['price'])
        total = float(item['total'])
        receipt.append(f" {qty:>2}  {name:<12} ${price:>5.2f}")
        receipt.append(f"                   ${total:>7.2f}")
    
    receipt.append("-" * 32)
    receipt.append(f" TOTAL: ${final_total:>8.2f}")
    
    if payment_method == "CASH":
        receipt.append("-" * 32)
    
    receipt.append("")
    receipt.append(" THANK YOU!")
    receipt.append(" Aziel Investments")
    receipt.append("=" * 32)
    receipt.append("")
    
    return "\n".join(receipt)


# ==============================
# DEBT PAYMENT RECEIPT
# ==============================
def generate_debt_payment_receipt(customer_name, receipt_no, amount_paid, previous_balance, new_balance, cash_tendered=0, change=0, note=""):
    """Generate receipt for debt payment"""
    
    receipt = []
    
    # Header
    receipt.append("=" * 48)
    receipt.append("         AZIEL INVESTMENTS")
    receipt.append("       DEBT PAYMENT RECEIPT")
    receipt.append("-" * 48)
    receipt.append(f"Receipt No: {receipt_no}")
    receipt.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    receipt.append(f"Cashier: {st.session_state.get('username', 'System')}")
    receipt.append("-" * 48)
    receipt.append(f"Customer: {customer_name}")
    receipt.append("-" * 48)
    receipt.append(f"{'Previous Balance:':<30} ${previous_balance:>10,.2f}")
    receipt.append(f"{'Amount Paid:':<30} ${amount_paid:>10,.2f}")
    
    if cash_tendered > 0 and cash_tendered >= amount_paid:
        receipt.append(f"{'Cash Tendered:':<30} ${cash_tendered:>10,.2f}")
        receipt.append(f"{'Change:':<30} ${change:>10,.2f}")
    
    receipt.append("-" * 48)
    receipt.append(f"{'New Balance:':<30} ${new_balance:>10,.2f}")
    receipt.append("=" * 48)
    
    if new_balance <= 0:
        receipt.append("      ✓ FULLY PAID - THANK YOU!")
    else:
        receipt.append(f"   Remaining balance: ${new_balance:,.2f}")
    
    receipt.append("=" * 48)
    if note:
        receipt.append(f"Note: {note}")
    receipt.append("Thank you for your payment!")
    receipt.append("Aziel Investments - Retreat Park, Harare")
    receipt.append("Contact: 0782 905 853")
    receipt.append("=" * 48)
    
    return "\n".join(receipt)


# ==============================
# PDF RECEIPT GENERATOR
# ==============================
def generate_receipt_pdf(receipt_text):
    """Generate PDF from receipt text"""
    
    if not PDF_AVAILABLE:
        return None

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(80*mm, 200*mm))  # Thermal receipt size
    
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
    change=0
):
    """Generate HTML receipt for browser printing"""
    
    items_html = ""
    for item in cart:
        items_html += f"""
        <tr>
            <td style="text-align:center">{item['qty']}</td>
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
            @page {{
                size: 80mm auto;
                margin: 0mm;
            }}
            body {{
                font-family: 'Courier New', monospace;
                font-size: 10pt;
                margin: 0;
                padding: 5mm;
                width: 80mm;
            }}
            .receipt {{
                width: 100%;
            }}
            .header {{
                text-align: center;
                margin-bottom: 10px;
            }}
            .header h1 {{
                font-size: 14pt;
                margin: 0;
            }}
            .header h2 {{
                font-size: 10pt;
                margin: 0;
                color: #666;
            }}
            .divider {{
                border-top: 1px dashed #000;
                margin: 5px 0;
            }}
            .items-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .items-table th {{
                text-align: left;
                border-bottom: 1px solid #000;
                padding: 3px 0;
            }}
            .items-table td {{
                padding: 2px 0;
            }}
            .totals {{
                text-align: right;
                margin-top: 10px;
            }}
            .footer {{
                text-align: center;
                margin-top: 15px;
                font-size: 8pt;
            }}
            @media print {{
                body {{
                    margin: 0;
                    padding: 2mm;
                }}
                .no-print {{
                    display: none;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                <h1>AZIEL INVESTMENTS</h1>
                <h2>Smart Retail ERP System</h2>
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
                <p>THANK YOU FOR SHOPPING!</p>
                <p>Aziel Investments - Retreat Park, Harare<br>
                Contact: 0782 905 853<br>
                Email: info@azielinvestments.co.zw</p>
            </div>
        </div>
        
        <div class="no-print" style="text-align:center; margin-top:20px;">
            <button onclick="window.print()">🖨️ Print Receipt</button>
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