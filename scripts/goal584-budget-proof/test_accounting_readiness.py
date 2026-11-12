"""One full-history accounting owner: pending deficits, strict contradictions."""
import copy
from pathlib import Path
import sys
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_admin_calls import accounting_totals_ready, verify_accounting_totals


def packet():
    ids = [str(uuid4()) for _ in range(4)]
    users = [{"user_id": uid, "spend_usd": ".6000000000000001" if index == 0 else ".2"}
             for index, uid in enumerate(ids)]
    keys = [{"user_id": user["user_id"], "model": model, "spend_usd": user["spend_usd"] if model == "goal584-a" else "0"}
            for user in users for model in ("goal584-a", "goal584-b")]
    rows = [{"request_id": "chatcmpl-goal584-" + uuid4().hex, "user_id": uid, "model_group": "goal584-a", "spend_usd": ".2"}
            for index, uid in enumerate(ids) for _ in range(3 if index == 0 else 1)]
    return [users, keys, rows, ids]


class AccountingReadinessTests(unittest.TestCase):
    def test_complete_four_payer_history_accepts_binary_rounding_and_exact_zero_b(self):
        values = packet()
        self.assertTrue(accounting_totals_ready(*values))
        self.assertIsNone(verify_accounting_totals(*values))

    def test_counter_deficit_is_pending_and_strict_final_wrapper_rejects_it(self):
        values = packet()
        values[0][0]["spend_usd"] = ".4"
        values[1][0]["spend_usd"] = ".4"
        self.assertFalse(accounting_totals_ready(*values))
        with self.assertRaises(AssertionError): verify_accounting_totals(*values)
        values[0][0]["spend_usd"] = ".6"
        values[1][0]["spend_usd"] = ".6"
        self.assertTrue(accounting_totals_ready(*values))

    def test_complete_history_surplus_and_any_nonzero_zero_total_are_contradictions(self):
        for collection, index, spend in ((0, 0, ".8"), (1, 0, ".8"), (1, 1, ".000000000001")):
            values = packet(); values[collection][index]["spend_usd"] = spend
            with self.subTest(collection=collection, index=index), self.assertRaises(AssertionError):
                accounting_totals_ready(*values)

    def test_incomplete_history_does_not_misclassify_an_ahead_counter_as_surplus(self):
        values = packet(); values[2] = []
        self.assertFalse(accounting_totals_ready(*values, history_complete=False))
        with self.assertRaises(AssertionError): accounting_totals_ready(*values)
        values[1].pop()
        with self.assertRaises(AssertionError): accounting_totals_ready(*values, history_complete=False)

    def test_duplicate_missing_foreign_identity_and_invalid_money_fail_immediately(self):
        for mutate in (lambda v: v[2].append(copy.deepcopy(v[2][0])), lambda v: v[0].pop(),
                       lambda v: v[1].pop(), lambda v: v[1].__setitem__(1, copy.deepcopy(v[1][0])),
                       lambda v: v[2][0].update(user_id=str(uuid4())), lambda v: v[2][0].update(model_group="foreign"),
                       lambda v: v[0][0].update(spend_usd="NaN"), lambda v: v[1][0].update(spend_usd="-1"),
                       lambda v: v[2][0].update(spend_usd="Infinity"), lambda v: v[2][0].update(spend_usd=True),
                       lambda v: v[2][0].pop("request_id")):
            for complete in (True, False):
                values = packet(); mutate(values)
                with self.subTest(mutation=mutate, complete=complete), self.assertRaises(AssertionError):
                    accounting_totals_ready(*values, history_complete=complete)


if __name__ == "__main__": unittest.main()
