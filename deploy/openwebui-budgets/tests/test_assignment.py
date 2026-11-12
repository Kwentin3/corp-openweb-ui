"""Assignment compatibility and native config-relative artifact loading."""

import copy
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assignment = load("employee_budget_assignment_test", HERE.parents[1] / "assignment.py")
USER = "1296bad0-1491-4c19-b7f2-93e57d812864"
# Actual aliases read from the accepted older native fixture41450358692,
# webui-native-12-snapshot.json. No credentials or algorithm-derived assertions.
FIXTURE_ALIASES = {
    "goal584-a": "owui-budget-v1-766615ffe0fb87e46be2325b63043da96e974de525f532c56249a8376e39958c",
    "goal584-b": "owui-budget-v1-d138a315e45316ab218f2c5709d53a970f83fe35f84bb2fcf636a760d414c147",
}


class AssignmentTests(unittest.TestCase):
    def test_actual_prior_fixture_aliases_are_unchanged(self):
        for model, alias in FIXTURE_ALIASES.items():
            self.assertEqual(assignment.assignment_alias(USER, model), alias)
            self.assertEqual(assignment.assignment_metadata(model), {
                "owui_budget_namespace": "user-model-v1", "owui_budget_model": model})

    def test_native_record_predicate_retains_exact_scope_and_metadata_behavior(self):
        model = "goal584-a"
        fields = dict(user_id=USER, team_id=None, models=[model], key_alias=FIXTURE_ALIASES[model],
                      metadata={**assignment.assignment_metadata(model), "unrelated": "retained"})
        self.assertTrue(assignment.assignment_matches(SimpleNamespace(**fields), USER, model))
        import json
        encoded = {**fields, "metadata": json.dumps(fields["metadata"])}
        self.assertTrue(assignment.assignment_matches(SimpleNamespace(**encoded), USER, model))
        for changes in [{"user_id": "foreign"}, {"team_id": "team"}, {"models": [model, "other"]},
                        {"key_alias": "wrong"}, {"metadata": "not-json"}, {"metadata": []},
                        {"metadata": {"owui_budget_namespace": "another-namespace"}}]:
            with self.subTest(changes=changes):
                self.assertFalse(assignment.assignment_matches(SimpleNamespace(**{**fields, **changes}), USER, model))
        # Preserve original getattr-based behavior; JSON adaptation is explicit in the client.
        self.assertFalse(assignment.assignment_matches(fields, USER, model))

    def test_auth_shims_use_native_loader_from_a_declared_sibling_artifact(self):
        source = HERE.parents[3] / "local/goal584/litellm/upstream/litellm/proxy/types_utils/utils.py"
        if source.exists():
            native_loader = load("native_config_loader_test", source)
        else:
            try:
                from litellm.proxy.types_utils import utils as native_loader
            except ImportError:
                self.skipTest("Pinned native loader unavailable; image qualification remains required")
        # Execute the actual native loader against the deployment's declared
        # filenames, without adding this directory to a runtime import path.
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            shutil.copyfile(HERE.parents[1] / "assignment.py", directory / "employee_budget_assignment.py")
            shutil.copyfile(HERE.parents[1] / "litellm_auth.py", directory / "litellm_auth.py")
            auth = load("auth_assignment_artifact_test", directory / "litellm_auth.py")
            with patch.dict(sys.modules, {"litellm.proxy.types_utils.utils": native_loader}):
                for model, alias in FIXTURE_ALIASES.items():
                    self.assertEqual(auth.assignment_alias(USER, model), alias)
                    self.assertEqual(auth.assignment_metadata(model), assignment.assignment_metadata(model))
                    record = SimpleNamespace(user_id=USER, team_id=None, models=[model], key_alias=alias,
                                             metadata=copy.deepcopy(auth.assignment_metadata(model)))
                    self.assertTrue(auth._assignment_matches(record, USER, model))
                self.assertEqual(auth.ASSIGNMENT_NAMESPACE, assignment.ASSIGNMENT_NAMESPACE)
                self.assertGreater(auth._assignment_symbol.cache_info().hits, 0)


if __name__ == "__main__":
    unittest.main()
