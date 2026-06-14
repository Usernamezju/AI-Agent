# AI Agent Framework

从零搭建的 ReAct 范式 AI Agent 框架——让大语言模型从"会说话"变成"能做事"，并在此基础上实现了记忆进化、多智能体协作、运行时工具合成等多项创新设计。

---

## 核心原理

基于 **ReAct（Reasoning + Acting）** 范式，通过 Thought → Action → Observation 感知-行动循环，赋予 LLM 动态调用外部工具的能力。不依赖 LangChain 等高层框架，所有核心组件均手动实现。

```
用户输入
  ↓
[Thought]  LLM 推理当前状态，决定下一步行动
  ↓
[Action]   选择工具 + 构造参数
  ↓
[Tool]     工具执行，返回结果
  ↓
[Observation]  结果反馈给 LLM
  ↓
（循环，直到 Final Answer）
```

---

## 项目结构

```
├── config/                     # 全局配置
│   ├── settings.py             #   统一配置入口（env + YAML + 默认值三层优先级）
│   ├── loader.py               #   YAML 配置加载器
│   └── tools_registry.json
├── src/
│   ├── core/                   # 核心执行引擎
│   │   ├── agent.py            #   Agent 主类 + ReAct 主循环
│   │   ├── state_machine.py    #   状态机（7 状态 + 严格转移表）
│   │   ├── parser.py           #   三层容错解析器
│   │   └── error_handler.py    #   异常反馈闭环
│   ├── llm/                    # LLM 通信层
│   │   ├── base.py             #   抽象基类
│   │   ├── deepseek_client.py  #   DeepSeek（OpenAI 兼容协议）
│   │   └── qwen_client.py      #   Qwen（同一客户端类）
│   ├── prompts/                # 提示词工程
│   │   ├── system_prompt.py    #   ReAct 模板（含可视化和辩论触发规则）
│   │   ├── few_shot_examples.py#   少样本示例
│   │   └── prompt_manager.py   #   动态消息构建
│   ├── tools/                  # 工具系统（9 个工具）
│   │   ├── base.py             #   BaseTool（ABC，duck typing 兼容）
│   │   ├── registry.py         #   统一注册表
│   │   ├── calculator.py       #   AST 安全计算器
│   │   ├── wikipedia_search.py #   维基百科搜索
│   │   ├── local_filesystem.py #   沙箱文件读写
│   │   ├── code_interpreter.py #   Python 子进程沙箱
│   │   ├── visualizer.py       #   Chart.js 图表生成
│   │   ├── debate_tool.py      #   多视角辩论工具
│   │   ├── memory_tool.py      #   长期记忆读写工具
│   │   ├── tool_synthesizer.py #   ★ 运行时工具合成
│   │   └── file_extractor.py   #   文件/图片内容提取
│   ├── memory/                 # 三层记忆体系
│   │   ├── message_queue.py    #   短期记忆（当次 ReAct 步骤）
│   │   ├── sliding_window.py   #   上下文窗口截断
│   │   ├── instruction_keeper.py#  初始指令保留
│   │   ├── token_counter.py    #   Token 估算
│   │   ├── conversation_history.py# 会话记忆（渐进式压缩）
│   │   ├── long_term_memory.py #   跨会话长期记忆
│   │   ├── memory_extractor.py #   LLM 自动提取 + 去重
│   │   └── reflection_store.py #   ★ Reflexion 复盘存储（BM25 索引）
│   ├── storage/                # 持久化层
│   │   ├── conversation_store.py# 对话历史持久化
│   │   └── search_engine.py    #   BM25 + AI 重排搜索引擎
│   └── multi_agent/            # 多智能体系统
│       ├── models.py           #   SubTask / ExecutionPlan 数据模型
│       ├── planner.py          #   LLM 任务分解器
│       ├── executor.py         #   拓扑调度 + 并行执行器
│       └── orchestrator.py     #   协调器（规划→执行→综合）
├── ui/                         # Streamlit Web 界面
│   ├── app.py                  #   主界面（对话 + 实时推理轨迹）
│   └── components/             #   聊天面板、思维追踪、工具统计
├── chainlit_app.py             # Chainlit 界面（ChatGPT 风格，推荐）
├── scripts/
│   └── run_agent.py            #   命令行交互入口
└── tests/                      # 测试套件
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 填入 DeepSeek API Key（必填）
# 填入 Qwen API Key（可选，用于多模态图片理解）
```

