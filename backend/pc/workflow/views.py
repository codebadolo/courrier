from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Workflow, WorkflowStep, WorkflowAction
from .serializers import (
    WorkflowSerializer,
    WorkflowStepSerializer,
    WorkflowActionSerializer
)


class WorkflowViewSet(viewsets.ModelViewSet):
    queryset = Workflow.objects.all()
    serializer_class = WorkflowSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def avancer(self, request, pk=None):
        workflow = self.get_object()

        step = workflow.steps.filter(step_number=workflow.current_step).first()
        if not step:
            return Response({"detail": "Étape courante introuvable."}, status=400)

        if step.statut != "valide":
            return Response({"detail": "La step actuelle doit être validée avant d’avancer."}, status=400)

        workflow.current_step += 1
        workflow.save()

        return Response({"status": "workflow avancé", "new_step": workflow.current_step})
    


class WorkflowStepViewSet(viewsets.ModelViewSet):
    queryset = WorkflowStep.objects.all()
    serializer_class = WorkflowStepSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        step = self.get_object()

        step.statut = "valide"
        step.commentaire = request.data.get("commentaire", "")
        step.save()

        WorkflowAction.objects.create(
            step=step,
            user=request.user,
            action="valider",
            commentaire=step.commentaire
        )

        return Response({"status": "step validée"})

    @action(detail=True, methods=["post"])
    def rejeter(self, request, pk=None):
        step = self.get_object()

        step.statut = "rejete"
        step.commentaire = request.data.get("commentaire", "")
        step.save()

        WorkflowAction.objects.create(
            step=step,
            user=request.user,
            action="rejeter",
            commentaire=step.commentaire
        )

        return Response({"status": "step rejetée"})

    @action(detail=True, methods=["post"])
    def commenter(self, request, pk=None):
        step = self.get_object()

        commentaire = request.data.get("commentaire", "")

        WorkflowAction.objects.create(
            step=step,
            user=request.user,
            action="commenter",
            commentaire=commentaire
        )

        step.commentaire = commentaire
        step.save()

        return Response({"status": "commentaire ajouté"})
    


class WorkflowActionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkflowAction.objects.all()
    serializer_class = WorkflowActionSerializer
    permission_classes = [permissions.IsAuthenticated]
