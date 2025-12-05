from django.db import models
from django.conf import settings
from courriers.models import Courrier


class Workflow(models.Model):
    courrier = models.OneToOneField(Courrier, on_delete=models.CASCADE, related_name='workflow')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    current_step = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'workflow_workflow'
        verbose_name = "Workflow"
        verbose_name_plural = "Workflows"

    def __str__(self):
        return f"Workflow - {self.courrier.reference}"


class WorkflowStep(models.Model):
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='steps')
    step_number = models.PositiveIntegerField()
    label = models.CharField(max_length=200)
    validator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    approbateur_service = models.ForeignKey('core.Service', on_delete=models.SET_NULL, null=True, blank=True)
    statut = models.CharField(
        max_length=30,
        choices=[
            ('en_attente', 'En attente'),
            ('valide', 'Validé'),
            ('rejete', 'Rejeté'),
            ('brouillon', 'Brouillon'),
        ],
        default='en_attente'
    )
    commentaire = models.TextField(blank=True, null=True)
    date_action = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'workflow_step'
        unique_together = ('workflow', 'step_number')
        ordering = ['step_number']

    def __str__(self):
        return f"{self.workflow.courrier.reference} - Step {self.step_number} ({self.statut})"


class WorkflowAction(models.Model):
    step = models.ForeignKey(WorkflowStep, on_delete=models.CASCADE, related_name='actions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50, choices=[('valider', 'Valider'), ('rejeter', 'Rejeter'), ('commenter', 'Commenter')])
    commentaire = models.TextField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workflow_action'
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} - {self.action}"
