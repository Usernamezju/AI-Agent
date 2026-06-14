from __future__ import annotations

import json

from retriever import XiyoujiRAG

class XiyoujiAgent:
    def __init__(self) -> None:
        self.rag = XiyoujiRAG()

    def search_character(self, character: str) -> list[dict]:
        """工具 1：查找单个人物。"""
        return self.rag.search(f"{character} 性格 经历 身份")

    def compare_characters(self, first: str, second: str) -> list[dict]:
        """工具 2：分别查找两个人物，帮助 AI 做对比。"""
        return self.rag.search(f"{first} {second} 性格 经历 对比", top_k=8)

    def search_event(self, description: str) -> list[dict]:
        """工具 3：查询《西游记》的具体情节、事件或事实。"""
        return self.rag.search(description, top_k=5)

    def answer(self, question: str) -> str:
        """让 AI 先选择工具，再根据工具结果回答。"""
        decision = self._choose_tool(question)
        tool_name = decision["tool"]
        arguments = decision.get("arguments", {})

        if tool_name == "none":
            return self._chat(question)

        if tool_name not in {"search_character", "compare_characters", "search_event"}:
            return self._chat(question)

        sources = getattr(self, tool_name)(**arguments)
        print(f"\n[Agent 调用工具] {tool_name}({arguments})")
        print(f"[Agent 检索结果] 找到 {len(sources)} 条原文\n")
        return self.rag.generate(question, sources)

    def _choose_tool(self, question: str) -> dict:
        """选择工具。"""
        tool_prompt = f"""你是《西游记》人物分析助手。判断用户问题该用哪个工具，只输出 JSON。

工具：
1. search_character：分析单个人物，参数 character
2. compare_characters：比较两个人物，参数 first 和 second
3. search_event：查询《西游记》的情节、事件、因果等具体内容，参数 description
4. none：问题与《西游记》无关，不需要检索，参数为空对象

问题：{question}
示例：
{{"tool": "search_character", "arguments": {{"character": "孙悟空"}}}}
{{"tool": "compare_characters", "arguments": {{"first": "猪八戒", "second": "沙僧"}}}}
{{"tool": "search_event", "arguments": {{"description": "孙悟空为什么被压在五行山下"}}}}
{{"tool": "none", "arguments": {{}}}}"""
        try:
            response = self.rag.chat_client.chat.completions.create(
                model=self.rag.chat_model,
                messages=[{"role": "user", "content": tool_prompt}],
                temperature=0,
                max_tokens=200,
            )
            content = response.choices[0].message.content
            if not content:
                return {"tool": "none", "arguments": {}}
            return json.loads(content)
        except Exception:
            return {"tool": "none", "arguments": {}}

    def _chat(self, question: str) -> str:
        response = self.rag.chat_client.chat.completions.create(
            model=self.rag.chat_model,
            messages=[{"role": "user", "content": question}],
            temperature=0.2,
        )
        return response.choices[0].message.content
    

if __name__ == "__main__":
    agent = XiyoujiAgent()
    print("我是西游记人物分析小助手。输入 exit 退出。")
    while True:
        question = input("\n你：").strip()
        if question.lower() == "exit":
            break
        if question:
            print("\n助手：", agent.answer(question))
