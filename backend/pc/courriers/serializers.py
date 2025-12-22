from rest_framework import serializers
from .models import Courrier, PieceJointe, Imputation, ActionHistorique

class PieceJointeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceJointe
        fields = "__all__"
        read_only_fields = ('courrier''uploaded_at', 'uploaded_by')

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
    reference = serializers.CharField(read_only=True)
    category = serializers.CharField(source="category.nom", read_only=True)
    service_impute = serializers.CharField(source="service_impute.nom", read_only=True)

    class Meta:
        model = Courrier
        fields = "__all__"
        read_only_fields = ('reference','created_by')

class CourrierCreateOCRSerializer(serializers.ModelSerializer):
    class Meta:
        model = Courrier
        fields = [
            "objet",
            "type",
            "confidentialite",
            "date_reception",
        ]

class CourrierCreateSerializer(serializers.ModelSerializer):
    pieces_jointes = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )
    ocr = serializers.BooleanField(default=True, write_only=True)  # Case à cocher OCR

    class Meta:
        model = Courrier
        fields = [
            "objet",
            "type",
            "confidentialite",
            "date_reception",
            "expediteur_nom",
            "expediteur_adresse",
            "expediteur_email",
            "canal",
            "category",
            "service_impute",
            "pieces_jointes",
            "ocr"
        ]