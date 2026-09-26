"""Verify the nine ordinary-chat receipts and their downloaded XLSX outputs."""
import importlib.util
import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "claude-opus-5", "claude-sonnet-4-6", "gpt-5.4-mini", "gpt-5.6-luna",
    "office-documents", "models/gemini-3.5-flash", "models/gemini-3.6-flash",
    "models/gemini-3.1-flash-lite", "models/gemini-3.5-flash-lite",
}
spec = importlib.util.spec_from_file_location(
    "workbook_verifier", ROOT.parent / "officecli-multi-xlsx/verify_workbook.py"
)
workbook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workbook)


def verify(root=ROOT):
    matrix = json.loads((root / "acceptance.json").read_text(encoding="utf-8"))
    assert {row["model"] for row in matrix["results"]} == EXPECTED
    assert len(matrix["results"]) == len(EXPECTED)
    assert matrix["role"] == "user"
    results = []
    for row in matrix["results"]:
        receipt = json.loads((root / row["receipt"]).read_text(encoding="utf-8"))
        assert receipt["user_id"] == matrix["user_id"]
        messages = receipt["messages"]
        sources = messages[0]["files"]
        assert {f["name"] for f in sources} == {"jan.xlsx", "feb.xlsx"}
        source_ids = {f["id"] for f in sources}
        assert len(source_ids) == 2 and None not in source_ids
        assistant = messages[-1]
        assert assistant["role"] == "assistant" and assistant["done"] is True
        assert assistant["model"] == row["model"] and not assistant.get("error")
        calls = assistant["calls"]
        creates = [c for c in calls if "create_office_spreadsheet" in c["name"] and c.get("result_file_id")]
        assert len(creates) == 1
        native_sources = {s["id"]: s for s in assistant["sources"]}
        for source in sources:
            native = native_sources[source["id"]]
            assert native["name"] == source["name"]
            assert native["user_id"] == matrix["user_id"]
            assert set(native["metadata_file_ids"]) == {source["id"]}
            assert set(native["created_by"]) == {matrix["user_id"]}
            fixture = ROOT.parent / "officecli-multi-xlsx" / source["name"]
            assert native["file_sha256"] == hashlib.sha256(fixture.read_bytes()).hexdigest()
            expected = "Product Quantity Price A 2 100 B 3 50" if source["name"] == "jan.xlsx" else "Product Quantity Price A 4 120 B 1 70"
            assert " ".join(" ".join(native["document"]).split()) == expected
        if row["model"].startswith("models/gemini-"):
            assert any(c["google_signature_present"] for c in calls)
        files = assistant["files"]
        assert len(files) == 1 and files[0]["status"] == 200
        assert files[0]["metadata_status"] == 200
        assert files[0]["user_id"] == matrix["user_id"]
        assert files[0]["id"] not in source_ids
        assert creates[0]["result_file_id"] == files[0]["id"]
        result = workbook.verify(root / row["workbook"])
        assert result["sha256"] == row["sha256"]
        results.append({"model": row["model"], "chat": receipt["chat"], **result})
    return {"image_id": matrix["image_id"], "profiles": len(results), "results": results}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=True))
