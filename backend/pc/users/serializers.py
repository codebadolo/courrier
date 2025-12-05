from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .models import Role, Permission, RolePermission

User = get_user_model()

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

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            raise serializers.ValidationError("Email et mot de passe requis.")

        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError("Identifiants invalides.")

        if not user.actif:
            raise serializers.ValidationError("Ce compte est désactivé.")

        data["user"] = user
        return data

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email", "nom", "prenom",
            "role", "service",
            "password"
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user

class UserDetailSerializer(serializers.ModelSerializer):
    service = serializers.StringRelatedField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email",
            "nom", "prenom",
            "role", "role_display",
            "service", "actif",
            "is_staff", "is_superuser",
            "created_at", "updated_at"
        ]

class UserListSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "prenom", "nom",
            "email",
            "role", "role_display",
        ]

class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "nom", "prenom",
            "service", "role",
            "actif",
        ]

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        return data

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

#class SignatureSerializer(serializers.ModelSerializer):
#    user = UserListSerializer(read_only=True)

#    class Meta:
#        model = Signature
#        fields = "__all__"
