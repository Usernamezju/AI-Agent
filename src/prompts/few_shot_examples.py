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
    {
        "user": "Show me what files are in the current directory",
        "steps": [
            {"thought": "I need to list the current directory. I'll use local_filesystem.",
             "action": "local_filesystem",
             "action_input": {"operation": "list", "path": "."},
             "observation": json.dumps({"path": ".", "entries": [
                 {"name": "greeting.txt", "type": "file"},
                 {"name": "notes", "type": "dir"},
             ]}, ensure_ascii=False)},
            {"thought": "I now know the directory contents.",
             "final_answer": "当前目录包含：greeting.txt（文件）和 notes（目录）。"},
        ],
    },
    {
        "user": "计算1到100中所有质数的和",
        "steps": [
            {
                "thought": "需要找出1到100的质数并求和，我来写Python代码实现。",
                "action": "code_interpreter",
                "action_input": {
                    "code": (
                        "def is_prime(n):\n"
                        "    if n < 2: return False\n"
                        "    for i in range(2, int(n**0.5)+1):\n"
                        "        if n % i == 0: return False\n"
                        "    return True\n\n"
                        "primes = [n for n in range(1, 101) if is_prime(n)]\n"
                        "print('质数列表:', primes)\n"
                        "print('质数个数:', len(primes))\n"
                        "print('质数之和:', sum(primes))"
                    ),
                },
                "observation": json.dumps({
                    "stdout": "质数列表: [2, 3, 5, 7, 11, 13, ...97]\n质数个数: 25\n质数之和: 1060",
                    "stderr": "", "returncode": 0, "success": True,
                }, ensure_ascii=False),
            },
            {"thought": "代码执行成功，得到了结果。",
             "final_answer": "1到100中所有质数共25个，它们的和为1060。"},
        ],
    },
    {
        "user": "读取 data.csv 文件，统计每列的平均值",
        "steps": [
            {
                "thought": "需要先确认 data.csv 是否存在，再用代码分析。",
                "action": "local_filesystem",
                "action_input": {"operation": "list", "path": "."},
                "observation": json.dumps({
                    "path": ".", "entries": [{"name": "data.csv", "type": "file"}],
                }, ensure_ascii=False),
            },
            {
                "thought": "文件存在，用 code_interpreter 读取并统计均值。",
                "action": "code_interpreter",
                "action_input": {
                    "code": (
                        "import csv\n\n"
                        "with open('data.csv', encoding='utf-8') as f:\n"
                        "    reader = csv.DictReader(f)\n"
                        "    rows = list(reader)\n\n"
                        "for col in rows[0].keys():\n"
                        "    try:\n"
                        "        vals = [float(r[col]) for r in rows]\n"
                        "        print(f'{col} 均值: {sum(vals)/len(vals):.2f}')\n"
                        "    except ValueError:\n"
                        "        print(f'{col}: 非数值列，跳过')"
                    ),
                },
                "observation": json.dumps({
                    "stdout": "age 均值: 28.50\nscore 均值: 85.30",
                    "stderr": "", "returncode": 0, "success": True,
                }, ensure_ascii=False),
            },
            {"thought": "统计完成。",
             "final_answer": "data.csv 中各数值列的平均值：age=28.50，score=85.30。"},
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
