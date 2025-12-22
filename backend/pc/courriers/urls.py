from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import CourrierViewSet, CourrierCreateWithOCR, CourrierEntrantAPIView

router = DefaultRouter()
router.register(r'courriers', CourrierViewSet, basename='courrier')

urlpatterns = router.urls

# Ajouter la route POST pour OCR
urlpatterns += [
    path('create-with-ocr/', CourrierCreateWithOCR.as_view(), name='create-with-ocr'),
    path("entrant/", CourrierEntrantAPIView.as_view()),
]