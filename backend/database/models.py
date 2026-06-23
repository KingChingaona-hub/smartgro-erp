# backend/database/models.py
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, 
    ForeignKey, Text, JSON, Numeric, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from .config import Base

class TimestampMixin:
    """Mixin for timestamp fields"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class TenantMixin:
    """Mixin for multi-tenant support"""
    tenant_id = Column(String(50), nullable=False, default="default", index=True)

class User(Base, TimestampMixin, TenantMixin):
    """User model"""
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_tenant_email", "tenant_id", "email"),
        Index("idx_users_tenant_username", "tenant_id", "username"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), nullable=False, default="cashier")
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    login_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<User {self.username}>"

class Product(Base, TimestampMixin, TenantMixin):
    """Product model"""
    __tablename__ = "products"
    __table_args__ = (
        Index("idx_products_tenant_sku", "tenant_id", "sku"),
        Index("idx_products_tenant_category", "tenant_id", "category"),
        Index("idx_products_tenant_status", "tenant_id", "status"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    barcode = Column(String(50), unique=True)
    category = Column(String(100))
    sub_category = Column(String(100))
    brand = Column(String(100))
    supplier = Column(String(200))
    
    # Pricing
    unit_price = Column(Numeric(10, 2), nullable=False)
    cost_price = Column(Numeric(10, 2))
    selling_price = Column(Numeric(10, 2))
    tax_rate = Column(Float, default=0.0)
    
    # Inventory
    current_stock = Column(Integer, default=0)
    min_stock_level = Column(Integer, default=5)
    max_stock_level = Column(Integer, default=100)
    reorder_point = Column(Integer, default=10)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Analytics
    view_count = Column(Integer, default=0)
    purchase_count = Column(Integer, default=0)
    
    # Additional data
    images = Column(JSON, default=[])
    attributes = Column(JSON, default={})
    
    def __repr__(self):
        return f"<Product {self.name} ({self.sku})>"

class Sale(Base, TimestampMixin, TenantMixin):
    """Sale model"""
    __tablename__ = "sales"
    __table_args__ = (
        Index("idx_sales_tenant_invoice", "tenant_id", "invoice_number"),
        Index("idx_sales_tenant_date", "tenant_id", "sale_date"),
        Index("idx_sales_tenant_status", "tenant_id", "status"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Customer info
    customer_name = Column(String(100))
    customer_email = Column(String(100))
    customer_phone = Column(String(20))
    
    # Financials
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax = Column(Numeric(10, 2), default=0)
    discount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), default=0)
    
    # Payment
    payment_method = Column(String(50))
    payment_status = Column(String(20), default="pending")
    status = Column(String(20), default="completed")
    
    # Dates
    sale_date = Column(DateTime, default=datetime.utcnow, index=True)
    notes = Column(Text)
    
    # Relationships
    user = relationship("User")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Sale {self.invoice_number}>"

class SaleItem(Base, TimestampMixin, TenantMixin):
    """Sale item model"""
    __tablename__ = "sale_items"
    __table_args__ = (
        Index("idx_sale_items_tenant_sale", "tenant_id", "sale_id"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id"))
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    
    product_name = Column(String(200))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    discount = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), nullable=False)
    
    # Relationships
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")
    
    def __repr__(self):
        return f"<SaleItem {self.product_name} x{self.quantity}>"

class Customer(Base, TimestampMixin, TenantMixin):
    """Customer model"""
    __tablename__ = "customers"
    __table_args__ = (
        Index("idx_customers_tenant_code", "tenant_id", "customer_code"),
        Index("idx_customers_tenant_email", "tenant_id", "email"),
        Index("idx_customers_tenant_phone", "tenant_id", "phone"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100))
    phone = Column(String(20))
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(50))
    
    # Loyalty
    loyalty_points = Column(Integer, default=0)
    total_purchases = Column(Integer, default=0)
    total_spent = Column(Numeric(10, 2), default=0)
    
    # Dates
    customer_since = Column(DateTime, default=datetime.utcnow)
    last_purchase_date = Column(DateTime)
    
    # Status
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    
    def __repr__(self):
        return f"<Customer {self.name}>"

class AuditLog(Base, TimestampMixin, TenantMixin):
    """Audit log model"""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_user_date", "user_id", "created_at"),
        Index("idx_audit_logs_action", "action"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String(50), nullable=False)
    resource = Column(String(50))
    resource_id = Column(String(50))
    details = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(255))
    
    # Relationship
    user = relationship("User")
    
    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id}>"