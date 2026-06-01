"""LangGraph agent state machine for inbound messages."""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

Workflow = Literal["help", "architect", "coder", "status"]


class AgentState(TypedDict, total=False):
    message: dict
    workflow: Workflow
    current_node: str
    reply: str


def parse_intent(state: AgentState) -> AgentState:
    message = state.get("message") or {}
    text = str(message.get("text") or "")
    mentions = message.get("mentioned_agents") or []

    workflow: Workflow = "help"
    if "Coder" in mentions:
        workflow = "coder"
    elif "Architect" in mentions:
        workflow = "architect"
    elif "Status" in mentions:
        workflow = "status"
    elif "@coder" in text.lower():
        workflow = "coder"
    elif "@architect" in text.lower():
        workflow = "architect"
    elif "@status" in text.lower():
        workflow = "status"

    return {"workflow": workflow, "current_node": "parse_intent"}


def route_workflow(state: AgentState) -> AgentState:
    return {"current_node": "route"}


def summarize(state: AgentState) -> AgentState:
    workflow = state.get("workflow") or "help"
    dashboard_url = "http://localhost:8081"

    replies = {
        "help": (
            "Thekedar agents:\n"
            "• @Architect — planning & Jira mapping (M3)\n"
            "• @Coder — cloud coding & PRs (M4+)\n"
            "• @Status — dashboard queries\n"
            f"Dashboard: {dashboard_url}"
        ),
        "architect": (
            "Architect mode: I'll map epics to the codebase once Jira is wired (M3). "
            f"Track runs on the dashboard: {dashboard_url}"
        ),
        "coder": (
            "Coder mode: I'll wake Cloud Workstations and open PRs in M4+. "
            f"Dashboard: {dashboard_url}"
        ),
        "status": (
            f"Status: check the dashboard for active runs and workstation health — {dashboard_url}"
        ),
    }
    return {"reply": replies[workflow], "current_node": "summarize"}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("route", route_workflow)
    graph.add_node("summarize", summarize)
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "route")
    graph.add_edge("route", "summarize")
    graph.add_edge("summarize", END)
    return graph.compile()
