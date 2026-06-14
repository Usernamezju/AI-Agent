"""Debate tool — two virtual debaters argue opposing stances for balanced analysis."""
from __future__ import annotations
import json


class DebateTool:
    name = "perspective_debate"
    description = (
        "For controversial, complex, or open-ended questions where a balanced "
        "multi-perspective analysis is valuable, use this tool to summon two "
        "virtual debaters with opposing stances. Each presents their strongest "
        "arguments. Use this BEFORE Final Answer when the question involves "
        "trade-offs, ethical dilemmas, predictions, or 'should/will X happen' topics. "
        "Do NOT use for factual questions with clear answers."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The controversial question or topic to debate.",
            },
            "stance_a": {
                "type": "string",
                "description": (
                    "The affirmative stance (e.g. '人工智能会取代程序员'). "
                    "Should be a clear, debatable position."
                ),
            },
            "stance_b": {
                "type": "string",
                "description": (
                    "The opposing stance (e.g. '人工智能不会取代程序员'). "
                    "Direct opposite of stance_a."
                ),
            },
            "rounds": {
                "type": "integer",
                "description": "Number of debate rounds (default 1, max 2).",
            },
        },
        "required": ["question", "stance_a", "stance_b"],
    }

    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    # ------------------------------------------------------------------
    def run(self, question: str, stance_a: str, stance_b: str,
            rounds: int = 1) -> str:
        rounds = min(int(rounds), 2)
        try:
            debate_log: list[dict] = []

            for r in range(rounds):
                pro = self._argue(question, stance_a, stance_b,
                                  role="正方", round_num=r + 1,
                                  prior_log=debate_log)
                con = self._argue(question, stance_b, stance_a,
                                  role="反方", round_num=r + 1,
                                  prior_log=debate_log)

                debate_log.append({
                    "round": r + 1,
                    "pro": {"stance": stance_a, "arguments": pro},
                    "con": {"stance": stance_b, "arguments": con},
                })

            return json.dumps({
                "question": question,
                "debate": debate_log,
                "instruction": (
                    "以上是正反双方的论据。请在下一个 Thought 中综合双方观点，"
                    "给出客观、平衡的最终结论。"
                ),
            }, ensure_ascii=False, indent=2)

        except Exception as exc:
            return json.dumps({"error": f"Debate failed: {exc}"})

    # ------------------------------------------------------------------
    def _argue(self, question: str, my_stance: str, opponent_stance: str,
               role: str, round_num: int, prior_log: list) -> str:
        """Prompt one debater to argue for their stance."""
        system = (
            f"你是一位专业辩手，你的立场是：{my_stance}。\n"
            "你必须为这个立场提供最有力的论据，不得改变立场。\n"
            "论据要具体、有逻辑，每条不超过 60 字，列出 3 条即可。\n"
            "只输出论据列表，不要开场白或总结。"
        )

        user_content = f"辩题：{question}"
        if round_num > 1 and prior_log:
            prev = prior_log[-1]
            opponent_args = (
                prev["con"]["arguments"]
                if role == "正方"
                else prev["pro"]["arguments"]
            )
            user_content += (
                f"\n\n对方上一轮论点：\n{opponent_args}\n\n"
                "请针对对方论点进行反驳，同时补充新的支持论据。"
            )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        raw = self._llm.chat(messages, temperature=0.8, max_tokens=3000)
        return raw.strip()
