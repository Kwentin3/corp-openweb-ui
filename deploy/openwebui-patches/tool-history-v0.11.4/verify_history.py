"""Verify the installed native converter; no provider, database or tool calls."""
from __future__ import annotations

import copy
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

# Native env initialization requires a key even for these stateless tests.
# This fixture is process-local and never becomes image/runtime configuration.
os.environ["WEBUI_SECRET_KEY"] = "synthetic-tool-history-test-key-only"

from open_webui.utils.misc import convert_output_to_messages

from apply_upstream import NEW, OLD, ORIGINAL_SHA256, PATCHED_SHA256, apply


def call(identifier, name="read", *, status="completed"):
    return {"type": "function_call", "call_id": identifier, "name": name,
            "arguments": '{"value":1}', "status": status}


def result(identifier, text="result", *, image=None):
    parts = [{"type": "input_text", "text": text}]
    if image:
        parts.append({"type": "input_image", "image_url": image})
    return {"type": "function_call_output", "call_id": identifier, "output": parts}


def message(text):
    return {"type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": text}]}


def convert(output):
    return convert_output_to_messages(output, raw=True, flatten_tool_images=True)


def pairs(messages):
    """Check the provider's immediate tool-call/result adjacency contract."""
    pending = set()
    for item in messages:
        if item["role"] == "tool":
            identifier = item["tool_call_id"]
            if identifier not in pending:
                raise AssertionError("Tool result outside its assistant batch")
            pending.remove(identifier)
        else:
            if pending:
                raise AssertionError("A message separates tool calls from results")
            pending = {x["id"] for x in item.get("tool_calls", [])}
    if pending:
        raise AssertionError("Missing tool results")


class NativeHistoryTests(unittest.TestCase):
    def test_sequential_rounds_keep_order(self):
        messages = convert([call("a"), result("a"), call("b"), result("b")])
        self.assertEqual([m["role"] for m in messages], ["assistant", "tool"] * 2)
        self.assertEqual(messages[0]["tool_calls"][0]["id"], "a")
        self.assertEqual(messages[2]["tool_calls"][0]["id"], "b")
        pairs(messages)

    def test_parallel_calls_remain_one_batch(self):
        messages = convert([call("a"), call("b"), result("b"), result("a")])
        self.assertEqual([m["role"] for m in messages], ["assistant", "tool", "tool"])
        self.assertEqual([c["id"] for c in messages[0]["tool_calls"]], ["a", "b"])
        pairs(messages)

    def test_text_and_later_parallel_round_preserve_adjacency(self):
        output = [call("a"), message("Reading."), result("a"),
                  call("b"), call("c"), message("Checking."), result("b"), result("c")]
        messages = convert(output)
        self.assertEqual([m["role"] for m in messages],
                         ["assistant", "tool", "assistant", "tool", "tool"])
        self.assertEqual(messages[0]["content"], "Reading.")
        self.assertEqual(messages[2]["content"], "Checking.")
        pairs(messages)

    def test_render_stays_before_subsequent_edits(self):
        output = [call("render", "render_office_file"),
                  result("render", image="/api/v1/files/old-render/content"),
                  call("edit", "apply_office_batch"), result("edit", "new version")]
        messages = convert(output)
        self.assertEqual([m["role"] for m in messages],
                         ["assistant", "tool", "user", "assistant", "tool"])
        self.assertEqual(messages[2]["content"][1]["image_url"]["url"],
                         "/api/v1/files/old-render/content")
        self.assertEqual(messages[-1]["content"], "new version")
        pairs(messages)

    def test_previous_prefix_stays_identical_when_round_is_added(self):
        output = []
        previous = []
        for index in range(5):
            identifier = str(index)
            output += [call(identifier), result(identifier, image=f"image-{index}")]
            current = convert(output)
            self.assertEqual(current[:len(previous)], previous)
            previous = current
            pairs(current)

    def test_incomplete_calls_do_not_lose_completed_results(self):
        output = [call("a"), result("a"), call("b", status="incomplete")]
        messages = convert(output)
        self.assertEqual([m["role"] for m in messages], ["assistant", "tool"])
        self.assertEqual(messages[-1]["tool_call_id"], "a")
        pairs(messages)

    def test_full_guide_and_native_output_are_preserved(self):
        guide = "Official guide\n" * 3000
        output = [call("guide", "load_officecli_skill"), result("guide", guide),
                  call("create", "create_office_document"), result("create", "attachment")]
        saved = copy.deepcopy(output)
        messages = convert(output)
        self.assertEqual(messages[1]["content"], guide)
        self.assertEqual(output, saved)
        pairs(messages)

    def test_multimodal_tool_output_remains_supported(self):
        messages = convert_output_to_messages(
            [call("a"), result("a", "render", image="image-a"), call("b"), result("b")],
            raw=True,
        )
        self.assertEqual(messages[1]["content"],
                         [{"type": "input_text", "text": "render"},
                          {"type": "input_image", "image_url": "image-a"}])
        pairs(messages)


class InstallerTests(unittest.TestCase):
    def test_exact_source_check_apply_repeat_and_drift_rejection(self):
        import open_webui.utils.misc as misc
        installed = Path(misc.__file__).read_bytes()
        digest = hashlib.sha256(installed).hexdigest()
        self.assertIn(digest, {ORIGINAL_SHA256, PATCHED_SHA256})
        original = installed if digest == ORIGINAL_SHA256 else installed.replace(NEW.encode(), OLD.encode())
        self.assertEqual(hashlib.sha256(original).hexdigest(), ORIGINAL_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "utils").mkdir()
            path = root / "utils/misc.py"
            path.write_bytes(original)
            apply(root, check=True)
            self.assertEqual(path.read_bytes(), original)
            apply(root)
            patched = path.read_bytes()
            self.assertEqual(hashlib.sha256(patched).hexdigest(), PATCHED_SHA256)
            apply(root)
            self.assertEqual(path.read_bytes(), patched)
            foreign = original + b"\n# foreign source\n"
            path.write_bytes(foreign)
            with self.assertRaisesRegex(RuntimeError, "Unsupported OpenWebUI"):
                apply(root)
            self.assertEqual(path.read_bytes(), foreign)


if __name__ == "__main__":
    unittest.main()
