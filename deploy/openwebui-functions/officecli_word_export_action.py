"""
title: В Word
author: Alpha Soft
version: 1.1.0
required_open_webui_version: 0.11.4
description: Export the selected completed answer through the existing OfficeCLI tool server.
"""

from __future__ import annotations


class Action:
    def __init__(self):
        self.actions = [
            {"id": "word", "name": "В Word"},
            {"id": "word_fields", "name": "Word: дата и подписи"},
        ]

    async def action(self, body: dict, __user__=None, __request__=None,
                     __event_emitter__=None, __id__=None):
        from open_webui.models.users import UserModel
        from open_webui.utils.tools import get_tools

        if __id__ not in {"word", "word_fields"}:
            raise ValueError("unknown Word export action")
        chat_id, message_id = body.get("chat_id"), body.get("id")
        if not isinstance(chat_id, str) or not isinstance(message_id, str) or not __user__ or __request__ is None:
            raise ValueError("native chat, selected message and user session are required")

        async def status(description, done):
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": description, "done": done}})

        await status("Создаю Word из выбранного ответа…", False)
        try:
            tools = await get_tools(__request__, ["server:officecli"], UserModel(**__user__),
                                    {"__user__": __user__, "__metadata__": {
                                        "chat_id": chat_id, "message_id": message_id}})
            tool = tools.get("export_answer_to_word")
            if not tool:
                raise ValueError("OfficeCLI is unavailable for this user")
            commands = []
            if __id__ == "word_fields":
                for text in ("Дата составления: «___» ____________ 20___ г.",
                             "Подписи сторон",
                             "Подпись: ____________________ / ФИО: ____________________",
                             "Подпись: ____________________ / ФИО: ____________________"):
                    commands.append({"command": "add", "parent": "/body", "type": "paragraph",
                                     "props": {"text": text, "style": "Normal", "size": "11pt",
                                               "spaceBefore": "8pt", "spaceAfter": "4pt"}})
            result, _ = await tool["callable"](output_name="answer.docx",
                                                 source_message="selected_assistant", commands=commands)
            if not isinstance(result, dict) or result.get("source_message_id") != message_id or result.get("source_text_preserved") is not True or not result.get("result_file_id"):
                raise ValueError("OfficeCLI did not return a source-bound Word result")
            await status("Word готов — файл прикреплён к ответу", True)
            return {key: result[key] for key in ("result_file_id", "result_sha256", "source_message_id",
                                                  "source_content_sha256", "source_text_preserved")}
        except Exception:
            await status("Не удалось создать Word. Исходный текст сохранён.", True)
            raise
