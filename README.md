# AI Agent Framework

从零搭建的 ReAct 范式 AI Agent 框架——让大语言模型从"会说话"变成"能做事"。

## 核心原理

基于 **ReAct（Reasoning + Acting）** 范式，通过 Thought → Action → Observation 感知-行动循环，赋予 LLM 动态调用外部工具的能力。纯手动管理状态机，不依赖 LangChain 等高层框架。

```
用户输入 → Thought → Action → 工具执行 → Observation → Thought → ... → Final Answer
```

## 项目结构

```
├── config/                 # 全局配置（API Key、模型参数、路径）
│   ├── settings.py
│   └── tools_registry.json
├── src/
│   ├── core/               # 核心执行引擎
│   │   ├── agent.py        #   Agent 主类 + ReAct 主循环
│   │   ├── state_machine.py#   状态机（7 个状态 + 转移表）
│   │   ├── parser.py       #   文本解析器（Thought/Action/Action Input 提取）
│   │   └── error_handler.py#   异常反馈闭环（解析失败→Observation 抛回）
│   ├── llm/                # LLM 通信层
│   │   ├── base.py         #   抽象基类
│   │   ├── deepseek_client.py
│   │   └── qwen_client.py
│   ├── prompts/            # 提示词工程
│   │   ├── system_prompt.py#   ReAct 模板
│   │   ├── few_shot_examples.py
│   │   └── prompt_manager.py
│   ├── tools/              # 工具系统（可扩展）
│   │   ├── base.py         #   工具抽象基类
│   │   ├── registry.py     #   统一注册表
│   │   ├── calculator.py   #   安全计算器（AST，不用 eval）
│   │   ├── wikipedia_search.py
│   │   └── local_filesystem.py  # 沙箱文件读写
│   ├── memory/             # 记忆管理
│   │   ├── message_queue.py
│   │   ├── sliding_window.py    # 滑动窗口截断
│   │   ├── instruction_keeper.py# 初始指令保留
│   │   └── token_counter.py
│   └── multi_agent/        # 多智能体协同（进阶）
├── ui/                     # Streamlit Web 界面
│   ├── app.py
│   └── components/
├── tests/                  # 测试套件
├── scripts/                # 启动脚本
│   └── run_agent.py        #   命令行交互入口
└── experiments/            # 实验日志
```

## 快速开始

### 1. 环境准备

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
```

`.env` 示例：
```
DEEPSEEK_API_KEY=sk-your-key-here
SANDBOX_ROOT=.
```

### 3. 命令行运行

```bash
python3 scripts/run_agent.py
```

交互示例：
```
>>> 计算 (15 + 7) * 3 / 2
Result : The result is 33.0.
Path   : IDLE → THINKING → PARSING → ACTING → OBSERVING → THINKING → PARSING → FINISHED
Rounds : 2

>>> 输出当前目录结构
Result : 当前目录包含：README.md, requirements.txt, src/, config/, ...
Rounds : 2
```

### 4. Web 界面运行

```bash
streamlit run ui/app.py
```

浏览器打开 `http://localhost:8501`，左侧对话面板 + 右侧实时推理轨迹。

## 配置项说明

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API Key（必填） |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `DEFAULT_LLM_PROVIDER` | `deepseek` | 默认 LLM 供应商 |
| `MAX_ITERATIONS` | `15` | 最大推理轮数 |
| `TEMPERATURE` | `0.7` | 采样温度 |
| `MAX_CONTEXT_TOKENS` | `8000` | 上下文 token 上限 |
| `SLIDING_WINDOW_SIZE` | `10` | 滑动窗口保留轮数 |
| `SANDBOX_ROOT` | `./sandbox` | 文件系统沙箱根目录 |
| `WIKIPEDIA_LANGUAGE` | `zh` | Wikipedia 搜索语言 |

## 如何添加新工具

1. 在 `src/tools/` 下新建文件，实现 `BaseTool` 接口：

```python
class MyTool:
    name = "my_tool"
    description = "What this tool does."
    parameters = {
        "type": "object",
        "properties": {"param1": {"type": "string", "description": "..."}},
        "required": ["param1"],
    }

    def run(self, param1: str) -> str:
        # Your logic here
        return "result string"
```

2. 在 `src/tools/__init__.py` 注册：

```python
from .my_tool import MyTool

def register_all_tools(sandbox_root=None):
    tool_registry.register_many([
        CalculatorTool(),
        WikipediaSearchTool(),
        LocalFileSystemTool(sandbox_root=sandbox_root),
        MyTool(),  # ← 新增
    ])
    return tool_registry
```

无需修改 `agent.py`、`registry.py` 或任何其他文件。

## 开发指南

| 如果你要... | 改这里 |
|-------------|--------|
| 调模型推理行为 | `src/prompts/system_prompt.py` |
| 增加格式示例 | `src/prompts/few_shot_examples.py` |
| 加新工具 | `src/tools/` + `src/tools/__init__.py` |
| 改状态流转逻辑 | `src/core/state_machine.py` |
| 调记忆/上下文策略 | `src/memory/sliding_window.py` |
| 改 Web 界面 | `ui/app.py` |
| 换 LLM 供应商 | `src/llm/` + `config/settings.py` |

## 技术路线

- **范式**：ReAct（Thought-Action-Observation 循环）
- **LLM**：DeepSeek / Qwen（OpenAI 兼容协议）
- **解析**：正则 + JSON 结构化提取，三层容错
- **记忆**：滑动窗口 + 指令保留 + Token 估算
- **安全**：AST 表达式求值、文件系统沙箱
- **UI**：Streamlit 流式渲染

## License

MIT — 浙江大学人工智能基础实验课程项目
