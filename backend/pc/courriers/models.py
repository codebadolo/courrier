from django.db import models
from django.conf import settings
from core.models import Category, Service


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


class Courrier(models.Model):
    reference = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=20, choices=TypeCourrier.choices, default=TypeCourrier.ENTRANT)

    objet = models.CharField(max_length=500)
    contenu_texte = models.TextField(blank=True, null=True)  # texte extrait via OCR/IA
    confidentialite = models.CharField(max_length=30, default='normal')

    expediteur_nom = models.CharField(max_length=255, blank=True, null=True)
    expediteur_adresse = models.TextField(blank=True, null=True)
    expediteur_email = models.EmailField(blank=True, null=True)

    destinataire_nom = models.CharField(max_length=255, blank=True, null=True)
    canal = models.CharField(max_length=50, blank=True, null=True)  # Physique, Email, Portail...

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

    class Meta:
        db_table = 'courrier_courrier'
        verbose_name = "Courrier"
        verbose_name_plural = "Courriers"
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['statut']),
            models.Index(fields=['created_at']),
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
