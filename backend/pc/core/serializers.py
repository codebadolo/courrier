from rest_framework import serializers
from .models import Service, Category, ClassificationRule, AuditLog


class ServiceSerializer(serializers.ModelSerializer):
    chef_name = serializers.CharField(source="chef.get_full_name", read_only=True)

    class Meta:
        model = Service
        fields = [
            "id", "nom", "description",
            "chef", "chef_name",
            "created_at"
        ]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "created_at"]


class ClassificationRuleSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.nom", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = ClassificationRule
        fields = [
            "id",
            "keyword",
            "service", "service_name",
            "category", "category_name",
            "priority",
            "active"
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user", "user_email",
            "action",
            "timestamp",
            "metadata"
        ]
        read_only_fields = ["timestamp"]
