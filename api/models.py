from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum, F, DecimalField


class Customer(models.Model):
    customer_id = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="معرف العميل")
    name = models.CharField(max_length=100, verbose_name="اسم العميل")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="رقم الهاتف", db_index=True)
    email = models.EmailField(blank=True, null=True, verbose_name="البريد الإلكتروني", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "عميل"
        verbose_name_plural = "العملاء"

    def __str__(self):
        return f"{self.name} ({self.customer_id})"


class Product(models.Model):
    name = models.CharField(max_length=100, verbose_name="اسم المنتج")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="السعر")
    category = models.CharField(max_length=50, default="مشروبات", verbose_name="الفئة", db_index=True)
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "منتج"
        verbose_name_plural = "المنتجات"

    def __str__(self):
        return f"{self.name} - {self.price} جنيه"


class Session(models.Model):
    STATUS_CHOICES = [
        ('active', 'نشط'),
        ('completed', 'مكتمل'),
        ('expired', 'منتهي'),
    ]
    SESSION_TYPE_CHOICES = [
        ('open', 'مفتوح'),
        ('timed', 'محدد بوقت'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="sessions", verbose_name="العميل")
    start_time = models.DateTimeField(default=timezone.now, verbose_name="وقت البداية", db_index=True)
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="وقت النهاية")
    planned_duration = models.DurationField(null=True, blank=True, verbose_name="المدة المخططة")
    session_type = models.CharField(max_length=10, choices=SESSION_TYPE_CHOICES, default='open', verbose_name="نوع الجلسة", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="الحالة", db_index=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10.00'), verbose_name="سعر الساعة")
    total_before_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="المبلغ قبل الخصم")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="المبلغ بعد الخصم")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="خصم")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "جلسة"
        verbose_name_plural = "الجلسات"
        ordering = ['-start_time']

    def __str__(self):
        return f"جلسة {self.customer.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration_minutes(self):
        if self.end_time:
            return int((self.end_time - self.start_time).total_seconds() / 60)
        return int((timezone.now() - self.start_time).total_seconds() / 60)

    @property
    def is_near_expiry(self):
        if self.session_type == 'timed' and self.planned_duration:
            expected_end = self.start_time + self.planned_duration
            return (expected_end - timezone.now()).total_seconds() <= 600
        return False

    @property
    def is_expired(self):
        if self.session_type == 'timed' and self.planned_duration:
            return timezone.now() > (self.start_time + self.planned_duration)
        return False

    def update_totals(self):
        orders_total = self.orders.aggregate(
            total=Sum(F('unit_price') * F('quantity'), output_field=DecimalField())
        )['total'] or Decimal('0.00')

        self.total_before_discount = orders_total
        self.total_amount = orders_total - self.discount
        self.save(update_fields=["total_before_discount", "total_amount"])


class Order(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='orders', verbose_name="الجلسة")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="المنتج")
    quantity = models.PositiveIntegerField(default=1, verbose_name="الكمية")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر الوحدة")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="السعر الإجمالي")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت الطلب")

    class Meta:
        verbose_name = "طلب"
        verbose_name_plural = "الطلبات"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
        self.session.update_totals()

    def __str__(self):
        return f"{self.product.name} x{self.quantity} - {self.session.customer.name}"


class Invoice(models.Model):
    session = models.OneToOneField(Session, on_delete=models.CASCADE, verbose_name="الجلسة")
    invoice_number = models.CharField(max_length=50, unique=True, verbose_name="رقم الفاتورة", db_index=True)
    session_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="مبلغ الجلسة")
    orders_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="مبلغ الطلبات")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ الإجمالي")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, default='cash', db_index=True)

    class Meta:
        verbose_name = "فاتورة"
        verbose_name_plural = "الفواتير"
        ordering = ['-created_at']

    def __str__(self):
        return f"فاتورة {self.invoice_number} - {self.session.customer.name}"


class Expense(models.Model):
    EXPENSE_TYPES = [
        ('electricity', 'كهرباء'),
        ('water', 'مياه'),
        ('rent', 'إيجار'),
        ('internet', 'إنترنت'),
        ('maintenance', 'صيانة'),
        ('supplies', 'مستلزمات'),
        ('other', 'أخرى'),
    ]

    type = models.CharField(max_length=20, choices=EXPENSE_TYPES, verbose_name="نوع المصروف", db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ")
    description = models.TextField(blank=True, null=True, verbose_name="الوصف")
    date = models.DateField(default=timezone.now, verbose_name="التاريخ", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "مصروف"
        verbose_name_plural = "المصروفات"
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} جنيه"


class ActivityLog(models.Model):
    LOG_TYPES = [
        ('customer_created', 'إنشاء عميل جديد'),
        ('session_started', 'بدء جلسة'),
        ('session_ended', 'انتهاء جلسة'),
        ('order_created', 'طلب جديد'),
        ('invoice_generated', 'توليد فاتورة'),
        ('expense_added', 'إضافة مصروف'),
    ]

    log_type = models.CharField(max_length=30, choices=LOG_TYPES, verbose_name="نوع الحدث", db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="العميل")
    staff_name = models.CharField(max_length=100, default="مدير النظام", verbose_name="اسم الموظف")
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="المبلغ")
    description = models.TextField(blank=True, null=True, verbose_name="التفاصيل")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="الوقت")

    class Meta:
        verbose_name = "سجل نشاط"
        verbose_name_plural = "سجل الأنشطة"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_log_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class Settings(models.Model):
    workspace_name = models.CharField(max_length=100, default="مساحة العمل", verbose_name="اسم المكان")
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10.00'), verbose_name="سعر الساعة الافتراضي")
    currency = models.CharField(max_length=10, default="جنيه", verbose_name="العملة")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="نسبة الضريبة")
    warning_minutes = models.IntegerField(default=10, verbose_name="تحذير قبل انتهاء الجلسة (بالدقائق)")

    class Meta:
        verbose_name = "إعدادات"
        verbose_name_plural = "إعدادات النظام"

    def __str__(self):
        return self.workspace_name

    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
