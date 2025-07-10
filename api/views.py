
# workspace_backend/views.py
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Customer, Product, Session, Order, Invoice, Expense, ActivityLog, Settings
from .serializers import (CustomerSerializer, ProductSerializer, SessionSerializer, 
                         OrderSerializer, InvoiceSerializer, ExpenseSerializer, ActivityLogSerializer, SettingsSerializer)

from rest_framework.decorators import api_view

from django.utils.timezone import now

from . import models






class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """البحث عن عميل بالمعرف"""
        customer_id = request.query_params.get('customer_id', '')
        if customer_id:
            try:
                customer = Customer.objects.get(customer_id=customer_id)
                serializer = self.get_serializer(customer)
                return Response(serializer.data)
            except Customer.DoesNotExist:
                return Response({'error': 'العميل غير موجود'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'error': 'معرف العميل مطلوب'}, status=status.HTTP_400_BAD_REQUEST)
    
    def perform_create(self, serializer):
        customer = serializer.save()
        # تسجيل النشاط
        ActivityLog.objects.create(
            log_type='customer_created',
            customer=customer,
            description=f'تم إنشاء عميل جديد: {customer.name}'
        )

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer

class SessionViewSet(viewsets.ModelViewSet):
    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """الحصول على الجلسات النشطة"""
        active_sessions = Session.objects.filter(status='active').select_related('customer')
        serializer = self.get_serializer(active_sessions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='end_session')
    def end_session(self, request, pk=None):
        """إنهاء الجلسة وتوليد الفاتورة مع تطبيق الخصم"""
        session = self.get_object()
        if session.status != 'active':
            return Response({'error': 'الجلسة غير نشطة'}, status=status.HTTP_400_BAD_REQUEST)

        # استلام الخصم ونوعه وطريقة الدفع من الفرونت
        discount = Decimal(request.data.get('discount', '0'))
        discount_type = request.data.get('discount_type', 'fixed')
        payment_method = request.data.get('payment_method', 'cash')  # لو عايز تسجله لاحقًا

        # إنهاء الجلسة
        session.end_time = timezone.now()
        session.status = 'completed'

        # حساب تكلفة الجلسة
        duration_hours = session.duration_minutes / 60
        session_amount = Decimal(str(duration_hours)) * session.hourly_rate

        # تكلفة الطلبات
        orders_amount = session.orders.aggregate(total=Sum('total_price'))['total'] or Decimal('0')

        # المجموع قبل الخصم
        total_before_discount = session_amount + orders_amount

        # تطبيق الخصم
        if discount_type in ['percent', 'percentage']:
            discount_amount = (total_before_discount * discount) / Decimal('100')
        else:
            discount_amount = discount


        # المجموع النهائي بعد الخصم
        final_total = total_before_discount - discount_amount

        # تحديث بيانات الجلسة
        session.total_amount = final_total
        session.discount = discount_amount
        session.save()

        # توليد رقم الفاتورة
        invoice_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{session.id}"

        # إنشاء الفاتورة
        invoice = Invoice.objects.create(
                    session=session,
                    invoice_number=invoice_number,
                    session_amount=session_amount,
                    orders_amount=orders_amount,
                    total_amount=final_total,
                    discount=discount_amount,
                    payment_method=payment_method
            )


        # تسجيل الخصم (لو فيه خصم فعلي)
        if discount_amount > 0:
            ActivityLog.objects.create(
                log_type='discount_applied',
                customer=session.customer,
                amount=discount_amount,
                description=f"تم تطبيق خصم {discount}% ({discount_type}) على جلسة العميل {session.customer.name}"
            )

        # تسجيل النشاطات
        ActivityLog.objects.create(
            log_type='session_ended',
            customer=session.customer,
            amount=final_total,
            description=f'انتهت جلسة العميل {session.customer.name} - مدة: {session.duration_minutes} دقيقة'
        )

        ActivityLog.objects.create(
            log_type='invoice_generated',
            customer=session.customer,
            amount=invoice.total_amount,
            description=f'تم توليد الفاتورة {invoice_number}'
        )

        return Response({
            'session': SessionSerializer(session).data,
            'invoice': InvoiceSerializer(invoice).data
        })

