from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from fastapi.testclient import TestClient

from officecli_openapi_proof.app import create_app
from officecli_openapi_proof.config import Settings
from officecli_openapi_proof.officecli import OfficeCliOutput, SubprocessOfficeCliExecutor


@dataclass
class RecordingOfficeCli:
    calls: list[tuple[str, ...]]

    def run(self, *arguments: str) -> OfficeCliOutput:
        self.calls.append(arguments)
        content = f"official {' '.join(arguments)} output"
        return OfficeCliOutput(
            command=("/usr/local/bin/officecli", *arguments),
            text=content,
            content_sha256=sha256(content.encode("utf-8")).hexdigest(),
            auto_resident_disabled=True,
        )


def test_load_word_skill_returns_official_executor_output(monkeypatch) -> None:
    monkeypatch.setenv("OFFICECLI_EXPECTED_VERSION", "1.0.148")
    executor = RecordingOfficeCli(calls=[])
    client = TestClient(create_app(executor))

    response = client.post("/v1/officecli/skills/load", json={"skill": "word"})

    assert response.status_code == 200
    assert response.json() == {
        "source": "officecli v1.0.148",
        "command": ["/usr/local/bin/officecli", "load_skill", "word"],
        "content": "official load_skill word output",
        "content_sha256": sha256(b"official load_skill word output").hexdigest(),
        "auto_resident_disabled": True,
    }
    assert executor.calls == [("load_skill", "word")]


def test_openapi_exposes_only_the_named_guidance_operations(monkeypatch) -> None:
    monkeypatch.setenv("OFFICECLI_EXPECTED_VERSION", "1.0.148")
    client = TestClient(create_app(RecordingOfficeCli(calls=[])))

    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/v1/officecli/skills/load"]["post"]["operationId"] == "load_officecli_skill"
    assert schema["paths"]["/v1/officecli/help"]["post"]["operationId"] == "get_officecli_help"


def test_help_uses_only_a_whitelisted_official_topic(monkeypatch) -> None:
    monkeypatch.setenv("OFFICECLI_EXPECTED_VERSION", "1.0.148")
    executor = RecordingOfficeCli(calls=[])
    client = TestClient(create_app(executor))

    response = client.post("/v1/officecli/help", json={"topic": "docx set paragraph"})

    assert response.status_code == 200
    assert response.json()["content"] == "official help docx set paragraph output"
    assert executor.calls == [("help", "docx", "set", "paragraph")]


def test_help_rejects_an_unbounded_shell_like_topic(monkeypatch) -> None:
    monkeypatch.setenv("OFFICECLI_EXPECTED_VERSION", "1.0.148")
    executor = RecordingOfficeCli(calls=[])
    client = TestClient(create_app(executor))

    response = client.post("/v1/officecli/help", json={"topic": "docx; rm -rf /"})

    assert response.status_code == 422
    assert executor.calls == []


def test_subprocess_executor_disables_auto_resident_for_official_guidance(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = "official skill"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        captured["shell"] = kwargs.get("shell", False)
        return Completed()

    monkeypatch.setattr("officecli_openapi_proof.officecli.subprocess.run", fake_run)
    executor = SubprocessOfficeCliExecutor(
        Settings(binary="/usr/local/bin/officecli", timeout_seconds=30, expected_version="1.0.148")
    )

    result = executor.run("load_skill", "word")

    assert captured["command"] == ("/usr/local/bin/officecli", "load_skill", "word")
    assert captured["shell"] is False
    assert captured["environment"]["OFFICECLI_SKIP_UPDATE"] == "1"
    assert captured["environment"]["OFFICECLI_NO_AUTO_RESIDENT"] == "1"
    assert result.text == "official skill"
    assert result.auto_resident_disabled is True
