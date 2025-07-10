
# workspace_backend/admin.py
from django.contrib import admin
from .models import Customer, Product, Session, Order, Invoice, Expense, ActivityLog, Settings

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'name', 'phone', 'created_at']
    search_fields = ['customer_id', 'name', 'phone']
    list_filter = ['created_at']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'start_time', 'end_time', 'status', 'total_amount']
    list_filter = ['status', 'session_type', 'start_time']
    search_fields = ['customer__name', 'customer__customer_id']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['session', 'product', 'quantity', 'total_price', 'created_at']
    list_filter = ['created_at', 'product']

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'session', 'total_amount', 'created_at']
    search_fields = ['invoice_number', 'session__customer__name']
    list_filter = ['created_at']

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['type', 'amount', 'date', 'description']
    list_filter = ['type', 'date']

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['log_type', 'customer', 'staff_name', 'amount', 'created_at']
    list_filter = ['log_type', 'created_at']
    search_fields = ['customer__name', 'staff_name']

@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ['workspace_name', 'hourly_rate', 'currency']
    
    def has_add_permission(self, request):
        return not Settings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False