from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import  FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from .models import Courrier, Imputation, PieceJointe, ActionHistorique, ModeleCourrier
from .serializers import (
    CourrierListSerializer, CourrierDetailSerializer,
    CourrierCreateSerializer, CourrierUpdateSerializer,
    ImputationSerializer, ActionHistoriqueSerializer,
    PieceJointeSerializer, ModeleCourrierSerializer,
    CourrierStatsSerializer, ImportCourrierSerializer,
    ExportCourrierSerializer
)
from workflow.services.ocr import process_ocr
from workflow.services.accuse_reception import send_accuse_reception_email
from workflow.services.classifier import classifier_courrier
from core.models import Category, Service
import uuid
import logging
import pandas as pd
import json
from datetime import datetime, timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
# from analyse_data import analyse_data

logger = logging.getLogger(__name__)


class CourrierViewSet(viewsets.ModelViewSet):
    """
    ViewSet complet pour la gestion des courriers
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet', 'expediteur_nom', 'contenu_texte']
    ordering_fields = ['created_at', 'date_reception', 'date_echeance', 'priorite']
    ordering = ['-created_at']
    
    filterset_fields = {
        'type': ['exact', 'in'],
        'statut': ['exact', 'in'],
        'priorite': ['exact', 'in'],
        'confidentialite': ['exact', 'in'],
        'canal': ['exact', 'in'],
        'category': ['exact', 'in'],
        'service_impute': ['exact', 'in'],
        'created_by': ['exact'],
        'date_reception': ['gte', 'lte', 'exact'],
        'date_echeance': ['gte', 'lte', 'exact'],
    }
    
    def get_queryset(self):
        queryset = Courrier.objects.all()
        
        # Filtrage par type
        type_courrier = self.request.query_params.get("type")
        if type_courrier:
            queryset = queryset.filter(type=type_courrier)
        
        # Filtrage par service de l'utilisateur
        if not self.request.user.is_superuser:
            user_service = self.request.user.service
            if user_service:
                queryset = queryset.filter(
                    Q(service_impute=user_service) |
                    Q(service_actuel=user_service) |
                    Q(responsable_actuel=self.request.user)
                )
        
        # Filtrage des courriers en retard
        if self.request.query_params.get("en_retard") == "true":
            queryset = queryset.filter(
                date_echeance__lt=timezone.now().date(),
                statut__in=['recu', 'impute', 'traitement']
            )
        
        # Filtrage des courriers urgents
        if self.request.query_params.get("urgent") == "true":
            queryset = queryset.filter(priorite='urgente')
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CourrierListSerializer
        elif self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return CourrierDetailSerializer
        return CourrierDetailSerializer
    
    def get_permissions(self):
        if self.request.method == 'OPTIONS':
            return [AllowAny()]
        return super().get_permissions()
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Création d'un courrier avec gestion des pièces jointes"""
        serializer = CourrierCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logger.info(f"Données reçues pour creation: {request.data}")
        
        if not serializer.is_valid():
            logger.error(f"Erreurs de validation: {serializer.errors}")
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Générer la référence
            type_courrier = serializer.validated_data.get('type', 'entrant')
            reference = self._generate_reference(type_courrier)
            
            # Créer le courrier
            courrier_data = serializer.validated_data.copy()
            courrier_data.pop('pieces_jointes', [])
            ocr_enabled = courrier_data.pop('ocr', True)
            classifier_enabled = courrier_data.pop('classifier', False)
            creer_workflow = courrier_data.pop('creer_workflow', True)
            
            courrier = Courrier.objects.create(
                reference=reference,
                created_by=request.user,
                **courrier_data
            )
            
            # Gérer les pièces jointes et OCR
            texte_ocr_global = self._process_pieces_jointes(
                request.FILES.getlist('pieces_jointes', []),
                courrier,
                request.user,
                ocr_enabled
            )
            
            if texte_ocr_global:
                courrier.contenu_texte = texte_ocr_global
                courrier.save(update_fields=['contenu_texte'])
            
            # Classification IA
            if classifier_enabled:
                self._process_classification_ia(courrier, request.user)
            
            # Créer un workflow si demandé
            if creer_workflow:
                self._creer_workflow_automatique(courrier, request.user)
            
            # Journaliser
            ActionHistorique.objects.create(
                courrier=courrier,
                user=request.user,
                action="CREATION",
                commentaire=f"Courrier {type_courrier} créé"
            )
            
            return Response(
                CourrierDetailSerializer(courrier, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Erreur création courrier: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Erreur création: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def imputer(self, request, pk=None):
        """Imputer un courrier à un service"""
        courrier = self.get_object()
        service_id = request.data.get('service_id')
        commentaire = request.data.get('commentaire', '')
        
        if not service_id:
            return Response(
                {"error": "Le service est requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = Service.objects.get(id=service_id)
            
            # Créer l'imputation
            imputation = Imputation.objects.create(
                courrier=courrier,
                service=service,
                responsable=request.user,
                commentaire=commentaire
            )
            
            # Mettre à jour le courrier
            courrier.service_impute = service
            courrier.service_actuel = service
            courrier.responsable_actuel = request.user
            courrier.statut = 'impute'
            courrier.save()
            
            # Journaliser
            ActionHistorique.objects.create(
                courrier=courrier,
                user=request.user,
                action="IMPUTATION",
                commentaire=f"Imputé au service {service.nom}"
            )
            
            return Response(
                {
                    "message": "Courrier imputé avec succès",
                    "imputation": ImputationSerializer(imputation).data
                },
                status=status.HTTP_200_OK
            )
            
        except Service.DoesNotExist:
            return Response(
                {"error": "Service non trouvé"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def traiter(self, request, pk=None):
        """Marquer un courrier comme en traitement"""
        courrier = self.get_object()
        
        if courrier.statut != 'impute':
            return Response(
                {"error": "Le courrier doit être imputé avant traitement"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        courrier.statut = 'traitement'
        courrier.save(update_fields=['statut'])
        
        ActionHistorique.objects.create(
            courrier=courrier,
            user=request.user,
            action="DEBUT_TRAITEMENT",
            commentaire="Début du traitement"
        )
        
        return Response(
            {"message": "Courrier en traitement"},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def repondre(self, request, pk=None):
        """Marquer un courrier comme répondu"""
        courrier = self.get_object()
        reponse_texte = request.data.get('reponse')
        
        if not reponse_texte:
            return Response(
                {"error": "Le texte de réponse est requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        courrier.statut = 'repondu'
        courrier.date_cloture = timezone.now().date()
        courrier.save(update_fields=['statut', 'date_cloture'])
        
        ActionHistorique.objects.create(
            courrier=courrier,
            user=request.user,
            action="REPONSE",
            commentaire=f"Réponse envoyée: {reponse_texte[:100]}..."
        )
        
        return Response(
            {"message": "Courrier marqué comme répondu"},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def archiver(self, request, pk=None):
        """Archiver un courrier"""
        courrier = self.get_object()
        
        courrier.archived = True
        courrier.date_archivage = timezone.now().date()
        courrier.save(update_fields=['archived', 'date_archivage'])
        
        ActionHistorique.objects.create(
            courrier=courrier,
            user=request.user,
            action="ARCHIVAGE",
            commentaire="Courrier archivé"
        )
        
        return Response(
            {"message": "Courrier archivé"},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """Récupérer les statistiques des courriers"""
        queryset = self.get_queryset()
        
        stats = {
            'total': queryset.count(),
            'entrants': queryset.filter(type='entrant').count(),
            'sortants': queryset.filter(type='sortant').count(),
            'internes': queryset.filter(type='interne').count(),
            'en_cours': queryset.filter(statut__in=['recu', 'impute', 'traitement']).count(),
            'en_retard': queryset.filter(
                date_echeance__lt=timezone.now().date(),
                statut__in=['recu', 'impute', 'traitement']
            ).count(),
            'traites': queryset.filter(statut='repondu').count(),
            'taux_traitement': 0,
            'delai_moyen': 0
        }
        
        # Calcul du taux de traitement
        if stats['total'] > 0:
            stats['taux_traitement'] = round((stats['traites'] / stats['total']) * 100, 2)
        
        # Calcul du délai moyen de traitement
        courriers_traites = queryset.filter(
            statut='repondu',
            date_reception__isnull=False,
            date_cloture__isnull=False
        )
        if courriers_traites.exists():
            delais = [
                (c.date_cloture - c.date_reception).days 
                for c in courriers_traites
            ]
            stats['delai_moyen'] = round(sum(delais) / len(delais), 2)
        
        serializer = CourrierStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        """Importer des courriers depuis un fichier CSV"""
        serializer = ImportCourrierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        fichier = serializer.validated_data['fichier']
        type_courrier = serializer.validated_data['type_courrier']
        mapping = serializer.validated_data.get('mapping', {})
        
        try:
            # Lire le fichier
            if fichier.name.endswith('.csv'):
                df = pd.read_csv(fichier)
            elif fichier.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(fichier)
            else:
                return Response(
                    {"error": "Format de fichier non supporté"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Appliquer le mapping
            if mapping:
                df = df.rename(columns=mapping)
            
            # Importer les courriers
            resultats = []
            for _, row in df.iterrows():
                try:
                    courrier = Courrier.objects.create(
                        reference=self._generate_reference(type_courrier),
                        type=type_courrier,
                        objet=row.get('objet', ''),
                        expediteur_nom=row.get('expediteur_nom', ''),
                        expediteur_email=row.get('expediteur_email', ''),
                        date_reception=row.get('date_reception') or timezone.now().date(),
                        created_by=request.user
                    )
                    resultats.append({
                        'reference': courrier.reference,
                        'status': 'success'
                    })
                except Exception as e:
                    resultats.append({
                        'ligne': _ + 1,
                        'status': 'error',
                        'error': str(e)
                    })
            
            return Response({
                "message": f"Import terminé: {len([r for r in resultats if r['status'] == 'success'])} succès",
                "resultats": resultats
            })
            
        except Exception as e:
            return Response(
                {"error": f"Erreur import: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def export(self, request):
        """Exporter des courriers"""
        serializer = ExportCourrierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        format = serializer.validated_data['format']
        periode_debut = serializer.validated_data.get('periode_debut')
        periode_fin = serializer.validated_data.get('periode_fin')
        type_courrier = serializer.validated_data['type_courrier']
        colonnes = serializer.validated_data['colonnes']
        
        # Filtrer les courriers
        queryset = self.get_queryset()
        if periode_debut:
            queryset = queryset.filter(date_reception__gte=periode_debut)
        if periode_fin:
            queryset = queryset.filter(date_reception__lte=periode_fin)
        if type_courrier != 'tous':
            queryset = queryset.filter(type=type_courrier)
        
        # Préparer les données
        data = []
        for courrier in queryset:
            item = {}
            for colonne in colonnes:
                if hasattr(courrier, colonne):
                    value = getattr(courrier, colonne)
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M')
                    item[colonne] = value
                elif colonne == 'category_nom' and courrier.category:
                    item[colonne] = courrier.category.name
                elif colonne == 'service_impute_nom' and courrier.service_impute:
                    item[colonne] = courrier.service_impute.nom
            data.append(item)
        
        # Exporter selon le format
        if format == 'json':
            return Response(data)
        elif format == 'csv':
            # Implémenter la génération CSV
            pass
        elif format == 'excel':
            # Implémenter la génération Excel
            pass
        elif format == 'pdf':
            # Implémenter la génération PDF
            pass
        
        return Response(
            {"message": "Export non implémenté pour ce format"},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    # Méthodes utilitaires
    def _generate_reference(self, type_courrier):
        """Générer une référence unique"""
        prefixes = {
            'entrant': 'CE',
            'sortant': 'CS',
            'interne': 'CI'
        }
        prefix = prefixes.get(type_courrier, 'CR')
        return f"{prefix}/{timezone.now().year}/{uuid.uuid4().hex[:6].upper()}"
    
    def _process_pieces_jointes(self, fichiers, courrier, user, ocr_enabled):
        """Traiter les pièces jointes et OCR"""
        texte_ocr_global = ""
        
        for fichier in fichiers:
            try:
                pj = PieceJointe.objects.create(
                    courrier=courrier,
                    fichier=fichier,
                    uploaded_by=user
                )
                
                if ocr_enabled:
                    texte = process_ocr(pj.fichier.path)
                    if texte:
                        texte_ocr_global += f"\n--- {fichier.name} ---\n{texte}\n"
                        
            except Exception as e:
                logger.error(f"Erreur pièce jointe {fichier.name}: {str(e)}")
        
        return texte_ocr_global
    
    def _process_classification_ia(self, courrier, user):
        """Traiter la classification IA"""
        try:
            result = classifier_courrier(courrier)
            
            if result and 'category' in result:
                # Mettre à jour la catégorie
                category_name = result['category']
                category = Category.objects.filter(name__icontains=category_name).first()
                if category:
                    courrier.category = category
            
            if result and 'service_impute' in result:
                # Mettre à jour le service
                service_name = result['service_impute']
                service = Service.objects.filter(nom__icontains=service_name).first()
                if service:
                    courrier.service_impute = service
                    courrier.statut = 'impute'
                    
                    # Créer l'imputation
                    Imputation.objects.create(
                        courrier=courrier,
                        service=service,
                        responsable=user,
                        suggestion_ia=True,
                        score_ia=result.get('confidence', 0.0)
                    )
            
            courrier.save()
            
            ActionHistorique.objects.create(
                courrier=courrier,
                user=user,
                action="CLASSIFICATION_IA",
                commentaire=f"Catégorie: {result.get('category', 'N/A')}"
            )
            
        except Exception as e:
            logger.error(f"Erreur classification IA: {str(e)}")
    
    def _creer_workflow_automatique(self, courrier, user):
        """Créer un workflow automatique"""
        try:
            from workflow.models import Workflow, WorkflowStep
            
            workflow = Workflow.objects.create(courrier=courrier)
            
            # Définir les étapes selon le type de courrier
            if courrier.type == 'entrant':
                steps_config = [
                    {'label': 'Réception et enregistrement', 'role': 'agent_courrier'},
                    {'label': 'Analyse préliminaire', 'role': 'chef'},
                    {'label': 'Traitement technique', 'role': 'collaborateur'},
                    {'label': 'Validation finale', 'role': 'direction'}
                ]
            elif courrier.type == 'sortant':
                steps_config = [
                    {'label': 'Rédaction', 'role': 'collaborateur'},
                    {'label': 'Visa chef de service', 'role': 'chef'},
                    {'label': 'Validation juridique', 'role': 'direction'},
                    {'label': 'Signature et envoi', 'role': 'direction'}
                ]
            else:  # interne
                steps_config = [
                    {'label': 'Rédaction', 'role': 'collaborateur'},
                    {'label': 'Validation hiérarchique', 'role': 'chef'},
                    {'label': 'Diffusion', 'role': 'agent_courrier'}
                ]
            
            # Créer les étapes
            for i, config in enumerate(steps_config, 1):
                WorkflowStep.objects.create(
                    workflow=workflow,
                    step_number=i,
                    label=config['label']
                )
            
            ActionHistorique.objects.create(
                courrier=courrier,
                user=user,
                action="WORKFLOW_CREATE",
                commentaire=f"Workflow créé avec {len(steps_config)} étapes"
            )
            
        except Exception as e:
            logger.error(f"Erreur création workflow: {str(e)}")
            
    @api_view(['GET'])
    def courriers_sortants(request):
        queryset = Courrier.objects.filter(type='sortant')
        serializer = CourrierListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
        # Dans CourrierViewSet, ajoutez cette méthode
    # @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    # def analyze_ai(self, request):
    #     """
    #     Analyse d'un courrier avec IA sans le créer
    #     """
    #     try:
    #         # Créer un objet courrier temporaire pour l'analyse
    #         courrier_data = {
    #             'objet': request.data.get('objet', ''),
    #             'expediteur_nom': request.data.get('expediteur_nom', ''),
    #             'expediteur_email': request.data.get('expediteur_email', ''),
    #             'expediteur_adresse': request.data.get('expediteur_adresse', ''),
    #             'date_reception': request.data.get('date_reception'),
    #             'canal': request.data.get('canal', 'physique'),
    #             'confidentialite': request.data.get('confidentialite', 'normale'),
    #             'priorite': request.data.get('priorite', 'normale'),
    #             'type': 'entrant'
    #         }
            
    #         # Traiter l'OCR si demandé
    #         texte_ocr = ""
    #         if request.data.get('ocr') == 'true':
    #             for fichier in request.FILES.getlist('pieces_jointes', []):
    #                 try:
    #                     # Sauvegarder temporairement le fichier
    #                     import tempfile
    #                     with tempfile.NamedTemporaryFile(delete=False, suffix=fichier.name) as tmp:
    #                         for chunk in fichier.chunks():
    #                             tmp.write(chunk)
    #                         tmp_path = tmp.name
                        
    #                     # Utiliser le service OCR
    #                     from workflow.services.ocr import process_ocr
    #                     texte = process_ocr(tmp_path, None)  # None car pas de courrier réel
    #                     if texte:
    #                         texte_ocr += f"\n--- {fichier.name} ---\n{texte}\n"
                        
    #                     # Nettoyer le fichier temporaire
    #                     import os
    #                     os.unlink(tmp_path)
                        
    #                 except Exception as e:
    #                     logger.error(f"Erreur OCR fichier {fichier.name}: {e}")
            
    #         # Analyser avec Gemini
    #         from workflow.services.gemini_courrier_service import gemini_courrier_service
            
    #         if analyse_data:
    #             return Response(analyse_data, status=status.HTTP_200_OK)
    #         else:
    #             return Response(
    #                 {
    #                     "error": "L'analyse IA a échoué",
    #                     "classification": {
    #                         "categorie_suggeree": "ADMINISTRATIF",
    #                         "service_suggere": "Secrétariat Général",
    #                         "confiance_categorie": 0.1,
    #                         "confiance_service": 0.1
    #                     },
    #                     "priorite": {
    #                         "niveau": "NORMALE",
    #                         "raison": "Échec de l'analyse IA"
    #                     }
    #                 },
    #                 status=status.HTTP_200_OK  # On retourne 200 même en cas d'erreur pour le frontend
    #             )
                
    #     except Exception as e:
    #         logger.error(f"Erreur analyse IA: {e}", exc_info=True)
    #         return Response(
    #             {"error": f"Erreur lors de l'analyse: {str(e)}"},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )

    # Dans views.py, méthode analyze_ai du CourrierViewSet

    # @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    # def analyze_ai(self, request):
    #     """
    #     Analyse d'un courrier avec IA sans le créer
    #     """
    #     try:
    #         # Créer un objet courrier temporaire pour l'analyse
    #         courrier_data = {
    #             'objet': request.data.get('objet', ''),
    #             'expediteur_nom': request.data.get('expediteur_nom', ''),
    #             'expediteur_email': request.data.get('expediteur_email', ''),
    #             'expediteur_adresse': request.data.get('expediteur_adresse', ''),
    #             'date_reception': request.data.get('date_reception'),
    #             'canal': request.data.get('canal', 'physique'),
    #             'confidentialite': request.data.get('confidentialite', 'normale'),
    #             'priorite': request.data.get('priorite', 'normale'),
    #             'type': 'entrant'
    #         }
            
    #         # Traiter l'OCR si demandé
    #         texte_ocr = ""
    #         if request.data.get('ocr') == 'true':
    #             for fichier in request.FILES.getlist('pieces_jointes', []):
    #                 try:
    #                     # Sauvegarder temporairement le fichier
    #                     import tempfile
    #                     with tempfile.NamedTemporaryFile(delete=False, suffix=fichier.name) as tmp:
    #                         for chunk in fichier.chunks():
    #                             tmp.write(chunk)
    #                         tmp_path = tmp.name
                        
    #                     # Utiliser le service OCR
    #                     from workflow.services.ocr import process_ocr
    #                     texte = process_ocr(tmp_path, None)  # None car pas de courrier réel
    #                     if texte:
    #                         texte_ocr += f"\n--- {fichier.name} ---\n{texte}\n"
                        
    #                     # Nettoyer le fichier temporaire
    #                     import os
    #                     os.unlink(tmp_path)
                        
    #                 except Exception as e:
    #                     logger.error(f"Erreur OCR fichier {fichier.name}: {e}")
            
    #         # Créer un objet courrier factice pour l'analyse
    #         class MockCourrier:
    #             def __init__(self, data, texte_ocr):
    #                 self.id = 0
    #                 self.reference = "TEMP"
    #                 self.objet = data.get('objet', '')
    #                 self.contenu_texte = texte_ocr
    #                 self.expediteur_nom = data.get('expediteur_nom', '')
    #                 self.expediteur_email = data.get('expediteur_email', '')
    #                 self.date_reception = data.get('date_reception')
    #                 self.type = data.get('type', 'entrant')
            
    #         mock_courrier = MockCourrier(courrier_data, texte_ocr)
            
    #         # Initialiser analyse_data à None
    #         analyse_data = None
            
    #         try:
    #             # Utiliser le service Gemini
    #             from workflow.services.gemini_courrier_service import gemini_courrier_service
    #             analyse_data = gemini_courrier_service.analyser_courrier(mock_courrier)
    #         except Exception as e:
    #             logger.error(f"Erreur lors de l'appel à Gemini: {e}")
    #             # En cas d'erreur, utiliser le classifieur local
    #             from workflow.services.classifier import classifier_courrier
    #             result = classifier_courrier(mock_courrier)
                
    #             # Formater la réponse
    #             analyse_data = {
    #                 "classification": {
    #                     "categorie_suggeree": result.get('category', 'ADMINISTRATIF'),
    #                     "service_suggere": result.get('service_impute', 'Secrétariat Général'),
    #                     "confiance_categorie": result.get('confidence', 0.5),
    #                     "confiance_service": result.get('confidence', 0.5)
    #                 },
    #                 "priorite": {
    #                     "niveau": result.get('priorite', 'NORMALE'),
    #                     "raison": "Analyse locale (Gemini indisponible)"
    #                 }
    #             }
            
    #         # Si analyse_data est toujours None, on retourne une analyse par défaut
    #         if not analyse_data:
    #             analyse_data = {
    #                 "classification": {
    #                     "categorie_suggeree": "ADMINISTRATIF",
    #                     "service_suggere": "Secrétariat Général",
    #                     "confiance_categorie": 0.1,
    #                     "confiance_service": 0.1
    #                 },
    #                 "priorite": {
    #                     "niveau": "NORMALE",
    #                     "raison": "Échec de l'analyse IA"
    #                 }
    #             }
            
    #         return Response(analyse_data, status=status.HTTP_200_OK)
                
    #     except Exception as e:
    #         logger.error(f"Erreur analyse IA: {e}", exc_info=True)
    #         return Response(
    #             {"error": f"Erreur lors de l'analyse: {str(e)}"},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )


    #     @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    #     def analyze(self, request):
    #         """
    #         Analyse un fichier avec OCR et IA pour pré-remplir le formulaire
    #         """
    #         fichier = request.FILES.get('fichier')
    #         if not fichier:
    #             return Response(
    #                 {"error": "Aucun fichier fourni"},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )
            
    #         # Traitement OCR
    #         texte_ocr = ""
    #         try:
    #             texte_ocr = process_ocr(fichier.temporary_file_path())
    #         except Exception as e:
    #             logger.error(f"Erreur OCR: {str(e)}")
            
    #         # Classification IA
    #         resultat_classification = {}
    #         try:
    #             # Simuler un courrier pour la classification
    #             class CourrierTemp:
    #                 def __init__(self, contenu_texte):
    #                     self.contenu_texte = contenu_texte
                
    #             courrier_temp = CourrierTemp(texte_ocr)
    #             resultat_classification = classifier_courrier(courrier_temp)
    #         except Exception as e:
    #             logger.error(f"Erreur classification IA: {str(e)}")
            
    #         # Extraction d'informations basiques
    #         import re
            
    #         infos = {
    #             'objet': '',
    #             'expediteur_nom': '',
    #             'expediteur_email': '',
    #             'expediteur_telephone': '',
    #         }
            
    #         if texte_ocr:
    #             # Extraire l'objet (première ligne significative)
    #             lines = texte_ocr.strip().split('\n')
    #             for line in lines:
    #                 if line.strip() and len(line.strip()) > 10:
    #                     infos['objet'] = line.strip()[:200]
    #                     break
                
    #             # Extraire les emails
    #             email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    #             emails = re.findall(email_pattern, texte_ocr)
    #             if emails:
    #                 infos['expediteur_email'] = emails[0]
                
    #             # Extraire les téléphones
    #             phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
    #             phones = re.findall(phone_pattern, texte_ocr)
    #             if phones:
    #                 infos['expediteur_telephone'] = phones[0][0] if isinstance(phones[0], tuple) else phones[0]
                
    #             # Essayer d'extraire le nom de l'expéditeur
    #             if "Expéditeur" in texte_ocr:
    #                 match = re.search(r'Expéditeur\s*:\s*(.*)', texte_ocr, re.IGNORECASE)
    #                 if match:
    #                     infos['expediteur_nom'] = match.group(1).strip()
    #             elif "De :" in texte_ocr:
    #                 match = re.search(r'De\s*:\s*(.*)', texte_ocr, re.IGNORECASE)
    #                 if match:
    #                     infos['expediteur_nom'] = match.group(1).strip()
            
    #         # Construire la réponse
    #         reponse = {
    #             "texte_ocr": texte_ocr,
    #             "classification": resultat_classification,
    #             "infos": infos
    #         }
            
    #         return Response(reponse, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def analyze_ai(self, request):
        """
        Analyse d'un courrier avec IA sans le créer
        """
        try:
            # Créer un objet courrier temporaire pour l'analyse
            courrier_data = {
                'objet': request.data.get('objet', ''),
                'expediteur_nom': request.data.get('expediteur_nom', ''),
                'expediteur_email': request.data.get('expediteur_email', ''),
                'expediteur_adresse': request.data.get('expediteur_adresse', ''),
                'date_reception': request.data.get('date_reception'),
                'canal': request.data.get('canal', 'physique'),
                'confidentialite': request.data.get('confidentialite', 'normale'),
                'priorite': request.data.get('priorite', 'normale'),
                'type': 'entrant'
            }
            
            # Traiter l'OCR si demandé
            texte_ocr = ""
            if request.data.get('ocr') == 'true':
                for fichier in request.FILES.getlist('pieces_jointes', []):
                    try:
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=fichier.name) as tmp:
                            for chunk in fichier.chunks():
                                tmp.write(chunk)
                            tmp_path = tmp.name
                        
                        from workflow.services.ocr import process_ocr
                        texte = process_ocr(tmp_path, None)
                        if texte:
                            texte_ocr += f"\n--- {fichier.name} ---\n{texte}\n"
                        
                        import os
                        os.unlink(tmp_path)
                        
                    except Exception as e:
                        logger.error(f"Erreur OCR fichier {fichier.name}: {e}")
            
            # Créer un courrier temporaire en base de données
            from courriers.models import Courrier
            from django.utils import timezone
            
            temp_courrier = Courrier.objects.create(
                reference="TEMP_ANALYSE_" + str(uuid.uuid4())[:8],
                type='entrant',
                objet=courrier_data.get('objet', ''),
                expediteur_nom=courrier_data.get('expediteur_nom', ''),
                expediteur_email=courrier_data.get('expediteur_email', ''),
                expediteur_adresse=courrier_data.get('expediteur_adresse', ''),
                date_reception=courrier_data.get('date_reception') or timezone.now().date(),
                canal=courrier_data.get('canal', 'physique'),
                confidentialite=courrier_data.get('confidentialite', 'normale'),
                priorite=courrier_data.get('priorite', 'normale'),
                created_by=request.user,
                contenu_texte=texte_ocr
            )
            
            analyse_data = None
            
            try:
                # Utiliser le service Gemini
                from workflow.services.gemini_courrier_service import gemini_courrier_service
                analyse_data = gemini_courrier_service.analyser_courrier(temp_courrier)
            except Exception as e:
                logger.error(f"Erreur lors de l'appel à Gemini: {e}")
                # En cas d'erreur, utiliser le classifieur local
                from workflow.services.classifier import classifier_courrier
                result = classifier_courrier(temp_courrier)
                
                # Formater la réponse
                analyse_data = {
                    "classification": {
                        "categorie_suggeree": result.get('category', 'ADMINISTRATIF'),
                        "service_suggere": result.get('service_impute', 'Secrétariat Général'),
                        "confiance_categorie": result.get('confidence', 0.5),
                        "confiance_service": result.get('confidence', 0.5)
                    },
                    "priorite": {
                        "niveau": result.get('priorite', 'NORMALE'),
                        "raison": "Analyse locale (Gemini indisponible)"
                    }
                }
            
            # Rechercher les IDs pour la catégorie et le service à partir des noms
            from core.models import Category, Service
            
            categorie_nom = analyse_data.get("classification", {}).get("categorie_suggeree")
            service_nom = analyse_data.get("classification", {}).get("service_suggere")
            
            categorie_id = None
            service_id = None
            
            if categorie_nom:
                try:
                    categorie = Category.objects.filter(name__icontains=categorie_nom).first()
                    categorie_id = categorie.id if categorie else None
                except Exception as e:
                    logger.error(f"Erreur recherche catégorie {categorie_nom}: {e}")
            
            if service_nom:
                try:
                    service = Service.objects.filter(nom__icontains=service_nom).first()
                    service_id = service.id if service else None
                except Exception as e:
                    logger.error(f"Erreur recherche service {service_nom}: {e}")
            
            # Mettre à jour l'analyse_data avec les IDs
            if 'classification' not in analyse_data:
                analyse_data['classification'] = {}
            analyse_data['classification']['categorie_id'] = categorie_id
            analyse_data['classification']['service_id'] = service_id
            
            # Supprimer le courrier temporaire
            temp_courrier.delete()
            
            return Response(analyse_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Erreur analyse IA: {e}", exc_info=True)
            return Response(
                {"error": f"Erreur lors de l'analyse: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )   
    # Ajoutez aussi cette action dans CourrierViewSet pour l'imputation rapide
    # (si ce n'est pas déjà fait)
        @action(detail=True, methods=['post'])
        def imputer_rapide(self, request, pk=None):
            """Imputation rapide d'un courrier"""
            courrier = self.get_object()
            service_id = request.data.get('service_id')
            commentaire = request.data.get('commentaire', '')
            
            if not service_id:
                return Response(
                    {"error": "Le service est requis"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                service = Service.objects.get(id=service_id)
                
                # Mettre à jour le courrier
                courrier.service_impute = service
                courrier.statut = 'impute'
                courrier.save()
                
                # Créer une imputation
                imputation = Imputation.objects.create(
                    courrier=courrier,
                    service=service,
                    responsable=request.user,
                    commentaire=commentaire
                )
                
                # Journaliser
                ActionHistorique.objects.create(
                    courrier=courrier,
                    user=request.user,
                    action="IMPUTATION_RAPIDE",
                    commentaire=f"Imputé au service {service.nom}"
                )
                
                return Response({
                    "message": "Courrier imputé avec succès",
                    "courrier_id": courrier.id,
                    "service": service.nom
                }, status=status.HTTP_200_OK)
                
            except Service.DoesNotExist:
                return Response(
                    {"error": "Service non trouvé"},
                    status=status.HTTP_404_NOT_FOUND
                )


class ImputationViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des imputations"""
    queryset = Imputation.objects.all().order_by('-date_imputation')
    serializer_class = ImputationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrer par courrier
        courrier_id = self.request.query_params.get('courrier_id')
        if courrier_id:
            queryset = queryset.filter(courrier_id=courrier_id)
        
        # Filtrer par service
        service_id = self.request.query_params.get('service_id')
        if service_id:
            queryset = queryset.filter(service_id=service_id)
        
        # Filtrage par suggestion IA
        suggestion_ia = self.request.query_params.get('suggestion_ia')
        if suggestion_ia:
            queryset = queryset.filter(suggestion_ia=(suggestion_ia.lower() == 'true'))
        
        return queryset


class PieceJointeViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des pièces jointes"""
    queryset = PieceJointe.objects.all().order_by('-uploaded_at')
    serializer_class = PieceJointeSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrer par courrier
        courrier_id = self.request.query_params.get('courrier_id')
        if courrier_id:
            queryset = queryset.filter(courrier_id=courrier_id)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
    
    # dans views.py, ajoutez cette action à la classe CourrierViewSet :



class ModeleCourrierViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des modèles de courrier"""
    queryset = ModeleCourrier.objects.filter(actif=True).order_by('nom')
    serializer_class = ModeleCourrierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom', 'contenu']
    
    @action(detail=True, methods=['post'])
    def utiliser(self, request, pk=None):
        """Utiliser un modèle pour créer un courrier"""
        modele = self.get_object()
        
        # Récupérer les variables du modèle
        variables = modele.variables
        valeurs = request.data.get('valeurs', {})
        
        # Remplacer les variables dans le contenu
        contenu = modele.contenu
        for var in variables:
            if var in valeurs:
                contenu = contenu.replace(f'{{{{ {var} }}}}', valeurs[var])
        
        return Response({
            "contenu": contenu,
            "entete": modele.entete,
            "pied_page": modele.pied_page,
            "modele": modele.nom
        })
    
# Dans views.py, ajoutez cette classe
class ImputationDashboardViewSet(viewsets.ViewSet):
    """
    ViewSet pour le dashboard d'imputation
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """
        Récupère tous les courriers en attente d'imputation
        """
        try:
            # Courriers en attente d'imputation (statut = 'recu')
            courriers_en_attente = Courrier.objects.filter(
                Q(statut='recu') | Q(service_impute__isnull=True),
                archived=False
            ).select_related('category', 'service_impute').order_by('-date_reception')
            
            # Filtrer par type si spécifié
            type_courrier = request.query_params.get('type')
            if type_courrier:
                courriers_en_attente = courriers_en_attente.filter(type=type_courrier)
            
            # Appliquer d'autres filtres
            search = request.query_params.get('search')
            if search:
                courriers_en_attente = courriers_en_attente.filter(
                    Q(objet__icontains=search) |
                    Q(reference__icontains=search) |
                    Q(expediteur_nom__icontains=search)
                )
            
            # Serializer pour l'imputation
            data = []
            for courrier in courriers_en_attente:
                # Analyser les suggestions IA si disponibles
                suggestions_ia = []
                if courrier.meta_analyse and 'classification' in courrier.meta_analyse:
                    suggestions_ia = [
                        {
                            'service_id': courrier.meta_analyse['classification'].get('service_id'),
                            'service_nom': courrier.meta_analyse['classification'].get('service_suggere'),
                            'confiance': courrier.meta_analyse['classification'].get('confiance_service', 0)
                        }
                    ]
                
                data.append({
                    'id': courrier.id,
                    'reference': courrier.reference,
                    'type': courrier.type,
                    'type_display': courrier.get_type_display(),
                    'objet': courrier.objet,
                    'expediteur_nom': courrier.expediteur_nom,
                    'expediteur_email': courrier.expediteur_email,
                    'date_reception': courrier.date_reception,
                    'category_id': courrier.category.id if courrier.category else None,
                    'category_nom': courrier.category.name if courrier.category else None,
                    'service_impute_id': courrier.service_impute.id if courrier.service_impute else None,
                    'service_impute_nom': courrier.service_impute.nom if courrier.service_impute else None,
                    'statut': courrier.statut,
                    'confidentialite': courrier.confidentialite,
                    'priorite': courrier.priorite,
                    'meta_analyse': courrier.meta_analyse,
                    'suggestions_ia': suggestions_ia,
                    'has_ia_suggestion': bool(suggestions_ia)
                })
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erreur récupération dashboard imputation: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """
        Statistiques pour le dashboard d'imputation
        """
        try:
            stats = {
                'total_en_attente': Courrier.objects.filter(
                    Q(statut='recu') | Q(service_impute__isnull=True),
                    archived=False
                ).count(),
                'entrants_en_attente': Courrier.objects.filter(
                    Q(statut='recu') | Q(service_impute__isnull=True),
                    type='entrant',
                    archived=False
                ).count(),
                'sortants_en_attente': Courrier.objects.filter(
                    Q(statut='recu') | Q(service_impute__isnull=True),
                    type='sortant',
                    archived=False
                ).count(),
                'internes_en_attente': Courrier.objects.filter(
                    Q(statut='recu') | Q(service_impute__isnull=True),
                    type='interne',
                    archived=False
                ).count(),
                'avec_suggestion_ia': Courrier.objects.filter(
                    meta_analyse__isnull=False,
                    archived=False
                ).count(),
            }
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erreur statistiques imputation: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Dans views.py, ajoutez cette action dans CourrierViewSet
@action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
def analyze_complete(self, request):
    """
    Analyse complète d'un courrier avec IA pour suggestions
    """
    try:
        # Extraire les données du formulaire
        data = {
            'objet': request.data.get('objet', ''),
            'expediteur_nom': request.data.get('expediteur_nom', ''),
            'expediteur_email': request.data.get('expediteur_email', ''),
            'expediteur_adresse': request.data.get('expediteur_adresse', ''),
            'date_reception': request.data.get('date_reception'),
            'canal': request.data.get('canal', 'physique'),
            'confidentialite': request.data.get('confidentialite', 'normale'),
            'priorite': request.data.get('priorite', 'normale'),
            'type': 'entrant'
        }
        
        # Traiter l'OCR si demandé
        texte_ocr = ""
        if request.data.get('ocr') == 'true':
            for fichier in request.FILES.getlist('pieces_jointes', []):
                try:
                    import tempfile
                    import os
                    with tempfile.NamedTemporaryFile(delete=False, suffix=fichier.name) as tmp:
                        for chunk in fichier.chunks():
                            tmp.write(chunk)
                        tmp_path = tmp.name
                    
                    from workflow.services.ocr import process_ocr
                    texte = process_ocr(tmp_path, None)
                    if texte:
                        texte_ocr += f"\n--- {fichier.name} ---\n{texte}\n"
                    
                    os.unlink(tmp_path)
                    
                except Exception as e:
                    logger.error(f"Erreur OCR fichier {fichier.name}: {e}")
        
        # Analyser avec IA
        from workflow.services.gemini_courrier_service import gemini_courrier_service
        
        # Créer un objet courrier factice
        class MockCourrier:
            def __init__(self, data, texte_ocr):
                self.id = 0
                self.reference = "TEMP_ANALYSE"
                self.objet = data.get('objet', '')
                self.contenu_texte = texte_ocr
                self.expediteur_nom = data.get('expediteur_nom', '')
                self.expediteur_email = data.get('expediteur_email', '')
                self.expediteur_adresse = data.get('expediteur_adresse', '')
                self.date_reception = data.get('date_reception')
                self.canal = data.get('canal', 'physique')
                self.confidentialite = data.get('confidentialite', 'normale')
                self.type = data.get('type', 'entrant')
        
        mock_courrier = MockCourrier(data, texte_ocr)
        analyse_data = gemini_courrier_service.analyser_courrier(mock_courrier)
        
        if not analyse_data:
            return Response(
                {"error": "L'analyse IA a échoué"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Enrichir avec les IDs des objets
        from core.models import Category, Service
        
        # Chercher la catégorie correspondante
        categorie_nom = analyse_data.get("classification", {}).get("categorie_suggeree")
        category = None
        if categorie_nom:
            category = Category.objects.filter(name__icontains(categorie_nom)).first()
        
        # Chercher le service correspondant
        service_nom = analyse_data.get("classification", {}).get("service_suggere")
        service = None
        if service_nom:
            service = Service.objects.filter(nom__icontains(service_nom)).first()
        
        # Préparer la réponse
        response_data = {
            "success": True,
            "analyse": analyse_data.get("analyse", {}),
            "classification": {
                "categorie_suggeree": categorie_nom,
                "service_suggere": service_nom,
                "categorie_id": category.id if category else None,
                "service_id": service.id if service else None,
                "confiance_categorie": analyse_data.get("classification", {}).get("confiance_categorie", 0),
                "confiance_service": analyse_data.get("classification", {}).get("confiance_service", 0)
            },
            "priorite": {
                "niveau": analyse_data.get("priorite", {}).get("niveau", "NORMALE"),
                "raison": analyse_data.get("priorite", {}).get("raison", ""),
                "confiance": 0.8  # Valeur par défaut
            },
            "metadata": {
                "timestamp": timezone.now().isoformat(),
                "ocr_applied": request.data.get('ocr') == 'true',
                "ocr_text_length": len(texte_ocr)
            }
        }
        
        # Ajouter une suggestion de confidentialité basée sur l'analyse
        confidentialite_suggestion = "normale"
        if "confidentiel" in (analyse_data.get("analyse", {}).get("resume", "") + analyse_data.get("analyse", {}).get("mots_cles", "")).lower():
            confidentialite_suggestion = "confidentielle"
        elif "restreint" in (analyse_data.get("analyse", {}).get("resume", "") + analyse_data.get("analyse", {}).get("mots_cles", "")).lower():
            confidentialite_suggestion = "restreinte"
        
        response_data["confidentialite_suggestion"] = confidentialite_suggestion
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur analyse complète: {e}", exc_info=True)
        return Response(
            {"error": f"Erreur lors de l'analyse: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )