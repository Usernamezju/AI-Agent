"""ReAct Agent — main execution loop tying together llm, tools, parser, prompts, and memory."""
import threading
from typing import Generator
from config.settings import settings
from src.llm import create_llm_client
from src.tools import register_all_tools, tool_registry
from src.prompts.prompt_manager import PromptManager
from src.memory import (MessageQueue, SlidingWindow, InstructionKeeper,
                         ConversationHistory, LongTermMemory, MemoryExtractor)
from .parser import parse_response, describe_parse_error
from .error_handler import format_observation, format_parse_error
from .state_machine import StateMachine, AgentState


class Agent:
    def __init__(self, provider: str | None = None) -> None:
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

        while not self._sm.is_terminal and self._iterations < settings.MAX_ITERATIONS:
            self._iterations += 1

            # --- THINKING ---
            self._sm.transition(AgentState.THINKING)
            messages = self._pm.build(user_query, self._mq.get_all())
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
                self._conv.add_turn(user_query, final_answer)
                # Extract long-term facts asynchronously
                threading.Thread(
                    target=self._extract_and_save,
                    args=(user_query, final_answer),
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
                yield {"type": "error", "round": self._iterations,
                       "message": "Model did not output a valid Action or Final Answer."}
                return

            # --- ACTING ---
            self._sm.transition(AgentState.ACTING)
            result = tool_registry.execute(parsed.action or "", **parsed.action_input or {})

            # --- OBSERVING ---
            self._sm.transition(AgentState.OBSERVING)
            obs = format_observation(result)
            self._mq.add_pair(raw, obs)
            yield {"type": "step", "round": self._iterations,
                   "thought": parsed.thought, "action": parsed.action,
                   "action_input": parsed.action_input, "observation": result, "raw": raw}

        # Max iterations
        if not self._sm.is_terminal:
            self._sm.transition(AgentState.ERROR)
            yield {"type": "error", "round": self._iterations,
                   "message": f"Exceeded max iterations ({settings.MAX_ITERATIONS})."}
            return

    # ------------------------------------------------------------------
    def _extract_and_save(self, user_query: str, final_answer: str) -> None:
        """Extract long-term facts from a finished turn and persist them."""
        try:
            facts = self._extractor.extract(user_query, final_answer)
            for f in facts:
                self._ltm.add_fact(f)
            if facts:
                self._ltm.save()
        except Exception:
            pass  # Extraction failure must not affect the main loop

    # ------------------------------------------------------------------
    def reset_conversation(self) -> None:
        """Clear both short-term working memory and long-term conversation history."""
        self._mq.clear()
        self._conv.clear()
        self._keeper.clear()
        self._sm.reset()

    # ------------------------------------------------------------------
    @property
    def state_path(self) -> str:
        return self._sm.path()

    @property
    def iteration_count(self) -> int:
        return self._iterations