class OrderViewSet(viewsets.ModelViewSet):
        queryset = Order.objects.all()
        serializer_class = OrderSerializer
        
        def perform_create(self, serializer):
            order = serializer.save()
            # تسجيل النشاط
            ActivityLog.objects.create(
                log_type='order_created',
                customer=order.session.customer,
                amount=order.total_price,
                description=f'طلب جديد: {order.product.name} x{order.quantity}'
            )
        # في OrderViewSet
        @action(detail=True, methods=['get'])
        def kitchen_receipt(self, request, pk=None):
            order = self.get_object()
            session = order.session
            product = order.product

            lines = []
            lines.append("===== طلب مطبخ =====")
            lines.append(f"العميل: {session.customer.name}")
            lines.append(f"الوقت: {order.created_at.strftime('%Y-%m-%d %H:%M')}")
            lines.append("------------------")
            lines.append(f"{product.name} × {order.quantity}")
            lines.append("===================")

            return Response({"receipt": "\n".join(lines)})
            

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    
    @action(detail=False, methods=['get'])
    def daily_revenue(self, request):
        """الأرباح اليومية"""
        today = timezone.now().date()
        daily_invoices = Invoice.objects.filter(created_at__date=today)
        total = daily_invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        return Response({'date': today, 'total_revenue': total, 'invoices_count': daily_invoices.count()})
    
    @action(detail=False, methods=['get'])
    def monthly_revenue(self, request):
        """الأرباح الشهرية"""
        today = timezone.now().date()
        month_start = today.replace(day=1)
        monthly_invoices = Invoice.objects.filter(created_at__date__gte=month_start)
        total = monthly_invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        return Response({'month': month_start.strftime('%Y-%m'), 'total_revenue': total, 'invoices_count': monthly_invoices.count()})
    
    @action(detail=True, methods=['get'])
    def print_receipt(self, request, pk=None):
        invoice = self.get_object()
        session = invoice.session
        orders = session.orders.all()

        lines = []
        lines.append("======== إيصال ========")
        lines.append(f"العميل: {session.customer.name}")
        lines.append(f"التاريخ: {invoice.created_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("------------------------")

        for order in orders:
            lines.append(f"{order.product.name} x{order.quantity} - {order.total_price}ج")

        lines.append("------------------------")
        lines.append(f"جلسة: {invoice.session_amount}ج")
        lines.append(f"طلبات: {invoice.orders_amount}ج")
        if invoice.discount > 0:
            lines.append(f"خصم: -{invoice.discount}ج")
        lines.append(f"الإجمالي: {invoice.total_amount}ج")
        lines.append(f"الدفع: {invoice.payment_method}")
        lines.append("========================")

        receipt_text = "\n".join(lines)
        return Response({"receipt": receipt_text})

class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    
    @action(detail=False, methods=['get'])
    def monthly_expenses(self, request):
        """المصروفات الشهرية"""
        today = timezone.now().date()
        month_start = today.replace(day=1)
        monthly_expenses = Expense.objects.filter(date__gte=month_start)
        total = monthly_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return Response({'month': month_start.strftime('%Y-%m'), 'total_expenses': total, 'expenses_count': monthly_expenses.count()})
    
    def perform_create(self, serializer):
        expense = serializer.save()
        # تسجيل النشاط
        ActivityLog.objects.create(
            log_type='expense_added',
            amount=expense.amount,
            description=f'تم إضافة مصروف: {expense.get_type_display()} - {expense.amount} جنيه'
        )

class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer


    
class SettingsViewSet(viewsets.ModelViewSet):
    queryset = Settings.objects.all()
    serializer_class = SettingsSerializer
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """الحصول على الإعدادات الحالية"""
        settings = Settings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)

from django.utils.timezone import now, make_aware
from django.utils.timezone import localtime
from datetime import datetime, time

@api_view(['GET'])
def dashboard_summary(request):
    today = localtime().date()


    # استخدم make_aware لضمان توقيت واضح
    start_today = make_aware(datetime.combine(today, time.min))
    end_today = make_aware(datetime.combine(today, time.max))

    first_day_of_month = today.replace(day=1)
    start_of_month = make_aware(datetime.combine(first_day_of_month, time.min))
    end_of_today = end_today

    # جلب البيانات
    invoices = Invoice.objects.all()

    today_total = invoices.filter(created_at__range=(start_today, end_today)).aggregate(total=Sum('total_amount'))['total'] or 0
    monthly_total = invoices.filter(created_at__range=(start_of_month, end_of_today)).aggregate(total=Sum('total_amount'))['total'] or 0
    total_expenses = Expense.objects.filter(created_at__range=(start_of_month, end_of_today)).aggregate(total=Sum('amount'))['total'] or 0
    net_profit = monthly_total - total_expenses

    active_sessions_count = Session.objects.filter(status='active').count()
    total_customers = Customer.objects.count()
    settings_data = SettingsSerializer(Settings.get_settings()).data

    return Response({
        "settings": settings_data,
        "daily_revenue": today_total,
        "monthly_revenue": monthly_total,
        "monthly_expenses": total_expenses,
        "net_profit": net_profit,
        "active_sessions_count": active_sessions_count,
        "total_customers": total_customers,
        "date": today,
        "month": today.strftime('%Y-%m'),
    })
