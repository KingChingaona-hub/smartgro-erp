# backend/core/validation.py
"""
Input validation and sanitization module
"""
import re
import bleach
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

# ==============================
# VALIDATION PATTERNS
# ==============================

PATTERNS = {
    "username": r'^[a-zA-Z0-9_]{3,50}$',
    "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    "phone_zimbabwe": r'^(0|\+263)?7[7-9][0-9]{7}$',
    "barcode": r'^[a-zA-Z0-9\-_]{4,50}$',
    "product_name": r'^[a-zA-Z0-9\s\-_\.]{2,200}$',
    "category": r'^[a-zA-Z0-9\s\-_]{2,100}$',
    "amount": r'^-?\d+(\.\d{1,2})?$',  # Allow negative for returns
    "quantity": r'^-?\d+$',  # Allow negative for returns
    "branch_code": r'^[A-Z0-9]{2,10}$',
    "receipt_no": r'^[a-zA-Z0-9\-_]{4,50}$',
    "customer_name": r'^[a-zA-Z0-9\s\-_\.]{2,100}$',
    "invoice_no": r'^[a-zA-Z0-9\-_]{4,50}$',
    "po_number": r'^[a-zA-Z0-9\-_]{4,50}$',
    "supplier_name": r'^[a-zA-Z0-9\s\-_\.]{2,100}$',
    "serial_number": r'^[a-zA-Z0-9\-_]{5,50}$'
}

# ==============================
# SANITIZATION
# ==============================

def sanitize_string(value: str, max_length: int = 500) -> str:
    """
    Sanitize a string input.
    Removes dangerous HTML/script tags and truncates.
    """
    if not value or not isinstance(value, str):
        return ""
    
    # Remove HTML tags
    clean = bleach.clean(value, tags=[], strip=True)
    
    # Remove extra whitespace
    clean = ' '.join(clean.split())
    
    # Truncate
    if len(clean) > max_length:
        clean = clean[:max_length]
    
    return clean


def sanitize_html(value: str, allowed_tags: Optional[List[str]] = None) -> str:
    """
    Sanitize HTML content.
    Allows only safe tags by default.
    """
    if not value or not isinstance(value, str):
        return ""
    
    if allowed_tags is None:
        allowed_tags = [
            'strong', 'em', 'u', 'p', 'br', 'ul', 'ol', 'li',
            'b', 'i', 'pre', 'code', 'blockquote', 'h1', 'h2',
            'h3', 'h4', 'h5', 'h6', 'a', 'img', 'table', 'tr',
            'td', 'th', 'thead', 'tbody'
        ]
    
    allowed_attributes = {
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'width', 'height'],
        '*': ['class', 'id', 'style']
    }
    
    return bleach.clean(
        value,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )


# ==============================
# VALIDATION FUNCTIONS
# ==============================

def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username format"""
    if not username or not isinstance(username, str):
        return False, "Username is required"
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 50:
        return False, "Username cannot exceed 50 characters"
    
    if not re.match(PATTERNS["username"], username):
        return False, "Username can only contain letters, numbers, and underscores"
    
    return True, "Valid username"


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format"""
    if not email:
        return True, ""  # Email is optional
    
    if not isinstance(email, str):
        return False, "Invalid email format"
    
    if len(email) > 100:
        return False, "Email cannot exceed 100 characters"
    
    if not re.match(PATTERNS["email"], email):
        return False, "Invalid email format"
    
    return True, "Valid email"


def validate_phone(phone: str, country: str = "ZW") -> Tuple[bool, str]:
    """Validate phone number"""
    if not phone:
        return True, ""  # Phone is optional
    
    if not isinstance(phone, str):
        return False, "Invalid phone format"
    
    # Remove spaces and special characters
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if country == "ZW":
        if not re.match(PATTERNS["phone_zimbabwe"], clean_phone):
            return False, "Invalid Zimbabwe phone number"
        
        # Standardize format
        if clean_phone.startswith('0'):
            clean_phone = '+263' + clean_phone[1:]
        elif not clean_phone.startswith('+'):
            clean_phone = '+263' + clean_phone
    
    return True, clean_phone


def validate_barcode(barcode: str) -> Tuple[bool, str]:
    """Validate barcode format"""
    if not barcode or not isinstance(barcode, str):
        return False, "Barcode is required"
    
    if len(barcode) < 4:
        return False, "Barcode must be at least 4 characters"
    
    if len(barcode) > 50:
        return False, "Barcode cannot exceed 50 characters"
    
    if not re.match(PATTERNS["barcode"], barcode):
        return False, "Barcode can only contain letters, numbers, hyphens, and underscores"
    
    return True, "Valid barcode"


