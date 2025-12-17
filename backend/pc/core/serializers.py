from rest_framework import serializers
from .models import Service, Category, ClassificationRule, AuditLog

from users.models import User


class MiniUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "prenom", "nom", "email"]
        read_only_fields = fields


class ServiceSerializer(serializers.ModelSerializer):
    chef_detail = MiniUserSerializer(source="chef", read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "nom",
            "description",
            "chef",          # ID du chef → pour l'édition
            "chef_detail",   # Détails du chef → pour l'affichage
            "created_at",
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
