from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import IAResult
from .serializers import IAResultSerializer
from courriers.models import Courrier
from .tasks import process_courrier_automatique

class IAResultViewSet(viewsets.ModelViewSet):
    queryset = IAResult.objects.all()
    serializer_class = IAResultSerializer

    @action(detail=True, methods=["post"])
    def process_auto(self, request, pk=None):
        """
        Traite automatiquement un courrier : OCR + NLP + workflow IA
        """
        courrier = get_object_or_404(Courrier, pk=pk)
        ia_result, workflow = process_courrier_automatique(courrier)
        serializer = IAResultSerializer(ia_result)
        return Response(serializer.data, status=status.HTTP_200_OK)
