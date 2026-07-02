import json
import sqlite3
import time
import uuid

from fastapi.testclient import TestClient

from stage2_stt.app import create_app


INTERNAL_TOKEN = "unit-test-internal-token"


def test_post_processing_template_routes_return_safe_metadata(monkeypatch, tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-summary",
        command="stt-summary",
        name="Краткий пересказ",
        content="Summarize {{TRANSCRIPT_TEXT}}",
        template_id="stage2.stt.summary.v1",
        public=True,
    )
    _enable_prompt_catalog(monkeypatch, db_path)
    client = TestClient(create_app())

    listed = client.get(
        "/stage2-api/transcription/post-processing/templates",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        params={"user_id": "user-1", "user_role": "user"},
    )
    by_id = client.get(
        "/stage2-api/transcription/post-processing/templates/stage2.stt.summary.v1",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        params={"user_id": "user-1", "user_role": "user"},
    )
    by_command = client.get(
        "/stage2-api/transcription/post-processing/templates/by-command/stt-summary",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        params={"user_id": "user-1", "user_role": "user"},
    )

    assert listed.status_code == 200
    assert by_id.status_code == 200
    assert by_command.status_code == 200
    assert listed.json()[0]["template_id"] == "stage2.stt.summary.v1"
    assert by_id.json()["command"] == "stt-summary"
    assert by_command.json()["openwebui_prompt_id"] == "prompt-summary"
    assert "Summarize" not in json.dumps(listed.json(), ensure_ascii=False)


def test_post_processing_template_route_missing_prompt_is_typed(monkeypatch, tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _enable_prompt_catalog(monkeypatch, db_path)
    client = TestClient(create_app())

    response = client.get(
        "/stage2-api/transcription/post-processing/templates/missing-template",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        params={"user_id": "user-1", "user_role": "user"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "prompt_not_found"


def test_post_processing_template_route_private_prompt_fails_closed(monkeypatch, tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-private",
        command="stt-summary",
        name="Краткий пересказ",
        content="Private {{TRANSCRIPT_TEXT}}",
        template_id="stage2.stt.summary.v1",
        public=False,
    )
    _enable_prompt_catalog(monkeypatch, db_path)
    client = TestClient(create_app())

    response = client.get(
        "/stage2-api/transcription/post-processing/templates/stage2.stt.summary.v1",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        params={"user_id": "user-2", "user_role": "user"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "prompt_access_denied"


def _enable_prompt_catalog(monkeypatch, db_path):
    monkeypatch.setenv("STAGE2_STT_INTERNAL_API_KEY", INTERNAL_TOKEN)
    monkeypatch.setenv("STAGE2_STT_PROMPT_CATALOG_MODE", "openwebui_sqlite")
    monkeypatch.setenv("STAGE2_STT_OPENWEBUI_PROMPT_DB_PATH", str(db_path))


def _create_prompt_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE prompt (
                id TEXT PRIMARY KEY,
                command TEXT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                data JSON,
                meta JSON,
                is_active BOOLEAN NOT NULL,
                version_id TEXT,
                tags JSON,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE access_grant (
                id TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                principal_type TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                permission TEXT NOT NULL,
                created_at BIGINT NOT NULL
            )
            """
        )
        conn.commit()


def _insert_prompt(
    path,
    *,
    prompt_id,
    command,
    name,
    content,
    template_id,
    public,
):
    now = int(time.time())
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO prompt(
                id, command, user_id, name, content, data, meta, is_active,
                version_id, tags, created_at, updated_at
            )
            VALUES (?, ?, 'owner-1', ?, ?, '{}', ?, 1, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                command,
                name,
                content,
                json.dumps(
                    {
                        "template_kind": "post_processing",
                        "template_id": template_id,
                        "requires_speakers": False,
                        "chunkable": False,
                    }
                ),
                f"version-{prompt_id}",
                json.dumps(["stage2-stt-v2", "stt-post-processing"]),
                now,
                now,
            ),
        )
        if public:
            conn.execute(
                """
                INSERT INTO access_grant(
                    id, resource_type, resource_id, principal_type,
                    principal_id, permission, created_at
                )
                VALUES (?, 'prompt', ?, 'user', '*', 'read', ?)
                """,
                (str(uuid.uuid4()), prompt_id, now),
            )
        conn.commit()
