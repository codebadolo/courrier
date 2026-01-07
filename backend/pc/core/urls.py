from rest_framework.routers import DefaultRouter
from .views import (
    ServiceViewSet,
    CategoryViewSet,
    ClassificationRuleViewSet,
    AuditLogViewSet
)

router = DefaultRouter()
router.register(r"services", ServiceViewSet)
router.register(r"categories", CategoryViewSet)
router.register(r"rules", ClassificationRuleViewSet)
router.register(r"auditlogs", AuditLogViewSet)

urlpatterns = router.urls