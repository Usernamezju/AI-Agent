"""Few-shot example library for ReAct format stability."""
import json

EXAMPLES = [
    {
        "user": "Calculate (15 + 7) * 3 / 2",
        "steps": [
            {"thought": "I'll evaluate the expression using the calculator.", "action": "calculator",
             "action_input": {"expression": "(15 + 7) * 3 / 2"}, "observation": "33.0"},
            {"thought": "The result is 33.0.", "final_answer": "The result is 33."},
        ],
    },
    {
        "user": "Who is Alan Turing and when was he born?",
        "steps": [
            {"thought": "I'll search Wikipedia for Alan Turing.", "action": "wikipedia_search",
             "action_input": {"query": "Alan Turing"},
             "observation": json.dumps({"title": "艾伦·图灵", "page_id": 12345,
                                         "extract": "艾伦·麦席森·图灵（1912年6月23日—1954年6月7日），英国计算机科学家…"},
                                        ensure_ascii=False)},
            {"thought": "I have the needed information.",
             "final_answer": "艾伦·图灵（Alan Turing）是英国计算机科学家，出生于1912年6月23日。"},
        ],
    },
    {
        "user": "Write 'Hello' into greeting.txt",
        "steps": [
            {"thought": "I'll use local_filesystem to write the file.", "action": "local_filesystem",
             "action_input": {"operation": "write", "path": "greeting.txt", "content": "Hello"},
             "observation": json.dumps({"path": "greeting.txt", "written_bytes": 5}, ensure_ascii=False)},
            {"thought": "File written successfully.",
             "final_answer": "已创建 greeting.txt 并写入 'Hello'。"},
        ],
    },
]


def format_few_shot_examples() -> str:
    lines = ["## Examples\n"]
    for i, ex in enumerate(EXAMPLES, 1):
        lines.append(f"### Example {i}\nUser: {ex['user']}\n")
        for step in ex["steps"]:
            lines.append(f"Thought: {step['thought']}")
            if "action" in step:
                lines.append(f"Action: {step['action']}")
                lines.append(f"Action Input: {json.dumps(step['action_input'], ensure_ascii=False)}")
                lines.append(f"Observation: {step['observation']}\n")
            else:
                lines.append(f"Final Answer: {step['final_answer']}\n")
    return "\n".join(lines)
