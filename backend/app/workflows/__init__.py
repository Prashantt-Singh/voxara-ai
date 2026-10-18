"""
Voxara AI - Workflows Module (Step 4A & 4B: Agentic Workflows & Skill Analysis)
"""

from app.workflows.state import (
    WorkflowState,
    ExecutionEvent,
    ExecutionEventModel,
    WorkflowDemoRequest,
    WorkflowDemoResponse,
    SkillAnalysisState,
    SkillAnalysisRequest,
    SkillAnalysisResponse,
    create_execution_event,
    generate_execution_id,
    generate_event_id,
)
from app.workflows.nodes import (
    receive_request,
    validate_request,
    produce_result,
)
from app.workflows.graph import (
    workflow_graph,
    build_workflow_graph,
    run_workflow,
)
from app.workflows.skill_nodes import (
    validate_input,
    compare_skills,
    analyze_skill_gaps,
    validate_analysis,
)
from app.workflows.skill_graph import (
    skill_analysis_graph,
    build_skill_analysis_graph,
    run_skill_analysis_workflow,
)

__all__ = [
    # State & Schemas
    "WorkflowState",
    "ExecutionEvent",
    "ExecutionEventModel",
    "WorkflowDemoRequest",
    "WorkflowDemoResponse",
    "SkillAnalysisState",
    "SkillAnalysisRequest",
    "SkillAnalysisResponse",
    "create_execution_event",
    "generate_execution_id",
    "generate_event_id",
    # Demo Workflow Nodes & Graph
    "receive_request",
    "validate_request",
    "produce_result",
    "workflow_graph",
    "build_workflow_graph",
    "run_workflow",
    # Skill Analysis Nodes & Graph
    "validate_input",
    "compare_skills",
    "analyze_skill_gaps",
    "validate_analysis",
    "skill_analysis_graph",
    "build_skill_analysis_graph",
    "run_skill_analysis_workflow",
]
