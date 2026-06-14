"""ReAct Agent — main execution loop tying together llm, tools, parser, prompts, and memory."""
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Generator
from config.settings import settings
from src.llm import create_llm_client
from src.tools import register_all_tools, tool_registry
from src.tools.memory_tool import MemoryStoreTool, MemoryRecallTool
from src.prompts.prompt_manager import PromptManager
from src.memory import (MessageQueue, SlidingWindow, InstructionKeeper,
                         ConversationHistory, LongTermMemory, MemoryExtractor)
from src.memory.reflection_store import ReflectionStore
from src.storage.conversation_store import ConversationStore
from src.storage.search_engine import SearchEngine
from .parser import parse_response, describe_parse_error
from .error_handler import format_observation, format_parse_error
from .state_machine import StateMachine, AgentState


class Agent:
    def __init__(self, provider: str | None = None, is_sub_agent: bool = False) -> None:
        self._llm = create_llm_client(provider)
        register_all_tools()
        self._pm = PromptManager(tool_registry.generate_descriptions())
        self._sm = StateMachine()
        self._mq = MessageQueue()
        self._keeper = InstructionKeeper()
        self._window = SlidingWindow()
        self._conv = ConversationHistory(llm_client=self._llm)
        self._ltm = LongTermMemory()
        self._extractor = MemoryExtractor(self._llm)
        # Register memory-access tools so the Agent can explicitly store/recall
        tool_registry.register(MemoryStoreTool(self._ltm, self._llm))
        tool_registry.register(MemoryRecallTool(self._ltm))
        from src.tools.debate_tool import DebateTool
        tool_registry.register(DebateTool(self._llm))
        from src.tools.tool_synthesizer import ToolSynthesizerTool
        tool_registry.register(ToolSynthesizerTool(registry=tool_registry))
        # Rebuild prompt with updated tool descriptions
        self._pm.update_tools(tool_registry.generate_descriptions())
        # Reflexion store
        self._reflection_store = ReflectionStore()
        # Conversation persistence + search (skipped for sub-agents)
        self._is_sub_agent = is_sub_agent
        if not is_sub_agent:
            self._store = ConversationStore()
            self._search = SearchEngine(self._store, self._llm)
        else:
            self._store = None
            self._search = None
        self._current_conv_id: str | None = None
        self._iterations: int = 0

    # ------------------------------------------------------------------
    def run(self, user_query: str) -> str:
        """Blocking ReAct loop — returns final answer."""
        result = None
        for step in self.run_stream(user_query):
            if step["type"] == "finished":
                result = step["answer"]
        return result or ""

    # ------------------------------------------------------------------
    def run_stream(self, user_query: str) -> Generator[dict, None, None]:
        """Generator version — yields dicts after each step for real-time UI updates."""
        self._sm.reset()
        self._mq.clear()
        self._keeper.set(user_query)
        self._iterations = 0

        # Ensure a conversation file exists and record the user query
        if self._store is not None:
            if self._current_conv_id is None:
                self._current_conv_id = self._store.new_conversation()
            self._store.add_message(self._current_conv_id, "user", user_query)

        # Collect full trace for post-task reflection
        all_steps: list[dict] = []

        # Retrieve past reflections and inject as system hint (once, before loop)
        past = self._reflection_store.search(user_query, top_k=3)
        reflection_hint = ""
        if past:
            lines = ["[Past Experience]",
                     "In similar past tasks, you encountered the following issues:"]
            for i, r in enumerate(past, 1):
                lines.append(f"{i}. {r.get('reflection', '')}")
            lines.append("Please avoid repeating these mistakes.")
            reflection_hint = "\n".join(lines)

        while not self._sm.is_terminal and self._iterations < settings.MAX_ITERATIONS:
            self._iterations += 1

            # --- THINKING ---
            self._sm.transition(AgentState.THINKING)
            # Refresh tool descriptions (in case new tools were synthesised)
            self._pm.update_tools(tool_registry.generate_descriptions())
            messages = self._pm.build(user_query, self._mq.get_all())
            # Inject past reflections as a system hint (after system prompt, before user query)
            if reflection_hint:
                messages.insert(1, {"role": "system", "content": reflection_hint})
            # Inject long-term memory facts into system prompt
            ltm_block = self._ltm.format_for_prompt()
            if ltm_block:
                messages[0]["content"] += ltm_block
            # Inject multi-turn conversation history (session memory)
            conv_ctx = self._conv.get_context_prompt()
            if conv_ctx:
                messages.insert(1, {"role": "user", "content": conv_ctx})
            messages = self._window.apply(messages)
            reminder = self._keeper.get_reminder()
            if reminder:
                messages.insert(1, {"role": "user", "content": reminder})
            raw = self._llm.chat(messages, settings.TEMPERATURE, settings.MAX_TOKENS)

            # --- PARSING ---
            self._sm.transition(AgentState.PARSING)
            parsed = parse_response(raw)

            # Finished?
            if parsed.is_finished:
                self._sm.transition(AgentState.FINISHED)
                final_answer = parsed.final_answer or ""
                all_steps.append({"thought": parsed.thought, "action": "Final Answer",
                                   "observation": final_answer})
                self._conv.add_turn(user_query, final_answer)
                # Extract long-term facts + deduplicate
                facts = self._extractor.extract(user_query, final_answer)
                for f in facts:
                    self._ltm.add_fact(f)
                if facts:                          # only dedup when new facts arrived
                    self._ltm.deduplicate(self._llm)
                self._ltm.save()
                # Persist assistant answer + update search index
                if self._store is not None:
                    self._store.add_message(self._current_conv_id, "assistant", final_answer)
                    self._search.add_to_index(self._current_conv_id)
                # Generate reflection asynchronously
                threading.Thread(
                    target=self._generate_reflection,
                    args=(user_query, all_steps, final_answer, True),
                    daemon=True,
                ).start()
                yield {"type": "finished", "answer": final_answer,
                       "round": self._iterations, "thought": parsed.thought, "raw": raw}
                return

            # Parse error → feedback loop
            parse_err = describe_parse_error(parsed.action_input)
            if parse_err:
                self._sm.transition(AgentState.OBSERVING)
                obs = format_parse_error(parsed.raw_text)
                self._mq.add_pair(raw, obs)
                yield {"type": "parse_error", "round": self._iterations,
                       "thought": parsed.thought, "error": parse_err, "raw": raw}
                continue

            # No action?
            if not parsed.has_action:
                self._sm.transition(AgentState.ERROR)
                err_msg = "Model did not output a valid Action or Final Answer."
                if self._store is not None:
                    self._store.add_message(self._current_conv_id, "assistant", f"[错误] {err_msg}")
                threading.Thread(
                    target=self._generate_reflection,
                    args=(user_query, all_steps, err_msg, False),
                    daemon=True,
                ).start()
                yield {"type": "error", "round": self._iterations,
                       "message": err_msg}
                return

            # --- ACTING ---
            self._sm.transition(AgentState.ACTING)
            result = tool_registry.execute(parsed.action or "", **parsed.action_input or {})

            # --- OBSERVING ---
            self._sm.transition(AgentState.OBSERVING)
            obs = format_observation(result)
            self._mq.add_pair(raw, obs)
            # Extract visualization file name if present
            viz_file = None
            if parsed.action == "visualize":
                try:
                    obs_data = json.loads(result)
                    viz_file = obs_data.get("visualization_file")
                except Exception:
                    pass
            all_steps.append({"thought": parsed.thought, "action": parsed.action,
                               "action_input": parsed.action_input, "observation": result})
            yield {"type": "step", "round": self._iterations,
                   "thought": parsed.thought, "action": parsed.action,
                   "action_input": parsed.action_input, "observation": result,
                   "visualization": viz_file, "raw": raw}

        # Max iterations
        if not self._sm.is_terminal:
            self._sm.transition(AgentState.ERROR)
            err_msg = f"Exceeded max iterations ({settings.MAX_ITERATIONS})."
            if self._store is not None:
                self._store.add_message(self._current_conv_id, "assistant", f"[错误] {err_msg}")
            threading.Thread(
                target=self._generate_reflection,
                args=(user_query, all_steps, err_msg, False),
                daemon=True,
            ).start()
            yield {"type": "error", "round": self._iterations,
                   "message": err_msg}
            return

    # ------------------------------------------------------------------
    def _generate_reflection(self, task: str, steps: list, answer: str,
                              success: bool) -> None:
        """Generate a post-task reflection and store it asynchronously."""
        try:
            # Format the reasoning trace
            trace_lines = []
            for s in steps:
                trace_lines.append(f"Thought: {s.get('thought', '?')}")
                act = s.get('action', '')
                if act and act != "Final Answer":
                    trace_lines.append(f"Action: {act}")
                    ai = s.get('action_input', {})
                    if ai:
                        trace_lines.append(f"Action Input: {json.dumps(ai, ensure_ascii=False)}")
                trace_lines.append(f"Observation: {s.get('observation', '?')[:500]}")
                trace_lines.append("")

            prompt = (
                "You just completed (or failed to complete) the following task:\n"
                f"Task: {task}\n\n"
                "Your reasoning trace:\n"
                f"{chr(10).join(trace_lines)}\n"
                f"Final answer: {answer}\n"
                f"Outcome: {'succeeded' if success else 'failed or incomplete'}\n\n"
                "Please write a brief retrospective (3-5 sentences) covering:\n"
                "1. Which reasoning steps or tool calls went wrong (if any)?\n"
                "2. What assumption was incorrect?\n"
                "3. What should be done differently next time for similar tasks?\n\n"
                "Also provide:\n"
                "- task_summary: one sentence describing the task type\n"
                "- keywords: 5-8 keywords for retrieval (comma-separated)\n"
                '- outcome: "success", "failure", or "partial"\n\n'
                "Respond in JSON:\n"
                '{"task_summary": "...", "outcome": "success|failure|partial", '
                '"reflection": "...", "keywords": ["...", "..."]}'
            )

            messages = [{"role": "user", "content": prompt}]
            raw = self._llm.chat(messages, temperature=0.3, max_tokens=600)

            # Parse JSON response
            data = json.loads(raw.strip())
            self._reflection_store.save({
                "id": uuid.uuid4().hex,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task_summary": data.get("task_summary", task[:100]),
                "outcome": data.get("outcome", "success" if success else "failure"),
                "reflection": data.get("reflection", ""),
                "keywords": data.get("keywords", []),
            })
        except Exception:
            pass  # Reflection failure must not affect the main loop

    # ------------------------------------------------------------------
    def reset_conversation(self) -> None:
        """Clear working memory and start a fresh conversation."""
        self._mq.clear()
        self._conv.clear()
        self._keeper.clear()
        self._sm.reset()
        if self._store is not None:
            self._current_conv_id = self._store.new_conversation()

    # ------------------------------------------------------------------
    @property
    def state_path(self) -> str:
        return self._sm.path()

    @property
    def iteration_count(self) -> int:
        return self._iterations
