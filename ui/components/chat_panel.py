"""Chat panel — renders conversation history and handles user input."""
import streamlit as st


def render_message(role: str, content: str) -> None:
    """Render a single chat bubble."""
    with st.chat_message(role):
        st.markdown(content)


def render_history(messages: list[dict]) -> None:
    """Render all messages in the conversation history."""
    for msg in messages:
        render_message(msg["role"], msg["content"])


def chat_input_placeholder() -> str | None:
    """Streamlit's built-in chat input widget."""
    return st.chat_input("输入你的任务，比如：计算 (15+7)*3/2 或 输出当前目录结构")
