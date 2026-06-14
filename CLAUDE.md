# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A ReAct (Reasoning + Acting) paradigm AI Agent framework built from scratch — no LangChain. The core loop is: Thought → Action → Tool Execution → Observation → Thought → … → Final Answer. The framework enables LLMs to dynamically invoke external tools (calculator, Wikipedia search, local filesystem) through structured output parsing.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI (ChatGPT-style interactive loop)
python3 scripts/run_agent.py

# Run Streamlit web UI
streamlit run ui/app.py

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_parser.py -v
```

## Architecture

### Core Loop (`src/core/agent.py`)

`Agent` is the main class. `run()` is a blocking wrapper around `run_stream()`, which is a generator that yields dicts at each step (for real-time UI). The loop:

1. Builds messages via `PromptManager` (system prompt + tool descriptions + conversation history)
2. Applies `SlidingWindow` truncation and injects `InstructionKeeper` reminder
3. Calls LLM → parses response → if finished, yield final answer; if parse error, feed back as Observation; otherwise execute tool and feed result as Observation
4. Loops until `Final Answer`, parse error without action, or `MAX_ITERATIONS` exhausted

### State Machine (`src/core/state_machine.py`)

7 states with strict transition validation:
```
IDLE → THINKING → PARSING → ACTING → OBSERVING → (loops to THINKING)
                         ↘ FINISHED    ↘ ERROR
```
Invalid transitions raise `RuntimeError`. The `path()` method returns a human-readable trace like `IDLE → THINKING → PARSING → ACTING → OBSERVING → THINKING → PARSING → FINISHED`.

### Parser (`src/core/parser.py`)

Three-layer fallback for extracting `Action Input` JSON:
1. ```json fenced block after `Action Input:`
2. Bare JSON object on the same/next line
3. Raw text with fence-stripping attempt (stores `__parse_error__` key on failure)

`describe_parse_error()` converts parse failures into human-readable messages that get fed back to the LLM as Observations, enabling self-correction.

### Tool System (`src/tools/`)

All tools implement `BaseTool` (ABC): `name`, `description`, `parameters` (JSON Schema), `run(**kwargs) → str`. `ToolRegistry` maps name→instance, generates descriptions for the system prompt, and executes tools with error wrapping. Adding a new tool only requires:
1. Create file in `src/tools/` implementing `BaseTool`
2. Register in `src/tools/__init__.py` → `register_all_tools()`

No changes needed to `agent.py`, `registry.py`, or any other module.

### Memory (`src/memory/`)

- `MessageQueue` — appends assistant-response + observation pairs
- `SlidingWindow` — truncates history to fit `MAX_CONTEXT_TOKENS`, keeping the original user query + last N×2 messages
- `InstructionKeeper` — retains the original task and injects a `[Reminder]` message when context is pruned
- `token_counter.py` — estimates token count (character-based fallback since tiktoken is optional)

### LLM Layer (`src/llm/`)

`BaseLLMClient` (ABC) defines `chat()` and `stream_chat()`. `DeepSeekClient` uses the OpenAI SDK with OpenAI-compatible protocol. Qwen reuse the same client class since both expose OpenAI-compatible endpoints. Factory function `create_llm_client(provider)` in `__init__.py` handles provider selection.

### Configuration (`config/settings.py`)

All settings from environment variables (via `python-dotenv`), with sensible defaults. Key vars: `DEEPSEEK_API_KEY`, `MAX_ITERATIONS` (15), `MAX_CONTEXT_TOKENS` (8000), `SLIDING_WINDOW_SIZE` (10), `SANDBOX_ROOT`, `WIKIPEDIA_LANGUAGE`.

### Multi-Agent (`src/multi_agent/`)

Skeleton module for orchestrator/planner/executor pattern. Currently empty stubs — work in progress for multi-agent coordination.

### UI (`ui/`)

Streamlit app with two-column layout: left side = chat panel, right side = real-time ReAct trace visualization via `thought_tracker.py` and `tool_visualizer.py`. Uses `run_stream()` for step-by-step rendering.

## Development Guide (from README)

| To change... | Modify |
|-------------|--------|
| Model reasoning behavior | `src/prompts/system_prompt.py` |
| Format examples (few-shot) | `src/prompts/few_shot_examples.py` |
| Add a new tool | `src/tools/` + `src/tools/__init__.py` |
| State transition logic | `src/core/state_machine.py` |
| Memory/context strategy | `src/memory/sliding_window.py` |
| Web UI | `ui/app.py` |
| Swap LLM provider | `src/llm/` + `config/settings.py` |
