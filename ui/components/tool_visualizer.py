"""Tool visualizer — displays tool call statistics."""
import streamlit as st
from collections import Counter


def render_tool_stats(steps: list[dict]) -> None:
    """Show a simple tool invocation counter."""
    counter: Counter = Counter()
    for s in steps:
        if s["type"] == "step" and s.get("action"):
            counter[s["action"]] += 1

    if not counter:
        st.caption("No tools called yet.")
        return

    st.markdown("**📊 Tool Calls**")
    cols = st.columns(len(counter))
    tool_colors = {
        "calculator": "#1565C0",
        "wikipedia_search": "#2E7D32",
        "local_filesystem": "#E65100",
    }
    for i, (name, count) in enumerate(counter.items()):
        color = tool_colors.get(name, "#666")
        with cols[i]:
            st.markdown(
                f"<div style='text-align:center;padding:0.5rem;border-radius:8px;"
                f"background:{color}15;border:2px solid {color}'>"
                f"<span style='font-size:1.5rem;font-weight:bold;color:{color}'>{count}</span><br>"
                f"<span style='font-size:0.75rem'>{name}</span></div>",
                unsafe_allow_html=True,
            )
