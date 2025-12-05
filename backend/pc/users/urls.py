from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuthViewSet, UserViewSet, RoleViewSet,
    PermissionViewSet, RolePermissionViewSet
)

router = DefaultRouter()
router.register("auth", AuthViewSet, basename="auth")
router.register("users", UserViewSet, basename="users")
router.register("roles", RoleViewSet, basename="roles")
router.register("permissions", PermissionViewSet, basename="permissions")
router.register("role-permissions", RolePermissionViewSet, basename="role-permissions")


urlpatterns = [
    path("", include(router.urls))
]
