from rest_framework import serializers
from .models import Courrier, PieceJointe, Imputation, ActionHistorique

class PieceJointeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceJointe
        fields = "__all__"

class ImputationSerializer(serializers.ModelSerializer):
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    responsable_nom = serializers.CharField(source="responsable.get_full_name", read_only=True)
    
    class Meta:
        model = Imputation
        fields = "__all__"

class ActionHistoriqueSerializer(serializers.ModelSerializer):
    user_nom = serializers.CharField(source="user.get_full_name", read_only=True)
    
    class Meta:
        model = ActionHistorique
        fields = "__all__"

class CourrierSerializer(serializers.ModelSerializer):
    pieces_jointes = PieceJointeSerializer(many=True, read_only=True)
    imputations = ImputationSerializer(many=True, read_only=True)
    historiques = ActionHistoriqueSerializer(many=True, read_only=True)
    
    class Meta:
        model = Courrier
        fields = "__all__"
