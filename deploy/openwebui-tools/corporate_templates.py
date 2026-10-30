"""
title: Corporate Template Publication
author: Alpha Soft
version: 0.1.0-candidate
required_open_webui_version: 0.12.2
description: Publish agreed text instructions and an existing original DOCX through native Skills and Knowledge.
"""

import re
from typing import Any

import aiohttp
from pydantic import BaseModel, Field


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("A confirmed native identifier is required")
    return value


def _read_grants(value):
    if not isinstance(value, list):
        raise ValueError("Native access grants are missing")
    grants = set()
    for grant in value:
        if not isinstance(grant, dict):
            raise ValueError("Invalid native access grant")
        if grant.get("permission") != "read":
            continue
        principal_type, principal_id = grant.get("principal_type"), grant.get("principal_id")
        if principal_type not in ("user", "group") or not isinstance(principal_id, str) or not principal_id:
            raise ValueError("Invalid native read grant")
        grants.add((principal_type, principal_id))
    return [{"principal_type": kind, "principal_id": principal, "permission": "read"}
            for kind, principal in sorted(grants)]


class Tools:
    class Valves(BaseModel):
        openwebui_base_url: str = Field(
            default="http://127.0.0.1:8080", description="This instance's trusted internal API origin.",
        )
        knowledge_id: str = Field(default="", description="Administrator-selected native template Knowledge ID.")

    def __init__(self):
        self.valves = self.Valves()

    async def _json(self, session, method, path, **kwargs):
        async with session.request(method, path, allow_redirects=False, **kwargs) as response:
            if not 200 <= response.status < 300:
                raise ValueError(f"Native API {method} failed with HTTP {response.status}; inspect state before retrying")
            result = await response.json()
            if not isinstance(result, dict):
                raise ValueError("Unexpected native API response; inspect state before retrying")
            return result

    async def _membership(self, session, knowledge_path, file_id, filename):
        # Native query searches filenames, not File IDs; inspect exact returned IDs.
        examined = 0
        for page in range(1, 101):
            result = await self._json(session, "GET", knowledge_path + "/files",
                                      params={"query": filename, "page": page})
            items = result.get("items")
            if not isinstance(items, list) or not isinstance(result.get("total"), int):
                raise ValueError("Invalid native Knowledge file listing")
            if any(item.get("id") == file_id for item in items):
                return True
            examined += len(items)
            if not items or examined >= result["total"]:
                return False
        raise ValueError("Native membership search exceeded 100 pages; narrow the filename before publication")

    async def _text_skill(self, session, skill_path, version):
        files = await self._json(session, "GET", skill_path + "/files")
        if (files.get("version_id") != version or not isinstance(files.get("files"), list)
                or len(files["files"]) != 1 or files["files"][0].get("path") != "SKILL.md"
                or files["files"][0].get("encoding")):
            raise ValueError("Publication requires the same Skill version containing only UTF-8 SKILL.md")

    async def publish_template(
        self, skill_id: str, file_id: str, __request__: Any = None, __metadata__: dict | None = None,
    ) -> dict:
        """Publish an AGREED original DOCX and its existing text-only Skill to the configured library.

        First prepare and agree the DOCX and instructions with the user, publish the
        document as a native File, and create the private instructions with native
        create_skill. Pass those exact skill_id and file_id. Never put a DOCX/base64
        into a Skill. This operation shares the original through the configured
        Knowledge and shares the Skill with its saved READ grants. Native owners
        enforce the caller's permissions. Partial results must be reported to the
        user; do not repeat a failed publication blindly or claim it is complete.
        """
        # Reject auxiliary tasks before any request or mutation.
        if not isinstance(__metadata__, dict) or __metadata__.get("task") is not None:
            raise ValueError("Publication requires a primary saved chat turn")
        _identifier(__metadata__.get("chat_id"))
        _identifier(__metadata__.get("message_id"))
        skill_id, file_id = _identifier(skill_id), _identifier(file_id)
        knowledge_id = _identifier(self.valves.knowledge_id)
        token = getattr(getattr(getattr(__request__, "state", None), "token", None), "credentials", None)
        if not isinstance(token, str) or not token:
            raise ValueError("Authenticated native request is required")

        receipt = {"status": "blocked", "skill_id": skill_id, "source_file_id": file_id,
                   "knowledge_id": knowledge_id, "completed_steps": [], "attempted_step": "preflight"}
        skill_path = f"/api/v1/skills/id/{skill_id}"
        knowledge_path = f"/api/v1/knowledge/{knowledge_id}"
        suffix = ("\n\n## Original template\n\n"
                  f"Original native File ID: `{file_id}`.\n"
                  f"Template Knowledge ID: `{knowledge_id}`.\n"
                  f"[Download original DOCX](/api/v1/files/{file_id}/content).\n"
                  "Retrieve this original with the existing OfficeCLI file workflow, make a new copy, "
                  "and fill that copy. Preserve the original document and its formatting.\n")
        try:
            async with aiohttp.ClientSession(
                base_url=self.valves.openwebui_base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {token}"}, trust_env=False,
                timeout=aiohttp.ClientTimeout(total=180, connect=10),
            ) as session:
                knowledge = await self._json(session, "GET", knowledge_path)
                if knowledge.get("id") != knowledge_id or knowledge.get("write_access") is not True:
                    raise ValueError("Configured Knowledge identity/write access is not confirmed")
                grants = _read_grants(knowledge.get("access_grants"))
                if not grants:
                    raise ValueError("Configured Knowledge has no shared read grants")
                skill = await self._json(session, "GET", skill_path)
                if skill.get("id") != skill_id or skill.get("write_access") is not True:
                    raise ValueError("Native Skill identity/write access is not confirmed")
                if not skill.get("is_active") or not isinstance(skill.get("content"), str) or not skill["content"].strip():
                    raise ValueError("An active Skill with agreed text instructions is required")
                version = _identifier(skill.get("version_id"))
                await self._text_skill(session, skill_path, version)
                source = await self._json(session, "GET", f"/api/v1/files/{file_id}")
                if (source.get("id") != file_id or not source.get("path") or not isinstance(source.get("filename"), str)
                        or not source["filename"].lower().endswith(".docx")):
                    raise ValueError("A readable native original DOCX is required")
                content = skill["content"]
                if "\n## Original template\n" in content and not content.endswith(suffix):
                    raise ValueError("Skill already contains a different original-template reference")
                content = content if content.endswith(suffix) else content.rstrip() + suffix
                already_linked = await self._membership(session, knowledge_path, file_id, source["filename"])

                # Native processing reads the saved original; no model-supplied text.
                if not isinstance(source.get("data"), dict) or source["data"].get("content") is None:
                    receipt["attempted_step"] = "process_file"
                    await self._json(session, "POST", "/api/v1/retrieval/process/file", json={"file_id": file_id})
                    source = await self._json(session, "GET", f"/api/v1/files/{file_id}")
                    if source.get("id") != file_id or not source.get("data") or source["data"].get("content") is None:
                        raise ValueError("Native original-file processing is not confirmed")
                    receipt["completed_steps"].append("process_file")

                # Sharing the original happens only after every local preflight.
                # Native add-file validates both Knowledge write and source File read.
                if not already_linked:
                    receipt["attempted_step"] = "link_original"
                    linked = await self._json(session, "POST", knowledge_path + "/file/add", json={"file_id": file_id})
                    if linked.get("id") != knowledge_id or not any(
                        item.get("id") == file_id for item in linked.get("files", [])
                    ):
                        raise ValueError("Native Knowledge did not confirm original-file membership")
                receipt["completed_steps"].append("link_original")

                if (content != skill["content"] or _read_grants(skill.get("access_grants")) != grants
                        or any(g.get("permission") != "read" for g in skill["access_grants"])):
                    receipt["attempted_step"] = "update_skill"
                    await self._json(session, "POST", skill_path + "/update", json={
                        "id": skill_id, "name": skill["name"], "description": skill.get("description"),
                        "content": content, "expected_version_id": version,
                        "meta": skill.get("meta", {}), "is_active": True, "access_grants": grants,
                    })
                receipt["completed_steps"].append("update_skill")
                receipt["attempted_step"] = "readback"
                saved = await self._json(session, "GET", skill_path)
                current_knowledge = await self._json(session, "GET", knowledge_path)
                if (saved.get("id") != skill_id or saved.get("content") != content
                        or not saved.get("is_active") or _read_grants(saved.get("access_grants")) != grants
                        or any(g.get("permission") != "read" for g in saved.get("access_grants", []))):
                    raise ValueError("Saved Skill instructions/read grants differ from the intended publication")
                await self._text_skill(session, skill_path, _identifier(saved.get("version_id")))
                if (current_knowledge.get("id") != knowledge_id
                        or _read_grants(current_knowledge.get("access_grants")) != grants
                        or not await self._membership(session, knowledge_path, file_id, source["filename"])):
                    raise ValueError("Knowledge read grants or original-file membership changed during publication")
                receipt.update(status="published", attempted_step=None, skill_version_id=saved.get("version_id"),
                               download_url=f"/api/v1/files/{file_id}/content", access_grants=grants)
                receipt["completed_steps"].append("readback")
        except Exception as error:
            receipt["status"] = "partial" if receipt["attempted_step"] != "preflight" else "blocked"
            # Never include response bodies or credentials in a user-facing receipt.
            receipt["error"] = str(error) if isinstance(error, ValueError) else type(error).__name__
            receipt["next_action"] = "Inspect native Skill and Knowledge state before retrying; no automatic rollback or retry was performed."
        return receipt
