#!/usr/bin/env python3
"""Check the ordinary domain upload and STT path using the configured admin."""

import json
import os
import time
import uuid
from pathlib import Path

import httpx


BASE_URL = "https://gpt.alpha-soft.ru"
VIDEO = Path("/tmp/media-production-smoke.mp4")


def main() -> None:
    email = os.environ["WEBUI_ADMIN_EMAIL"]
    password = os.environ["WEBUI_ADMIN_PASSWORD"]
    with httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(240, connect=15)) as client:
        response = client.post("/api/v1/auths/signin", json={"email": email, "password": password})
        response.raise_for_status()
        client.headers["Authorization"] = "Bearer " + response.json()["token"]
        models_response = client.get("/api/models")
        models_response.raise_for_status()
        models = models_response.json().get("data") or []
        preferred = (os.environ.get("DEFAULT_MODELS") or "").split(",")[0]
        model = next((item for item in models if item.get("id") == preferred), None)
        if model is None:
            model = next((item for item in models if item.get("owned_by") != "arena"), None)
        if model is None:
            raise RuntimeError("No ordinary model is available for STT smoke")
        with VIDEO.open("rb") as source:
            upload = client.post("/api/v1/files/?process=true", files={"file": (VIDEO.name, source, "video/mp4")})
        upload.raise_for_status()
        file_id = upload.json()["id"]
        print(json.dumps({"uploaded_file_id": file_id, "model": model["id"]}), flush=True)
        try:
            deadline = time.monotonic() + 120
            while True:
                response = client.get(f"/api/v1/files/{file_id}")
                response.raise_for_status()
                record = response.json()
                status = (record.get("data") or {}).get("status")
                if status in {"completed", "failed"}:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("Video preparation timeout")
                time.sleep(1)
            if status != "completed" or record["meta"]["content_type"] != "audio/mpeg":
                raise RuntimeError(f"Video did not become audio: {status}")
            upload_dir = Path("/app/backend/data/uploads")
            if list(upload_dir.glob(f"{file_id}_*.mp4")):
                raise RuntimeError("Original video blob survived")
            content = client.get(f"/api/v1/files/{file_id}/content")
            content.raise_for_status()
            if not content.headers.get("content-type", "").startswith("audio/"):
                raise RuntimeError("File content is not audio")
            attachment = {"type": "file", "file": record, "id": file_id,
                          "name": record["filename"], "status": "uploaded",
                          "size": record["meta"]["size"], "content_type": "audio/mpeg"}
            message_id = str(uuid.uuid4())
            prompt = "Кратко опиши содержание аудио."
            body = {"stream": False, "model": model["id"], "params": {},
                    "messages": [{"role": "user", "content": prompt}],
                    "files": [attachment], "tool_servers": [], "features": {},
                    "variables": {}, "session_id": str(uuid.uuid4()), "id": str(uuid.uuid4()),
                    "parent_id": None,
                    "user_message": {"id": message_id, "parentId": None, "childrenIds": [],
                                     "role": "user", "content": prompt, "files": [attachment],
                                     "timestamp": int(time.time()), "models": [model["id"]]},
                    "background_tasks": {"title_generation": False, "tags_generation": False,
                                         "follow_up_generation": False}}
            completion = client.post("/api/chat/completions", json=body)
            print(json.dumps({"completion_status": completion.status_code,
                              "completion_type": completion.headers.get("content-type")}), flush=True)
            deadline = time.monotonic() + 180
            while True:
                response = client.get(f"/api/v1/files/{file_id}")
                response.raise_for_status()
                marker = (response.json().get("data") or {}).get("stage2_audio_context_filter") or {}
                if marker.get("state") == "transcribed-v1" or time.monotonic() > deadline:
                    break
                time.sleep(2)
            if marker.get("state") != "transcribed-v1" or not marker.get("transcript"):
                try:
                    completion_keys = sorted(completion.json())
                except ValueError:
                    completion_keys = []
                raise RuntimeError(f"Ordinary chat did not persist STT: response keys={completion_keys}")
            print(json.dumps({"video_to_audio": "passed", "stt": "transcribed-v1",
                              "transcript_chars": len(marker["transcript"])}), flush=True)
        finally:
            deletion = client.delete(f"/api/v1/files/{file_id}")
            print(json.dumps({"test_file_delete_status": deletion.status_code}), flush=True)


if __name__ == "__main__":
    main()
