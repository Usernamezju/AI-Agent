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


def _handle_upload(uploaded_file, agent: Agent, scope: str = "global") -> None:
    """Save uploaded file to sandbox, extract text/image, and inject a notice.

    *scope* is ``"global"`` or ``"session"`` — determines the target subdirectory.
    """
    from pathlib import Path
    from config.settings import settings
    from src.tools.file_extractor import extract_text, extract_image_description, IMAGE_EXTENSIONS

    file_key = f"{scope}:{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state.last_uploaded == file_key:
        return
    st.session_state.last_uploaded = file_key

    sandbox = Path(settings.SANDBOX_ROOT)
    conv_id = getattr(agent, "_current_conv_id", None)

    # Determine save directory based on scope
    if scope == "session" and conv_id:
        save_dir = sandbox / "sessions" / conv_id
        path_hint = f"sessions/{conv_id}/{uploaded_file.name}（仅本对话）"
    else:
        save_dir = sandbox / "global"
        path_hint = f"global/{uploaded_file.name}（所有对话可用）"

    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / uploaded_file.name
    save_path.write_bytes(uploaded_file.getvalue())

    suffix = save_path.suffix.lower()

    # ---- image → Qwen-VL description ----
    if suffix in IMAGE_EXTENSIONS:
        from src.llm import create_llm_client
        try:
            vision_client = create_llm_client("qwen")
            vision_client.model = settings.QWEN_VISION_MODEL
            description, img_error = extract_image_description(save_path, vision_client)
        except Exception:
            description, img_error = "", "无法创建视觉模型客户端，请检查 QWEN_API_KEY"

        if img_error:
            notice = (
                f"[系统通知] 用户上传了图片：{uploaded_file.name}（{uploaded_file.size} 字节）\n"
                f"文件已保存至 {path_hint}\n"
                f"图片理解失败：{img_error}"
            )
        else:
            preview = description[:300] + "…" if len(description) > 300 else description
            notice = (
                f"[系统通知] 用户上传了图片：{uploaded_file.name}（{uploaded_file.size} 字节）\n"
                f"文件已保存至 {path_hint}\n"
                f"图片内容描述（Qwen-VL）：\n```\n{preview}\n```\n"
                "请基于以上描述回答用户关于此图片的问题。"
            )
    else:
        # ---- text / PDF / other ----
        text, error = extract_text(save_path)
        if error:
            notice = (
                f"[系统通知] 用户上传了文件：{uploaded_file.name}（{uploaded_file.size} 字节）\n"
                f"文件已保存至 {path_hint}，但文本提取失败：{error}\n"
                "如需读取，请使用 local_filesystem 工具。"
            )
        else:
            preview = text[:300] + "…" if len(text) > 300 else text
            notice = (
                f"[系统通知] 用户上传了文件：{uploaded_file.name}（{uploaded_file.size} 字节）\n"
                f"文件已保存至 {path_hint}，内容预览：\n"
                f"```\n{preview}\n```\n"
                f"完整内容可用 local_filesystem 工具读取，path 填写 \"{path_hint.split('（')[0]}\"。"
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
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════
with st.sidebar:
    # ---- Settings panel with tabs ----
    with st.expander("⚙️ 设置", expanded=False):
        _settings_agent: Agent = st.session_state.agent
        _stabs = st.tabs(["🔑 模型", "🧠 记忆", "🔧 工具", "📂 目录"])

        # ================================================================
        # Tab 1: Model settings
        # ================================================================
        with _stabs[0]:
            from dotenv import load_dotenv
            _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            load_dotenv(_env_path, override=True)
            _cur_provider = os.getenv("DEFAULT_LLM_PROVIDER", "deepseek")
            _cur_deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
            _cur_qwen_key = os.getenv("QWEN_API_KEY", "")
            _cur_deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            _cur_qwen_model = os.getenv("QWEN_MODEL", "qwen-plus")

            provider = st.selectbox("LLM 供应商", ["deepseek", "qwen"],
                                     index=0 if _cur_provider == "deepseek" else 1,
                                     key="settings_provider")
            if provider == "deepseek":
                api_key = st.text_input("DeepSeek API Key", value=_cur_deepseek_key,
                                         type="password", key="settings_ds_key", placeholder="sk-...")
                model = st.text_input("模型名称", value=_cur_deepseek_model, key="settings_ds_model")
            else:
                api_key = st.text_input("Qwen API Key", value=_cur_qwen_key,
                                         type="password", key="settings_qw_key", placeholder="sk-...")
                model = st.text_input("模型名称", value=_cur_qwen_model, key="settings_qw_model")

            if st.button("💾 保存设置", use_container_width=True, key="settings_save"):
                with open(_env_path, "w", encoding="utf-8") as f:
                    f.write("# AI Agent Framework — Configuration\n")
                    f.write(f"DEFAULT_LLM_PROVIDER={provider}\n")
                    if provider == "deepseek":
                        f.write(f"DEEPSEEK_API_KEY={api_key}\n")
                        if model: f.write(f"DEEPSEEK_MODEL={model}\n")
                        if _cur_qwen_key: f.write(f"QWEN_API_KEY={_cur_qwen_key}\n")
                    else:
                        f.write(f"QWEN_API_KEY={api_key}\n")
                        if model: f.write(f"QWEN_MODEL={model}\n")
                        if _cur_deepseek_key: f.write(f"DEEPSEEK_API_KEY={_cur_deepseek_key}\n")
                    f.write("SANDBOX_ROOT=./sandbox\n")
                try:
                    from src.llm import create_llm_client
                    from src.tools import tool_registry
                    _settings_agent._llm = create_llm_client(provider)
                    _settings_agent._pm.update_tools(tool_registry.generate_descriptions())
                    _settings_agent._extractor._llm = _settings_agent._llm
                    st.success(f"已切换到 {provider} / {model}")
                except Exception as e:
                    st.error(f"切换失败：{e}")

        # ================================================================
        # Tab 2: Long-term memory
        # ================================================================
        with _stabs[1]:
            _ltm = _settings_agent._ltm
            st.caption("新增记忆")
            if "fact_input_counter" not in st.session_state:
                st.session_state.fact_input_counter = 0
            new_fact = st.text_area("新增记忆", height=60,
                                     key=f"set_fact_{st.session_state.fact_input_counter}",
                                     label_visibility="collapsed", placeholder="输入需要记住的内容…")
            if st.button("添加", key=f"set_addf_{st.session_state.fact_input_counter}",
                         disabled=(not new_fact.strip()), use_container_width=True):
                _ltm.add_fact(new_fact.strip()); _ltm.save()
                st.session_state.fact_input_counter += 1; st.rerun()
            st.divider()
            facts = _ltm.get_all_facts()
            if not facts:
                st.caption("暂无长期记忆")
            else:
                for fact in reversed(facts):
                    fid, ts, content = fact["id"], fact["timestamp"][:10], fact["content"]
                    st.markdown(f"<small style='color:#888'>{ts}</small>", unsafe_allow_html=True)
                    st.markdown(f"<small>{content}</small>", unsafe_allow_html=True)
                    c1, c2 = st.columns([1, 1])
                    if c1.button("✏️", key=f"smed_{fid}"):
                        st.session_state[f"smediting_{fid}"] = True; st.rerun()
                    if c2.button("🗑", key=f"smdel_{fid}"):
                        _ltm.remove_fact(fid); _ltm.save(); st.rerun()
                    if st.session_state.get(f"smediting_{fid}"):
                        nc = st.text_area("编辑", value=content, height=60,
                                           key=f"smarea_{fid}", label_visibility="collapsed")
                        sc1, sc2 = st.columns(2)
                        if sc1.button("保存", key=f"smsave_{fid}"):
                            _ltm.update_fact(fid, nc.strip()); _ltm.save()
                            st.session_state[f"smediting_{fid}"] = False; st.rerun()
                        if sc2.button("取消", key=f"smcancel_{fid}"):
                            st.session_state[f"smediting_{fid}"] = False; st.rerun()
                st.divider()
                if st.button("🗑️ 清空全部记忆", key="sm_clear", use_container_width=True):
                    _ltm.clear(); st.rerun()

        # ================================================================
        # Tab 3: Tools
        # ================================================================
        with _stabs[2]:
            from src.tools import tool_registry as _tr
            all_tools = _tr.list_all() if hasattr(_tr, "list_all") else _tr.list_names()
            if isinstance(all_tools[0], str) if all_tools else True:
                all_tools = [{"name": n} for n in all_tools]
            builtin = [t for t in all_tools if not t.get("synthesized")]
            synthesized = [t for t in all_tools if t.get("synthesized")]
            if builtin:
                st.caption(f"内置工具（{len(builtin)}）")
                for t in builtin:
                    desc = t.get("description", "")[:60]
                    st.markdown(f"<small>🔹 <b>{t['name']}</b> — {desc}…</small>",
                                unsafe_allow_html=True)
            if synthesized:
                st.caption(f"✨ AI 合成（{len(synthesized)}）")
                for t in synthesized:
                    st.markdown(f"<small style='color:#f0a500'>🔸 <b>{t['name']}</b></small>",
                                unsafe_allow_html=True)
                    if st.button("🗑", key=f"smtool_{t['name']}"):
                        _tr.unregister(t['name']); st.rerun()
            if not all_tools:
                st.caption("暂无工具")

        # ================================================================
        # Tab 4: Directory memory
        # ================================================================
        with _stabs[3]:
            _dm_all = _settings_agent._dir_memory.list_all()
            _dm_cur = st.session_state.get("working_dir", "")
            _dm_match = next((e for e in _dm_all if e["path"] == _dm_cur), None)
            if not _dm_all:
                st.caption("Agent 访问目录后会自动生成记忆")
            else:
                if _dm_match:
                    st.caption(f"📁 当前目录")
                    st.markdown(f"<small style='color:#888'>{_dm_match['memory'][:200]}</small>",
                                unsafe_allow_html=True)
                    st.divider()
                for entry in _dm_all:
                    if entry["path"] != _dm_cur:
                        st.markdown(f"<small style='color:#888'>{entry['path'][:40]}<br>{entry['memory'][:60]}…</small>",
                                    unsafe_allow_html=True)
                        if st.button("🗑", key=f"smdm_{entry['path'][:20]}"):
                            _settings_agent._dir_memory.delete(entry["path"]); st.rerun()
    st.markdown("### 🔍 搜索对话")
    def _do_search():
        q = st.session_state.get("search_query", "").strip()
        if q:
            agent_obj: Agent = st.session_state.agent
            st.session_state.search_results = agent_obj._search.search(
                q, use_ai=st.session_state.get("use_ai_search", False))
        else:
            st.session_state.search_results = None

    sq = st.text_input("搜索对话", placeholder="输入关键词后按 Enter 搜索…",
                        key="search_query", label_visibility="collapsed",
                        on_change=_do_search)
    c1, c2 = st.columns(2)
    use_ai = c1.checkbox("AI 语义", value=False, key="use_ai_search",
                         on_change=_do_search)
    if c2.button("搜索", key="search_btn", use_container_width=True):
        _do_search()

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

    _default_dir = str(Path.cwd())
    if "working_dir" not in st.session_state:
        st.session_state.working_dir = _default_dir

    st.sidebar.caption("📂 工作目录")

    _fs_tool = _sidebar_tr.get("local_filesystem")
    _ci_tool = _sidebar_tr.get("code_interpreter")
    _current = getattr(_fs_tool, "current_root", st.session_state.working_dir)

    _display = _current if len(_current) <= 42 else "…" + _current[-40:]
    st.sidebar.markdown(
        f"<small style='color:#888'><code>{_display}</code></small>",
        unsafe_allow_html=True,
    )

    # --- Manual path input (with Windows→WSL auto-conversion) ---
    _manual = st.sidebar.text_input(
        "输入路径", placeholder="粘贴路径后按 Enter…",
        key="wd_manual", label_visibility="collapsed"
    )
    if _manual and _manual.strip() != _current:
        _mp = _manual.strip()
        import platform, re as _re
        if platform.system() == "Linux" and _re.match(r'^[A-Z]:[\\/]', _mp):
            _mp = "/mnt/" + _mp[0].lower() + _mp[2:].replace("\\", "/")
        _mp = str(Path(_mp).expanduser().resolve())
        if not Path(_mp).exists():
            st.sidebar.error(f"路径不存在：{_mp}")
        else:
            _err = _fs_tool.set_root(_mp) if _fs_tool else ""
            if not _err and _ci_tool:
                _err = _ci_tool.set_sandbox(_mp)
            if _err:
                st.sidebar.error(f"切换失败：{_err}")
            else:
                st.session_state.working_dir = _mp
                st.sidebar.success(f"已切换")
                st.rerun()

    # System-native folder picker
    def _pick_directory(initial: str) -> str:
        import subprocess, sys, shutil
        try:
            win_initial = subprocess.run(
                ["wslpath", "-w", initial], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except Exception:
            win_initial = initial
        for ps_cmd in ("powershell.exe", "powershell"):
            if not shutil.which(ps_cmd):
                continue
            ps = ("Add-Type -AssemblyName System.Windows.Forms;"
                  "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
                  "$d.Description='选择工作目录';"
                  f"$d.SelectedPath={repr(win_initial)};"
                  "if($d.ShowDialog()-eq'OK'){$d.SelectedPath}")
            try:
                r = subprocess.run([ps_cmd,"-NoProfile","-Command",ps],
                                   capture_output=True,text=True,timeout=120)
                wp = r.stdout.strip()
                if wp:
                    wsl = subprocess.run(["wslpath","-u",wp],capture_output=True,text=True,timeout=5)
                    return wsl.stdout.strip() or wp
            except Exception:
                continue
        if sys.platform == "win32":
            try:
                import tkinter as tk; from tkinter import filedialog
                root=tk.Tk();root.withdraw();root.wm_attributes('-topmost',1)
                d=filedialog.askdirectory(title='选择工作目录',initialdir=initial)
                root.destroy();return d or ""
            except Exception:
                pass
        try:
            import tkinter as tk; from tkinter import filedialog
            root=tk.Tk();root.withdraw();root.wm_attributes('-topmost',1)
            d=filedialog.askdirectory(title='选择工作目录',initialdir=initial)
            root.destroy()
            if d: return d
        except Exception:
            pass
        for cmd,args in [("zenity",["--file-selection","--directory","--title=选择工作目录"]),
                          ("kdialog",["--getexistingdirectory",initial])]:
            if shutil.which(cmd):
                try:
                    r=subprocess.run([cmd]+args,capture_output=True,text=True,timeout=30)
                    if r.stdout.strip(): return r.stdout.strip()
                except Exception:
                    continue
        return ""

    # Browse button
    if st.sidebar.button("📁 浏览…", key="wd_browse", use_container_width=True):
        _picked = _pick_directory(_current)
        if _picked:
            _err = _fs_tool.set_root(_picked) if _fs_tool else ""
            if not _err and _ci_tool:
                _err = _ci_tool.set_sandbox(_picked)
            if _err:
                st.sidebar.error(f"切换失败：{_err}")
            else:
                st.session_state.working_dir = _picked
                st.rerun()

    st.sidebar.divider()

    # ═══════════════════════════════════════════════════════════════════
    # Dual-tier file upload: global + session
    # ═══════════════════════════════════════════════════════════════════
    from pathlib import Path as _Path
    from config.settings import settings as _fs_settings

    _sandbox_path = _Path(_fs_settings.SANDBOX_ROOT)
    sidebar_agent: Agent = st.session_state.agent

    ftab1, ftab2 = st.sidebar.tabs(["🌐 全局文件", "💬 对话文件"])

    # ---- Tab 1: Global files ----
    with ftab1:
        st.caption("所有对话可访问")
        global_dir = _sandbox_path / "global"
        global_dir.mkdir(parents=True, exist_ok=True)
        # Upload
        gfile = st.file_uploader(
            "全局上传", type=None, key="global_uploader",
            label_visibility="collapsed",
        )
        if gfile is not None:
            _handle_upload(gfile, sidebar_agent, scope="global")
        # List
        gfiles = sorted([f for f in global_dir.iterdir() if f.is_file()],
                        key=lambda x: x.name)
        if not gfiles:
            st.caption("（空）")
        else:
            for gf in gfiles:
                cg1, cg2 = st.columns([5, 1])
                with cg1:
                    st.markdown(f"<small>{gf.name}</small>", unsafe_allow_html=True)
                with cg2:
                    if st.button("🗑", key=f"delg_{gf.name}", use_container_width=True):
                        gf.unlink()
                        st.rerun()

    # ---- Tab 2: Session files ----
    with ftab2:
        st.caption("仅当前对话可见")
        _sid = sidebar_agent._current_conv_id
        if not _sid:
            st.caption("请先发送消息以开始对话")
        else:
            session_dir = _sandbox_path / "sessions" / _sid
            session_dir.mkdir(parents=True, exist_ok=True)
            # Upload
            sfile = st.file_uploader(
                "对话上传", type=None, key="session_uploader",
                label_visibility="collapsed",
            )
            if sfile is not None:
                _handle_upload(sfile, sidebar_agent, scope="session")
            # List
            sfiles = sorted([f for f in session_dir.iterdir() if f.is_file()],
                            key=lambda x: x.name)
            if not sfiles:
                st.caption("（空）")
            else:
                for sf in sfiles:
                    cs1, cs2 = st.columns([5, 1])
                    with cs1:
                        st.markdown(f"<small>{sf.name}</small>", unsafe_allow_html=True)
                    with cs2:
                        if st.button("🗑", key=f"dels_{sf.name}", use_container_width=True):
                            sf.unlink()
                            st.rerun()

# ---- chat_input must be at top level (outside any column) so it floats to bottom ----
query = st.chat_input("输入任务…")

# ═══════════════════════════════════════════════════════════════════════
# File upload popover (📎 button — placed above chat area)
# ═══════════════════════════════════════════════════════════════════════
with st.popover("📎 添加文件"):
    st.caption("添加文件到当前对话")
    _pop_tab1, _pop_tab2 = st.tabs(["📂 从全局选取", "📤 本地上传"])

    _pop_agent: Agent = st.session_state.agent
    _pop_sid = _pop_agent._current_conv_id
    _pop_sandbox = Path(_fs_settings.SANDBOX_ROOT)

    with _pop_tab1:
        # List global files, click to copy to session
        _gdir = _pop_sandbox / "global"
        _gdir.mkdir(parents=True, exist_ok=True)
        _gfiles = sorted([f for f in _gdir.iterdir() if f.is_file()], key=lambda x: x.name)
        if not _gfiles:
            st.caption("全局目录为空")
        else:
            for _gf in _gfiles:
                if st.button(f"📄 {_gf.name}", key=f"pop_g_{_gf.name}", use_container_width=True):
                    if _pop_sid:
                        _sdir = _pop_sandbox / "sessions" / _pop_sid
                        _sdir.mkdir(parents=True, exist_ok=True)
                        (_sdir / _gf.name).write_bytes(_gf.read_bytes())
                        st.rerun()
                    else:
                        st.warning("请先发送消息以开始对话")

    with _pop_tab2:
        if not _pop_sid:
            st.caption("请先发送消息以开始对话")
        else:
            _pfile = st.file_uploader("拖拽文件到此处", type=None, key="popup_uploader",
                                      label_visibility="collapsed")
            if _pfile is not None:
                _handle_upload(_pfile, _pop_agent, scope="session")

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
# Query handling (top-level, after all containers)
# =====================================================================
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.ma_tasks = []
    st.session_state.ma_trace = []

    if st.session_state.multi_agent_mode:
        # ---- Multi-agent path ----
        orch: Orchestrator = st.session_state.orchestrator
        with st.chat_message("assistant"):
            think_container = st.status("🧠 多智能体规划中…", expanded=True)

            events = []
            final_answer = ""
            for event in orch.run_stream(query):
                events.append(event)
                if event["type"] == "plan":
                    st.session_state.ma_tasks = event["tasks"]
                    think_container.write(f"📋 任务计划：{len(event['tasks'])} 个子任务")
                elif event["type"] == "task_start":
                    for t in st.session_state.ma_tasks:
                        if t["id"] == event["task_id"]:
                            t["status"] = "running"
                    think_container.write(f"🔄 执行中：{event.get('task_id', '?')}")
                elif event["type"] == "task_done":
                    for t in st.session_state.ma_tasks:
                        if t["id"] == event["task_id"]:
                            t["status"] = event["status"]
                    st.session_state.ma_trace.append(event)
                    ok = "✅" if event.get("status") == "done" else "❌"
                    think_container.write(
                        f"{ok} 完成：{event.get('task_id', '?')} — {str(event.get('result', ''))[:100]}")
                elif event["type"] == "finished":
                    final_answer = event.get("answer", "")
                    think_container.update(
                        label=f"思考完成（{len(events)} 个事件）", state="complete", expanded=False)
            st.session_state.ma_trace = events
            st.session_state.trace = events
            st.markdown(final_answer or "No result.")

        st.session_state.messages.append({"role": "assistant", "content": final_answer})
    else:
        # ---- Single-agent path ----
        agent: Agent = st.session_state.agent
        with st.chat_message("assistant"):
            # Real-time thinking container
            think_container = st.status("思考中…", expanded=True)
            steps: list[dict] = []
            final: str = ""

            for step in agent.run_stream(query):
                steps.append(step)
                etype = step.get("type")

                if etype == "step":
                    action = step.get("action", "?")
                    thought = step.get("thought", "")[:200]
                    obs = step.get("observation", "")[:200]
                    think_container.write(
                        f"🔧 **{action}**\n\n> {thought}\n\n👁 {obs}"
                    )
                elif etype == "parse_error":
                    think_container.write(f"⚠️ Parse error: {step.get('error', '?')}")
                elif etype == "finished":
                    final = step.get("answer", "")
                    think_container.update(
                        label=f"思考完成（{len(steps)} 步）", state="complete", expanded=False)
                elif etype == "error":
                    final = step.get("message", "Error.")
                    think_container.update(label="思考出错", state="error")

            st.session_state.trace = steps
            if not final:
                final = next((s.get("message", "No result.") for s in steps if s.get("type") == "error"), "No result.")
            st.markdown(final)

            # Render any visualizations generated during this run
            viz_files = [s["visualization"] for s in steps if s.get("visualization")]
            if viz_files:
                from pathlib import Path
                from config.settings import settings
                _conv_id = getattr(st.session_state.agent, "_current_conv_id", None)
                _sandbox_root = str(Path(settings.SANDBOX_ROOT).resolve())
                for vf in viz_files:
                    # Try: absolute path, sandbox root, viz tool save dir, session dir
                    candidates = [Path(vf),
                                  Path(_sandbox_root) / Path(vf).name,
                                  Path(_sandbox_root) / vf]
                    try:
                        candidates.append(Path(st.session_state.get("working_dir", ".")) / Path(vf).name)
                    except Exception:
                        pass
                    if _conv_id:
                        try:
                            candidates.append(
                                Path(_sandbox_root) / "sessions" / _conv_id / "viz" / Path(vf).name)
                        except Exception:
                            pass
                    for vp in candidates:
                        try:
                            if vp.exists():
                                st.caption(f"📊 {Path(vp).name}")
                                st.components.v1.html(
                                    vp.read_text(encoding="utf-8"),
                                    height=420, scrolling=False)
                                break
                        except Exception:
                            continue

        st.session_state.messages.append({"role": "assistant", "content": final})

    st.rerun()
