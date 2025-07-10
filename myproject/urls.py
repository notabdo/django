# workspace_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api import views

# إنشاء Router للـ API
router = DefaultRouter()
router.register(r'customers', views.CustomerViewSet)
router.register(r'products', views.ProductViewSet)
router.register(r'sessions', views.SessionViewSet)
router.register(r'orders', views.OrderViewSet)
router.register(r'invoices', views.InvoiceViewSet)
router.register(r'expenses', views.ExpenseViewSet)
router.register(r'activity-logs', views.ActivityLogViewSet)
router.register(r'settings', views.SettingsViewSet)

# بدل router.register للـ dashboard
from api.views import dashboard_summary

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('api/dashboard/stats/', dashboard_summary),  # ✅ هنا بدون as_view
]

