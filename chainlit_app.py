"""Chainlit UI — ReAct Agent with ChatGPT-style interface.

Run with:
    chainlit run chainlit_app.py --watch
"""
from __future__ import annotations
import asyncio
import json

import chainlit as cl
from src.core.agent import Agent
from config.settings import settings

# ═══════════════════════════════════════════════════════════════════════
# Startup
# ═══════════════════════════════════════════════════════════════════════


@cl.on_chat_start
async def on_start() -> None:
    agent = Agent()
    cl.user_session.set("agent", agent)

    await cl.Message(
        content=(
            "👋 **你好！我是 AI Agent**\n"
            "基于 ReAct 范式，我可以调用工具完成复杂任务。\n\n"
            "试试这些示例：\n"
            "- 计算 (2^10 - 1) × 3.14\n"
            "- 搜索图灵奖的介绍\n"
            "- 列出当前沙箱目录的文件"
        ),
        actions=[
            cl.Action(name="example_1", value="计算 (2^10 - 1) × 3.14", label="📐 数学计算"),
            cl.Action(name="example_2", value="搜索图灵奖的介绍", label="🔍 百科搜索"),
            cl.Action(name="example_3", value="列出当前沙箱目录的文件", label="📁 文件操作"),
        ],
    ).send()


# ═══════════════════════════════════════════════════════════════════════
# Example button callbacks
# ═══════════════════════════════════════════════════════════════════════


@cl.action_callback("example_1")
@cl.action_callback("example_2")
@cl.action_callback("example_3")
async def on_example(action: cl.Action) -> None:
    agent: Agent = cl.user_session.get("agent")
    await cl.Message(content=action.value, author="User").send()
    await run_react(agent, action.value)


# ═══════════════════════════════════════════════════════════════════════
# Message handler
# ═══════════════════════════════════════════════════════════════════════


@cl.on_message
async def on_message(message: cl.Message) -> None:
    agent: Agent = cl.user_session.get("agent")
    content = message.content.strip()

    # ---- Special commands (bypass ReAct) ----
    if content == "/memory":
        await show_memory_panel(agent)
        return

    if content == "/clear_memory":
        agent._ltm.clear()
        await cl.Message(content="✅ 长期记忆已清空").send()
        return

    if content.startswith("/forget"):
        parts = content.split(maxsplit=1)
        if len(parts) < 2:
            await cl.Message(content="⚠️ 用法：`/forget <id前8位>`").send()
            return
        id_prefix = parts[1].strip()
        matched = None
        for f in agent._ltm.get_all_facts():
            if f["id"].startswith(id_prefix):
                matched = f
                break
        if matched:
            agent._ltm.remove_fact(matched["id"])
            agent._ltm.save()
            await cl.Message(content=f"✅ 已删除：{matched['content']}").send()
        else:
            await cl.Message(content=f"⚠️ 未找到 id 前缀为 `{id_prefix}` 的记忆").send()
        return

    # ---- Normal ReAct path ----
    await run_react(agent, content)


# ═══════════════════════════════════════════════════════════════════════
# Core ReAct runner
# ═══════════════════════════════════════════════════════════════════════


async def run_react(agent: Agent, query: str) -> None:
    """Execute one ReAct loop and render steps via Chainlit primitives."""

    # Run the synchronous generator in a thread
    steps = await asyncio.to_thread(list, agent.run_stream(query))

    final_answer: str | None = None
    final_answer_raw: str = ""
    current_step: cl.Step | None = None

    for event in steps:
        etype = event.get("type")

        # ---------------------------------------------------------------
        # Finished — send final answer
        # ---------------------------------------------------------------
        if etype == "finished":
            final_answer = event.get("answer", "")
            final_answer_raw = event.get("raw", "")
            await cl.Message(content=final_answer).send()

        # ---------------------------------------------------------------
        # Step — one Thought → Action → Observation cycle
        # ---------------------------------------------------------------
        elif etype == "step":
            action_name = event.get("action", "unknown")
            action_input = event.get("action_input", {})

            step = cl.Step(name=f"🔧 {action_name}")
            step.input = f"**Thought**\n{event.get('thought', '…')}"

            # Attach Action Input as JSON if present
            if action_input:
                step.elements = [
                    cl.Text(
                        content=json.dumps(action_input, ensure_ascii=False, indent=2),
                        language="json",
                        name="Action Input",
                    )
                ]

            step.output = f"**Observation**\n{event.get('observation', '…')}"
            await step.send()
            current_step = step

        # ---------------------------------------------------------------
        # Parse error — LLM output couldn't be parsed; show feedback
        # ---------------------------------------------------------------
        elif etype == "parse_error":
            step = cl.Step(name="⚠️ Parse Error")
            step.output = event.get("error", "Failed to parse LLM output.")
            await step.send()

        # ---------------------------------------------------------------
        # Fatal error
        # ---------------------------------------------------------------
        elif etype == "error":
            await cl.Message(
                content=f"❌ {event.get('message', 'Unknown error')}",
                author="System",
            ).send()

    # ---- Agent.run_stream already handles LTM extraction + dedup in its finished branch ----

# ═══════════════════════════════════════════════════════════════════════
# Memory panel
# ═══════════════════════════════════════════════════════════════════════


async def show_memory_panel(agent: Agent) -> None:
    """Display all long-term memory entries."""
    facts = agent._ltm.get_all_facts()
    if not facts:
        await cl.Message(content="📭 暂无长期记忆。").send()
        return

    lines = ["### 🧠 当前长期记忆\n"]
    for f in facts:
        date = f["timestamp"][:10]
        lines.append(f"- `{f['id'][:8]}` · {date} · {f['content']}")
    lines.append("")
    lines.append("---")
    lines.append("输入 `/forget <id前8位>` 删除某条记忆")
    lines.append("输入 `/clear_memory` 清空全部")

    await cl.Message(content="\n".join(lines)).send()
