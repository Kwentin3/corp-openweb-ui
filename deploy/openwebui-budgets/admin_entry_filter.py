"""
title: Employee budget entry
author: Corporate Open WebUI
version: 0.1.0
required_open_webui_version: 0.12.2
description: Load the existing private budget Skill through native chat context.
"""


class Filter:
    async def inlet(self, body: dict, __user__=None, __metadata__=None, __task__=None) -> dict:
        if not isinstance(__user__, dict) or __user__.get("role") != "admin":
            return body
        tools = body.get("tool_ids")
        if not isinstance(tools, list) or "employee_budget_admin" not in tools or "tools" in body:
            return body
        if (not isinstance(__metadata__, dict) or not __metadata__.get("chat_id")
                or __task__ or __metadata__.get("task") not in (None, "")
                or __metadata__.get("internal") or __metadata__.get("direct")):
            return body
        from open_webui.env import VERSION

        if VERSION != "0.12.2":
            raise ValueError("Employee budget Skill entry requires qualification on this OpenWebUI version.")
        context = __metadata__.setdefault("chat_context", {})
        mentioned = context.setdefault("mentioned_skill_ids", [])
        if "goal584-budget-admin-guide" not in mentioned:
            context["mentioned_skill_ids"] = [*mentioned, "goal584-budget-admin-guide"]
        return body