`.env` 示例：
```
DEEPSEEK_API_KEY=sk-your-key-here
QWEN_API_KEY=sk-your-qwen-key-here   # 可选
SANDBOX_ROOT=./sandbox
```

### 3. 启动

```bash
# Chainlit 界面（推荐，ChatGPT 风格）
chainlit run chainlit_app.py --watch

# 原 Streamlit 界面
streamlit run ui/app.py

# 命令行模式
python scripts/run_agent.py
```

---

## 功能全览

### 一、ReAct 核心引擎

#### 1.1 严格状态机

用 7 个枚举状态 + 静态转移表管理 Agent 生命周期，非法状态跳转直接抛 `RuntimeError`，确保执行路径可预测：

```
IDLE → THINKING → PARSING → ACTING → OBSERVING → (回到 THINKING)
                          ↘ FINISHED    ↘ ERROR
```

任务完成后可通过 `agent.state_path` 获取完整执行路径，例如：

```
IDLE → THINKING → PARSING → ACTING → OBSERVING → THINKING → PARSING → FINISHED
```

#### 1.2 三层容错解析器

LLM 输出格式并不总是完美的。解析器对 `Action Input` 采用三层降级策略：

1. **层一**：识别 ` ```json ... ``` ` 围栏块内的 JSON
2. **层二**：识别 `Action Input:` 后裸写的 JSON 对象
3. **层三**：提取原始文本，剥离围栏后尝试解析；解析失败则在 dict 中存入 `__parse_error__` 键，触发错误反馈闭环

解析失败时，错误描述会作为 `Observation` 反馈给 LLM，让其自我纠正——这是框架容错能力的核心。

#### 1.3 工具系统（Duck Typing）

工具注册采用 duck typing 而非强制继承：只要对象拥有 `name`、`description`、`parameters`、`run()` 四个属性，即可注册到 `ToolRegistry`。新增工具无需修改任何核心文件：

```python
# 只需两步：
# 1. 实现工具类（不必继承 BaseTool）
class MyTool:
    name = "my_tool"
    description = "..."
    parameters = {"type": "object", "properties": {...}, "required": [...]}
    def run(self, **kwargs) -> str: ...

# 2. 在 register_all_tools() 中注册
```

---

### 二、工具集（9 个）

#### 2.1 安全计算器（calculator）

基于 Python `ast` 模块的白名单求值器，**完全不使用 `eval()`**。只允许通过白名单节点类型（`BinOp`、`UnaryOp`、`Constant`、`Call`）和白名单函数（`abs`、`round`、`sqrt`、`pow`），拒绝一切其他 AST 节点，从根源杜绝代码注入风险。

#### 2.2 维基百科搜索（wikipedia_search）

调用 Wikipedia REST API，先搜索最佳匹配标题，再获取文章摘要，截断到 1200 字符。使用 `urllib`（Python 标准库），**零外部依赖**。支持中文（`zh`）和其他语言版本。

#### 2.3 沙箱文件系统（local_filesystem）

支持 `read` / `write` / `list` 三种操作。安全策略：通过 `Path.resolve()` + `startswith()` 双重校验，确保所有路径操作都被限制在沙箱根目录内，无法通过 `../` 等路径穿越逃逸。

#### 2.4 代码解释器（code_interpreter）

LLM 编写 Python 代码，框架在 **独立子进程** 中执行，结果通过标准输出返回。关键设计：
- 临时文件写入沙箱目录，执行后立即删除
- 与 `local_filesystem` 共享工作目录，可读写同一批文件
- 执行超时限制（最长 30 秒）
- 过滤 `DeprecationWarning` 等噪音，只返回真实错误

这让 Agent 具备了完整的「写代码 → 运行 → 看结果」能力。

