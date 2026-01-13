from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CourrierViewSet, ImputationViewSet,
    PieceJointeViewSet, ModeleCourrierViewSet,
    ImputationDashboardViewSet
    
)

router = DefaultRouter()
router.register(r"courriers", CourrierViewSet, basename="courrier")
router.register(r"imputations", ImputationViewSet, basename="imputation")
router.register(r"pieces-jointes", PieceJointeViewSet, basename="piecejointe")
router.register(r"modeles", ModeleCourrierViewSet, basename="modelecourrier")
router.register(r"imputation-dashboard", ImputationDashboardViewSet, basename="imputation-dashboard")

urlpatterns = [
    path('', include(router.urls)),
    path('courriers/analyze_complete/', CourrierViewSet.as_view({'post': 'analyze_complete'}), name='analyze-complete'),
]