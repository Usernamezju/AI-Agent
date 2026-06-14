# 🤖 AI Agent Framework

基于 **ReAct（Reasoning + Acting）** 范式，通过 Thought → Action → Observation
循环，让大语言模型动态调用工具完成任务。

## 可用工具
- 🧮 **calculator** — 安全数学计算（AST，不使用 eval）
- 🔍 **wikipedia_search** — Wikipedia 中文搜索
- 📁 **local_filesystem** — 沙箱文件读写

## 快捷命令
| 命令 | 说明 |
|------|------|
| `/memory` | 查看当前长期记忆 |
| `/forget <id>` | 删除指定记忆条目 |
| `/clear_memory` | 清空全部长期记忆 |