#### 2.5 数据可视化（visualize）

接收结构化数据，生成基于 **Chart.js** 的自包含 HTML 图表文件，渲染到对话界面。支持 6 种图表类型（bar / line / pie / doughnut / radar / scatter），颜色方案内置 8 色循环。

**触发机制**：系统提示词中注入了图表选择规则，当数据涉及比较、趋势、比例、分布（≥3个数据点）时，Agent **自主决定** 是否调用可视化——不需要用户明确要求。

#### 2.6 多视角辩论（perspective_debate）

对有争议的问题，框架发起两次 LLM 调用，分别让"正方"和"反方"以各自立场论辩，最多支持 2 轮交叉辩论（第 2 轮包含对对方上轮论点的反驳）。Agent 综合辩论结果给出平衡结论。

**触发机制**：与可视化类似，系统提示词内嵌了触发规则——凡涉及伦理争议、预测类、开放式问题，Agent 会主动调用辩论工具。

#### 2.7 长期记忆工具（memory_store / memory_recall）

允许 Agent 在对话中主动存储和检索长期事实。这两个工具需要注入 `LongTermMemory` 和 LLM 客户端实例，因此在 `agent.py` 中通过依赖注入注册，而不是在 `__init__.py` 里静态注册。

---

### 三、三层记忆体系

这是本框架在记忆管理上最完整的设计，三层各司其职：

```
┌─────────────────────────────────────────────────────┐
│  短期记忆（MessageQueue）                             │
│  → 当次 ReAct 循环内的 Thought/Action/Observation    │
│  → 循环结束即清空                                     │
├─────────────────────────────────────────────────────┤
│  会话记忆（ConversationHistory）                      │
│  → 当次对话内的多轮问答历史                           │
│  → Token 超限时 LLM 自动压缩最旧的一半，保留摘要      │
│  → 信息永不丢失，只会渐进变稀疏                       │
├─────────────────────────────────────────────────────┤
│  长期记忆（LongTermMemory）                           │
│  → 跨会话持久化（JSON 文件）                          │
│  → LLM 自动从每轮对话中提取值得记住的事实             │
│  → LLM 自动去重合并语义相似条目                       │
│  → 每次推理前注入系统提示词                           │
└─────────────────────────────────────────────────────┘
```

#### 3.1 渐进式对话压缩

`ConversationHistory` 的核心创新：当 Token 估算超出预算（上下文窗口的 25%），不是简单地截断最早的轮次，而是：

1. 把最老的一半轮次 + 当前摘要一起发给 LLM
2. LLM 将它们压缩成不超过 300 字的更新摘要
3. 保留最近轮次的完整文本

这样无论对话多长，信息都不会彻底丢失，只是越旧的内容越稀疏。

#### 3.2 LLM 驱动的记忆提取与去重

`MemoryExtractor` 在每轮对话结束后自动运行：
- **提取**：判断对话中是否有"值得长期记住"的信息（用户姓名、偏好、明确要求记住的事）
- **去重**：提取时传入已有记忆列表，避免重复存储
- **更新**：与已有记忆矛盾的新信息标注 `[UPDATE]` 前缀
- **LLM 合并**：定期用 LLM 合并语义相似的条目，防止记忆膨胀

所有记忆写入均使用**原子操作**（先写 `.tmp` 文件，再 `os.replace`），防止程序崩溃导致数据损坏。

#### 3.3 上下文窗口保护

`SlidingWindow` 保留原始用户 query + 最近 N×2 条消息，超出的部分截断；`InstructionKeeper` 在截断发生时，将原始任务作为 `[Reminder]` 消息重新注入，防止 Agent 因上下文丢失而"忘记"自己在做什么。

---

### 四、★ Reflexion 架构——从经验中学习

> **思路来源**：Shinn et al., *"Reflexion: Language Agents with Verbal Reinforcement Learning"* (NeurIPS 2023)
>
> 原论文核心思想：让 Agent 在任务失败后生成"语言反思"并存储，下次遇到类似任务时读取这些反思作为"过去的教训"，实现无需梯度更新的经验积累。

