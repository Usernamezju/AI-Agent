"""Thought tracker — renders each round's Thought/Action/Observation in expandable cards."""
import streamlit as st
import json


def render_round(step: dict) -> None:
    """Render a single round of the ReAct loop."""
    r = step["round"]
    t = step["type"]

    if t == "step":
        action = step.get("action", "?")
        with st.expander(f"Round {r} — {action}", expanded=(r <= 2)):
            st.markdown(f"**🧠 Thought:** {step['thought']}")
            st.markdown(f"**🔧 Action:** `{action}`")
            try:
                ai_str = json.dumps(step.get("action_input", {}), ensure_ascii=False, indent=2)
            except Exception:
                ai_str = str(step.get("action_input", ""))
            st.code(ai_str, language="json")

            obs = step.get("observation", "")

            # Specialized rendering for debate
            if action == "perspective_debate":
                try:
                    data = json.loads(obs)
                    for rd in data.get("debate", []):
                        st.markdown(f"**Round {rd['round']}**")
                        col_pro, col_con = st.columns(2)
                        with col_pro:
                            st.markdown(f"🟢 **正方**：{rd['pro']['stance']}")
                            st.info(rd['pro']['arguments'])
                        with col_con:
                            st.markdown(f"🔴 **反方**：{rd['con']['stance']}")
                            st.error(rd['con']['arguments'])
                    if data.get("instruction"):
                        st.caption(data["instruction"])
                except Exception:
                    st.markdown("**👁 Observation:**")
                    st.text(obs[:2000])
            else:
                st.markdown("**👁 Observation:**")
                st.text(obs[:2000])

    elif t == "parse_error":
        with st.expander(f"Round {r} — ⚠ Parse Error", expanded=True):
            st.markdown(f"**🧠 Thought:** {step['thought']}")
            st.error(step["error"])
            st.caption("Raw output:")
            st.code(step.get("raw", "")[:1000])

    elif t == "finished":
        with st.expander(f"Round {r} — ✅ Final Answer", expanded=True):
            st.markdown(f"**🧠 Thought:** {step['thought']}")
            st.success(step["answer"])

    elif t == "error":
        with st.expander(f"Round {r} — ❌ Error", expanded=True):
            st.error(step["message"])


def render_trace(steps: list[dict]) -> None:
    """Render all rounds of a full ReAct trace."""
    if not steps:
        st.caption("(No trace yet)")
        return
    for step in steps:
        render_round(step)
