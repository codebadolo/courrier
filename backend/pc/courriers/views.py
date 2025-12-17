# courriers/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.utils import timezone
from .models import Courrier, PieceJointe, Imputation, ActionHistorique
from .serializers import CourrierSerializer, PieceJointeSerializer
from workflow.models import Workflow, WorkflowStep
from workflow.services.gemini import classify_courrier_with_gemini
from workflow.services.ocr import process_ocr
from core.models import Category, Service

class CourrierViewSet(viewsets.ModelViewSet):
    queryset = Courrier.objects.all().order_by('-created_at')
    serializer_class = CourrierSerializer

    def perform_create(self, serializer):
        # Création du courrier
        courrier = serializer.save(created_at=timezone.now(), created_by=self.request.user)

        # Création du workflow associé
        workflow = Workflow.objects.create(courrier=courrier, current_step=1)

        # Traitement des pièces jointes (OCR)
        if courrier.pieces_jointes.exists():
            for pj in courrier.pieces_jointes.all():
                text_extracted = process_ocr(pj.fichier.path)
                if text_extracted:
                    courrier.contenu_texte = (courrier.contenu_texte or "") + "\n" + text_extracted
            courrier.save()

        # Classification automatique avec Gemini
        if courrier.contenu_texte:
            result = classify_courrier_with_gemini(courrier.contenu_texte)
            # Affectation catégorie et service
            category = Category.objects.filter(nom=result.get("categorie")).first()
            service = Service.objects.filter(nom=result.get("service")).first()
            if category:
                courrier.category = category
            if service:
                courrier.service_impute = service
            courrier.save()

            # Création de l’imputation automatique
            if service:
                Imputation.objects.create(
                    courrier=courrier,
                    service=service,
                    responsable=service.chef if hasattr(service, 'chef') else None,
                    suggestion_ia=True,
                    score_ia=result.get("score", None),
                    date_imputation=timezone.now()
                )

        # Historique
        ActionHistorique.objects.create(
            courrier=courrier,
            user=self.request.user,
            action="Création du courrier et workflow initialisé",
            date=timezone.now()
        )

    def update(self, request, *args, **kwargs):
        # Update du courrier classique
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_at=timezone.now())

        # Historique
        ActionHistorique.objects.create(
            courrier=instance,
            user=request.user,
            action="Mise à jour du courrier",
            anciens_valeurs=str(instance.__dict__),
            nouvelles_valeurs=str(serializer.validated_data),
            date=timezone.now()
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
