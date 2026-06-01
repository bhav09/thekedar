"""LangGraph orchestrator tests."""

from thekedar_orchestrator.graph import build_graph


def test_graph_help_reply() -> None:
    graph = build_graph()
    result = graph.invoke({"message": {"text": "hello", "mentioned_agents": []}})
    assert "Thekedar agents" in result["reply"]
    assert result["workflow"] == "help"


def test_graph_coder_mention() -> None:
    graph = build_graph()
    result = graph.invoke(
        {"message": {"text": "fix login", "mentioned_agents": ["Coder"]}}
    )
    assert result["workflow"] == "coder"
    assert "Coder mode" in result["reply"]
