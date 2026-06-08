"""State machine for the ReAct agent lifecycle."""
from enum import Enum, auto


class AgentState(Enum):
    IDLE      = auto()
    THINKING  = auto()
    PARSING   = auto()
    ACTING    = auto()
    OBSERVING = auto()
    FINISHED  = auto()
    ERROR     = auto()


_VALID = {
    AgentState.IDLE:      {AgentState.THINKING, AgentState.ERROR},
    AgentState.THINKING:  {AgentState.PARSING, AgentState.ERROR},
    AgentState.PARSING:   {AgentState.ACTING, AgentState.FINISHED, AgentState.OBSERVING, AgentState.ERROR},
    AgentState.ACTING:    {AgentState.OBSERVING, AgentState.ERROR},
    AgentState.OBSERVING: {AgentState.THINKING, AgentState.FINISHED, AgentState.ERROR},
    AgentState.FINISHED:  set(),
    AgentState.ERROR:     set(),
}


class StateMachine:
    def __init__(self) -> None:
        self._state = AgentState.IDLE
        self._trace: list[AgentState] = [AgentState.IDLE]

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in (AgentState.FINISHED, AgentState.ERROR)

    def transition(self, to: AgentState) -> None:
        allowed = _VALID.get(self._state, set())
        if to not in allowed:
            raise RuntimeError(f"Invalid transition: {self._state.name} → {to.name}")
        self._state = to
        self._trace.append(to)

    def reset(self) -> None:
        self._state = AgentState.IDLE
        self._trace = [AgentState.IDLE]

    def path(self) -> str:
        return " → ".join(s.name for s in self._trace)