def validate_product_name(name: str) -> Tuple[bool, str]:
    """Validate product name"""
    if not name or not isinstance(name, str):
        return False, "Product name is required"
    
    if len(name) < 2:
        return False, "Product name must be at least 2 characters"
    
    if len(name) > 200:
        return False, "Product name cannot exceed 200 characters"
    
    if not re.match(PATTERNS["product_name"], name):
        return False, "Product name contains invalid characters"
    
    return True, "Valid product name"


def validate_category(category: str) -> Tuple[bool, str]:
    """Validate category name"""
    if not category or not isinstance(category, str):
        return False, "Category is required"
    
    if len(category) < 2:
        return False, "Category must be at least 2 characters"
    
    if len(category) > 100:
        return False, "Category cannot exceed 100 characters"
    
    if not re.match(PATTERNS["category"], category):
        return False, "Category contains invalid characters"
    
    return True, "Valid category"


def validate_amount(amount: Union[int, float, str]) -> Tuple[bool, float, str]:
    """
    Validate amount value.
    Allows negative values for returns/refunds.
    """
    try:
        if isinstance(amount, str):
            amount = float(amount)
        
        # Allow negative amounts for returns/refunds
        # if amount < 0:
        #     return False, 0, "Amount cannot be negative"
        
        if amount > 999999999.99:
            return False, 0, "Amount too large"
        
        # Round to 2 decimal places
        amount = round(amount, 2)
        
        return True, amount, "Valid amount"
    except (ValueError, TypeError):
        return False, 0, "Invalid amount format"


def validate_quantity(quantity: Union[int, str]) -> Tuple[bool, int, str]:
    """
    Validate quantity value.
    Allows negative values for returns (stock deduction).
    """
    try:
        if isinstance(quantity, str):
            quantity = int(quantity)
        
        # Allow negative quantities for returns
        # if quantity < 0:
        #     return False, 0, "Quantity cannot be negative"
        
        if quantity > 9999999:
            return False, 0, "Quantity too large"
        
        return True, quantity, "Valid quantity"
    except (ValueError, TypeError):
        return False, 0, "Invalid quantity format"


def validate_receipt_no(receipt_no: str) -> Tuple[bool, str]:
    """Validate receipt number"""
    if not receipt_no or not isinstance(receipt_no, str):
        return False, "Receipt number is required"
    
    if len(receipt_no) < 4:
        return False, "Receipt number must be at least 4 characters"
    
    if len(receipt_no) > 50:
        return False, "Receipt number cannot exceed 50 characters"
    
    if not re.match(PATTERNS["receipt_no"], receipt_no):
        return False, "Receipt number contains invalid characters"
    
    return True, "Valid receipt number"


def validate_customer_name(name: str) -> Tuple[bool, str]:
    """Validate customer name"""
    if not name or not isinstance(name, str):
        return False, "Customer name is required"
    
    if len(name) < 2:
        return False, "Customer name must be at least 2 characters"
    
    if len(name) > 100:
        return False, "Customer name cannot exceed 100 characters"
    
    if not re.match(PATTERNS["customer_name"], name):
        return False, "Customer name contains invalid characters"
    
    return True, "Valid customer name"


def validate_date(date_str: str, format: str = "%Y-%m-%d") -> Tuple[bool, datetime, str]:
    """Validate date string"""
    if not date_str or not isinstance(date_str, str):
        return False, None, "Date is required"
    
    try:
        date_obj = datetime.strptime(date_str, format)
        return True, date_obj, "Valid date"
    except ValueError:
        return False, None, f"Invalid date format. Expected {format}"


def validate_supplier_name(name: str) -> Tuple[bool, str]:
    """Validate supplier name"""
    if not name or not isinstance(name, str):
        return False, "Supplier name is required"
    
    if len(name) < 2:
        return False, "Supplier name must be at least 2 characters"
    
    if len(name) > 100:
        return False, "Supplier name cannot exceed 100 characters"
    
    if not re.match(PATTERNS["supplier_name"], name):
        return False, "Supplier name contains invalid characters"
    
    return True, "Valid supplier name"


def validate_branch_code(code: str) -> Tuple[bool, str]:
    """Validate branch code"""
    if not code or not isinstance(code, str):
        return False, "Branch code is required"
    
    if len(code) < 2:
        return False, "Branch code must be at least 2 characters"
    
    if len(code) > 10:
        return False, "Branch code cannot exceed 10 characters"
    
    if not re.match(PATTERNS["branch_code"], code):
        return False, "Branch code can only contain uppercase letters and numbers"
    
    return True, "Valid branch code"


