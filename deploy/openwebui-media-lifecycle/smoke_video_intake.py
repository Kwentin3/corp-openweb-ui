#!/usr/bin/env python3
"""Run the native upload route against an isolated OpenWebUI instance."""

from __future__ import annotations

import argparse
import secrets
import time
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--uploads", type=Path, default=Path("/app/backend/data/uploads"))
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        signup = client.post("/api/v1/auths/signup", json={
            "name": "Media intake test",
            "email": "media-intake-test@example.invalid",
            "password": secrets.token_urlsafe(24),
        })
        signup.raise_for_status()
        token = signup.json()["token"]
        client.headers["Authorization"] = f"Bearer {token}"

        with args.video.open("rb") as video:
            response = client.post("/api/v1/files/", files={"file": (args.video.name, video, "video/mp4")})
        response.raise_for_status()
        file_id = response.json()["id"]
        initial = client.get(f"/api/v1/files/{file_id}")
        initial.raise_for_status()
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            status = client.get(f"/api/v1/files/{file_id}/process/status")
            status.raise_for_status()
            current = status.json()["status"]
            if current in ("completed", "failed"):
                break
            time.sleep(1)
        else:
            raise AssertionError("Video preparation did not finish in 180 seconds")
        record = client.get(f"/api/v1/files/{file_id}")
        record.raise_for_status()
        item = record.json()
        assert current == "completed", (current, item.get("data", {}).get("error"))
        assert item["meta"]["content_type"] == "audio/mpeg", item["meta"]
        assert item["filename"].endswith(".mp3"), item["filename"]
        assert item["data"]["stage2_video_intake"]["state"] == "completed"
        assert Path(item["path"]).is_file(), item["path"]
        assert not list(args.uploads.glob(f"{file_id}_*.mp4")), "Source video still exists"
        content = client.get(f"/api/v1/files/{file_id}/content")
        content.raise_for_status()
        assert content.headers["content-type"].startswith("audio/"), content.headers
        print({"status": current, "file_id": file_id, "audio_bytes": item["meta"]["size"], "source_video_files": 0})


if __name__ == "__main__":
    main()
