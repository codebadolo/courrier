from datetime import date
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import RapportStatistique
from .serializers import RapportStatistiqueSerializer


class RapportStatistiqueViewSet(viewsets.ModelViewSet):
    queryset = RapportStatistique.objects.all()
    serializer_class = RapportStatistiqueSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Filtrer par période : ?start=2024-01-01&end=2024-01-31
    def get_queryset(self):
        qs = super().get_queryset()

        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")

        if start:
            qs = qs.filter(periode_debut__gte=start)
        if end:
            qs = qs.filter(periode_fin__lte=end)

        return qs

    @action(detail=False, methods=["post"])
    def generer(self, request):
        """
        Génère un rapport automatique – exemple d’analyse :
        - nombre de courriers entrants / sortants
        - workflow stats
        - services les plus actifs
        - etc.
        """

        titre = request.data.get("titre", "Rapport Automatique")
        periode_debut = request.data.get("periode_debut")
        periode_fin = request.data.get("periode_fin")

        if not (periode_debut and periode_fin):
            return Response({"detail": "Veuillez fournir les dates."}, status=400)

        # ⚠️ Exemple de données fictives (à connecter avec tes modèles réels)
        data = {
            "nombre_courriers": 128,
            "courriers_par_service": {
                "RH": 35,
                "Finance": 50,
                "Direction": 43,
            },
            "workflow_stats": {
                "validés": 105,
                "rejetés": 8,
                "en_attente": 15,
            }
        }

        rapport = RapportStatistique.objects.create(
            titre=titre,
            periode_debut=periode_debut,
            periode_fin=periode_fin,
            data=data,
            generated_by=request.user.email
        )

        return Response(RapportStatistiqueSerializer(rapport).data, status=201)
