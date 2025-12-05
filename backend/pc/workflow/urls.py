from rest_framework.routers import DefaultRouter
from .views import WorkflowViewSet, WorkflowStepViewSet, WorkflowActionViewSet

router = DefaultRouter()
router.register(r"workflows", WorkflowViewSet)
router.register(r"steps", WorkflowStepViewSet)
router.register(r"actions", WorkflowActionViewSet)

urlpatterns = router.urls
