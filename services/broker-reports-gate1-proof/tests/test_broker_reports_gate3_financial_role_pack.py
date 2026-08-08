from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from broker_reports_gate1 import (
    Gate3FinancialLabelDictionaryFactory,
    Gate3FinancialRolePackFactory,
)
from broker_reports_gate1.gate3_financial_role_pack import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE3_ROLE_PACK_V1_FILE_SHA256,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"


EXPECTED_PROFILES = {
    "SECURITY_PURCHASE": (
        ("date", "asset", "quantity", "amount", "currency"),
        ("unit_price",),
    ),
    "SECURITY_DISPOSAL": (
        ("date", "asset", "quantity", "amount", "currency"),
        ("unit_price",),
    ),
    "DIVIDEND_INCOME": (("date", "amount", "currency"), ("asset",)),
    "COUPON_INCOME": (("date", "amount", "currency"), ("asset",)),
    "INTEREST_INCOME": (("date", "amount", "currency"), ()),
    "SECURITIES_LENDING_INCOME": (
        ("date", "amount", "currency"),
        ("asset",),
    ),
    "ACCRUED_COUPON_COMPONENT": (("amount", "currency"), ()),
    "TRANSACTION_CHARGE": (("date", "amount", "currency"), ("asset",)),
    "TAX_WITHHELD": (("date", "amount", "currency"), ("asset",)),
}


def test_role_pack_is_closed_hash_pinned_and_covers_the_dictionary() -> None:
    owner = Gate3FinancialRolePackFactory.create()
    pack = owner.load_published()
    schema = json.loads(
        (
            REPO_ROOT
            / "docs/stage2/contracts/BROKER_REPORTS_GATE3_FINANCIAL_ROLE_PACK.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(pack)
    resource = PACKAGE_ROOT / "gate3_financial_role_pack.v1.json"
    assert hashlib.sha256(resource.read_bytes()).hexdigest() == (
        GATE3_ROLE_PACK_V1_FILE_SHA256
    )
    assert [role["role_id"] for role in pack["roles"]] == [
        "date",
        "asset",
        "quantity",
        "unit_price",
        "amount",
        "currency",
    ]
    assert "related_fact" not in json.dumps(pack, ensure_ascii=False)
    assert pack["binding_contract"] == {
        "value_source": "canonical_target_text",
        "exact_text_policy": "optional_nonempty_literal_substring",
        "normalized_or_computed_values_allowed": False,
        "maximum_bindings_per_role_per_fact": 1,
        "missing_status": "missing",
    }
    assert {
        profile["financial_label"]: (
            tuple(profile["required_roles"]),
            tuple(profile["optional_roles"]),
        )
        for profile in pack["profiles"]
    } == EXPECTED_PROFILES
    dictionary = Gate3FinancialLabelDictionaryFactory.create().load_published()
    assert [profile["financial_label"] for profile in pack["profiles"]] == [
        label["label_id"] for label in dictionary["labels"]
    ]


def test_role_pack_is_the_only_meaning_owner_and_has_bounded_model_view() -> None:
    owner = Gate3FinancialRolePackFactory.create()
    markdown = owner.render_model_markdown()
    source = inspect.getsource(type(owner))
    assert len(markdown) < 3_000
    assert markdown.count("# Financial roles") == 1
    assert "Gate3FinancialRolePackFactory.create" in FACTORY_REQUIRED
    assert "must not be duplicated" in FORBIDDEN
    for role in ("date", "asset", "quantity", "unit_price", "amount", "currency"):
        assert f"### {role}" in markdown
        assert f'"{role}"' not in source
