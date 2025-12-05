from rest_framework import serializers
from .models import Workflow, WorkflowStep, WorkflowAction


class WorkflowActionSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = WorkflowAction
        fields = [
            "id",
            "step",
            "user", "user_email",
            "action",
            "commentaire",
            "date"
        ]
        read_only_fields = ["date"]


class WorkflowStepSerializer(serializers.ModelSerializer):
    validator_email = serializers.CharField(source="validator.email", read_only=True)
    service_name = serializers.CharField(source="approbateur_service.nom", read_only=True)
    actions = WorkflowActionSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowStep
        fields = [
            "id",
            "workflow",
            "step_number",
            "label",
            "validator",
            "validator_email",
            "approbateur_service",
            "service_name",
            "statut",
            "commentaire",
            "date_action",
            "actions"
        ]


class WorkflowSerializer(serializers.ModelSerializer):
    courrier_reference = serializers.CharField(source="courrier.reference", read_only=True)
    steps = WorkflowStepSerializer(many=True, read_only=True)

    class Meta:
        model = Workflow
        fields = [
            "id",
            "courrier",
            "courrier_reference",
            "created_at",
            "updated_at",
            "current_step",
            "steps"
        ]
        read_only_fields = ["created_at", "updated_at"]
