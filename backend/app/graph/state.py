"""Contrat de l'état partagé (blackboard) entre tous les agents.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class UserRole(StrEnum):
    DEVELOPER = "developer"
    SCRUM_MASTER = "scrum_master"
    PRODUCT_MANAGER = "product_manager"
    CLIENT = "client"


class AgentName(StrEnum):
    SUPERVISOR = "supervisor"
    RAG = "rag"
    JIRA = "jira"
    RISK = "risk"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


# --------------------------------------------------------------------------- #
# Objets métier échangés entre agents
# --------------------------------------------------------------------------- #


class RoutingDecision(BaseModel):
    """Sortie structurée du Supervisor (outil `route_to_specialist_agent`)."""

    next: Literal["rag", "jira", "risk", "finish"]
    subtask: str = Field(description="Sous-tâche à confier à l'agent choisi")
    reasoning: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Citation(BaseModel):
    """Source documentaire citée par l'agent RAG."""

    title: str
    page_id: str | None = None
    url: str | None = None
    score: float | None = None


class JiraIssueRef(BaseModel):
    key: str
    summary: str
    status: str | None = None
    assignee: str | None = None
    priority: str | None = None
    story_points: float | None = None


class PendingAction(BaseModel):
    """Écriture Jira en attente de validation humaine (HITL)."""

    action_id: str = Field(default_factory=lambda: str(uuid4()))
    tool: str = Field(description="Ex. create_user_story, assign_ticket")
    args: dict[str, Any] = Field(default_factory=dict)
    project_key: str
    preview: str = Field(description="Texte lisible affiché dans la carte d'approbation")
    status: ActionStatus = ActionStatus.PENDING
    requested_by: AgentName = AgentName.JIRA
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RiskAssessment(BaseModel):
    """Résultat de `compute_delay_risk_score`."""

    score: float = Field(ge=0.0, le=1.0)
    level: RiskLevel
    avg_velocity: float | None = None
    committed_points: float | None = None
    unassigned_blockers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


def risk_level_from_score(score: float) -> RiskLevel:
    """Seuils : <0.25 low, <0.5 medium, <0.75 high, sinon critical."""
    if score < 0.25:
        return RiskLevel.LOW
    if score < 0.5:
        return RiskLevel.MEDIUM
    if score < 0.75:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


# --------------------------------------------------------------------------- #
# État du graphe LangGraph
# --------------------------------------------------------------------------- #


class GraphState(BaseModel):
    # Conversation
    messages: Annotated[list[AnyMessage], add_messages] = Field(default_factory=list)
    thread_id: str | None = None

    # Utilisateur (alimenté par l'API après authentification)
    user_id: str | None = None
    user_role: UserRole = UserRole.DEVELOPER

    # Routage
    next_agent: AgentName | None = None
    subtask: str | None = None
    routing_history: list[RoutingDecision] = Field(default_factory=list)

    # Résultats partagés (blackboard) : un agent écrit, un autre lit
    error_codes: list[str] = Field(
        default_factory=list,
        description="Codes d'erreur extraits par l'agent Jira, consommés par l'agent RAG",
    )
    jira_issues: list[JiraIssueRef] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    risk: RiskAssessment | None = None

    # Human-in-the-loop
    pending_actions: list[PendingAction] = Field(default_factory=list)

    # Sortie
    final_answer: str | None = None
    errors: list[str] = Field(default_factory=list)
