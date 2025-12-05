from rest_framework import serializers
from .models import Courrier, PieceJointe, Imputation, ActionHistorique
from core.serializers import CategorySerializer, ServiceSerializer
from users.serializers import UserSerializer

class PieceJointeSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = PieceJointe
        fields = '__all__'

class CourrierSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    service_impute = ServiceSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    pieces_jointes = PieceJointeSerializer(many=True, read_only=True)
    imputations = serializers.StringRelatedField(many=True, read_only=True)
    historiques = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Courrier
        fields = '__all__'

class ImputationSerializer(serializers.ModelSerializer):
    courrier = CourrierSerializer(read_only=True)
    service = ServiceSerializer(read_only=True)
    responsable = UserSerializer(read_only=True)

    class Meta:
        model = Imputation
        fields = '__all__'

class ActionHistoriqueSerializer(serializers.ModelSerializer):
    courrier = CourrierSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = ActionHistorique
        fields = '__all__'
