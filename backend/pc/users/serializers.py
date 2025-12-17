from rest_framework import serializers
from .models import User, Role, Permission, RolePermission
from core.models import Service

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nom",
            "prenom",
            "role",
            "service",
            "actif",
        ]

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(email=email, password=password)
            if not user:
                raise serializers.ValidationError("Email ou mot de passe incorrect")
            attrs["user"] = user
            return attrs
        raise serializers.ValidationError("Email et mot de passe sont requis")

# -------------------------
# User serializers
# -------------------------
class UserListSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    service_name = serializers.CharField(source="service.nom", read_only=True)  # Nom du service
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            "id",
            "prenom",
            "nom",
            "full_name",
            "email",
            "role",
            "role_display",
            "service_name",
            "actif",
            "is_staff",
            "created_at",
            "updated_at",
        ]
    
    def get_full_name(self, obj):
        return f"{obj.prenom} {obj.nom}"

class UserDetailSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    service_name = serializers.CharField(source="service.nom", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "prenom",
            "nom",
            "full_name",
            "email",
            "role",
            "role_display",
            "service",
            "service_name",
            "actif",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
            "created_at",
            "updated_at",
        ]
    
    def get_full_name(self, obj):
        return f"{obj.prenom} {obj.nom}"

class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "prenom", "nom", "role", "service", "password"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

# users/serializers.py
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'prenom', 'nom', 'role', 'service', 'actif']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        return data

# -------------------------
# Roles & permissions
# -------------------------
class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = "__all__"

class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "nom", "description", "created_at", "permissions"]

    def get_permissions(self, obj):
        perms = Permission.objects.filter(rolepermission__role=obj)
        return PermissionSerializer(perms, many=True).data

class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = "__all__"
