from django.db import models
from django.conf import settings
from core.models import Category, Service
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q


class TypeCourrier(models.TextChoices):
    ENTRANT = 'entrant', 'Entrant'
    SORTANT = 'sortant', 'Sortant'
    INTERNE = 'interne', 'Interne'


class StatusCourrier(models.TextChoices):
    RECU = 'recu', 'Reçu'
    IMPUTE = 'impute', 'Imputé'
    TRAITEMENT = 'traitement', 'En traitement'
    REPONDU = 'repondu', 'Répondu'
    ARCHIVE = 'archive', 'Archivé'

class PriorityLevel(models.TextChoices):
    BASSE = 'basse', 'Basse'
    NORMALE = 'normale', 'Normale'
    HAUTE = 'haute', 'Haute'
    URGENTE = 'urgente', 'Urgente'

class Courrier(models.Model):
    # Champs pour l'IA
    meta_analyse = models.JSONField(default=dict, blank=True, null=True)  # Stocke l'analyse Gemini
    reponse_suggeree = models.TextField(blank=True, null=True)  # Réponse suggérée par IA
    
    priorite = models.CharField(
        max_length=20,
        choices=[
            ('basse', 'Basse'),
            ('normale', 'Normale'),
            ('haute', 'Haute'),
            ('urgente', 'Urgente'),
        ],
        default='normale'
    )
    
    reference = models.CharField(max_length=100, unique=True, blank=True)
    type = models.CharField(max_length=20, choices=TypeCourrier.choices)
    
    objet = models.CharField(max_length=500)
    contenu_texte = models.TextField(blank=True, null=True)  # texte extrait via OCR/IA
    
    expediteur_nom = models.CharField(max_length=255, blank=True, null=True)
    expediteur_adresse = models.TextField(blank=True, null=True)
    expediteur_email = models.EmailField(blank=True, null=True)
    expediteur_telephone = models.CharField(max_length=20, blank=True, null=True)
    destinataire_nom = models.CharField(max_length=255, blank=True, null=True)
    
    # Canal de réception/émission
    CANAL_CHOICES = [
        ('physique', 'Physique'),
        ('email', 'Email'),
        ('portail', 'Portail'),
        ('telephone', 'Téléphone'),
        ('autre', 'Autre'),
    ]
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES, default='physique')
    
    # Confidentialité
    CONFIDENTIALITE_CHOICES = [
        ('normale', 'Normale'),
        ('restreinte', 'Restreinte'),
        ('confidentielle', 'Confidentielle'),
    ]
    confidentialite = models.CharField(
        max_length=20, 
        choices=CONFIDENTIALITE_CHOICES, 
        default='normale'
    )
    
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    service_impute = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    
    statut = models.CharField(max_length=30, choices=StatusCourrier.choices, default=StatusCourrier.RECU)
    
    date_reception = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    date_envoi = models.DateField(null=True, blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='courriers_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    archived = models.BooleanField(default=False)
    date_archivage = models.DateField(null=True, blank=True)
    date_limite_traitement = models.DateField(null=True, blank=True)
    date_cloture = models.DateField(null=True, blank=True)
    
    qr_code = models.CharField(max_length=100, blank=True, null=True, unique=True)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    
    # Pour l'imputation multiple (un courrier peut passer par plusieurs services)
    service_actuel = models.ForeignKey(
        Service, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='courriers_actuels'
    )
    responsable_actuel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courriers_encours'
    )

    class Meta:
        db_table = 'courrier_courrier'
        verbose_name = "Courrier"
        verbose_name_plural = "Courriers"
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['statut']),
            models.Index(fields=['created_at']),
            models.Index(fields=['priorite']),
        ]

    def __str__(self):
        return self.reference
class PieceJointe(models.Model):
    courrier = models.ForeignKey(Courrier, on_delete=models.CASCADE, related_name='pieces_jointes')
    fichier = models.FileField(upload_to='courriers/pieces/')
    description = models.CharField(max_length=255, blank=True, null=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'courrier_piecejointe'
        verbose_name = "Pièce jointe"
        verbose_name_plural = "Pièces jointes"

    def __str__(self):
        return f"PJ - {self.courrier.reference}"


class Imputation(models.Model):
    courrier = models.ForeignKey(Courrier, on_delete=models.CASCADE, related_name='imputations')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    commentaire = models.TextField(blank=True, null=True)
    suggestion_ia = models.BooleanField(default=False)
    score_ia = models.FloatField(null=True, blank=True)  # confiance de la suggestion IA
    date_imputation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'courrier_imputation'
        verbose_name = "Imputation"
        verbose_name_plural = "Imputations"

    def __str__(self):
        return f"Imputation {self.courrier.reference} -> {self.service and self.service.nom}"


class ActionHistorique(models.Model):
    courrier = models.ForeignKey(Courrier, on_delete=models.CASCADE, related_name='historiques')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    anciens_valeurs = models.TextField(blank=True, null=True)
    nouvelles_valeurs = models.TextField(blank=True, null=True)
    commentaire = models.TextField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'courrier_historique'
        verbose_name = "Historique action"
        verbose_name_plural = "Historique actions"

    def __str__(self):
        return f"{self.date} - {self.action}"


# dans courriers/models.py ou créer templates/models.py

class ModeleCourrier(models.Model):
    TYPE_CHOICES = [
        ('entrant', 'Réponse à courrier entrant'),
        ('sortant', 'Courrier sortant standard'),
        ('interne', 'Note interne'),
    ]
    
    nom = models.CharField(max_length=200)
    type_modele = models.CharField(max_length=20, choices=TYPE_CHOICES)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    contenu = models.TextField()  # Template avec variables {{ }}
    variables = models.JSONField(default=list)  # Liste des variables disponibles
    entete = models.TextField(blank=True, null=True)
    pied_page = models.TextField(blank=True, null=True)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'courrier_modele'
        
    def __str__(self):
        return self.nom
    

class CourrierService:
    @staticmethod
    def get_courrier_stats(service_id):
        cache_key = f'courrier_stats_{service_id}'
        stats = cache.get(cache_key)
        if not stats:
            stats = Courrier.objects.filter(
                service_impute_id=service_id,
                date_reception__gte=timezone.now() - timedelta(days=30)
            ).aggregate(
                total=Count('id'),
                en_cours=Count('id', filter=Q(statut='traitement')),
                en_retard=Count('id', filter=Q(date_echeance__lt=timezone.now()))
            )
            cache.set(cache_key, stats, timeout=300)  # 5 minutes
        return stats