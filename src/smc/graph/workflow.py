"""急诊短路；其余按意图分叉检索，再融合、安全。"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from smc.graph.nodes import (
    dept_or_med_or_knowledge_node,
    emergency_gate_node,
    fuse_stream_node,
    intent_node,
    retrieve_hybrid_node,
    retrieve_med_node,
    retrieve_triage_node,
    safety_rewrite_node,
)
from smc.graph.state import AgentState


def _after_emergency(state: AgentState) -> str:
    if state.get("emergency"):
        return "safety_rewrite"
    return "intent"


def _after_intent(state: AgentState) -> str:
    intent = state.get("intent")
    if intent == "triage":
        return "retrieve_triage"
    if intent in {"visit_prep", "knowledge"}:
        return "retrieve_hybrid"
    if intent == "medication_info":
        return "retrieve_med"
    return "fuse_stream"


def build_workflow():
    graph = StateGraph(AgentState)
    graph.add_node("emergency_gate", emergency_gate_node)
    graph.add_node("intent", intent_node)
    graph.add_node("retrieve_triage", retrieve_triage_node)
    graph.add_node("retrieve_hybrid", retrieve_hybrid_node)
    graph.add_node("retrieve_med", retrieve_med_node)
    graph.add_node("dept_or_med_or_knowledge", dept_or_med_or_knowledge_node)
    graph.add_node("fuse_stream", fuse_stream_node)
    graph.add_node("safety_rewrite", safety_rewrite_node)

    graph.set_entry_point("emergency_gate")
    graph.add_conditional_edges(
        "emergency_gate",
        _after_emergency,
        {"safety_rewrite": "safety_rewrite", "intent": "intent"},
    )
    graph.add_conditional_edges(
        "intent",
        _after_intent,
        {
            "retrieve_triage": "retrieve_triage",
            "retrieve_hybrid": "retrieve_hybrid",
            "retrieve_med": "retrieve_med",
            "fuse_stream": "fuse_stream",
        },
    )
    graph.add_edge("retrieve_triage", "dept_or_med_or_knowledge")
    graph.add_edge("retrieve_hybrid", "dept_or_med_or_knowledge")
    graph.add_edge("retrieve_med", "dept_or_med_or_knowledge")
    graph.add_edge("dept_or_med_or_knowledge", "fuse_stream")
    graph.add_edge("fuse_stream", "safety_rewrite")
    graph.add_edge("safety_rewrite", END)
    return graph.compile()
