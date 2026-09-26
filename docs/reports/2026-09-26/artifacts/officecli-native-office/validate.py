"""Verify downloaded native Office artifacts against synthetic source packages."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).parent
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def semantic(node):
    # OfficeCLI assigns stable paragraph IDs and serializes empty properties.
    # Ignore only these non-content changes, attribute order and indentation.
    attrs = tuple(sorted((k, v) for k, v in node.attrib.items()
        if k not in (W14 + "paraId", W14 + "textId", "{http://www.w3.org/XML/1998/namespace}space")))
    text = node.text or ""
    if node.tag not in (W + "t", A + "t") and not text.strip():
        text = ""
    children = tuple(semantic(c) for c in node
        if not (c.tag == W + "pPr" and not c.attrib and not len(c) and not (c.text or "").strip()))
    return node.tag, attrs, text, children


def xml(data):
    return semantic(ET.fromstring(data))


def verify_edit(source: Path, result: Path):
    docx = source.suffix == ".docx"
    part = "word/document.xml" if docx else "ppt/slides/slide1.xml"
    old, new = ("SOURCE ALPHA 41", "EDITED ALPHA 91") if docx else ("SOURCE BETA 52", "EDITED BETA 92")
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(result) as dst:
        assert dst.testzip() is None
        added = set(dst.namelist()) - set(src.namelist())
        assert added <= {"docProps/custom.xml"}, added
        assert not set(src.namelist()) - set(dst.namelist()), "removed package parts"
        for name in src.namelist():
            x, y = src.read(name), dst.read(name)
            if name == part:
                assert old.encode() in x and new.encode() in y and old.encode() not in y
                assert xml(x.replace(old.encode(), new.encode())) == xml(y), name
            elif name == "docProps/custom.xml":
                left, right = ET.fromstring(x), ET.fromstring(y)
                for root in (left, right):
                    for child in list(root):
                        if child.get("name") == "OfficeCLI.LastModified":
                            root.remove(child)
                assert semantic(left) == semantic(right), name
            elif name in ("[Content_Types].xml", "_rels/.rels"):
                left, right = ET.fromstring(x), ET.fromstring(y)
                for root in (left, right):
                    for child in list(root):
                        if child.get("PartName") == "/docProps/custom.xml" or child.get("Type", "").endswith("/custom-properties"):
                            root.remove(child)
                assert semantic(left) == semantic(right), name
            elif name.endswith((".xml", ".rels")):
                assert xml(x) == xml(y), name
            else:
                assert x == y, name
        if added:
            custom = ET.fromstring(dst.read("docProps/custom.xml"))
            assert {c.get("name") for c in custom} == {"OfficeCLI.Version", "OfficeCLI.LastModified"}
    return {"source": source.name, "result": result.name, "preservation": "PASS", "requested_text_edit": "PASS"}


def verify_create(result):
    with zipfile.ZipFile(result) as z:
        assert z.testzip() is None
        if result.suffix == ".docx":
            texts = [n.text or "" for n in ET.fromstring(z.read("word/document.xml")).iter(W + "t")]
            assert texts == ["Office Native Check", "SOURCE ALPHA 41", "KEEP WORD 73"], texts
        else:
            slides = sorted(n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
            assert len(slides) == 2, slides
            texts = [[n.text or "" for n in ET.fromstring(z.read(s)).iter(A + "t")] for s in slides]
            assert texts == [["SOURCE BETA 52"], ["KEEP SLIDE 84"]], texts
    return {"result": result.name, "requested_content": "PASS"}


def verify_receipt(path):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for index, m in enumerate(receipt["messages"]):
        if m["role"] != "assistant":
            continue
        assert m.get("done") is True and not m.get("error"), path.name
        calls = m.get("calls", [])
        outputs = [c for c in calls if c.get("result_file_id")]
        assert len(outputs) == 2, (path.name, outputs)
        assert len(m["files"]) == 2
        assert {c["result_file_id"] for c in outputs} == {f["id"] for f in m["files"]}
        assert m.get("final"), "empty final answer"
        for f in m["files"]:
            assert f["status"] == 200 and f["user_id"] == receipt["user_id"]
            expected_mime = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if f["name"].endswith(".docx") else "application/vnd.openxmlformats-officedocument.presentationml.presentation")
            assert f["mime"] == expected_mime, f["name"]
            if "base64" in f:
                binary = base64.b64decode(f.pop("base64"))
                f["local_file"] = path.stem + "-" + str(index) + Path(f["name"]).suffix
                (ROOT / f["local_file"]).write_bytes(binary)
            local = ROOT / f["local_file"]
            assert hashlib.sha256(local.read_bytes()).hexdigest() == f["sha256"]
            output = next(c for c in outputs if c["result_file_id"] == f["id"])
            assert output["result_sha256"] == f["sha256"]
            assert output["batch_result"]["data"]["summary"]["failed"] == 0
            assert output["validation_result"]["data"]["count"] == 0
            if output["name"].startswith("create_"):
                results.append(verify_create(local))
            else:
                source_id = output["source_file_id"]
                inspection = next(c for c in calls if c["name"].startswith("inspect_") and c["arguments"].get("file_id") == source_id)
                assert not inspection.get("tool_error")
                results.append(verify_edit(ROOT / ("template" + local.suffix), local))
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"receipt": path.name, "chat": receipt["chat"], "checks": results}


if __name__ == "__main__":
    import sys
    paths = [ROOT / n for n in sys.argv[1:]]
    results = [verify_receipt(p) for p in paths]
    print(json.dumps(results, ensure_ascii=False, indent=2))