#### 本项目的实现

传统 ReAct Agent 失败了就失败了，下次面对同类问题仍会犯同样的错误。我们在框架层面增加了完整的 Reflexion 闭环：

**任务结束后（异步后台线程）**：
1. 收集本轮完整推理轨迹（所有 Thought/Action/Observation）
2. 向 LLM 发起一次"事后复盘"调用，提示词要求分析：哪步推理出错、哪个假设不正确、下次应怎么做
3. LLM 返回结构化 JSON：`{task_summary, outcome, reflection, keywords}`
4. 复盘记录存入 `ReflectionStore`，使用**原子写入**持久化到 `reflections.json`

**下次任务开始前**：
1. 用用户新的 query 在 `ReflectionStore` 中执行 BM25 检索（`top_k=3`）
2. 检索到相关复盘时，构造 `[Past Experience]` 系统消息注入到消息列表的第 2 条
3. Agent 带着"上次的教训"进入推理循环

**关键设计**：反思生成在 `daemon=True` 的后台线程中运行，不阻塞 `yield finished` 的返回，UI 无任何延迟感知。反思生成失败（LLM 返回格式错误等）静默跳过，绝不影响主流程。

#### ReflectionStore 的 BM25 实现

`reflection_store.py` 内含一个**零外部依赖**的 BM25 实现，支持中英文混合检索：
- 中文：单字（unigram）+ 相邻双字（bigram）分词
- 英文：正则提取完整单词
- 停用词过滤（中英文各一套）
- IDF = log((N - df + 0.5) / (df + 0.5) + 1)，标准 Robertson IDF 公式
- 增量索引（新增记录无需全量重建）

---

### 五、★ 运行时工具合成——Agent 自己造工具

> **思路来源**：Voyager (*Wang et al.*, 2023) 中 Minecraft Agent 自动积累技能库的思路；  
> LATM: *"Large Language Models as Tool Makers"* (*Cai et al.*, 2023) 中让 LLM 为自己创造工具的范式。

#### 核心思想

传统框架的工具集由开发者预先定义，静态不变。本项目实现了**运行时工具合成**：当 Agent 在推理过程中发现没有合适工具时，可以自主编写一个 Python 函数，经验证后注册进 `ToolRegistry`，并在后续推理步骤中直接调用——工具集在对话过程中动态生长。

这与 Code Interpreter 的本质区别在于：Code Interpreter 每次执行都是"临时计算"，结果只是文字；Tool Synthesizer 执行后创造了一个可重复调用的**具名工具**，相当于 Agent **习得了新技能**。

#### 实现细节（tool_synthesizer.py）

1. **命名校验**：工具名必须匹配 `^[a-z][a-z0-9_]{1,39}$`，不允许与已有工具重名
2. **安全黑名单**（在 `exec()` 前检查）：禁止 `import os`、`import sys`、`subprocess`、`__import__`、`open(`、`exec(`、`eval(`
3. **语法编译**：`compile(code, '<tool>', 'exec')` 检查语法错误
4. **隔离执行 + 超时**：在独立 namespace 中 `exec()` 函数定义；用 `ThreadPoolExecutor` + `future.result(timeout=5)` 对测试调用加 5 秒超时
5. **动态注册**：用 `type()` 动态创建类，在闭包中捕获函数引用，注册进 `ToolRegistry`
6. **即时生效**：`agent.py` 在每轮循环调用 LLM 之前刷新工具描述（`pm.update_tools(registry.generate_descriptions())`），新工具在下一步即出现在 Agent 的可用工具列表中

---

### 六、多智能体系统

#### 6.1 架构

```
用户请求
  ↓
Planner（LLM 任务分解）
  → 生成带依赖关系的 SubTask 列表（DAG）
  ↓
Executor（拓扑调度器）
  → 无依赖的任务用 ThreadPoolExecutor 并行执行
  → 有依赖的任务串行，前置结果自动注入为上下文
  ↓
Orchestrator（综合器）
  → 将所有子任务结果合并，LLM 生成最终答案
```

#### 6.2 关键设计

