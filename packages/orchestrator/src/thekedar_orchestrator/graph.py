"""LangGraph agent state machine — routes to OrchestratorServices."""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from thekedar_orchestrator.services import OrchestratorServices

Workflow = Literal["help", "architect", "coder", "status"]


class AgentState(TypedDict, total=False):
    message: dict
    workflow: Workflow
    current_node: str
    reply: str
    run_id: str
    correlation_id: str | None
    issue_key: str | None
    pr_url: str | None
    status: str
    paused: bool


def parse_intent(state: AgentState) -> AgentState:
    message = state.get("message") or {}
    text = str(message.get("text") or "")
    mentions = message.get("mentioned_agents") or []

    workflow: Workflow = "help"
    if "Coder" in mentions or "@coder" in text.lower():
        workflow = "coder"
    elif "Architect" in mentions or "@architect" in text.lower():
        workflow = "architect"
    elif "Status" in mentions or "@status" in text.lower():
        workflow = "status"

    return {"workflow": workflow, "current_node": "parse_intent"}


def build_graph(services: OrchestratorServices):
    async def route_workflow(state: AgentState) -> AgentState:
        from thekedar_shared.schemas import MessageEvent

        message = MessageEvent.model_validate(state["message"])
        workflow = str(state.get("workflow") or "help")
        run_id = str(state.get("run_id") or "")

        if workflow == "coder":
            result = await services.run_coder_pipeline(
                message,
                run_id,
                state.get("correlation_id"),
            )
        else:
            result = await services.run(
                message,
                workflow,
                run_id,
                state.get("correlation_id"),
            )

        return {
            **result,
            "reply": result.get("reply", ""),
            "current_node": result.get("current_node", "done"),
            "paused": result.get("status") == "awaiting_approval",
        }

    graph = StateGraph(AgentState)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("route_workflow", route_workflow)
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "route_workflow")
    graph.add_edge("route_workflow", END)
    return graph.compile()
