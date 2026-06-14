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
    {
        "user": "比较中国、美国、日本2023年GDP（单位：万亿美元）",
        "steps": [
            {
                "thought": "我知道这三个国家的GDP数据，用柱状图展示对比更直观。",
                "action": "visualize",
                "action_input": {
                    "chart_type": "bar",
                    "title": "2023年GDP对比（万亿美元）",
                    "labels": ["中国", "美国", "日本"],
                    "datasets": [{"label": "GDP", "data": [17.7, 27.4, 4.2]}],
                    "y_label": "GDP（万亿美元）",
                },
                "observation": "{\"visualization_file\": \"viz_a1b2c3d4.html\", \"status\": \"rendered\"}",
            },
            {"thought": "图表已生成，补充文字说明。",
             "final_answer": "如图所示，2023年美国GDP最高（27.4万亿美元），中国其次（17.7万亿），日本第三（4.2万亿）。"},
        ],
    },
    {
        "user": "人工智能会取代程序员吗？",
        "steps": [
            {
                "thought": (
                    "这是一个有争议的预测性问题，正反双方都有有力论据。"
                    "我应该用辩论工具收集两方观点再给出结论。"
                ),
                "action": "perspective_debate",
                "action_input": {
                    "question": "人工智能会取代程序员吗？",
                    "stance_a": "人工智能将全面取代程序员",
                    "stance_b": "人工智能不会取代程序员，只会改变编程方式",
                    "rounds": 1,
                },
                "observation": json.dumps({
                    "question": "人工智能会取代程序员吗？",
                    "debate": [{
                        "round": 1,
                        "pro": {
                            "stance": "人工智能将全面取代程序员",
                            "arguments": (
                                "1. GitHub Copilot 已能自动生成70%的常规代码，效率远超人类。\n"
                                "2. AI 不需要休息、不会出错、学习成本为零，边际成本趋近于零。\n"
                                "3. 历史上每次技术革命都彻底淘汰了旧职业（如打字员、电话接线员）。"
                            ),
                        },
                        "con": {
                            "stance": "人工智能不会取代程序员，只会改变编程方式",
                            "arguments": (
                                "1. AI 生成的代码需要人类审查和调试，理解业务需求仍需人类判断。\n"
                                "2. 系统架构、安全设计、跨团队协作等高阶能力 AI 尚不具备。\n"
                                "3. 软件需求膨胀速度快于 AI 能力提升，程序员总量不会减少。"
                            ),
                        },
                    }],
                    "instruction": "以上是正反双方的论据。请综合给出平衡结论。",
                }, ensure_ascii=False),
            },
            {
                "thought": (
                    "正方指出 AI 代码生成能力强、成本低；"
                    "反方指出业务理解和架构设计仍需人类。"
                    "两方都有道理，结论应当是角色转变而非完全取代。"
                ),
                "final_answer": (
                    "AI 不会完全取代程序员，但会深刻改变编程职业的内容。"
                    "重复性编码工作将被 AI 承担，程序员的价值将向需求理解、"
                    "系统设计和 AI 协作方向转移。未来的程序员更像'AI 指挥家'而非'代码工人'。"
                ),
            },
        ],
    },
    {
        "user": "Convert a list of temperatures from Celsius to Fahrenheit: [0, 20, 37, 100]",
        "steps": [
            {
                "thought": "I don't have a unit conversion tool. I'll create one.",
                "action": "tool_synthesizer",
                "action_input": {
                    "tool_name": "celsius_to_fahrenheit",
                    "tool_description": "Converts a list of Celsius temperatures to Fahrenheit",
                    "parameters_schema": {
                        "type": "object",
                        "properties": {
                            "values": {"type": "array", "items": {"type": "number"}}
                        },
                        "required": ["values"],
                    },
                    "function_code": "def run(values, **kwargs):\n    return str([round(v * 9/5 + 32, 1) for v in values])",
                    "test_call": {"values": [0, 100]},
                },
                "observation": "Tool 'celsius_to_fahrenheit' successfully created. Test output: [32.0, 212.0]",
            },
            {
                "thought": "Tool registered. Now I'll use it.",
                "action": "celsius_to_fahrenheit",
                "action_input": {"values": [0, 20, 37, 100]},
                "observation": "[32.0, 68.0, 98.6, 212.0]",
            },
            {
                "thought": "I have the results.",
                "final_answer": "The temperatures in Fahrenheit are: 32.0, 68.0, 98.6, 212.0",
            },
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
