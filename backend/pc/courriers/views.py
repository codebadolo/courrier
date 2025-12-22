from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from .models import Courrier, PieceJointe
from .serializers import CourrierSerializer, CourrierCreateSerializer
from workflow.services.ocr import process_ocr
from workflow.services.accuse_reception import send_accuse_reception_email
from workflow.services.classifier import classifier_courrier
from workflow.models import WorkflowAction
import uuid



class CourrierViewSet(viewsets.ModelViewSet):
    queryset = Courrier.objects.all().order_by('-created_at')
    serializer_class = CourrierSerializer


class CourrierCreateWithOCR(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        fichier = request.FILES.get("file")
        objet = request.data.get("objet")
        type_courrier = request.data.get("type")

        if not fichier or not objet or not type_courrier:
            return Response(
                {"error": "Fichier, objet et type sont requis"}, status=400
            )

        # Générer une référence unique
        reference = f"CR-{uuid.uuid4().hex[:8].upper()}"

        # Création du courrier
        courrier = Courrier.objects.create(
            reference=reference,
            objet=objet,
            type=type_courrier,
            created_by=request.user if request.user.is_authenticated else None
        )

        # Enregistrement de la pièce jointe
        pj = PieceJointe.objects.create(
            courrier=courrier,
            fichier=fichier,
            uploaded_by=request.user if request.user.is_authenticated else None
        )

        # OCR si PDF ou image
        try:
            texte = process_ocr(file_path=pj.fichier.path, courrier=courrier)
        except Exception as e:
            return Response(
                {"error": f"Impossible de traiter le fichier via OCR: {e}"},
                status=500
            )

        serializer = CourrierSerializer(courrier)
        return Response(serializer.data, status=201)



#  class CourrierEntrantCreateAPIView(APIView):
#     """
#     Enregistrement complet d’un courrier entrant
#     """
#     def post(self, request):
#         serializer = CourrierCreateSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=400)

#         data = serializer.validated_data

#         # Générer une référence automatique
#         reference = f"CE/2025/{uuid.uuid4().hex[:5].upper()}"  # exemple CE/2025/00123

#         # Création du courrier
#         courrier = Courrier.objects.create(
#             reference=reference,
#             objet=data["objet"],
#             type=data["type"],
#             confidentialite=data.get("confidentialite", "normal"),
#             date_reception=data.get("date_reception"),
#             expediteur_nom=data.get("expediteur_nom"),
#             expediteur_adresse=data.get("expediteur_adresse"),
#             expediteur_email=data.get("expediteur_email"),
#             canal=data.get("canal"),
#             category=data.get("category"),
#             service_impute=data.get("service_impute"),
#             created_by=request.user if request.user.is_authenticated else None
#         )

#         # Gestion des pièces jointes
#         fichiers = data.get("pieces_jointes", [])
#         for f in fichiers:
#             pj = PieceJointe.objects.create(
#                 courrier=courrier,
#                 fichier=f,
#                 uploaded_by=request.user if request.user.is_authenticated else None
#             )
#             # OCR automatique si demandé
#             if data.get("ocr", True):
#                 try:
#                     texte = process_ocr(file_path=pj.fichier.path, courrier=courrier)
#                 except Exception as e:
#                     return Response(
#                         {"error": f"OCR impossible pour {f.name}: {e}"},
#                         status=500
#                     )

#         serializer_out = CourrierSerializer(courrier)
#         return Response(serializer_out.data, status=201)


class CourrierEntrantAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        # --------------------------
        # Données principales
        # --------------------------
        objet = request.data.get("objet")
        confidentialite = request.data.get("confidentialite", "normal")
        date_reception = request.data.get("date_reception")
        expediteur_nom = request.data.get("expediteur_nom")
        expediteur_email = request.data.get("expediteur_email")
        canal = request.data.get("canal")
        category_id = request.data.get("category")
        service_id = request.data.get("service_impute")
        classifier = request.data.get("classifier", "false") == "true"

        ocr_enabled = request.data.get("ocr", "true") == "true"
        fichiers = request.FILES.getlist("pieces_jointes")

        if not objet:
            return Response(
                {"error": "Le champ 'objet' est obligatoire"},
                status=400
            )

        # --------------------------
        # Référence automatique
        # --------------------------
        reference = f"CE/{timezone.now().year}/{uuid.uuid4().hex[:6].upper()}"

        courrier = Courrier.objects.create(
            reference=reference,
            type="entrant",
            objet=objet,
            confidentialite=confidentialite,
            date_reception=date_reception,
            expediteur_nom=expediteur_nom,
            expediteur_email=expediteur_email,
            canal=canal,
            category_id=category_id,
            service_impute_id=service_id,
            created_by=request.user if request.user.is_authenticated else None
        )

        texte_ocr_global = ""

        # --------------------------
        # Pièces jointes + OCR
        # --------------------------
        for fichier in fichiers:
            pj = PieceJointe.objects.create(
                courrier=courrier,
                fichier=fichier,
                uploaded_by=request.user if request.user.is_authenticated else None
            )

            if ocr_enabled:
                texte = process_ocr(pj.fichier.path, courrier=None)
                texte_ocr_global += "\n" + texte

        if ocr_enabled and texte_ocr_global.strip():
            courrier.contenu_texte = texte_ocr_global
            courrier.save(update_fields=["contenu_texte"])

        from workflow.services.classifier import classifier_courrier

        # ... après OCR
        if request.data.get("classifier") == "true":
            result = classifier_courrier(courrier)
            # On met à jour le courrier
            if "category" in result:
                # si tu stockes category comme ForeignKey, récupère l'objet
                from core.models import Category
                cat = Category.objects.filter(nom=result["category"]).first()
                courrier.category = cat

            if "service_impute" in result:
                from core.models import Service
                serv = Service.objects.filter(nom=result["service_impute"]).first()
                courrier.service_impute = serv

            # si priorité existe, tu peux ajouter un champ dans le modèle
            # courrier.priority = result.get("priority", "Normal")

            courrier.save()


        if classifier:
            result = classifier_courrier(courrier)
            courrier.category = result.get("category")
            courrier.service_impute = result.get("service")
            courrier.save(update_fields=["category", "service_impute"])

            WorkflowAction.objects.create(
                courrier=courrier,
                user=request.user,
                action="Classification automatique",
                commentaire=f"Catégorie: {result.get('category')} | Service: {result.get('service')}"
            )

        # --- Accusé de réception email ---
        if canal.lower() == "email" and courrier.expediteur_email:
            send_accuse_reception_email(courrier)
            WorkflowAction.objects.create(
                courrier=courrier,
                user=request.user,
                action="Accusé de réception envoyé",
                commentaire="Envoyé par email"
            )


        return Response(
            CourrierSerializer(courrier).data,
            status=status.HTTP_201_CREATED
        )