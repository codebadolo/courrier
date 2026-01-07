from rest_framework import serializers
from django.utils import timezone
from datetime import datetime
from .models import (
    Courrier, PieceJointe, Imputation, ActionHistorique,
    ModeleCourrier, TypeCourrier, StatusCourrier, PriorityLevel
)
from core.serializers import ServiceSerializer, CategorySerializer, MiniUserSerializer
from users.serializers import UserSerializer


class PieceJointeSerializer(serializers.ModelSerializer):
    fichier_url = serializers.SerializerMethodField()
    fichier_nom = serializers.SerializerMethodField()
    fichier_taille = serializers.SerializerMethodField()
    uploaded_by_detail = MiniUserSerializer(source='uploaded_by', read_only=True)
    
    class Meta:
        model = PieceJointe
        fields = [
            'id', 'courrier', 'fichier', 'fichier_url', 'fichier_nom',
            'fichier_taille', 'description', 'uploaded_by', 'uploaded_by_detail',
            'uploaded_at'
        ]
        read_only_fields = ['uploaded_at', 'uploaded_by']
    
    def get_fichier_url(self, obj):
        request = self.context.get('request')
        if request and obj.fichier:
            return request.build_absolute_uri(obj.fichier.url)
        return None
    
    def get_fichier_nom(self, obj):
        if obj.fichier:
            return obj.fichier.name.split('/')[-1]
        return None
    
    def get_fichier_taille(self, obj):
        if obj.fichier:
            try:
                return obj.fichier.size
            except:
                return None
        return None


class ImputationSerializer(serializers.ModelSerializer):
    service_detail = ServiceSerializer(source='service', read_only=True)
    responsable_detail = UserSerializer(source='responsable', read_only=True)
    courrier_reference = serializers.CharField(source='courrier.reference', read_only=True)
    courrier_objet = serializers.CharField(source='courrier.objet', read_only=True)
    
    class Meta:
        model = Imputation
        fields = [
            'id', 'courrier', 'courrier_reference', 'courrier_objet',
            'service', 'service_detail', 'responsable', 'responsable_detail',
            'commentaire', 'suggestion_ia', 'score_ia', 'date_imputation'
        ]
        read_only_fields = ['date_imputation']


class ActionHistoriqueSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source='user', read_only=True)
    courrier_reference = serializers.CharField(source='courrier.reference', read_only=True)
    
    class Meta:
        model = ActionHistorique
        fields = [
            'id', 'courrier', 'courrier_reference', 'user', 'user_detail',
            'action', 'anciens_valeurs', 'nouvelles_valeurs', 'commentaire', 'date'
        ]
        read_only_fields = ['date']


class CourrierListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste (allégé)"""
    category_nom = serializers.CharField(source='category.name', read_only=True)
    service_impute_nom = serializers.CharField(source='service_impute.nom', read_only=True)
    expediteur_initiale = serializers.SerializerMethodField()
    jours_restants = serializers.SerializerMethodField()
    est_en_retard = serializers.SerializerMethodField()
    priorite_icone = serializers.SerializerMethodField()
    
    class Meta:
        model = Courrier
        fields = [
            'id', 'reference', 'type', 'objet', 'expediteur_nom',
            'expediteur_initiale', 'date_reception', 'date_echeance',
            'statut', 'priorite', 'priorite_icone', 'confidentialite',
            'category', 'category_nom', 'service_impute', 'service_impute_nom',
            'jours_restants', 'est_en_retard', 'created_at'
        ]
    
    def get_expediteur_initiale(self, obj):
        if obj.expediteur_nom:
            mots = obj.expediteur_nom.split()
            if len(mots) >= 2:
                return f"{mots[0][0]}{mots[1][0]}".upper()
            return obj.expediteur_nom[0:2].upper()
        return "??"
    
    def get_jours_restants(self, obj):
        if obj.date_echeance:
            delta = obj.date_echeance - timezone.now().date()
            return max(0, delta.days)
        return None
    
    def get_est_en_retard(self, obj):
        if obj.date_echeance and obj.statut not in ['repondu', 'archive']:
            return obj.date_echeance < timezone.now().date()
        return False
    
    def get_priorite_icone(self, obj):
        icones = {
            'urgente': '🔥',
            'haute': '⚠️',
            'normale': '📄',
            'basse': '📋'
        }
        return icones.get(obj.priorite, '📄')


class CourrierDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un courrier"""
    # Relations directes
    category_detail = CategorySerializer(source='category', read_only=True)
    service_impute_detail = ServiceSerializer(source='service_impute', read_only=True)
    service_actuel_detail = ServiceSerializer(source='service_actuel', read_only=True)
    responsable_actuel_detail = UserSerializer(source='responsable_actuel', read_only=True)
    created_by_detail = UserSerializer(source='created_by', read_only=True)
    
    # Relations inverses
    pieces_jointes = PieceJointeSerializer(many=True, read_only=True)
    imputations = ImputationSerializer(many=True, read_only=True)
    historiques = ActionHistoriqueSerializer(many=True, read_only=True)
    
    # Calculs
    jours_restants = serializers.SerializerMethodField()
    est_en_retard = serializers.SerializerMethodField()
    delai_traitement = serializers.SerializerMethodField()
    
    # Display fields
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    priorite_display = serializers.CharField(source='get_priorite_display', read_only=True)
    confidentialite_display = serializers.CharField(source='get_confidentialite_display', read_only=True)
    canal_display = serializers.CharField(source='get_canal_display', read_only=True)
    
    # Workflow
    workflow_existe = serializers.SerializerMethodField()
    workflow_statut = serializers.SerializerMethodField()
    
    class Meta:
        model = Courrier
        fields = [
            # Identifiants
            'id', 'reference',
            
            # Type et statut
            'type', 'type_display', 'statut', 'statut_display',
            
            # Contenu
            'objet', 'contenu_texte', 'meta_analyse', 'reponse_suggeree',
            
            # Priorité et confidentialité
            'priorite', 'priorite_display', 'confidentialite', 'confidentialite_display',
            
            # Expéditeur/Destinataire
            'expediteur_nom', 'expediteur_adresse', 'expediteur_email',
            'destinataire_nom', 'canal', 'canal_display',
            
            # Classification
            'category', 'category_detail', 'service_impute', 'service_impute_detail',
            'service_actuel', 'service_actuel_detail', 'responsable_actuel', 'responsable_actuel_detail',
            
            # Dates
            'date_reception', 'date_echeance', 'date_envoi', 'date_limite_traitement',
            'date_cloture', 'created_at', 'updated_at', 'date_archivage',
            
            # Gestion
            'created_by', 'created_by_detail', 'archived',
            
            # Codes
            'qr_code', 'barcode',
            
            # Calculs
            'jours_restants', 'est_en_retard', 'delai_traitement',
            
            # Workflow
            'workflow_existe', 'workflow_statut',
            
            # Relations
            'pieces_jointes', 'imputations', 'historiques'
        ]
        read_only_fields = [
            'reference', 'created_at', 'updated_at', 'created_by',
            'jours_restants', 'est_en_retard', 'delai_traitement',
            'workflow_existe', 'workflow_statut'
        ]
    
    def get_jours_restants(self, obj):
        if obj.date_echeance:
            delta = obj.date_echeance - timezone.now().date()
            return delta.days
        return None
    
    def get_est_en_retard(self, obj):
        if obj.date_echeance and obj.statut not in ['repondu', 'archive']:
            return obj.date_echeance < timezone.now().date()
        return False
    
    def get_delai_traitement(self, obj):
        if obj.date_reception and obj.date_cloture:
            return (obj.date_cloture - obj.date_reception).days
        elif obj.date_reception:
            return (timezone.now().date() - obj.date_reception).days
        return None
    
    def get_workflow_existe(self, obj):
        return hasattr(obj, 'workflow') and obj.workflow is not None
    
    def get_workflow_statut(self, obj):
        if hasattr(obj, 'workflow'):
            return {
                'current_step': obj.workflow.current_step,
                'total_steps': obj.workflow.steps.count() if hasattr(obj.workflow, 'steps') else 0
            }
        return None


class CourrierCreateSerializer(serializers.ModelSerializer):
    pieces_jointes = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False,
        help_text="Liste des fichiers à joindre"
    )
    ocr = serializers.BooleanField(default=True, write_only=True)
    classifier = serializers.BooleanField(default=False, write_only=True)
    creer_workflow = serializers.BooleanField(default=True, write_only=True)
    
    class Meta:
        model = Courrier
        fields = [
            'type', 'objet', 'priorite', 'confidentialite',
            'date_reception', 'expediteur_nom', 'expediteur_adresse',
            'expediteur_email', 'destinataire_nom', 'canal',
            'category', 'service_impute', 'date_echeance',
            'pieces_jointes', 'ocr', 'classifier', 'creer_workflow'
        ]
    
    def validate(self, data):
        # Validation personnalisée
        if data.get('type') == 'entrant' and not data.get('expediteur_nom'):
            raise serializers.ValidationError({
                "expediteur_nom": "L'expéditeur est obligatoire pour un courrier entrant"
            })
        
        if data.get('type') == 'sortant' and not data.get('destinataire_nom'):
            raise serializers.ValidationError({
                "destinataire_nom": "Le destinataire est obligatoire pour un courrier sortant"
            })
        
        # Date d'échéance doit être dans le futur
        if data.get('date_echeance'):
            if data['date_echeance'] < timezone.now().date():
                raise serializers.ValidationError({
                    "date_echeance": "La date d'échéance doit être dans le futur"
                })
        
        return data


class CourrierUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Courrier
        fields = [
            'objet', 'priorite', 'confidentialite',
            'date_echeance', 'category', 'service_impute',
            'service_actuel', 'responsable_actuel', 'statut'
        ]
    
    def validate_statut(self, value):
        """Validation des transitions de statut"""
        instance = self.instance
        transitions_valides = {
            'recu': ['impute', 'archive'],
            'impute': ['traitement', 'archive'],
            'traitement': ['repondu', 'archive'],
            'repondu': ['archive'],
            'archive': []
        }
        
        if instance and instance.statut in transitions_valides:
            if value not in transitions_valides[instance.statut]:
                raise serializers.ValidationError(
                    f"Transition invalide de {instance.statut} vers {value}"
                )
        
        return value


class ModeleCourrierSerializer(serializers.ModelSerializer):
    category_detail = CategorySerializer(source='category', read_only=True)
    service_detail = ServiceSerializer(source='service', read_only=True)
    type_modele_display = serializers.CharField(source='get_type_modele_display', read_only=True)
    utilisations = serializers.SerializerMethodField()
    
    class Meta:
        model = ModeleCourrier
        fields = [
            'id', 'nom', 'type_modele', 'type_modele_display',
            'category', 'category_detail', 'contenu', 'variables',
            'entete', 'pied_page', 'service', 'service_detail',
            'actif', 'utilisations', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_utilisations(self, obj):
        from courriers.models import Courrier
        return Courrier.objects.filter(
            objet__icontains=obj.nom
        ).count()


class CourrierStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    entrants = serializers.IntegerField()
    sortants = serializers.IntegerField()
    internes = serializers.IntegerField()
    en_cours = serializers.IntegerField()
    en_retard = serializers.IntegerField()
    traites = serializers.IntegerField()
    taux_traitement = serializers.FloatField()
    delai_moyen = serializers.FloatField()
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['taux_traitement'] = round(data['taux_traitement'], 2)
        data['delai_moyen'] = round(data['delai_moyen'], 2)
        return data


class ImportCourrierSerializer(serializers.Serializer):
    """Serializer pour l'import de courriers"""
    fichier = serializers.FileField(help_text="Fichier CSV ou Excel")
    type_courrier = serializers.ChoiceField(choices=TypeCourrier.choices)
    mapping = serializers.JSONField(
        default=dict,
        help_text="Mapping des colonnes (ex: {'A': 'expediteur_nom', 'B': 'objet'})"
    )


class ExportCourrierSerializer(serializers.Serializer):
    """Serializer pour l'export de courriers"""
    format = serializers.ChoiceField(choices=['csv', 'excel', 'pdf', 'json'])
    periode_debut = serializers.DateField(required=False)
    periode_fin = serializers.DateField(required=False)
    type_courrier = serializers.ChoiceField(
        choices=TypeCourrier.choices + [('tous', 'Tous')],
        default='tous'
    )
    colonnes = serializers.ListField(
        child=serializers.CharField(),
        default=['reference', 'objet', 'expediteur_nom', 'date_reception', 'statut']
    )

# courriers/serializers.py