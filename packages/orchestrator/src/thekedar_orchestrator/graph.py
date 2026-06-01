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
    async def execute(state: AgentState) -> AgentState:
        from thekedar_shared.schemas import MessageEvent

        message = MessageEvent.model_validate(state["message"])
        result = await services.run(
            message,
            str(state.get("workflow") or "help"),
            str(state.get("run_id") or ""),
            state.get("correlation_id"),
        )
        return {
            **result,
            "reply": result.get("reply", ""),
            "current_node": result.get("current_node", "done"),
        }

    graph = StateGraph(AgentState)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("execute", execute)
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "execute")
    graph.add_edge("execute", END)
    return graph.compile()
