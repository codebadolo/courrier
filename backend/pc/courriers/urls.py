from rest_framework.routers import DefaultRouter
from .views import CourrierViewSet
router = DefaultRouter()
router.register(r'courriers', CourrierViewSet)
router.register(r'create-with-ocr', CourrierViewSet, basename='create-with-ocr')


urlpatterns = router.urls
