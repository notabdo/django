# workspace_backend/serializers.py
from rest_framework import serializers
from .models import Customer, Product, Session, Order, Invoice, Expense, ActivityLog, Settings
from django.utils import timezone
from decimal import Decimal
import uuid

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'session', 'product', 'quantity', 'unit_price', 'total_price', 'created_at', 'product_name']
    
    def create(self, validated_data):
        # التأكد من حساب السعر الإجمالي
        if 'unit_price' not in validated_data:
            validated_data['unit_price'] = validated_data['product'].price
        return super().create(validated_data)

class SessionSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_id = serializers.CharField(source='customer.customer_id', read_only=True)
    orders = OrderSerializer(many=True, read_only=True)
    duration_minutes = serializers.ReadOnlyField()
    is_near_expiry = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = Session
        fields = ['id', 'customer', 'customer_name', 'customer_id', 'start_time', 'end_time', 
                 'planned_duration', 'session_type', 'status', 'hourly_rate', 'total_amount',
                 'orders', 'duration_minutes', 'is_near_expiry', 'is_expired', 'created_at']

from .models import Order  # لو مش مستوردها




class InvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='session.customer.name', read_only=True)
    session_duration = serializers.IntegerField(source='session.duration_minutes', read_only=True)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    payment_method = serializers.CharField(read_only=True)
    orders = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'session_amount',
            'orders_amount',
            'discount',
            'total_amount',
            'payment_method',
            'customer_name',
            'session_duration',
            'created_at',
            'orders'
        ]

    def get_orders(self, obj):
        orders = Order.objects.filter(session=obj.session)
        return OrderSerializer(orders, many=True).data


class ExpenseSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = Expense
        fields = ['id', 'type', 'type_display', 'amount', 'description', 'date', 'created_at']

class ActivityLogSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    
    class Meta:
        model = ActivityLog
        fields = ['id', 'log_type', 'log_type_display', 'customer', 'customer_name', 
                 'staff_name', 'amount', 'description', 'created_at']

class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settings
        fields = '__all__'
