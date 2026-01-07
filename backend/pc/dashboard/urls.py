from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RapportStatistiqueViewSet

router = DefaultRouter()
router.register(r"rapports", RapportStatistiqueViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
