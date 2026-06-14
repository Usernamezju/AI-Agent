"""Streamlit UI — chat interface with real-time ReAct trace sidebar."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import streamlit as st
from src.core import Agent
from src.multi_agent import Orchestrator
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
for key, default in [("messages", []), ("trace", []), ("agent", None),
                       ("orchestrator", None), ("multi_agent_mode", False),
                       ("ma_tasks", []), ("ma_trace", [])]:
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.agent is None:
    st.session_state.agent = Agent()
if st.session_state.orchestrator is None:
    st.session_state.orchestrator = Orchestrator()

# Session state for search results
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "last_uploaded" not in st.session_state:
    st.session_state.last_uploaded = ""


# ═══════════════════════════════════════════════════════════════════════
# File upload handler
# ═══════════════════════════════════════════════════════════════════════


def _handle_upload(uploaded_file, agent: Agent) -> None:
    """Save uploaded file to sandbox, extract text/image, and inject a notice."""
    from pathlib import Path
    from config.settings import settings
    from src.tools.file_extractor import extract_text, extract_image_description, IMAGE_EXTENSIONS

    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state.last_uploaded == file_key:
        return
    st.session_state.last_uploaded = file_key

    sandbox = Path(settings.SANDBOX_ROOT)
    sandbox.mkdir(parents=True, exist_ok=True)
    save_path = sandbox / uploaded_file.name
    save_path.write_bytes(uploaded_file.getvalue())

    suffix = save_path.suffix.lower()

    # ---- image → Qwen-VL description ----
    if suffix in IMAGE_EXTENSIONS:
        from src.llm import create_llm_client
        try:
            vision_client = create_llm_client("qwen")
            # Override model to vision-capable one
            if hasattr(vision_client, "_client"):
                # Store original model name, swap in vision model
                pass  # Will be set via internal attribute
            vision_client.model = settings.QWEN_VISION_MODEL
            description, img_error = extract_image_description(save_path, vision_client)
        except Exception:
            description, img_error = "", "无法创建视觉模型客户端，请检查 QWEN_API_KEY"

        if img_error:
            notice = (
                f"[系统通知] 用户上传了图片：{uploaded_file.name}（{uploaded_file.size} 字节）\n"
                f"文件已保存至 sandbox/{uploaded_file.name}\n"
                f"图片理解失败：{img_error}"
            )
        else:
            preview = description[:300] + "…" if len(description) > 300 else description
            notice = (
                f"[系统通知] 用户上传了图片：{uploaded_file.name}（{uploaded_file.size} 字节）\n"
                f"文件已保存至 sandbox/{uploaded_file.name}\n"
                f"图片内容描述（Qwen-VL）：\n```\n{preview}\n```\n"
                "请基于以上描述回答用户关于此图片的问题。"
            )
    else:
        # ---- text / PDF / other ----
        text, error = extract_text(save_path)
        if error:
            notice = (
                f"[系统通知] 用户上传了文件：{uploaded_file.name}（{uploaded_file.size} 字节）\n"
                f"文件已保存至 sandbox/{uploaded_file.name}，但文本提取失败：{error}\n"
                "如需读取，请使用 local_filesystem 工具。"
            )
        else:
            preview = text[:300] + "…" if len(text) > 300 else text
            notice = (
                f"[系统通知] 用户上传了文件：{uploaded_file.name}（{uploaded_file.size} 字节）\n"
                f"文件已保存至 sandbox/{uploaded_file.name}，内容预览：\n"
                f"```\n{preview}\n```\n"
                f"完整内容可用 local_filesystem 工具读取，path 填写 \"{uploaded_file.name}\"。"
            )

    st.session_state.messages.append({"role": "user", "content": notice})
    if hasattr(agent, "_conv"):
        agent._conv.add_turn("[文件上传通知]", notice)

    st.success(f"已上传：{uploaded_file.name}（{uploaded_file.size} 字节）")
    if suffix in IMAGE_EXTENSIONS:
        st.info("图片正由视觉模型理解中…")
    elif 'error' in dir() and error:
        st.warning(error)

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR — Search + Conversation history
# ═══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🔍 搜索对话")
    sq = st.text_input("搜索对话", placeholder="输入关键词…", key="search_query",
                        label_visibility="collapsed")
    c1, c2 = st.columns(2)
    use_ai = c1.checkbox("AI 语义", value=False, key="use_ai_search")
    if c2.button("搜索", key="search_btn", use_container_width=True):
        if sq.strip():
            agent_obj: Agent = st.session_state.agent
            results = agent_obj._search.search(sq.strip(), use_ai=use_ai)
            st.session_state.search_results = results
        else:
            st.session_state.search_results = None

    # Clear search
    if st.session_state.search_results is not None:
        if st.button("✕ 清除搜索", use_container_width=True):
            st.session_state.search_results = None
            st.rerun()

    st.divider()

    # New conversation
    if st.button("🆕 新对话", use_container_width=True):
        st.session_state.agent.reset_conversation()
        st.session_state.messages = []
        st.session_state.trace = []
        st.session_state.search_results = None
        st.rerun()

    st.divider()

    agent_obj: Agent = st.session_state.agent
    results = st.session_state.search_results

    if results is not None:
        # ---- Search results ----
        if not results:
            st.caption("未找到匹配的对话")
        else:
            st.caption(f"找到 {len(results)} 条结果")
            for r in results:
                # Highlight query tokens in snippet
                snippet = r.get("snippet", "")
                for token in sq.strip().split():
                    snippet = snippet.replace(token, f"**{token}**")
                label = f"**{r['title'][:18]}** · 相关度 {r['score']:.2f}"
                if st.button(label, key=f"sr_{r['id']}", use_container_width=True,
                             help=snippet[:200]):
                    conv = agent_obj._store.get_conversation(r["id"])
                    if conv:
                        st.session_state.messages = conv.get("messages", [])
                        agent_obj._current_conv_id = r["id"]
                        st.rerun()
    else:
        # ---- Conversation history list ----
        st.markdown("#### 📝 历史对话")
        convs = agent_obj._store.list_conversations(limit=50)
        if not convs:
            st.caption("暂无历史对话")
        else:
            # Group by date
            from datetime import date
            today = date.today()
            groups: dict[str, list] = {"今天": [], "昨天": [], "更早": []}
            for c in convs:
                try:
                    ts = c["updated_at"][:10]
                    d = date.fromisoformat(ts)
                except Exception:
                    groups["更早"].append(c)
                    continue
                if d == today:
                    groups["今天"].append(c)
                elif d == today.replace(day=today.day - 1):
                    groups["昨天"].append(c)
                else:
                    groups["更早"].append(c)

            for group_name in ["今天", "昨天", "更早"]:
                items = groups[group_name]
                if not items:
                    continue
                st.sidebar.caption(group_name)
                for c in items:
                    title = c["title"] or "未命名对话"
                    if len(title) > 18:
                        title = title[:18] + "…"
                    col_a, col_b = st.columns([4, 1])
                    with col_a:
                        if st.button(title, key=f"hist_{c['id']}", use_container_width=True,
                                     help=c.get("updated_at", "")):
                            conv = agent_obj._store.get_conversation(c["id"])
                            if conv:
                                st.session_state.messages = conv.get("messages", [])
                                agent_obj._current_conv_id = c["id"]
                                st.rerun()
                    with col_b:
                        if st.button("🗑", key=f"del_{c['id']}", use_container_width=True):
                            agent_obj._store.delete_conversation(c["id"])
                            if agent_obj._current_conv_id == c["id"]:
                                agent_obj._current_conv_id = None
                                st.session_state.messages = []
                            st.rerun()

    st.sidebar.divider()

    # ---- Working directory switcher ----
    from config.settings import settings as _settings
    from src.tools import tool_registry as _sidebar_tr

    _default_sandbox = str(_settings.SANDBOX_ROOT)

    if "working_dir" not in st.session_state:
        st.session_state.working_dir = _default_sandbox

    st.sidebar.caption("📂 工作目录")

    _fs_tool = _sidebar_tr.get("local_filesystem")
    _ci_tool = _sidebar_tr.get("code_interpreter")
    _current = getattr(_fs_tool, "current_root", st.session_state.working_dir)

    # Show current path + mode badge
    _is_sandbox = Path(_current).resolve() == Path(_default_sandbox).resolve()
    _badge = "🔒 沙箱" if _is_sandbox else "📁 自定义"
    _display = _current if len(_current) <= 36 else "…" + _current[-34:]
    st.sidebar.markdown(
        f"<small style='color:#888'>{_badge}：<code>{_display}</code></small>",
        unsafe_allow_html=True,
    )

    # --- browse button (native OS dialog via tkinter) ---
    def _pick_directory() -> str:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", 1)
            chosen = filedialog.askdirectory(
                title="选择工作目录",
                initialdir=_current,
            )
            root.destroy()
            return chosen or ""
        except Exception:
            return ""

    _bc1, _bc2, _bc3 = st.sidebar.columns([2, 2, 2])
    with _bc1:
        if st.button("📁 浏览", key="wd_browse", use_container_width=True):
            chosen = _pick_directory()
            if chosen:
                _err = _fs_tool.set_root(chosen) if _fs_tool else ""
                if not _err and _ci_tool:
                    _err = _ci_tool.set_sandbox(chosen)
                if _err:
                    st.sidebar.error(f"切换失败：{_err}")
                else:
                    st.session_state.working_dir = chosen
                    st.rerun()
    with _bc2:
        if st.button("✏️ 手输", key="wd_manual_toggle", use_container_width=True):
            st.session_state["wd_manual"] = not st.session_state.get("wd_manual", False)
            st.rerun()
    with _bc3:
        if st.button("🔒 沙箱", key="wd_reset", use_container_width=True):
            if _fs_tool:
                _fs_tool.set_root(_default_sandbox)
            if _ci_tool:
                _ci_tool.set_sandbox(_default_sandbox)
            st.session_state.working_dir = _default_sandbox
            st.session_state["wd_manual"] = False
            st.rerun()

    # Manual path input (collapsed by default)
    if st.session_state.get("wd_manual", False):
        _new_dir = st.sidebar.text_input(
            "手动输入路径", value=_current,
            key="wd_input", label_visibility="collapsed",
            placeholder="输入绝对路径…",
        )
        if st.sidebar.button("确认切换", key="wd_apply", use_container_width=True):
            _err = _fs_tool.set_root(_new_dir) if _fs_tool else ""
            if not _err and _ci_tool:
                _err = _ci_tool.set_sandbox(_new_dir)
            if _err:
                st.sidebar.error(f"切换失败：{_err}")
            else:
                st.session_state.working_dir = _new_dir
                st.session_state["wd_manual"] = False
                st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("📎 上传文件")
    uploaded_file = st.sidebar.file_uploader(
        "上传文件",
        type=None,
        key="file_uploader",
        label_visibility="collapsed",
    )
    if uploaded_file is not None:
        # Access agent from session state inside sidebar context
        sidebar_agent: Agent = st.session_state.agent
        _handle_upload(uploaded_file, sidebar_agent)
        st.rerun()

# ---- chat_input at top level (must be outside any container) ----
query = st.chat_input("输入任务…")

# ---- Layout ---------------------------------------------------------
left, right = st.columns([3, 2])

# =====================================================================
# LEFT — Chat panel (history only, no input)
# =====================================================================
with left:
    st.title("🤖 AI Agent Framework")

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# =====================================================================
# RIGHT — Sidebar panels
# =====================================================================
with right:
    tab1, tab2 = st.tabs(["🧠 推理轨迹", "🤝 多智能体"])

    # =====================================================================
    # Tab 1 — Single-agent trace
    # =====================================================================
    with tab1:
        render_trace(st.session_state.trace)
        st.divider()
        render_tool_stats(st.session_state.trace)

    # =====================================================================
    # Tab 2 — Multi-agent mode
    # =====================================================================
    with tab2:
        st.toggle("启用多智能体模式", key="multi_agent_mode",
                  help="开启后，复杂任务将被自动拆解为子任务并行执行")

        ma_tasks = st.session_state.ma_tasks
        if ma_tasks:
            # ---- Graphviz dependency chart ----
            dot = "digraph {\n  rankdir=TB;\n  node [style=filled, fontname=sans-serif];\n"
            color_map = {"pending": "lightgray", "running": "lightblue",
                         "done": "lightgreen", "error": "lightcoral"}
            for t in ma_tasks:
                c = color_map.get(t.get("status", "pending"), "lightgray")
                label = f"{t['id']}: {t['description'][:20]}"
                dot += f'  {t["id"]} [label="{label}", fillcolor={c}];\n'
            for t in ma_tasks:
                for dep in t.get("depends_on", []):
                    dot += f"  {dep} -> {t['id']};\n"
            dot += "}"
            st.graphviz_chart(dot)

            # ---- Task result expanders ----
            for t in ma_tasks:
                status_emoji = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}
                emoji = status_emoji.get(t.get("status", "pending"), "❓")
                with st.expander(f"{emoji} [{t['id']}] {t['description'][:30]}",
                                 expanded=(t.get("status") == "done")):
                    # Find result from trace
                    result_text = ""
                    for ev in st.session_state.ma_trace:
                        if ev.get("task_id") == t["id"] and ev.get("type") == "task_done":
                            result_text = ev.get("result", "")
                    if result_text:
                        st.markdown(result_text)
                    else:
                        st.caption("等待执行…")
        else:
            st.caption("开启多智能体模式后，复杂任务计划将在此显示")

    st.divider()

    # ==================================================================
    # Long-term memory panel
    # ==================================================================
    with st.expander("🧠 长期记忆", expanded=True):
        agent_obj: Agent = st.session_state.agent
        ltm = agent_obj._ltm

        # ---- ① Manual add ----
        st.caption("新增记忆")
        if "fact_input_counter" not in st.session_state:
            st.session_state.fact_input_counter = 0
        new_fact = st.text_area(
            "新增记忆内容",
            height=80,
            key=f"new_fact_input_{st.session_state.fact_input_counter}",
            label_visibility="collapsed",
            placeholder="输入需要长期记住的内容…",
        )
        add_col, _ = st.columns([1, 3])
        with add_col:
            if st.button("添加", key=f"add_fact_btn_{st.session_state.fact_input_counter}",
                         disabled=(not new_fact.strip()),
                         use_container_width=True):
                ltm.add_fact(new_fact.strip())
                ltm.save()
                st.session_state.fact_input_counter += 1
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

    # ==================================================================
    # Tool library panel
    # ==================================================================
    from src.tools import tool_registry as _tr
    all_tools = _tr.list_all()
    builtin = [t for t in all_tools if not t["synthesized"]]
    synthesized = [t for t in all_tools if t["synthesized"]]

    panel_title = "🔧 工具库"
    if synthesized:
        panel_title += f"  ✨ +{len(synthesized)} AI 合成"

    with st.expander(panel_title, expanded=bool(synthesized)):
        def _render_tool_row(t: dict, border_color: str, bg_color: str, badge: str = "") -> None:
            name = t["name"]
            rk = f"tool_renaming_{name}"
            if rk not in st.session_state:
                st.session_state[rk] = False

            if st.session_state[rk]:
                # --- rename mode ---
                new_name = st.text_input(
                    "新名称", value=name, key=f"tool_rename_input_{name}",
                    label_visibility="collapsed",
                )
                rc1, rc2, _ = st.columns([1, 1, 4])
                with rc1:
                    if st.button("保存", key=f"tool_rename_save_{name}",
                                 use_container_width=True):
                        new_name = new_name.strip()
                        if new_name and new_name != name:
                            if _tr.rename(name, new_name):
                                st.session_state.agent._pm.update_tools(
                                    _tr.generate_descriptions())
                            else:
                                st.warning(f"名称 '{new_name}' 已存在或无效")
                        st.session_state[rk] = False
                        st.rerun()
                with rc2:
                    if st.button("取消", key=f"tool_rename_cancel_{name}",
                                 use_container_width=True):
                        st.session_state[rk] = False
                        st.rerun()
            else:
                # --- display mode ---
                col_info, col_edit, col_del = st.columns([8, 1, 1])
                with col_info:
                    st.markdown(
                        f"<div style='padding:6px 8px;margin:4px 0;border-radius:6px;"
                        f"background:{bg_color};border-left:3px solid {border_color}'>"
                        f"<b style='color:{border_color}'>{name}</b>{badge}<br>"
                        f"<small style='color:#aaa'>"
                        f"{t['description'][:80]}{'…' if len(t['description'])>80 else ''}"
                        f"</small></div>",
                        unsafe_allow_html=True,
                    )
                with col_edit:
                    if st.button("✏️", key=f"tool_rename_btn_{name}",
                                 help=f"重命名 {name}"):
                        # Close other rename inputs
                        for other in all_tools:
                            if other["name"] != name:
                                st.session_state[f"tool_renaming_{other['name']}"] = False
                        st.session_state[rk] = True
                        st.rerun()
                with col_del:
                    if st.button("🗑", key=f"del_tool_{name}",
                                 help=f"移除 {name}"):
                        _tr.unregister(name)
                        st.session_state.agent._pm.update_tools(_tr.generate_descriptions())
                        st.rerun()

        if builtin:
            st.markdown("<small style='color:#888'>内置工具</small>",
                        unsafe_allow_html=True)
            for t in builtin:
                _render_tool_row(t, border_color="#4a8cf7", bg_color="#1e2a3a")

        if synthesized:
            st.markdown("<small style='color:#f0a500'>✨ AI 运行时合成工具</small>",
                        unsafe_allow_html=True)
            badge = (
                "<span style='margin-left:6px;font-size:0.7rem;background:#f0a500;"
                "color:#000;border-radius:3px;padding:1px 5px'>AI 合成</span>"
            )
            for t in synthesized:
                _render_tool_row(t, border_color="#f0a500", bg_color="#2a2010",
                                 badge=badge)

        if not all_tools:
            st.caption("暂无工具")

    # ==================================================================
    # Directory memory panel
    # ==================================================================
    dir_memories = st.session_state.agent._dir_memory.list_all()
    dm_title = f"📂 目录记忆（{len(dir_memories)}）" if dir_memories else "📂 目录记忆"
    with st.expander(dm_title, expanded=False):
        if not dir_memories:
            st.caption("Agent 访问文件目录后，会自动在此生成目录记忆。")
        else:
            for entry in dir_memories:
                dpath = entry["path"]
                ts = entry["updated_at"][:10] if entry["updated_at"] else ""
                dm_key = f"dm_editing_{dpath}"
                if dm_key not in st.session_state:
                    st.session_state[dm_key] = False

                st.markdown(
                    f"<small style='color:#888'>📁 <code>{dpath}</code>"
                    f"{'  ·  ' + ts if ts else ''}</small>",
                    unsafe_allow_html=True,
                )

                if st.session_state[dm_key]:
                    new_mem = st.text_area(
                        "编辑目录记忆", value=entry["memory"], height=120,
                        key=f"dm_area_{dpath}", label_visibility="collapsed",
                    )
                    dc1, dc2, _ = st.columns([1, 1, 4])
                    with dc1:
                        if st.button("保存", key=f"dm_save_{dpath}",
                                     use_container_width=True):
                            st.session_state.agent._dir_memory.save(dpath, new_mem.strip())
                            st.session_state[dm_key] = False
                            st.rerun()
                    with dc2:
                        if st.button("取消", key=f"dm_cancel_{dpath}",
                                     use_container_width=True):
                            st.session_state[dm_key] = False
                            st.rerun()
                else:
                    st.markdown(
                        f"<div style='padding:6px 8px;margin:4px 0 8px 0;border-radius:6px;"
                        f"background:#1a2a1a;border-left:3px solid #2e7d32;font-size:0.85rem'>"
                        f"{entry['memory']}</div>",
                        unsafe_allow_html=True,
                    )
                    dc1, dc2, _ = st.columns([1, 1, 5])
                    with dc1:
                        if st.button("✏️", key=f"dm_edit_{dpath}",
                                     help="编辑此目录记忆", use_container_width=True):
                            for e2 in dir_memories:
                                st.session_state[f"dm_editing_{e2['path']}"] = False
                            st.session_state[dm_key] = True
                            st.rerun()
                    with dc2:
                        if st.button("🗑", key=f"dm_del_{dpath}",
                                     help="删除此目录记忆", use_container_width=True):
                            st.session_state.agent._dir_memory.delete(dpath)
                            st.rerun()
                st.divider()

# =====================================================================
# Query handling (top-level, after all containers)
# =====================================================================
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.trace = []
    st.session_state.ma_tasks = []
    st.session_state.ma_trace = []

    if st.session_state.multi_agent_mode:
        # ---- Multi-agent path ----
        orch: Orchestrator = st.session_state.orchestrator
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *多智能体规划中...*")

            events = []
            final_answer = ""
            for event in orch.run_stream(query):
                events.append(event)
                if event["type"] == "plan":
                    st.session_state.ma_tasks = event["tasks"]
                    placeholder.markdown("⏳ *任务规划完成，执行子任务中...*")
                elif event["type"] == "task_start":
                    for t in st.session_state.ma_tasks:
                        if t["id"] == event["task_id"]:
                            t["status"] = "running"
                elif event["type"] == "task_done":
                    for t in st.session_state.ma_tasks:
                        if t["id"] == event["task_id"]:
                            t["status"] = event["status"]
                    st.session_state.ma_trace.append(event)
                elif event["type"] == "finished":
                    final_answer = event.get("answer", "")
            st.session_state.ma_trace = events
            st.session_state.trace = events
            placeholder.markdown(final_answer or "No result.")

        st.session_state.messages.append({"role": "assistant", "content": final_answer})
    else:
        # ---- Single-agent path ----
        agent: Agent = st.session_state.agent
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *Thinking...*")

            steps = list(agent.run_stream(query))
            st.session_state.trace = steps

            final = next((s["answer"] for s in steps if s["type"] == "finished"), None)
            if final is None:
                final = next((s["message"] for s in steps if s["type"] == "error"), "No result.")
            placeholder.markdown(final)

            # Render any visualizations generated during this run
            viz_files = [s["visualization"] for s in steps if s.get("visualization")]
            if viz_files:
                from config.settings import settings
                from pathlib import Path
                for vf in viz_files:
                    viz_path = Path(settings.SANDBOX_ROOT) / vf
                    if viz_path.exists():
                        st.components.v1.html(
                            viz_path.read_text(encoding="utf-8"),
                            height=420, scrolling=False)

        st.session_state.messages.append({"role": "assistant", "content": final})

    st.rerun()
