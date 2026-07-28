# backend/tools/ask_user.py
"""ask_user 工具 — 子 Agent 通过此工具暂停并向用户提问，等待回复后继续。

使用 deepagents HumanInTheLoopMiddleware 的 `respond` 决策类型：
工具调用被拦截，用户回复直接作为工具结果返回给 Agent。
"""

from langchain.tools import tool


@tool
def ask_user(question: str) -> str:
    """向用户提问并暂停执行等待回复。当你需要用户提供信息、
    确认需求、回答问题时，必须使用此工具。不要在回复正文中直接提问。

    Args:
        question: 要问用户的问题，应当清晰明确、逐个提问。
    """
    return question
