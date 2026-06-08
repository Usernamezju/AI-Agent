"""ReAct Agent — main execution loop tying together llm, tools, parser, prompts, and memory."""
from config.settings import settings
from src.llm import create_llm_client
from src.tools import register_all_tools, tool_registry
from src.prompts.prompt_manager import PromptManager
from src.memory import MessageQueue, SlidingWindow, InstructionKeeper
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
        self._iterations: int = 0

    # ------------------------------------------------------------------
    def run(self, user_query: str) -> str:
        """Execute the ReAct loop for *user_query* and return the final answer."""
        self._sm.reset()
        self._mq.clear()
        self._keeper.set(user_query)
        self._iterations = 0

        while not self._sm.is_terminal and self._iterations < settings.MAX_ITERATIONS:
            self._iterations += 1

            # --- THINKING ---
            self._sm.transition(AgentState.THINKING)
            messages = self._pm.build(user_query, self._mq.get_all())
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
                return parsed.final_answer or ""

            # Parse error → feedback loop (Self-Correction)
            parse_err = describe_parse_error(parsed.action_input)
            if parse_err:
                self._sm.transition(AgentState.OBSERVING)
                obs = format_parse_error(parsed.raw_text)
                self._mq.add_pair(raw, obs)
                continue

            # No action?
            if not parsed.has_action:
                self._sm.transition(AgentState.ERROR)
                return "Error: model did not output a valid Action or Final Answer."

            # --- ACTING ---
            self._sm.transition(AgentState.ACTING)
            result = tool_registry.execute(parsed.action or "", **parsed.action_input or {})

            # --- OBSERVING ---
            self._sm.transition(AgentState.OBSERVING)
            obs = format_observation(result)
            self._mq.add_pair(raw, obs)

        # Max iterations reached
        if not self._sm.is_terminal:
            self._sm.transition(AgentState.ERROR)
            return f"Error: exceeded max iterations ({settings.MAX_ITERATIONS})."
        return ""

    # ------------------------------------------------------------------
    @property
    def state_path(self) -> str:
        return self._sm.path()

    @property
    def iteration_count(self) -> int:
        return self._iterations
