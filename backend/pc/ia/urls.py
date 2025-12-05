from rest_framework.routers import DefaultRouter
from .views import  IAResultViewSet

router = DefaultRouter()
router.register(r'ia-resultats', IAResultViewSet)


urlpatterns = router.urls
