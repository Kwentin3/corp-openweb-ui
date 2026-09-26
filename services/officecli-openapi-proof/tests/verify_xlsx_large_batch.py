"""Real OfficeCLI qualification: run with the pinned binary and adapter installed.

    python tests/verify_xlsx_large_batch.py

No provider, user files, or OpenWebUI writes are needed.
"""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from officecli_openapi_proof.app import CreateSpreadsheetRequest, ApplySpreadsheetBatchRequest
from officecli_openapi_proof.config import load_settings
from officecli_openapi_proof.officecli import OfficeCliFailure, SubprocessOfficeCliExecutor


class LargeXlsxBatch(unittest.TestCase):
    def test_complete_batch_and_atomic_failure(self):
        settings = load_settings()
        executor = SubprocessOfficeCliExecutor(settings)
        self.assertEqual(executor.run("--version").text.strip(), settings.expected_version)
        for count in (66, 256):
            with self.subTest(count=count), TemporaryDirectory() as directory:
                path = str(Path(directory) / "result.xlsx")
                executor.run("create", path, "--locale", "en-US", "--json")
                commands = [
                    {"command": "set", "path": f"/Sheet1/A{i}", "props": {"value": str(i)}}
                    for i in range(1, count + 1)
                ]
                for contract in (CreateSpreadsheetRequest, ApplySpreadsheetBatchRequest):
                    request = contract(output_name="result.xlsx", commands=commands)
                    self.assertEqual(request.commands, commands)
                executor.run("batch", path, "--stop-on-error", "--json", input_text=json.dumps(commands))
                executor.run("validate", path, "--json")
                # Read the artifact independently, including the final operation.
                with ZipFile(path) as archive:
                    root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
                    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                    values = {c.attrib["r"]: c.findtext("s:v", namespaces=ns)
                              for c in root.findall(".//s:c", ns)}
                self.assertEqual(values, {f"A{i}": str(i) for i in range(1, count + 1)})
                before = sha256(Path(path).read_bytes()).hexdigest()
                failing = commands[:-1] + [{"command": "set", "path": "/MissingSheet/A1", "props": {"value": "bad"}}]
                failing[0] = {"command": "set", "path": "/Sheet1/A1", "props": {"value": "999"}}
                try:
                    output = executor.run("batch", path, "--stop-on-error", "--json", input_text=json.dumps(failing))
                except OfficeCliFailure:
                    pass
                else:
                    self.assertFalse(json.loads(output.text)["success"])
                self.assertEqual(sha256(Path(path).read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
