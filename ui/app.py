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

    # New conversation button
    if st.button("🆕 新对话", use_container_width=True):
        st.session_state.agent.reset_conversation()
        st.session_state.messages = []
        st.session_state.trace = []
        st.rerun()

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

    st.divider()

    # ==================================================================
    # Long-term memory panel
    # ==================================================================
    with st.expander("🧠 长期记忆", expanded=True):
        agent_obj: Agent = st.session_state.agent
        ltm = agent_obj._ltm

        # ---- ① Manual add ----
        st.caption("新增记忆")
        new_fact = st.text_area(
            "新增记忆内容",
            height=80,
            key="new_fact_input",
            label_visibility="collapsed",
            placeholder="输入需要长期记住的内容…",
        )
        add_col, _ = st.columns([1, 3])
        with add_col:
            if st.button("添加", key="add_fact_btn", disabled=(not new_fact.strip()),
                         use_container_width=True):
                ltm.add_fact(new_fact.strip())
                ltm.save()
                st.session_state.new_fact_input = ""
                st.rerun()

        st.divider()

        # ---- ② Memory entries ----
        facts = ltm.get_all_facts()
        if not facts:
            st.caption("暂无长期记忆")
        else:
            for fact in reversed(facts):
                fid = fact["id"]
                ts = fact["timestamp"][:10]  # YYYY-MM-DD
                content = fact["content"]

                # Editing state for this row
                edit_key = f"editing_{fid}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                if st.session_state[edit_key]:
                    # --- Edit mode ---
                    new_content = st.text_area(
                        "编辑记忆",
                        value=content,
                        height=80,
                        key=f"edit_area_{fid}",
                        label_visibility="collapsed",
                    )
                    c1, c2, _ = st.columns([1, 1, 4])
                    with c1:
                        if st.button("保存", key=f"save_{fid}", use_container_width=True):
                            ltm.update_fact(fid, new_content.strip())
                            ltm.save()
                            st.session_state[edit_key] = False
                            st.rerun()
                    with c2:
                        if st.button("取消", key=f"cancel_{fid}", use_container_width=True):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    # --- Display mode ---
                    row_cols = st.columns([1, 8, 1.2, 1.2])
                    with row_cols[0]:
                        st.markdown(f"<small style='color:#888'>{ts}</small>",
                                    unsafe_allow_html=True)
                    with row_cols[1]:
                        st.markdown(content)
                    with row_cols[2]:
                        if st.button("✏️ 编辑", key=f"edit_{fid}", use_container_width=True):
                            # Close any other open edit
                            for f2 in facts:
                                if f2["id"] != fid:
                                    st.session_state[f"editing_{f2['id']}"] = False
                            st.session_state[edit_key] = True
                            st.rerun()
                    with row_cols[3]:
                        if st.button("🗑️ 删除", key=f"del_{fid}", use_container_width=True):
                            ltm.remove_fact(fid)
                            ltm.save()
                            st.rerun()

        # ---- ③ Clear all ----
        st.divider()
        if facts:
            clear_warning = st.empty()
            if st.button("🗑️ 清空全部记忆", key="clear_all_btn", type="secondary",
                         use_container_width=True):
                if "confirm_clear" not in st.session_state:
                    st.session_state["confirm_clear"] = False
                st.session_state["confirm_clear"] = True

            if st.session_state.get("confirm_clear"):
                clear_warning.warning("确认要清空所有长期记忆吗？此操作不可撤销。")
                cc1, cc2, _ = st.columns([1, 1, 4])
                with cc1:
                    if st.button("确认清空", key="confirm_clear_yes", use_container_width=True):
                        ltm.clear()
                        st.session_state["confirm_clear"] = False
                        st.rerun()
                with cc2:
                    if st.button("取消", key="confirm_clear_no", use_container_width=True):
                        st.session_state["confirm_clear"] = False
                        st.rerun()
