"""Streamlit UI — chat interface with real-time ReAct trace sidebar."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from src.core import Agent
from ui.components.thought_tracker import render_trace
from ui.components.chat_panel import render_message
from ui.components.tool_visualizer import render_tool_stats

st.set_page_config(page_title="AI Agent", layout="wide")

# ---- CSS ------------------------------------------------------------
css_path = os.path.join(os.path.dirname(__file__), "static", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---- Session state --------------------------------------------------
for key, default in [("messages", []), ("trace", []), ("agent", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.agent is None:
    st.session_state.agent = Agent()

# ---- Layout ---------------------------------------------------------
left, right = st.columns([3, 2])

# =====================================================================
# LEFT — Chat panel
# =====================================================================
with left:
    st.title("🤖 AI Agent Framework")

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    query = st.chat_input("输入任务…")
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        st.session_state.trace = []

        agent: Agent = st.session_state.agent
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *Thinking...*")

            steps = list(agent.run_stream(query))
            st.session_state.trace = steps

            # Find final answer
            final = next((s["answer"] for s in steps if s["type"] == "finished"), None)
            if final is None:
                final = next((s["message"] for s in steps if s["type"] == "error"), "No result.")
            placeholder.markdown(final)

        st.session_state.messages.append({"role": "assistant", "content": final})
        st.rerun()

# =====================================================================
# RIGHT — Sidebar panels
# =====================================================================
with right:
    st.subheader("🧠 推理轨迹")
    render_trace(st.session_state.trace)

    st.divider()
    render_tool_stats(st.session_state.trace)
