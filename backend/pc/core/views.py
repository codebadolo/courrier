from rest_framework import viewsets, filters, permissions
from .models import Service, Category, ClassificationRule, AuditLog
from .serializers import (
    ServiceSerializer,
    CategorySerializer,
    ClassificationRuleSerializer,
    AuditLogSerializer
)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all().order_by("nom")
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["nom", "description"]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "description"]


class ClassificationRuleViewSet(viewsets.ModelViewSet):
    queryset = ClassificationRule.objects.all().order_by("priority")
    serializer_class = ClassificationRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["keyword"]
    ordering_fields = ["priority"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):  # Log = READ ONLY
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["action", "user__email"]
    ordering_fields = ["timestamp"]