- **单任务退化**：如果 Planner 判断任务足够简单（只生成 1 个无依赖子任务），直接走单 Agent 路径，跳过多智能体开销
- **子 Agent 隔离**：每个子任务创建独立的 `Agent(is_sub_agent=True)` 实例，拥有独立的 `MessageQueue` 和 `ConversationHistory`，不会互相干扰
- **对话记录隔离**：`is_sub_agent=True` 时跳过 `ConversationStore`，避免多个子任务在历史记录中产生多条无关对话
- **依赖结果传递**：子任务执行时，其前置依赖的结果以"已知信息"的形式拼接到任务描述中

---

### 七、对话持久化与全文搜索

#### 7.1 对话持久化（ConversationStore）

每条对话存储为独立的 JSON 文件（`conversations/<uuid>.json`），包含消息列表、时间戳、自动标题（取首条用户消息前 20 字）。所有写操作均为原子操作（tmp + `os.replace`）。

#### 7.2 BM25 全文搜索引擎

`search_engine.py` 从零实现了完整的 BM25 检索引擎，**零外部依赖**（不使用 `rank_bm25`）：

- **分词器**：中文单字+双字 bigram，英文完整单词，共用停用词表（中英各约 50 词）
- **BM25 评分**：标准 Robertson BM25，k₁=1.5，b=0.75
- **增量索引**：新对话完成后直接追加到索引，不触发全量重建
- **懒加载**：首次搜索时自动建立索引，冷启动零开销

#### 7.3 AI 重排（AIReranker）

当候选结果数量超过 `top_k` 时，将前 10 个候选连同标题和摘要片段发给 LLM，让其按语义相关性重新排序，返回 id 列表。这个两阶段架构（BM25 召回 + AI 精排）在不引入向量数据库的前提下，实现了兼顾效率与语义准确性的搜索。

---

### 八、文件上传与多模态

#### 8.1 文本文件

`FileExtractor` 支持直接提取内容的格式：`.txt`、`.md`、`.py`、`.js`、`.ts`、`.json`、`.csv`、`.yaml`、`.xml`、`.html`、`.log`、`.rst`。超过 50,000 字符自动截断并提示。PDF 需安装 `PyPDF2`。

#### 8.2 图片理解

图片文件（`jpg`、`png`、`webp` 等）先 Base64 编码，通过 **Qwen-VL**（通义千问视觉模型）理解图片内容，将描述文字作为上下文传给 Agent。这绕开了 DeepSeek 不支持多模态的限制，通过多模型协作实现图片理解。

---

### 九、LLM 层

#### 9.1 双模型支持

| 供应商 | 模型 | 用途 |
|--------|------|------|
| DeepSeek | `deepseek-chat` | 主要推理（低价格高性能）|
| Qwen | `qwen-plus` | 备选主推理 |
| Qwen-VL | `qwen-vl-plus` | 图片理解 |

两套客户端均使用 OpenAI SDK + OpenAI 兼容协议，切换供应商只需修改环境变量 `DEFAULT_LLM_PROVIDER`。

#### 9.2 Factory 模式

`create_llm_client(provider)` 工厂函数根据 provider 名称返回对应客户端实例，上层代码对具体实现完全透明。

---

### 十、Chainlit 界面

`chainlit_app.py` 提供 ChatGPT 风格的对话界面：

- **流式渲染**：用 `asyncio.to_thread` 在线程中运行同步生成器，每个 ReAct 步骤以 `cl.Step` 展示 Thought + Action Input + Observation
- **内置命令**：
  - `/memory` — 查看所有长期记忆
  - `/forget <id前8位>` — 删除指定记忆
  - `/clear_memory` — 清空全部记忆
- **快捷示例按钮**：启动时展示三个可点击的示例任务

---

