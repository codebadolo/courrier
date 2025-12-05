from rest_framework import viewsets, permissions
from .models import Courrier, PieceJointe, Imputation, ActionHistorique
from .serializers import CourrierSerializer, PieceJointeSerializer, ImputationSerializer, ActionHistoriqueSerializer

class CourrierViewSet(viewsets.ModelViewSet):
    queryset = Courrier.objects.all().order_by('-created_at')
    serializer_class = CourrierSerializer
    permission_classes = [permissions.IsAuthenticated]

class PieceJointeViewSet(viewsets.ModelViewSet):
    queryset = PieceJointe.objects.all().order_by('-uploaded_at')
    serializer_class = PieceJointeSerializer
    permission_classes = [permissions.IsAuthenticated]

class ImputationViewSet(viewsets.ModelViewSet):
    queryset = Imputation.objects.all().order_by('-date_imputation')
    serializer_class = ImputationSerializer
    permission_classes = [permissions.IsAuthenticated]

class ActionHistoriqueViewSet(viewsets.ModelViewSet):
    queryset = ActionHistorique.objects.all().order_by('-date')
    serializer_class = ActionHistoriqueSerializer
    permission_classes = [permissions.IsAuthenticated]