def validate_serial_number(serial: str) -> Tuple[bool, str]:
    """Validate serial number"""
    if not serial or not isinstance(serial, str):
        return False, "Serial number is required"
    
    if len(serial) < 5:
        return False, "Serial number must be at least 5 characters"
    
    if len(serial) > 50:
        return False, "Serial number cannot exceed 50 characters"
    
    if not re.match(PATTERNS["serial_number"], serial):
        return False, "Serial number contains invalid characters"
    
    return True, "Valid serial number"


# ==============================
# DICTIONARY VALIDATION
# ==============================

def validate_dict(data: Dict[str, Any], rules: Dict[str, Dict]) -> Tuple[bool, Dict[str, str]]:
    """
    Validate a dictionary against rules.
    
    Example:
        rules = {
            'username': {'required': True, 'type': 'str', 'max_len': 50},
            'email': {'required': False, 'type': 'email'},
            'age': {'required': False, 'type': 'int', 'min': 0, 'max': 120}
        }
    """
    errors = {}
    
    for field, rule in rules.items():
        value = data.get(field)
        required = rule.get('required', False)
        
        # Check required
        if required and (value is None or value == ""):
            errors[field] = f"{field} is required"
            continue
        
        # Skip validation if not required and empty
        if not required and (value is None or value == ""):
            continue
        
        # Type validation
        field_type = rule.get('type', 'str')
        
        if field_type == 'str':
            if not isinstance(value, str):
                errors[field] = f"{field} must be a string"
                continue
            
            max_len = rule.get('max_len', 500)
            if len(value) > max_len:
                errors[field] = f"{field} cannot exceed {max_len} characters"
        
        elif field_type == 'int':
            try:
                value = int(value)
                min_val = rule.get('min')
                max_val = rule.get('max')
                
                if min_val is not None and value < min_val:
                    errors[field] = f"{field} must be at least {min_val}"
                if max_val is not None and value > max_val:
                    errors[field] = f"{field} cannot exceed {max_val}"
            except (ValueError, TypeError):
                errors[field] = f"{field} must be a valid number"
        
        elif field_type == 'float':
            try:
                value = float(value)
                min_val = rule.get('min')
                max_val = rule.get('max')
                
                if min_val is not None and value < min_val:
                    errors[field] = f"{field} must be at least {min_val}"
                if max_val is not None and value > max_val:
                    errors[field] = f"{field} cannot exceed {max_val}"
            except (ValueError, TypeError):
                errors[field] = f"{field} must be a valid number"
        
        elif field_type == 'email':
            if not re.match(PATTERNS["email"], str(value)):
                errors[field] = f"{field} is not a valid email"
        
        elif field_type == 'phone':
            valid, msg = validate_phone(str(value))
            if not valid:
                errors[field] = msg
        
        elif field_type == 'date':
            format = rule.get('format', '%Y-%m-%d')
            valid, _, msg = validate_date(str(value), format)
            if not valid:
                errors[field] = msg
    
    return len(errors) == 0, errors


# ==============================
# SANITIZATION HELPERS
# ==============================

def clean_input(data: Any) -> Any:
    """Recursively clean input data"""
    if isinstance(data, str):
        return sanitize_string(data)
    elif isinstance(data, dict):
        return {k: clean_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_input(item) for item in data]
    else:
        return data


def prepare_for_database(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare dictionary data for database insertion.
    Converts None to appropriate defaults.
    """
    result = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str):
            result[key] = sanitize_string(value)
        else:
            result[key] = value
    return result


# ==============================
# SECURE RANDOM GENERATORS
# ==============================

def generate_secure_id(prefix: str = "", length: int = 12) -> str:
    """Generate a secure random ID"""
    import secrets
    import string
    
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    if prefix:
        return f"{prefix}{random_part}"
    return random_part


def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ==============================
# XSS PREVENTION
# ==============================

def escape_html(text: str) -> str:
    """Escape HTML characters to prevent XSS"""
    if not text or not isinstance(text, str):
        return text
    
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;'
    }
    
    for char, escaped in replacements.items():
        text = text.replace(char, escaped)
    
    return text


def safe_json(data: Any) -> str:
    """Convert data to JSON safely"""
    import json
    
    try:
        return json.dumps(data, default=str)
    except:
        return "{}"