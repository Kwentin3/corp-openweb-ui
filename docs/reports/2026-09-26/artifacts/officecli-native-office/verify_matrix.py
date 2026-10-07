"""Recheck the qualified cases and bind the exact native fixture sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from validate import verify_receipt

ROOT = Path(__file__).parent
FINAL_FILTER_SHA256 = "0cf225ff80feda14820fe600294a2f5b37d2c1363c7ad3d8566f1e8bc5cb3d04"
CASES = [
    ("claude-opus-5", "user", "opus-final-create.json", "opus-final.json"),
    ("claude-sonnet-4-6", "user", "sonnet-final-create.json", "sonnet-user.json"),
    ("gpt-5.4-mini", "user", "mini-final-create.json", "mini-user.json"),
    ("gpt-5.6-luna", "user", "luna-final-create.json", "luna-user.json"),
    ("models/gemini-3.5-flash", "user", "g35-fixed-create.json", "g35-edit-only.json"),
    ("models/gemini-3.6-flash", "user", "g36-user.json", "g36-user.json"),
    ("models/gemini-3.1-flash-lite", "user", "g31l-user.json", "g31l-user.json"),
    ("models/gemini-3.5-flash-lite", "user", "g35l-user.json", "g35l-user.json"),
    ("office-documents", "user", "office-user.json", "office-user.json"),
    ("gpt-6-luna", "admin", "g6l-final-create.json", "g6l.json"),
    ("gpt-6-sol", "admin", "g6s-final-create.json", "g6s-edit.json"),
    ("claude-opus-5-5", "admin", "c55-final-create.json", "c55-final.json"),
]


def answer(receipt, operation_prefix):
    candidates = [m for m in receipt["messages"] if m["role"] == "assistant"
        and any(c["name"].startswith(operation_prefix) and c.get("result_file_id") for c in m["calls"])]
    assert len(candidates) == 1, (receipt["chat"], operation_prefix)
    return candidates[0]


if __name__ == "__main__":
    bindings = json.loads((ROOT / "source-binding.json").read_text(encoding="utf-8"))
    successful = [b for b in bindings if b.get("result_file_id")]
    assert len(successful) == 24
    fixtures = {ext: hashlib.sha256((ROOT / ("template" + ext)).read_bytes()).hexdigest()
        for ext in (".docx", ".pptx")}
    for b in successful:
        ext = ".docx" if b["call_name"] == "apply_office_batch" else ".pptx"
        assert b["source_sha256"] == fixtures[ext] and b["source_bytes_preserved"] is True
    validated = {}
    for _, _, creation, edit in CASES:
        for name in (creation, edit):
            if name not in validated:
                validated[name] = verify_receipt(ROOT / name)
    rows = []
    unique_outputs = set()
    for model, role, creation, edit in CASES:
        row = {"model": model, "role": role, "creation_receipt": creation, "edit_receipt": edit}
        for stage, name, prefix in (("creation", creation, "create_"), ("edit", edit, "apply_")):
            receipt = json.loads((ROOT / name).read_text(encoding="utf-8"))
            m = answer(receipt, prefix)
            assert m["model"] == model and len(m["files"]) == 2
            row[stage] = {"status": "PASS", "chat": receipt["chat"], "message": m["id"],
                "files": [{k: f[k] for k in ("id", "local_file", "sha256", "bytes")} for f in m["files"]]}
            unique_outputs.update(f["id"] for f in m["files"])
        rows.append(row)
    assert len(unique_outputs) == 48
    result = {"filter_sha256": FINAL_FILTER_SHA256, "models": 12, "qualified_output_files": 48,
        "fixture_sha256": fixtures, "creation_on_final_instruction": True,
        "edit_contract_unchanged_by_final_paragraph_example": True,
        "rows": rows, "private_file_cross_user_status": 404}
    (ROOT / "acceptance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"models": len(rows), "qualified_output_files": len(unique_outputs), "status": "PASS"}))