## 配置项说明

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key（必填）|
| `QWEN_API_KEY` | — | Qwen API Key（可选，用于图片理解）|
| `DEFAULT_LLM_PROVIDER` | `deepseek` | 默认 LLM 供应商 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek 模型名称 |
| `QWEN_MODEL` | `qwen-plus` | Qwen 模型名称 |
| `MAX_ITERATIONS` | `15` | 最大推理轮数 |
| `TEMPERATURE` | `0.7` | 采样温度 |
| `MAX_TOKENS` | `4096` | 单次生成最大 Token |
| `MAX_CONTEXT_TOKENS` | `8000` | 上下文 Token 上限 |
| `SLIDING_WINDOW_SIZE` | `10` | 滑动窗口保留轮数 |
| `SANDBOX_ROOT` | `./sandbox` | 文件系统沙箱根目录 |
| `WIKIPEDIA_LANGUAGE` | `zh` | Wikipedia 搜索语言 |
| `MULTI_AGENT_MAX_WORKERS` | `3` | 多智能体并行线程数 |

---

## 开发指南

| 如果你要… | 改这里 |
|-----------|--------|
| 调模型推理行为 | `src/prompts/system_prompt.py` |
| 增加格式示例 | `src/prompts/few_shot_examples.py` |
| 加新工具（静态）| `src/tools/` + `src/tools/__init__.py` |
| 加需要注入依赖的工具 | `src/core/agent.py` 的 `__init__` |
| 改状态转移逻辑 | `src/core/state_machine.py` |
| 调记忆/上下文策略 | `src/memory/sliding_window.py` |
| 改会话压缩策略 | `src/memory/conversation_history.py` |
| 改 Reflexion 提示词 | `src/core/agent.py` → `_generate_reflection()` |
| 改 Web 界面 | `chainlit_app.py` / `ui/app.py` |
| 换 LLM 供应商 | `src/llm/` + `config/settings.py` |
| 调搜索参数（k₁、b）| `src/storage/search_engine.py` → `BM25.__init__` |

---

## 设计亮点总结

| 设计 | 位置 | 说明 |
|------|------|------|
| AST 白名单计算器 | `tools/calculator.py` | 彻底杜绝 eval 注入 |
| 三层容错解析 | `core/parser.py` | LLM 输出格式容错，自动反馈纠错 |
| Duck typing 工具注册 | `tools/registry.py` | 无需继承，最大扩展灵活性 |
| 原子文件写入 | 所有持久化模块 | tmp + os.replace，防崩溃数据丢失 |
| 渐进式对话压缩 | `memory/conversation_history.py` | 信息永不丢失，只会渐进稀疏化 |
| LLM 记忆提取+去重 | `memory/memory_extractor.py` | 自动识别值得记忆的信息并防重复 |
| BM25 零依赖实现 | `storage/search_engine.py` | 中英混合检索，无需外部库 |
| BM25 + AI 两阶段搜索 | `storage/search_engine.py` | 效率与语义准确性兼顾 |
| 单任务退化 | `multi_agent/orchestrator.py` | 简单任务自动跳过多智能体开销 |
| is_sub_agent 隔离 | `core/agent.py` | 子 Agent 不污染对话历史 |
| ★ Reflexion 经验积累 | `memory/reflection_store.py` | 失败→复盘→存储→检索→教训注入 |
| ★ 运行时工具合成 | `tools/tool_synthesizer.py` | Agent 自主造工具，工具集动态生长 |

---

## 技术栈

- **范式**：ReAct（Thought-Action-Observation 循环）
- **LLM**：DeepSeek / Qwen（OpenAI 兼容协议）+ Qwen-VL（多模态）
- **解析**：正则 + JSON 结构化提取，三层容错
- **记忆**：短期 / 会话 / 长期三层体系 + Reflexion 复盘
- **检索**：BM25（零依赖手写）+ LLM 语义重排
- **安全**：AST 白名单计算、文件系统沙箱（路径穿越防护）、工具合成安全黑名单
- **并发**：`ThreadPoolExecutor`（多智能体并行）、`asyncio.to_thread`（Chainlit 异步桥接）、`daemon` 线程（Reflexion 异步后台）
- **UI**：Chainlit（推荐）/ Streamlit（备选）
- **持久化**：原子 JSON 文件写入（全部存储模块统一）

---

## License

MIT — 浙江大学人工智能基础实验课程项目
