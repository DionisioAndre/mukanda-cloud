"""backend/apps/accounts/urls.py"""
from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import LoginView, CompanyViewSet, DepartmentViewSet, UserViewSet, CrossDeptPermViewSet, MeView

router = SimpleRouter()
router.register('companies',           CompanyViewSet,       basename='company')
router.register('departments',         DepartmentViewSet,    basename='department')
router.register('users',               UserViewSet,          basename='user')
router.register('cross-dept-permissions', CrossDeptPermViewSet, basename='cross-dept-perm')

urlpatterns = [
    path('token/',          LoginView.as_view(),  name='token_obtain_pair'),
    path('me/',             MeView.as_view(),     name='me'),
    path('', include(router.urls)),
]
