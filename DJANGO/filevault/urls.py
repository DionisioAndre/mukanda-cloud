"""backend/filevault/urls.py"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/logout/',  TokenBlacklistView.as_view(), name='token_blacklist'),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/files/', include('apps.files.urls')),
    path('api/audit/', include('apps.audit.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
