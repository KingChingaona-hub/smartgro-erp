import re

# ==============================
# ZIMBABWE PHONE NUMBER VALIDATION
# ==============================

def validate_zimbabwe_phone(phone):
    """
    Validate and standardize Zimbabwe phone numbers
    Supports formats:
    - 0777123456
    - 0777 123 456
    - +263777123456
    - 263777123456
    - 0712345678
    """
    if not phone:
        return False, "", "Phone number is required"
    
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', str(phone))
    
    # Check length and format
    if len(cleaned) == 9:
        # Format: 0777123456 -> needs leading 0? Actually 9 digits is too short
        # Assume it's missing first digit
        if cleaned.startswith('7') or cleaned.startswith('71'):
            cleaned = '0' + cleaned
        else:
            return False, "", f"Invalid phone format: {phone}"
    
    if len(cleaned) == 10:
        # Format: 0777123456
        if cleaned.startswith('07') or cleaned.startswith('071'):
            standardized = cleaned
        else:
            return False, "", f"Invalid Zimbabwe phone: must start with 07"
    
    elif len(cleaned) == 11:
        # Format: 263777123456
        if cleaned.startswith('263'):
            standardized = '0' + cleaned[3:]
        else:
            return False, "", f"Invalid Zimbabwe phone: {phone}"
    
    elif len(cleaned) == 12:
        # Format: +263777123456
        if cleaned.startswith('263'):
            standardized = '0' + cleaned[3:]
        else:
            return False, "", f"Invalid phone: {phone}"
    
    else:
        return False, "", f"Phone number must be 10 digits (e.g., 0777123456)"
    
    # Final validation: should start with 07
    if not standardized.startswith('07'):
        return False, "", f"Zimbabwe phone numbers must start with 07"
    
    return True, standardized, "Valid"


def format_phone_display(phone):
    """Format phone for display: 0777 123 456"""
    phone = re.sub(r'\D', '', str(phone))
    if len(phone) >= 10:
        return f"{phone[:4]} {phone[4:7]} {phone[7:10]}"
    return phone


def get_whatsapp_link(phone, message):
    """Generate WhatsApp link with standardized phone"""
    import urllib.parse
    
    # Standardize phone for WhatsApp (international format without +)
    phone = re.sub(r'\D', '', str(phone))
    if phone.startswith('0'):
        phone = '263' + phone[1:]
    
    encoded_msg = urllib.parse.quote(message)
    return f"https://wa.me/{phone}?text={encoded_msg}"