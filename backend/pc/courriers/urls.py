from rest_framework.routers import DefaultRouter
from .views import CourrierViewSet, PieceJointeViewSet, ImputationViewSet, ActionHistoriqueViewSet

router = DefaultRouter()
router.register(r'courriers', CourrierViewSet)
router.register(r'pieces', PieceJointeViewSet)
router.register(r'imputations', ImputationViewSet)
router.register(r'historiques', ActionHistoriqueViewSet)

urlpatterns = router.urls
