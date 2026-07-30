from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-30"
OUTPUT_STEM = (
    "BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_"
    "ARCHITECTURE_AUDIT_GOAL15"
)
REPORT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.report.md"
TRANSPARENT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.transparent.json"
RECEIPT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.receipt.safe.json"

BASE_COMMIT = "737682f7dacdd0ff6b1d68c06e51d64c86a4283c"
GOAL_ID = "BROKER_REPORTS_GATE2_GOAL15_TYPE_FIRST_ARCHITECTURE_AUDIT"
RECOMMENDATION_ID = "SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C"
CONFIDENCE = "medium"
TOKEN_ESTIMATOR_ID = "compact_request_utf8_bytes_div_4_plus_64_v1"
TOKEN_ESTIMATOR_OVERHEAD = 64

VARIANT_IDS = (
    "ONE_CALL_CHOICES_AND_PLAUSIBLE_TYPES",
    "ONE_CALL_TYPE_FIRST_FAIL_CLOSED",
    "TYPE_FIRST_THEN_RECORD_SELECTION",
)
VARIANT_LABELS = {
    VARIANT_IDS[0]: "Variant A",
    VARIANT_IDS[1]: "Variant B",
    VARIANT_IDS[2]: "Variant C",
}
VARIANT_A_STAGE1_INSTRUCTION = (
    "Return every plausible type_key from plausible_type_cards that matches "
    "the visible source meaning, preserving card order. Judge type "
    "plausibility independently of whether complete_options can be "
    "constructed. Set selected_choice only when exactly one plausible type "
    "remains and the visible source uniquely supports one complete option of "
    "that type; otherwise set selected_choice to null."
)
TYPE_FIRST_STAGE1_INSTRUCTION = (
    "Return every plausible type_key from plausible_type_cards that matches "
    "the visible source meaning, preserving card order. Return all plausible "
    "types, not only the best one. Judge type plausibility independently of "
    "whether any complete record can be constructed."
)
STAGE2_INSTRUCTION = (
    "The financial type is fixed by Stage 1. Do not reconsider or return a "
    "type. Select one choice_key only when the visible source uniquely "
    "supports one complete option of selected_type_card; otherwise return "
    "selected_choice as null."
)

CASE_ORDER = (
    "syn_successor_v2_unique_cash",
    "syn_successor_v2_unique_printed_total",
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_no_registry_type",
    "syn_successor_v2_missing_discriminator",
    "syn_successor_v2_detail_vs_subtotal",
    "syn_successor_v2_adjacent_equal",
    "syn_successor_v2_adjacent_fx",
    "syn_successor_v2_optional_missing",
    "syn_successor_v2_forbidden_neighbour",
)
DETAILED_CASE_IDS = (
    "syn_successor_v2_unique_cash",
    "syn_successor_v2_no_registry_type",
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_detail_vs_subtotal",
)

PLAUSIBLE_LOCAL_TYPES = {
    "syn_successor_v2_unique_cash": ["type_1"],
    "syn_successor_v2_unique_printed_total": ["type_2"],
    "syn_successor_v2_multiple_compatible": ["type_1", "type_2"],
    "syn_successor_v2_no_registry_type": [],
    "syn_successor_v2_missing_discriminator": ["type_1", "type_2"],
    "syn_successor_v2_detail_vs_subtotal": ["type_2"],
    "syn_successor_v2_adjacent_equal": ["type_1"],
    "syn_successor_v2_adjacent_fx": ["type_1"],
    "syn_successor_v2_optional_missing": ["type_1"],
    "syn_successor_v2_forbidden_neighbour": ["type_1"],
}

SOURCE_SUMMARIES = {
    "syn_successor_v2_unique_cash": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {"meaning": "amount", "literal": "-120.5000"},
                            {"meaning": "currency", "literal": "RUB"},
                            {
                                "meaning": "as of date",
                                "literal": "2026-03-01",
                            },
                            {
                                "meaning": "description",
                                "literal": "Cash balance",
                            },
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_unique_printed_total": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {"meaning": "amount", "literal": "880.00"},
                            {"meaning": "currency", "literal": "USD"},
                            {
                                "meaning": "as of date",
                                "literal": "2026-03-02",
                            },
                            {
                                "meaning": "description",
                                "literal": "Printed total",
                            },
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_multiple_compatible": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {"meaning": "amount a", "literal": "310.00"},
                            {"meaning": "amount b", "literal": "410.00"},
                            {
                                "meaning": "description",
                                "literal": "Possible cash",
                            },
                            {"meaning": "currency", "literal": "EUR"},
                            {
                                "meaning": "as of date",
                                "literal": "2026-03-03",
                            },
                            {
                                "meaning": "description 2",
                                "literal": "Possible total",
                            },
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_no_registry_type": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {"meaning": "amount", "literal": "42.25"},
                            {"meaning": "currency", "literal": "CHF"},
                            {"meaning": "date", "literal": "2026-03-04"},
                            {
                                "meaning": "description",
                                "literal": "Broker fee detail",
                            },
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_missing_discriminator": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {"meaning": "amount", "literal": "90.10"},
                            {"meaning": "currency", "literal": "GBP"},
                            {"meaning": "date", "literal": "2026-03-05"},
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_detail_vs_subtotal": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {"meaning": "currency", "literal": "USD"},
                            {"meaning": "date", "literal": "2026-03-06"},
                            {
                                "meaning": "detail amount",
                                "literal": "25.00",
                            },
                            {
                                "meaning": "description",
                                "literal": "Fee detail and subtotal",
                            },
                            {
                                "meaning": "subtotal amount",
                                "literal": "125.00",
                            },
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_adjacent_equal": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {
                                "meaning": "amount left",
                                "literal": "100.00",
                            },
                            {
                                "meaning": "amount right",
                                "literal": "100.00",
                            },
                            {"meaning": "currency", "literal": "RUB"},
                            {"meaning": "date", "literal": "2026-03-07"},
                            {
                                "meaning": "description",
                                "literal": "Cash balance candidates",
                            },
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_adjacent_fx": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {
                                "meaning": "amount eur",
                                "literal": "200.00",
                            },
                            {
                                "meaning": "amount usd",
                                "literal": "200.00",
                            },
                            {
                                "meaning": "currency eur",
                                "literal": "EUR",
                            },
                            {
                                "meaning": "currency usd",
                                "literal": "USD",
                            },
                            {"meaning": "date", "literal": "2026-03-08"},
                            {
                                "meaning": "description",
                                "literal": "Cash balance candidates",
                            },
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_optional_missing": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {"meaning": "amount", "literal": "71.00"},
                            {"meaning": "currency", "literal": "CNY"},
                            {
                                "meaning": "as of date",
                                "literal": "2026-03-09",
                            },
                            {
                                "meaning": "description",
                                "literal": "Available cash",
                            },
                        ],
                    }
                ],
            }
        ]
    },
    "syn_successor_v2_forbidden_neighbour": {
        "children": [
            {
                "kind": "table",
                "children": [
                    {
                        "kind": "row",
                        "values": [
                            {"meaning": "amount", "literal": "55.00"},
                            {"meaning": "currency", "literal": "JPY"},
                            {"meaning": "date", "literal": "2026-03-10"},
                            {
                                "meaning": "description",
                                "literal": "Selected cash balance",
                            },
                        ],
                    }
                ],
            }
        ]
    },
}

SOURCE_SUMMARY_HASHES = {
    "syn_successor_v2_unique_cash": (
        "17939142da9573c227f1572f0db4880defa792de8222270d7cc5be94874ca0fd"
    ),
    "syn_successor_v2_unique_printed_total": (
        "38e4bea83a81585adb4507f1f824d3c6a62b95ca3dbc1c5a9edb6c5e8289fa9e"
    ),
    "syn_successor_v2_multiple_compatible": (
        "a57db2fce25ac14ed9ce54a615b9706868933ac49f56d1dd7b45d40a0ed0d679"
    ),
    "syn_successor_v2_no_registry_type": (
        "b28d94f13eb34f7ac374ec7d1e35f0705414ca483b446cc6e21259059c276b65"
    ),
    "syn_successor_v2_missing_discriminator": (
        "312cc730517e3cb08bd38b9d9231f0f63f629cd4ab2cb73e4865a7285a8a44de"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "1ace0eee5e8887802488b2f1bb8ffce6b0c6d395f817508dc9c01bdcbf2c5ada"
    ),
    "syn_successor_v2_adjacent_equal": (
        "402dbc93e6e28b41ae36cd0329d66017ee1aef43995a9706ea88477a11feee81"
    ),
    "syn_successor_v2_adjacent_fx": (
        "eacb64962d01edc76b0667844fc59870c125e8a26ea827d860ffa70672f7908c"
    ),
    "syn_successor_v2_optional_missing": (
        "f76aa417a8005a4c1a2204b11354ebc9d969e4ce00b8fb6cbbf2c4d792587507"
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "42f4a085ec9bb1227ddbcd51c19327d2232500aab8f487fd1dc3dc977947ea92"
    ),
}

COMPLETE_OPTIONS = {
    "syn_successor_v2_unique_cash": [
        {"choice_key": "choice_1", "type_key": "type_2"},
        {"choice_key": "choice_2", "type_key": "type_1"},
    ],
    "syn_successor_v2_unique_printed_total": [
        {"choice_key": "choice_1", "type_key": "type_1"},
        {"choice_key": "choice_2", "type_key": "type_2"},
    ],
    "syn_successor_v2_multiple_compatible": [],
    "syn_successor_v2_no_registry_type": [
        {"choice_key": "choice_1", "type_key": "type_2"},
        {"choice_key": "choice_2", "type_key": "type_1"},
    ],
    "syn_successor_v2_missing_discriminator": [
        {"choice_key": "choice_1", "type_key": "type_2"},
        {"choice_key": "choice_2", "type_key": "type_1"},
    ],
    "syn_successor_v2_detail_vs_subtotal": [],
    "syn_successor_v2_adjacent_equal": [],
    "syn_successor_v2_adjacent_fx": [],
    "syn_successor_v2_optional_missing": [
        {"choice_key": "choice_1", "type_key": "type_2"},
        {"choice_key": "choice_2", "type_key": "type_1"},
    ],
    "syn_successor_v2_forbidden_neighbour": [
        {"choice_key": "choice_1", "type_key": "type_2"},
        {"choice_key": "choice_2", "type_key": "type_1"},
    ],
}

EXPECTED_REQUEST_METRICS = {
    "syn_successor_v2_unique_cash": (2444, 675, 2111, 592),
    "syn_successor_v2_unique_printed_total": (2442, 675, 2109, 592),
    "syn_successor_v2_multiple_compatible": (2428, 671, 2208, 616),
    "syn_successor_v2_no_registry_type": (2439, 674, 2106, 591),
    "syn_successor_v2_missing_discriminator": (2383, 660, 2050, 577),
    "syn_successor_v2_detail_vs_subtotal": (2388, 661, 2168, 606),
    "syn_successor_v2_adjacent_equal": (2384, 660, 2164, 605),
    "syn_successor_v2_adjacent_fx": (2428, 671, 2208, 616),
    "syn_successor_v2_optional_missing": (2442, 675, 2109, 592),
    "syn_successor_v2_forbidden_neighbour": (2443, 675, 2110, 592),
}

EXPECTED_REQUEST_HASHES = {
    "syn_successor_v2_unique_cash": (
        "e069b37643006b55102c744222612b836ece3c01c26e3b06851391607a050619",
        "c6252d122143134fe4f00d49fbb400e4f407a4ad2a296b35bb6ab4604b12bec3",
    ),
    "syn_successor_v2_unique_printed_total": (
        "e99a0301e0e1c9551904dfb6557536c4dceb9cadd0f7a8823176c96d623969df",
        "c22194832fa4c03492c6cf49169b97ef43d4b02d0a1029568df8273955e3500a",
    ),
    "syn_successor_v2_multiple_compatible": (
        "ec89ee6471a4d379adc01eaff34c0dee7dda098ef2550c0a3e624f0a1b440a2d",
        "56450d341c011235a3ccb5b235873c1e7af9f30b8ad47c0b8638279134d4e663",
    ),
    "syn_successor_v2_no_registry_type": (
        "3e787fd3b0e95446ad2878d33a4a44b35e4a3946444fde5dfed83193d0f1056a",
        "d1bc8fd89734c68a27cf428448ab00ff3e7631267e96623fb5a3b4eff02b71d2",
    ),
    "syn_successor_v2_missing_discriminator": (
        "e08d989b97dd095a4bf4fd341f6ff7c93c5a028429ec9fd3e13974fdd9ee9f4f",
        "1f797c2ea5048eee42d020a1670f451c32387a39747559f952cbfb7d1ba08ac1",
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "e08f502cdc73462f443bd00768f0250ded6ca2b260d30fbd17fa604c3234b3c1",
        "cfd809548fbcdad500bb960f3d6f5062d9bf3166c9b744c0a95cef217efaf72a",
    ),
    "syn_successor_v2_adjacent_equal": (
        "f3d639086b38766679ebace3b107fc6cd395b32d51fa39b43804766bd47a3dab",
        "88faf64efa00e3b60c9a832f047d8d37f170207571adf7e9091a51d78d613638",
    ),
    "syn_successor_v2_adjacent_fx": (
        "e8e3a171b50d3d0c308dfa66ed4f14c19626caabdb1c421ff7a7a40e17616cbc",
        "3e061822888bf5c117ed11c11800688f48357179292c9742095b526297936a24",
    ),
    "syn_successor_v2_optional_missing": (
        "5d09e2a39f0dd8088297c1125e8d7765b255f25979650c9303608c3ffd32faed",
        "6692c4c172836c152fb09eed07c81605bfbb4708c64f072389697b17295d3cff",
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "89dc149f3b05a716845e85a3397fe36ceda1d3fa6aa51cc12c46c168ddf3a76e",
        "61082b91e89e09289f3ffbd90aa6b140a9c7bf81c96acc054678a79cb3f2a139",
    ),
}

SUCCESSOR_MANIFEST_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
OUTCOME_AUDIT_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6_outcome_audit_v1"
    / "manifest.json"
)
SEMANTIC_PACK_PATH = (
    SERVICE_ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
GOAL8_RECEIPT_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-29"
    / "BROKER_REPORTS_GATE2_NON_ACTIVE_CONTEXT_V2_1_GOAL8.receipt.safe.json"
)
GOAL12_PRECALL_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-29"
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
    ".precall.transparent.json"
)

HISTORICAL_AUTHORITIES = (
    (
        "goal12_precall_plan",
        REPO_ROOT
        / "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".precall.plan.safe.json",
        "2b3a25cd04f0fffc6532477a44b93f6ce78e7e32f76bc239cceb13a2f5abacfe",
    ),
    (
        "goal12_precall_transparent",
        GOAL12_PRECALL_PATH,
        "f64ef2e1daa92cc3eaa204ed34f1e753595ce0d4c7a4fd937492a6c145c58537",
    ),
    (
        "goal12_terminal_receipt",
        REPO_ROOT
        / "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".receipt.safe.json",
        "b4e77203c7fdffd96ad09b4a7ef5364ccef09072c8fc645e38a36a142dfffc8b",
    ),
    (
        "goal12_terminal_report",
        REPO_ROOT
        / "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".report.md",
        "fa5d4e6d5961124e59bcd4204291772476dc7afb6c41ee80b719b658b3d3664b",
    ),
    (
        "goal12_terminal_transparent",
        REPO_ROOT
        / "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".transparent.json",
        "7f4718f13763c9963592326e8481072606219435495fb6fbd59655a881197281",
    ),
    (
        "goal13_forensic_receipt",
        REPO_ROOT
        / "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13"
        ".receipt.safe.json",
        "7c350ce0b24c8e252fc963cf9d9d7c05d3a895c169fb855dcb16afcfc9226735",
    ),
    (
        "goal13_forensic_report",
        REPO_ROOT
        / "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13"
        ".report.md",
        "7161542710ef9c33a45d3c16fb30f10ed97636e1d59d6c2e01bad88083a0379b",
    ),
    (
        "goal14_comparative_receipt",
        REPO_ROOT
        / "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_REVIEW_"
        "GOAL14.receipt.safe.json",
        "360c8b23f713bd3981947de2c222da6e28b001d330809b4c6c1575245a86e63c",
    ),
    (
        "goal14_comparative_report",
        REPO_ROOT
        / "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_REVIEW_"
        "GOAL14.report.md",
        "186eb0f7b9aa40f68bd672b2a9b2680eb029df3ec11a998a039caeec9a5051dd",
    ),
    (
        "goal14_comparative_transparent",
        REPO_ROOT
        / "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_REVIEW_"
        "GOAL14.transparent.json",
        "c4956f26947ccff533ccd094ac734eb8cfdcf96bd9dbc183fe5940c3d165db96",
    ),
)

SOURCE_AUTHORITIES = HISTORICAL_AUTHORITIES + (
    (
        "successor_v2_fixture_manifest",
        SUCCESSOR_MANIFEST_PATH,
        "448a3ea8622a6421c292e5daccef4c5ae65c38a7720a83e1cb8151daa4d2e1aa",
    ),
    (
        "corrected_outcome_audit",
        OUTCOME_AUDIT_PATH,
        "9d99e32d80a38a3621821d0e1918584a82615cca1cf1212e481f5e52811b8249",
    ),
    (
        "unchanged_semantic_pack",
        SEMANTIC_PACK_PATH,
        "ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f",
    ),
    (
        "goal8_candidate_compilation_receipt",
        GOAL8_RECEIPT_PATH,
        "acb60826af9faba23ed9351f41397c3815eb6a8da0a335368bfaff7d2d7f6661",
    ),
    (
        "architecture_authorities",
        REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md",
        "b6fe72328836d795b2b04ddbf3330da2e0a36bd2f023161405957ce205fa0b30",
    ),
    (
        "candidate_compiler_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v6_candidate_compiler.py",
        "c6b5a3baa33aae2ff0f39bd7d82e414bcb67a61a04e26d02dff824bf0fba936a",
    ),
    (
        "packet_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v6_packet.py",
        "175c450dbbd5ef3912bd160fa390cb85e1821f68321831ad8b58430c26d13e0e",
    ),
    (
        "semantic_instruction_prompt_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v6_prompt.py",
        "a6334ae2dd7e0f417e8ad629dbec9423ccc297b8fe20acac119d6b2caadfb8fc",
    ),
    (
        "request_builder_and_estimator_owner",
        SERVICE_ROOT / "broker_reports_gate1/gate2_model_requests.py",
        "70142660c31adf2b595ee81aedf54afd35568eaed1713f5e5085f38d67725a73",
    ),
    (
        "economy_accounting_owner",
        SERVICE_ROOT / "broker_reports_gate1/gate2_economy_budget.py",
        "46efe45c2fd507e0e8e5efe729eec298aeade5cb2cf3d9b989316d077bdae942",
    ),
    (
        "economy_policy_owner",
        SERVICE_ROOT / "broker_reports_gate1/gate2_economy_model_policy.py",
        "69a3835f690e441e3f3888e523521aea7eccf208ead9c2e074607620bc880d27",
    ),
    (
        "production_orchestration_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_evidence_production_runtime.py",
        "b92537a5fbfe9ad0ff35fdbbb6812a97905b62a041ccea89705a712c1f3c24ec",
    ),
    (
        "choice_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v6_choice.py",
        "e47e754f33032460edfd6ea25377bd2eeb75c181b307c64440965ab1e409d4d5",
    ),
    (
        "context_linter_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v6_context_linter.py",
        "99145aa603e1e42a7a9036a3d77e2cceedb82510734d25f0c1763c2933a875aa",
    ),
    (
        "provider_adapter_owner",
        SERVICE_ROOT / "broker_reports_gate1/gate2_provider_adapters.py",
        "3e7cae769d023ef81cc052519507eceeeb3e5988abd7ed93194f4a8f5b36e2ac",
    ),
    (
        "expansion_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v6_expansion.py",
        "d1b7856d7c3b08012f154778a05e76bb139e43078266151ae5cda69e7aa21e5c",
    ),
    (
        "validation_and_materialization_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_evidence_materialization.py",
        "bcadcf529bdade058b2facb6ee5bce1b1a57cae69f06a113f73a727dbd3e33ba",
    ),
    (
        "decision_evidence_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v6_evidence.py",
        "a7f33a47fff6622e8d03c2311003cd7ff92fa1da564d6596bcaf1de64abae1ed",
    ),
    (
        "semantic_pack_projection_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v5_projection.py",
        "a248cd93c3634b4d19b4da3c06e151c6e339e6e9ab33c6a69c4e2c0e1618deb7",
    ),
    (
        "totality_owner",
        SERVICE_ROOT
        / "broker_reports_gate1/gate2_financial_semantic_v6_totality.py",
        "0149f27d638501c3f468c70e68985f77da9886396e54bde95353cd2cb578d2a3",
    ),
)

AUTHORITY_MATRIX = (
    {
        "concern": "Packet construction / semantic instruction",
        "existing_owner": (
            "Gate2FinancialSemanticV6PacketFactory.create + "
            "financial_semantic_v6_prompt"
        ),
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_packet.py:107,4765,5065; "
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_prompt.py:13,32"
        ),
        "changes": {
            VARIANT_IDS[0]: "additive_profile",
            VARIANT_IDS[1]: "additive_profile",
            VARIANT_IDS[2]: "additive_profile",
        },
    },
    {
        "concern": "Semantic Pack/type projection",
        "existing_owner": "Gate2FinancialSemanticV5ProjectionFactory",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v5_projection.py:126,199"
        ),
        "changes": {
            VARIANT_IDS[0]: "unchanged",
            VARIANT_IDS[1]: "unchanged",
            VARIANT_IDS[2]: "unchanged",
        },
    },
    {
        "concern": "Candidate Compilation",
        "existing_owner": "Gate2FinancialCandidateCompilerFactory.create",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_candidate_compiler.py:42,130,271"
        ),
        "changes": {
            VARIANT_IDS[0]: "unchanged",
            VARIANT_IDS[1]: "unchanged",
            VARIANT_IDS[2]: "unchanged",
        },
    },
    {
        "concern": "Choice contract",
        "existing_owner": "Gate2FinancialSemanticV6ChoiceContractFactory.create",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_choice.py:80,249,531"
        ),
        "changes": {
            VARIANT_IDS[0]: "additive_profile",
            VARIANT_IDS[1]: "additive_profile",
            VARIANT_IDS[2]: "additive_profile",
        },
    },
    {
        "concern": "Context Linter",
        "existing_owner": "Gate2FinancialSemanticV6ContextLinterFactory",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_context_linter.py:82,362,596"
        ),
        "changes": {
            VARIANT_IDS[0]: "additive_profile",
            VARIANT_IDS[1]: "additive_profile",
            VARIANT_IDS[2]: "additive_profile",
        },
    },
    {
        "concern": "request builder",
        "existing_owner": "Gate2OpenWebUIRequestBuilder",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_model_requests.py:210,227,358"
        ),
        "changes": {
            VARIANT_IDS[0]: "additive_profile",
            VARIANT_IDS[1]: "additive_profile",
            VARIANT_IDS[2]: "additive_profile",
        },
    },
    {
        "concern": "provider adapters",
        "existing_owner": "Gate2ProviderAdapterFactory.create",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_provider_adapters.py:39,547,908"
        ),
        "changes": {
            VARIANT_IDS[0]: "unchanged",
            VARIANT_IDS[1]: "unchanged",
            VARIANT_IDS[2]: "unchanged",
        },
    },
    {
        "concern": "expansion",
        "existing_owner": "Gate2FinancialSemanticV6DecisionExpansionFactory",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_expansion.py:54,120,219"
        ),
        "changes": {
            VARIANT_IDS[0]: "behavior_change_later_required",
            VARIANT_IDS[1]: "behavior_change_later_required",
            VARIANT_IDS[2]: "behavior_change_later_required",
        },
    },
    {
        "concern": "validation",
        "existing_owner": "Gate2FinancialEvidenceValidatedDecisionFactory.create",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_evidence_materialization.py:89"
        ),
        "changes": {
            VARIANT_IDS[0]: "unchanged",
            VARIANT_IDS[1]: "unchanged",
            VARIANT_IDS[2]: "unchanged",
        },
    },
    {
        "concern": "materialization",
        "existing_owner": "Gate2FinancialEvidenceMaterializerFactory.create",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_evidence_materialization.py:145"
        ),
        "changes": {
            VARIANT_IDS[0]: "unchanged",
            VARIANT_IDS[1]: "unchanged",
            VARIANT_IDS[2]: "unchanged",
        },
    },
    {
        "concern": "persistence/replay",
        "existing_owner": "Gate2FinancialSemanticV6DecisionEvidenceFactory",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_evidence.py:115,450,1156"
        ),
        "changes": {
            VARIANT_IDS[0]: "additive_profile",
            VARIANT_IDS[1]: "additive_profile",
            VARIANT_IDS[2]: "additive_profile",
        },
    },
    {
        "concern": "operation/economy accounting",
        "existing_owner": "Gate2EconomyBudgetSessionFactory",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_economy_budget.py:44,131,305"
        ),
        "changes": {
            VARIANT_IDS[0]: "additive_profile",
            VARIANT_IDS[1]: "additive_profile",
            VARIANT_IDS[2]: "behavior_change_later_required",
        },
    },
)

COMPARISON_CRITERIA = (
    ("Domain safety", 3, 3, 4, 4),
    ("typed accuracy potential", 2, 4, 3, 5),
    ("under-typing risk", 2, 4, 2, 5),
    ("separation of semantic and code responsibilities", 3, 2, 5, 5),
    ("influence of constructible choices on type judgment", 3, 1, 5, 5),
    ("observability of model decision", 1, 5, 4, 5),
    ("deterministic reason derivation", 2, 4, 5, 5),
    ("request size", 1, 3, 5, 4),
    ("expected token cost", 1, 4, 5, 3),
    ("latency", 1, 5, 5, 3),
    ("number of provider calls", 1, 5, 5, 3),
    ("implementation complexity", 1, 3, 5, 2),
    ("test complexity", 1, 3, 5, 2),
    ("persistence/replay complexity", 1, 4, 5, 2),
    ("provider portability", 1, 4, 5, 4),
    ("rollback simplicity", 1, 4, 5, 3),
    ("compatibility with current two-type Pack", 1, 5, 5, 5),
    ("scaling to larger managed ontology", 2, 2, 3, 3),
    ("compatibility with future type shortlisting", 2, 2, 5, 5),
    ("usefulness for MVP", 2, 3, 5, 3),
)

UNRESOLVED_ASSUMPTIONS = (
    {
        "id": "type_first_contract_unqualified",
        "question": (
            "Will an eligible model reproduce the audited plausible-type sets "
            "under the proposed type-first prompt and schema?"
        ),
        "missing_evidence": "No live or offline model qualification of this contract.",
    },
    {
        "id": "false_singleton_risk",
        "question": (
            "How often can a false singleton type judgment combine with one "
            "complete matching option and yield unsafe typed output?"
        ),
        "missing_evidence": "No accepted-corpus error-rate evidence.",
    },
    {
        "id": "synthetic_two_type_scope",
        "question": (
            "Do the conclusions generalize beyond synthetic fixtures and the "
            "current two-type managed Pack?"
        ),
        "missing_evidence": "No representative accepted-corpus generalization proof.",
    },
    {
        "id": "same_type_multi_option_frequency",
        "question": (
            "Does singleton-type/multiple-complete-option state occur often "
            "enough to justify Stage 2?"
        ),
        "missing_evidence": "No governed fixture or frequency evidence.",
    },
    {
        "id": "stage2_safety_and_value",
        "question": (
            "Can a bounded Stage 2 select the right same-type record with a "
            "safe net completeness gain?"
        ),
        "missing_evidence": "No Stage 2 qualification or outcome evidence.",
    },
    {
        "id": "larger_ontology_behavior",
        "question": (
            "When does a larger ontology require deterministic type "
            "shortlisting before the model?"
        ),
        "missing_evidence": "No larger managed ontology benchmark.",
    },
    {
        "id": "future_product_entrypoint",
        "question": (
            "Which versioned inactive profile and policy change will be "
            "authorized inside the existing production orchestration owner?"
        ),
        "missing_evidence": "No implementation authorization or two-call policy.",
    },
)

THOUGHT_SOURCE = {
    "children": [
        {
            "kind": "table",
            "children": [
                {
                    "kind": "row",
                    "values": [
                        {"meaning": "amount", "literal": "100.00"},
                        {"meaning": "currency", "literal": "USD"},
                        {"meaning": "as of date", "literal": "2026-03-31"},
                        {"meaning": "description", "literal": "Cash balance"},
                    ],
                },
                {
                    "kind": "row",
                    "values": [
                        {"meaning": "amount", "literal": "90.00"},
                        {"meaning": "currency", "literal": "USD"},
                        {"meaning": "as of date", "literal": "2025-12-31"},
                        {
                            "meaning": "description",
                            "literal": "Cash balance comparative",
                        },
                    ],
                },
            ],
        }
    ]
}
THOUGHT_OPTIONS = [
    {"choice_key": "choice_1", "type_key": "type_1"},
    {"choice_key": "choice_2", "type_key": "type_1"},
]
THOUGHT_DIFFERENTIATORS = [
    {
        "choice_key": "choice_1",
        "values": [
            {"meaning": "as of date", "literal": "2026-03-31"},
            {"meaning": "description", "literal": "Cash balance"},
        ],
    },
    {
        "choice_key": "choice_2",
        "values": [
            {"meaning": "as of date", "literal": "2025-12-31"},
            {
                "meaning": "description",
                "literal": "Cash balance comparative",
            },
        ],
    },
]

_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "credential",
        "customer_data",
        "filesystem_path",
        "hidden_reasoning",
        "managed_to_local_type_mapping",
        "private_ref",
        "provider_envelope",
        "raw_provider_envelope",
        "secret",
    }
)
_LOCAL_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/](?:Users|Documents|Desktop)[\\/]|"
    r"/(?:home|Users|private|tmp)/)"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)

    report, transparent, receipt = build_artifacts()
    outputs = {
        REPORT_PATH: report.encode("utf-8"),
        TRANSPARENT_PATH: _json_bytes(transparent),
        RECEIPT_PATH: _json_bytes(receipt),
    }
    write_or_check_outputs(outputs=outputs, check=arguments.check)
    print(
        _compact_json(
            {
                "status": "passed",
                "mode": "check" if arguments.check else "write",
                "variants_total": len(transparent["variants"]),
                "detailed_cases_total": len(transparent["detailed_case_ids"]),
                "governed_cases_total": len(
                    transparent["per_case_simulations"]
                ),
                "provider_calls_total": 0,
                "runtime_changes_total": 0,
                "product_logic_changes_total": 0,
                "historical_files_modified_total": 0,
                "recommendation_id": RECOMMENDATION_ID,
            }
        )
    )
    return 0


def build_artifacts() -> tuple[str, dict[str, Any], dict[str, Any]]:
    evidence_hashes = _validate_source_authorities()
    successor = _read_json(SUCCESSOR_MANIFEST_PATH)
    audit = _read_json(OUTCOME_AUDIT_PATH)
    semantic_pack = _read_json(SEMANTIC_PACK_PATH)
    goal8_receipt = _read_json(GOAL8_RECEIPT_PATH)
    goal12_precall = _read_json(GOAL12_PRECALL_PATH)

    _validate_embedded_integrity(audit, "integrity_sha256")
    _validate_embedded_integrity(semantic_pack, "integrity_sha256")
    _validate_embedded_integrity(goal8_receipt, "integrity_sha256")
    _validate_embedded_integrity(goal12_precall, "integrity_sha256")

    type_cards = _load_exact_type_cards(goal12_precall)
    _validate_frozen_inputs(
        successor=successor,
        audit=audit,
        goal8_receipt=goal8_receipt,
        type_cards=type_cards,
    )

    audit_by_case = {item["case_id"]: item for item in audit["cases"]}
    simulations = [
        _build_case_simulation(
            case_id=case_id,
            audit_case=audit_by_case[case_id],
            type_cards=type_cards,
        )
        for case_id in CASE_ORDER
    ]
    variants = _build_variants(simulations=simulations, type_cards=type_cards)
    same_type_scenario = _build_same_type_scenario(type_cards=type_cards)
    budget = _build_budget(
        simulations=simulations,
        same_type_scenario=same_type_scenario,
    )
    comparison = _build_comparison()

    transparent_material = {
        "schema_version": (
            "broker_reports_gate2_type_first_semantic_decision_"
            "architecture_audit_v1"
        ),
        "goal_identity": GOAL_ID,
        "status": "completed_offline_architecture_audit",
        "base_commit": BASE_COMMIT,
        "active": False,
        "synthetic_evidence_only": True,
        "analysis_boundary": {
            "documentation_only": True,
            "provider_neutral_logical_contracts_only": True,
            "implementation_authorized": False,
            "runtime_activation": False,
            "production_approval": False,
        },
        "variants": variants,
        "detailed_case_ids": list(DETAILED_CASE_IDS),
        "per_case_simulations": simulations,
        "same_type_multiple_option_scenario": same_type_scenario,
        "authority_change_surface": {
            "rows": [
                {
                    **copy.deepcopy(row),
                    "new_owner_required": {
                        variant_id: False for variant_id in VARIANT_IDS
                    },
                }
                for row in AUTHORITY_MATRIX
            ],
            "new_owner_required_total": 0,
            "orchestration_boundary": (
                "Any future sequencing remains inside "
                "Gate2FinancialEvidenceProductionRuntime._decide through its "
                "existing factory; no parallel runtime route."
            ),
            "stage2_failure_boundary": (
                "A technical Stage 2 failure aborts before ArtifactStore writes; "
                "submitted calls remain accounted and are not rolled back."
            ),
        },
        "byte_and_call_budget": budget,
        "comparison": comparison,
        "recommendation": {
            "recommendation_id": RECOMMENDATION_ID,
            "confidence": CONFIDENCE,
            "why_selected": [
                (
                    "It hides constructible choices during type judgment and "
                    "keeps the model decision observable as a plausible-type set."
                ),
                (
                    "It reproduces all ten corrected routes with one planned "
                    "call per fixture and deterministic code-owned reasons."
                ),
                (
                    "It reserves Stage 2 only for accepted evidence that "
                    "same-type record selection materially improves completeness."
                ),
            ],
            "why_not_variant_a": (
                "Variant A keeps constructible choices in the type judgment and "
                "couples type and record decisions; GOAL 14 supports this as an "
                "unresolved risk, not a proven causal defect."
            ),
            "why_not_variant_c_now": (
                "No governed fixture triggers Stage 2, so C adds no demonstrated "
                "completeness while adding two-call policy, latency, replay and "
                "failure-accounting surface."
            ),
            "remaining_risks": [
                item["id"] for item in UNRESOLVED_ASSUMPTIONS
            ],
            "evidence_present": [
                "ten corrected audited plausible-type sets",
                "exact complete-option counts by local type",
                "zero same-type multiple-option governed fixtures",
                "deterministic request byte/call accounting",
                "existing-owner authority map",
            ],
            "evidence_missing": [
                item["missing_evidence"] for item in UNRESOLVED_ASSUMPTIONS
            ],
        },
        "unresolved_assumptions": [
            copy.deepcopy(item) for item in UNRESOLVED_ASSUMPTIONS
        ],
        "evidence_hashes": [
            {
                "identity": identity,
                "repository_lf_sha256": evidence_hashes[identity],
            }
            for identity, _path, _expected in SOURCE_AUTHORITIES
        ],
        "execution_accounting": {
            "provider_calls_total": 0,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        },
        "change_accounting": {
            "runtime_changes_total": 0,
            "product_logic_changes_total": 0,
            "prompt_changes_total": 0,
            "context_changes_total": 0,
            "choice_changes_total": 0,
            "pack_changes_total": 0,
            "historical_files_modified_total": 0,
            "runtime_activation_total": 0,
            "new_architecture_owner_total": 0,
        },
    }
    transparent = _with_integrity(transparent_material)
    _validate_repository_safe_output(transparent)
    report = _render_report(transparent)

    receipt_material = {
        "schema_version": (
            "broker_reports_gate2_type_first_semantic_decision_"
            "architecture_audit_receipt_v1"
        ),
        "goal_identity": GOAL_ID,
        "base_commit": BASE_COMMIT,
        "variant_ids": list(VARIANT_IDS),
        "cases_simulated": list(CASE_ORDER),
        "detailed_cases_simulated": list(DETAILED_CASE_IDS),
        "provider_calls_total": 0,
        "runtime_changes_total": 0,
        "product_logic_changes_total": 0,
        "historical_files_modified_total": 0,
        "recommendation_id": RECOMMENDATION_ID,
        "confidence": CONFIDENCE,
        "unresolved_assumptions_count": len(UNRESOLVED_ASSUMPTIONS),
        "report_file_sha256": _sha256_bytes(report.encode("utf-8")),
        "transparent_file_sha256": _sha256_bytes(_json_bytes(transparent)),
    }
    receipt = _with_integrity(receipt_material)
    _validate_repository_safe_output(receipt)
    return report, transparent, receipt


def _load_exact_type_cards(goal12_precall: dict[str, Any]) -> list[dict[str, Any]]:
    observed: list[list[dict[str, Any]]] = []
    for slot in goal12_precall.get("slots", []):
        messages = slot["exact_model_visible_request"]["messages"]
        if len(messages) != 2:
            raise ValueError("goal12_message_count_invalid")
        payload = json.loads(messages[1]["content"])
        observed.append(payload["type_cards"])
    if not observed or any(item != observed[0] for item in observed[1:]):
        raise ValueError("goal12_type_cards_not_stable")
    cards = copy.deepcopy(observed[0])
    if _sha256_json(cards) != (
        "f0b25addd4fdf26e6bbd96e734d3f2406d8809bbad7df30cad46b6dbfaa8e133"
    ):
        raise ValueError("goal12_type_cards_hash_invalid")
    if len(_canonical_json_bytes(cards)) != 1298:
        raise ValueError("goal12_type_cards_bytes_invalid")
    return cards


def _validate_frozen_inputs(
    *,
    successor: dict[str, Any],
    audit: dict[str, Any],
    goal8_receipt: dict[str, Any],
    type_cards: list[dict[str, Any]],
) -> None:
    if [item["type_key"] for item in type_cards] != ["type_1", "type_2"]:
        raise ValueError("local_type_card_order_invalid")

    fixture_by_case = {item["case_id"]: item for item in successor["cases"]}
    audit_semantic = [
        item
        for item in audit["cases"]
        if item["expected_route"] == "semantic_model"
    ]
    if [item["case_id"] for item in audit_semantic] != list(CASE_ORDER):
        raise ValueError("governed_case_set_invalid")
    excluded = [
        item["case_id"]
        for item in audit["cases"]
        if item["expected_route"] != "semantic_model"
    ]
    if excluded != [
        "syn_successor_v2_repeated_header",
        "syn_successor_v2_unsupported_shape",
    ]:
        raise ValueError("technical_preclose_case_set_invalid")

    goal8_by_case = {
        item["case_id"]: item for item in goal8_receipt["case_receipts"]
    }
    for audit_case in audit_semantic:
        case_id = audit_case["case_id"]
        plausible = PLAUSIBLE_LOCAL_TYPES[case_id]
        options = COMPLETE_OPTIONS[case_id]
        source = SOURCE_SUMMARIES[case_id]
        if len(plausible) != len(audit_case["plausible_type_ids"]):
            raise ValueError(f"plausible_type_count_invalid:{case_id}")
        if len(options) != audit_case["expected_typed_options"]:
            raise ValueError(f"candidate_option_count_invalid:{case_id}")
        if len(options) != goal8_by_case[case_id]["choices"]:
            raise ValueError(f"goal8_choice_count_invalid:{case_id}")
        if set(plausible) - {"type_1", "type_2"}:
            raise ValueError(f"unknown_local_plausible_type:{case_id}")
        if any(
            item["type_key"] not in {"type_1", "type_2"}
            for item in options
        ):
            raise ValueError(f"unknown_local_option_type:{case_id}")
        if _sha256_json(source) != SOURCE_SUMMARY_HASHES[case_id]:
            raise ValueError(f"source_summary_hash_invalid:{case_id}")

        fixture_literals = sorted(
            item["literal"] for item in fixture_by_case[case_id]["cells"]
        )
        source_literals = sorted(
            item["literal"]
            for table in source["children"]
            for row in table["children"]
            for item in row["values"]
        )
        if source_literals != fixture_literals:
            raise ValueError(f"source_fixture_literal_parity_invalid:{case_id}")


def _plausible_types_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "string",
            "enum": ["type_1", "type_2"],
        },
        "uniqueItems": True,
        "maxItems": 2,
    }


def _stage1_response_schema(
    *, include_choice: bool, choice_keys: list[str]
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "plausible_types": _plausible_types_schema(),
    }
    required = ["plausible_types"]
    if include_choice:
        properties["selected_choice"] = {"enum": [None, *choice_keys]}
        required.append("selected_choice")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _type_first_request(
    *,
    source_summary: dict[str, Any],
    type_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "response_schema": _stage1_response_schema(
            include_choice=False,
            choice_keys=[],
        ),
        "user_context": {
            "task": TYPE_FIRST_STAGE1_INSTRUCTION,
            "source_summary": copy.deepcopy(source_summary),
            "plausible_type_cards": copy.deepcopy(type_cards),
        },
    }


def _build_stage1_request(
    *,
    variant_id: str,
    case_id: str,
    type_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    if variant_id in (VARIANT_IDS[1], VARIANT_IDS[2]):
        return _type_first_request(
            source_summary=SOURCE_SUMMARIES[case_id],
            type_cards=type_cards,
        )
    if variant_id != VARIANT_IDS[0]:
        raise ValueError(f"unknown_variant:{variant_id}")
    options = COMPLETE_OPTIONS[case_id]
    return {
        "response_schema": _stage1_response_schema(
            include_choice=True,
            choice_keys=[item["choice_key"] for item in options],
        ),
        "user_context": {
            "task": VARIANT_A_STAGE1_INSTRUCTION,
            "source_summary": copy.deepcopy(SOURCE_SUMMARIES[case_id]),
            "plausible_type_cards": copy.deepcopy(type_cards),
            "complete_options": copy.deepcopy(options),
            "differentiators": [],
        },
    }


def _build_stage2_request(
    *, type_cards: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "response_schema": {
            "type": "object",
            "properties": {
                "selected_choice": {
                    "enum": [None, "choice_1", "choice_2"],
                }
            },
            "required": ["selected_choice"],
            "additionalProperties": False,
        },
        "user_context": {
            "task": STAGE2_INSTRUCTION,
            "source_summary": copy.deepcopy(THOUGHT_SOURCE),
            "selected_type_card": copy.deepcopy(type_cards[0]),
            "complete_options": copy.deepcopy(THOUGHT_OPTIONS),
            "differentiators": copy.deepcopy(THOUGHT_DIFFERENTIATORS),
        },
    }


def _request_metrics(request: dict[str, Any]) -> dict[str, Any]:
    payload = _canonical_json_bytes(request)
    return {
        "canonicalization": (
            "minified_json_utf8_ensure_ascii_false_sort_keys_true"
        ),
        "request_utf8_bytes": len(payload),
        "estimated_input_tokens": max(
            1,
            (len(payload) + 3) // 4 + TOKEN_ESTIMATOR_OVERHEAD,
        ),
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "request_sha256": _sha256_bytes(payload),
    }


def _option_counts(options: list[dict[str, str]]) -> dict[str, int]:
    return {
        type_key: sum(
            item["type_key"] == type_key for item in options
        )
        for type_key in ("type_1", "type_2")
    }


def _matching_options(
    *, plausible_types: list[str], options: list[dict[str, str]]
) -> list[dict[str, str]]:
    if len(plausible_types) != 1:
        return []
    return [
        copy.deepcopy(item)
        for item in options
        if item["type_key"] == plausible_types[0]
    ]


def _derive_final(
    *,
    variant_id: str,
    plausible_types: list[str],
    options: list[dict[str, str]],
) -> tuple[str, str, dict[str, str] | None, bool]:
    if not plausible_types:
        return (
            "unclassified_financial_input",
            "no_registry_type",
            None,
            False,
        )
    if len(plausible_types) >= 2:
        return (
            "unclassified_financial_input",
            "ambiguous_registry_type",
            None,
            False,
        )
    matching = _matching_options(
        plausible_types=plausible_types,
        options=options,
    )
    if len(matching) == 1:
        return "typed_input", "typed_supported", matching[0], False
    if len(matching) > 1 and variant_id == VARIANT_IDS[2]:
        return "typed_input", "typed_supported", matching[0], True
    if len(matching) > 1 and variant_id == VARIANT_IDS[0]:
        return "typed_input", "typed_supported", matching[0], False
    return (
        "unclassified_financial_input",
        "single_registry_type_no_safe_record",
        None,
        False,
    )


def _route_label(
    *,
    variant_id: str,
    disposition: str,
    reason_code: str,
    stage2_required: bool,
) -> str:
    if stage2_required:
        return "type_first_then_stage2_record_selection"
    if disposition == "typed_input":
        if variant_id == VARIANT_IDS[0]:
            return "one_call_joint_type_and_choice"
        return "type_first_auto_accept_single_matching_option"
    return f"fail_closed_{reason_code}"


def _code_decision_text(
    *,
    variant_id: str,
    plausible_types: list[str],
    matching_count: int,
) -> str:
    if len(plausible_types) == 0:
        return "Derive no_registry_type from distinct plausible count 0."
    if len(plausible_types) >= 2:
        return (
            "Derive ambiguous_registry_type from distinct plausible count 2+."
        )
    if matching_count == 0:
        return (
            "Filter Compiler options to the singleton type; zero remain, so "
            "derive single_registry_type_no_safe_record."
        )
    if matching_count == 1:
        return (
            "Filter to one complete matching option, restore the exact "
            "code-owned Typed Option, validate and materialize."
        )
    if variant_id == VARIANT_IDS[2]:
        return (
            "Filter to multiple same-type options and invoke bounded Stage 2; "
            "null maps to single_registry_type_no_safe_record."
        )
    if variant_id == VARIANT_IDS[1]:
        return (
            "Filter to multiple same-type options and fail closed with "
            "single_registry_type_no_safe_record."
        )
    return (
        "Cross-check the selected local choice against the singleton plausible "
        "type, then restore only an exact code-owned option."
    )


def _failure_modes(variant_id: str) -> list[str]:
    common = [
        (
            "A false singleton type judgment plus one matching complete option "
            "can still produce semantically wrong typed output."
        ),
        "Invalid schema/type keys fail as technical response errors; no repair.",
    ]
    if variant_id == VARIANT_IDS[0]:
        return [
            (
                "Visible constructible choices may anchor or distort the "
                "plausible-type cardinality judgment."
            ),
            (
                "A selected choice inconsistent with the singleton type fails "
                "technically and is not converted into a semantic reason."
            ),
            *common,
        ]
    if variant_id == VARIANT_IDS[1]:
        return [
            (
                "A true singleton type with multiple safe options is "
                "deliberately under-typed."
            ),
            *common,
        ]
    return [
        (
            "A future same-type Stage 2 can choose the wrong record even though it "
            "cannot change the financial type."
        ),
        (
            "A Stage 2 transport/schema/usage failure aborts the operation; "
            "already submitted calls remain accounted."
        ),
        *common,
    ]


def _build_case_simulation(
    *,
    case_id: str,
    audit_case: dict[str, Any],
    type_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    plausible_types = copy.deepcopy(PLAUSIBLE_LOCAL_TYPES[case_id])
    options = copy.deepcopy(COMPLETE_OPTIONS[case_id])
    counts = _option_counts(options)
    variant_results: list[dict[str, Any]] = []

    for variant_id in VARIANT_IDS:
        request = _build_stage1_request(
            variant_id=variant_id,
            case_id=case_id,
            type_cards=type_cards,
        )
        metrics = _request_metrics(request)
        metric_index = 0 if variant_id == VARIANT_IDS[0] else 2
        expected = EXPECTED_REQUEST_METRICS[case_id]
        expected_hash = EXPECTED_REQUEST_HASHES[case_id][
            0 if variant_id == VARIANT_IDS[0] else 1
        ]
        if (
            metrics["request_utf8_bytes"] != expected[metric_index]
            or metrics["estimated_input_tokens"]
            != expected[metric_index + 1]
            or metrics["request_sha256"] != expected_hash
        ):
            raise ValueError(
                f"logical_request_metric_drift:{case_id}:{variant_id}"
            )

        matching = _matching_options(
            plausible_types=plausible_types,
            options=options,
        )
        disposition, reason_code, selected, stage2_required = _derive_final(
            variant_id=variant_id,
            plausible_types=plausible_types,
            options=options,
        )
        if stage2_required:
            raise ValueError(f"unexpected_governed_stage2:{case_id}")
        if (
            disposition != audit_case["expected_disposition"]
            or reason_code != audit_case["expected_reason_code"]
        ):
            raise ValueError(
                f"mechanical_expected_answer_mismatch:{case_id}:{variant_id}"
            )

        response: dict[str, Any] = {
            "plausible_types": copy.deepcopy(plausible_types)
        }
        if variant_id == VARIANT_IDS[0]:
            response["selected_choice"] = (
                selected["choice_key"] if selected is not None else None
            )
        final_value: dict[str, Any]
        if selected is None:
            final_value = {"reason_code": reason_code}
        else:
            final_value = {
                "typed_option": {
                    "choice_key": selected["choice_key"],
                    "local_type_key": selected["type_key"],
                    "restoration": "exact_code_owned_typed_option",
                }
            }
        assumptions = [
            "proposed_stage1_returns_frozen_audited_plausible_set"
        ]
        if variant_id == VARIANT_IDS[0]:
            assumptions.append(
                "visible_choices_do_not_distort_type_cardinality"
            )
            if selected is not None:
                assumptions.append(
                    "joint_response_selects_the_semantically_correct_option"
                )

        variant_results.append(
            {
                "variant_id": variant_id,
                "llm_visible_fields": list(request["user_context"]),
                "stage1_request": request,
                "stage1_request_metrics": metrics,
                "stage1_response": response,
                "code_decision": _code_decision_text(
                    variant_id=variant_id,
                    plausible_types=plausible_types,
                    matching_count=len(matching),
                ),
                "stage2_required": False,
                "stage2_request": None,
                "stage2_response": None,
                "route": _route_label(
                    variant_id=variant_id,
                    disposition=disposition,
                    reason_code=reason_code,
                    stage2_required=False,
                ),
                "final_canonical_disposition": disposition,
                "final_reason_or_typed_option": final_value,
                "llm_call_count": 1,
                "possible_completeness_loss": (
                    "none_observed_in_governed_fixture"
                ),
                "unproven_semantic_assumptions": assumptions,
                "possible_failure_modes": _failure_modes(variant_id),
            }
        )

    return {
        "case_id": case_id,
        "expected_semantic_state": audit_case["taxonomy_state"],
        "exact_source_summary": copy.deepcopy(SOURCE_SUMMARIES[case_id]),
        "exact_source_summary_sha256": SOURCE_SUMMARY_HASHES[case_id],
        "audited_plausible_types": plausible_types,
        "plausible_type_count": len(plausible_types),
        "complete_options": options,
        "available_complete_option_counts_by_type": counts,
        "expected_final_answer": {
            "disposition": audit_case["expected_disposition"],
            "reason_code": audit_case["expected_reason_code"],
        },
        "semantic_audit_status": "authority_pinned",
        "variant_results": variant_results,
    }


def _canonical_backend_transformation(variant_id: str) -> dict[str, Any]:
    common_tail = [
        "restore_exact_code_owned_typed_option",
        "run_existing_validation_and_materialization",
        "persist_only_after_terminal_evidence_is_complete",
    ]
    if variant_id == VARIANT_IDS[0]:
        return {
            "steps": [
                "validate_ordered_unique_local_type_keys",
                "derive_reason_from_distinct_plausible_type_count",
                "validate_selected_choice_membership_and_singleton_type_match",
                *common_tail,
            ],
            "contradiction_policy": "technical_failure_without_repair",
        }
    if variant_id == VARIANT_IDS[1]:
        return {
            "steps": [
                "validate_ordered_unique_local_type_keys",
                "derive_reason_from_distinct_plausible_type_count",
                "filter_complete_options_to_singleton_type",
                "accept_only_when_matching_option_count_equals_one",
                *common_tail,
            ],
            "same_type_multiple_option_policy": (
                "single_registry_type_no_safe_record"
            ),
        }
    return {
        "steps": [
            "validate_ordered_unique_local_type_keys",
            "derive_reason_from_distinct_plausible_type_count",
            "filter_complete_options_to_singleton_type",
            "skip_stage2_for_zero_or_one_matching_option",
            "invoke_stage2_only_for_two_or_more_matching_options",
            "validate_stage2_choice_against_fixed_type_option_set",
            *common_tail,
        ],
        "stage2_null_policy": "single_registry_type_no_safe_record",
        "technical_failure_policy": "abort_without_semantic_relabeling",
    }


def _build_variants(
    *,
    simulations: list[dict[str, Any]],
    type_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    representative = next(
        item
        for item in simulations
        if item["case_id"] == "syn_successor_v2_unique_cash"
    )
    representative_by_variant = {
        item["variant_id"]: item for item in representative["variant_results"]
    }
    definitions = {
        VARIANT_IDS[0]: {
            "llm_responsibility": [
                "return every plausible visible type key",
                (
                    "select one local complete option only when one plausible "
                    "type and one uniquely supported record remain"
                ),
            ],
            "code_responsibility": [
                "validate local type and choice keys",
                "cross-check selected option type against singleton type",
                "derive canonical reason from type cardinality",
                "restore, validate and materialize exact code-owned option",
            ],
            "strengths": [
                "one call",
                "observable type set and record selection",
                "can resolve a same-type multiple-option state",
            ],
            "limitations": [
                "constructible choices remain visible during type judgment",
                "type and record decisions remain coupled",
                "larger option sets increase request surface",
            ],
        },
        VARIANT_IDS[1]: {
            "llm_responsibility": [
                "return every plausible visible type key only",
            ],
            "code_responsibility": [
                "derive reason from type cardinality",
                "filter complete options to the singleton type",
                "accept only exactly one matching option",
                "fail closed for zero or multiple matching options",
            ],
            "strengths": [
                "cleanest separation between meaning and construction",
                "one call and smallest governed request",
                "simple replay, accounting and rollback boundary",
            ],
            "limitations": [
                (
                    "deliberately under-types singleton-type cases with multiple "
                    "complete options"
                ),
                "false singleton risk remains",
            ],
        },
        VARIANT_IDS[2]: {
            "llm_responsibility": [
                "Stage 1 returns plausible type keys only",
                (
                    "Stage 2 selects among complete options of one already-fixed "
                    "type or returns null"
                ),
            ],
            "code_responsibility": [
                "derive Stage 1 route and filter options",
                "invoke Stage 2 only for two or more same-type options",
                "bind both stages to one operation and replay ledger",
                "restore and validate one exact option",
            ],
            "strengths": [
                "preserves type-first separation",
                "can recover completeness in same-type multiple-option state",
                "Stage 2 cannot reclassify the financial type",
            ],
            "limitations": [
                "zero Stage 2 triggers in the ten governed fixtures",
                "requires future two-call policy and multi-stage replay profile",
                "adds latency and a record-level model error surface",
            ],
        },
    }

    variants: list[dict[str, Any]] = []
    for variant_id in VARIANT_IDS:
        representative_result = representative_by_variant[variant_id]
        item = {
            "variant_id": variant_id,
            "label": VARIANT_LABELS[variant_id],
            **copy.deepcopy(definitions[variant_id]),
            "logical_stage1_request_sketch": copy.deepcopy(
                representative_result["stage1_request"]
            ),
            "logical_stage1_response_sketch": copy.deepcopy(
                representative_result["stage1_response"]
            ),
            "logical_stage2_request_sketch": None,
            "logical_stage2_response_sketch": None,
            "canonical_backend_transformation": (
                _canonical_backend_transformation(variant_id)
            ),
            "provider_specific_wrapper_required": False,
            "new_owner_required": False,
        }
        if variant_id == VARIANT_IDS[2]:
            item["logical_stage2_request_sketch"] = _build_stage2_request(
                type_cards=type_cards
            )
            item["logical_stage2_response_sketch"] = {
                "selected_choice": "choice_1"
            }
        variants.append(item)
    return variants


def _build_same_type_scenario(
    *, type_cards: list[dict[str, Any]]
) -> dict[str, Any]:
    stage1_request = _type_first_request(
        source_summary=THOUGHT_SOURCE,
        type_cards=type_cards,
    )
    stage2_request = _build_stage2_request(type_cards=type_cards)
    stage1_metrics = _request_metrics(stage1_request)
    stage2_metrics = _request_metrics(stage2_request)
    if stage1_metrics != {
        "canonicalization": (
            "minified_json_utf8_ensure_ascii_false_sort_keys_true"
        ),
        "request_utf8_bytes": 2323,
        "estimated_input_tokens": 645,
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "request_sha256": (
            "0d27210f62a09d0471750e29aaddf0a5fd2df71b4605ce74cc1ab452e19e62ff"
        ),
    }:
        raise ValueError("same_type_stage1_metric_drift")
    if stage2_metrics != {
        "canonicalization": (
            "minified_json_utf8_ensure_ascii_false_sort_keys_true"
        ),
        "request_utf8_bytes": 2073,
        "estimated_input_tokens": 583,
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "request_sha256": (
            "79ccef316b0057e8a819526e7466c15c213ddc5d67a844aaa6b46ab9b61b5e71"
        ),
    }:
        raise ValueError("same_type_stage2_metric_drift")
    return {
        "scenario_id": "doc_only_single_type_two_complete_options",
        "evidence_class": "documentation_only_thought_experiment",
        "benchmark_fixture": False,
        "product_case": False,
        "frequency_evidence": False,
        "why_type_is_one": (
            "The thought experiment stipulates that both visible rows express "
            "cash-balance semantics, so the audited local set is [type_1]."
        ),
        "why_options_are_multiple": (
            "Two complete prebound records of type_1 remain: current reporting "
            "date and comparative prior date."
        ),
        "exact_source_summary": copy.deepcopy(THOUGHT_SOURCE),
        "stipulated_plausible_types": ["type_1"],
        "complete_options": copy.deepcopy(THOUGHT_OPTIONS),
        "complete_option_counts_by_type": {"type_1": 2, "type_2": 0},
        "stage1_request": stage1_request,
        "stage1_response": {"plausible_types": ["type_1"]},
        "stage1_request_metrics": stage1_metrics,
        "variant_a": {
            "route": "one_call_joint_type_and_choice",
            "simulated_response": {
                "plausible_types": ["type_1"],
                "selected_choice": "choice_1",
            },
            "final": {
                "disposition": "typed_input",
                "typed_option": "choice_1",
            },
            "calls": 1,
        },
        "variant_b": {
            "route": "fail_closed_single_registry_type_no_safe_record",
            "final": {
                "disposition": "unclassified_financial_input",
                "reason_code": "single_registry_type_no_safe_record",
            },
            "calls": 1,
        },
        "variant_c": {
            "route": "type_first_then_stage2_record_selection",
            "stage2_request": stage2_request,
            "stage2_response": {"selected_choice": "choice_1"},
            "stage2_null_response": {"selected_choice": None},
            "stage2_request_metrics": stage2_metrics,
            "final_when_selected": {
                "disposition": "typed_input",
                "typed_option": "choice_1",
            },
            "final_when_null": {
                "disposition": "unclassified_financial_input",
                "reason_code": "single_registry_type_no_safe_record",
            },
            "calls": 2,
        },
        "residual_risk": (
            "Stage 2 can still associate current and comparative rows "
            "incorrectly; code proves membership and fixed type, not semantic "
            "correctness of the selected record."
        ),
    }


def _build_budget(
    *,
    simulations: list[dict[str, Any]],
    same_type_scenario: dict[str, Any],
) -> dict[str, Any]:
    by_variant: dict[str, Any] = {}
    for variant_id in VARIANT_IDS:
        per_case: list[dict[str, Any]] = []
        for case in simulations:
            result = next(
                item
                for item in case["variant_results"]
                if item["variant_id"] == variant_id
            )
            per_case.append(
                {
                    "case_id": case["case_id"],
                    "stage1_request_utf8_bytes": result[
                        "stage1_request_metrics"
                    ]["request_utf8_bytes"],
                    "stage1_estimated_input_tokens": result[
                        "stage1_request_metrics"
                    ]["estimated_input_tokens"],
                    "stage1_calls": 1,
                    "stage2_request_utf8_bytes": 0,
                    "stage2_estimated_input_tokens": 0,
                    "stage2_calls": 0,
                    "total_calls": 1,
                }
            )
        bytes_values = [
            item["stage1_request_utf8_bytes"] for item in per_case
        ]
        token_values = [
            item["stage1_estimated_input_tokens"] for item in per_case
        ]
        by_variant[variant_id] = {
            "per_case": per_case,
            "governed_stage1_request_utf8_bytes_total": sum(bytes_values),
            "governed_stage1_estimated_input_tokens_total": sum(token_values),
            "governed_stage1_request_utf8_bytes_max": max(bytes_values),
            "governed_stage1_estimated_input_tokens_max": max(token_values),
            "governed_stage1_calls_total": 10,
            "governed_stage2_calls_total": 0,
            "governed_aggregate_calls_total": 10,
            "architectural_worst_calls_per_operation": (
                2 if variant_id == VARIANT_IDS[2] else 1
            ),
            "ten_operation_architectural_upper_bound_calls": (
                20 if variant_id == VARIANT_IDS[2] else 10
            ),
        }

    if (
        by_variant[VARIANT_IDS[0]][
            "governed_stage1_request_utf8_bytes_total"
        ]
        != 24221
        or by_variant[VARIANT_IDS[0]][
            "governed_stage1_estimated_input_tokens_total"
        ]
        != 6697
        or by_variant[VARIANT_IDS[1]][
            "governed_stage1_request_utf8_bytes_total"
        ]
        != 21343
        or by_variant[VARIANT_IDS[1]][
            "governed_stage1_estimated_input_tokens_total"
        ]
        != 5979
    ):
        raise ValueError("governed_request_budget_drift")

    return {
        "measurement_scope": (
            "provider-neutral logical request object; excludes transport "
            "wrappers and is not provider tokenizer output"
        ),
        "canonical_serialization": {
            "encoding": "utf-8",
            "json": "minified",
            "ensure_ascii": False,
            "sort_keys": True,
            "separators": [",", ":"],
        },
        "planning_estimator": {
            "id": TOKEN_ESTIMATOR_ID,
            "formula": "ceil(canonical_utf8_bytes/4)+64",
            "provider_tokenizer": False,
        },
        "variants": by_variant,
        "same_type_thought_experiment": {
            "stage1": copy.deepcopy(
                same_type_scenario["stage1_request_metrics"]
            ),
            "stage2": copy.deepcopy(
                same_type_scenario["variant_c"]["stage2_request_metrics"]
            ),
            "aggregate_calls": 2,
            "aggregate_estimated_input_tokens": 1228,
        },
        "current_economy_policy": {
            "policy_id": "broker_reports_economy_model_policy_v1",
            "policy_version": "1.5.0",
            "policy_hash": (
                "467ce6050a69ff96f1a3cae4e2f37d8c4c62fb2dd69c757208d9ee9813698714"
            ),
            "financial_maximum_estimated_input_tokens": 3072,
            "financial_maximum_output_tokens": 640,
            "financial_maximum_provider_calls_per_operation": 1,
            "variant_c_implication": (
                "future versioned behavior/policy change inside the existing "
                "economy owner; not a new owner"
            ),
        },
    }


def _build_comparison() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    totals = {variant_id: 0 for variant_id in VARIANT_IDS}
    maximum = 0
    for criterion, weight, score_a, score_b, score_c in COMPARISON_CRITERIA:
        scores = {
            VARIANT_IDS[0]: score_a,
            VARIANT_IDS[1]: score_b,
            VARIANT_IDS[2]: score_c,
        }
        rows.append(
            {
                "criterion": criterion,
                "weight": weight,
                "scores": scores,
            }
        )
        maximum += weight * 5
        for variant_id, score in scores.items():
            totals[variant_id] += weight * score
    if maximum != 160 or totals != {
        VARIANT_IDS[0]: 101,
        VARIANT_IDS[1]: 142,
        VARIANT_IDS[2]: 130,
    }:
        raise ValueError("comparison_score_drift")
    return {
        "score_scale": "1_to_5_higher_is_better",
        "rubric_is_measured_model_quality": False,
        "weighting_note": (
            "Domain safety, responsibility separation and freedom from "
            "constructible-choice influence outweigh byte/token cost."
        ),
        "criteria": rows,
        "maximum_weighted_score": maximum,
        "weighted_totals": {
            variant_id: {
                "score": totals[variant_id],
                "maximum": maximum,
                "percentage": round(totals[variant_id] * 100 / maximum, 1),
            }
            for variant_id in VARIANT_IDS
        },
    }


def _render_report(transparent: dict[str, Any]) -> str:
    variants = {
        item["variant_id"]: item for item in transparent["variants"]
    }
    cases = {
        item["case_id"]: item
        for item in transparent["per_case_simulations"]
    }
    budget_variants = transparent["byte_and_call_budget"]["variants"]
    comparison = transparent["comparison"]
    scenario = transparent["same_type_multiple_option_scenario"]

    lines = [
        "# Broker Reports Gate 2 — Type-First Semantic Decision Architecture Audit",
        "",
        (
            "Status: `COMPLETED_OFFLINE_ARCHITECTURE_AUDIT`; "
            "recommendation: "
            f"`{RECOMMENDATION_ID}`; confidence: `{CONFIDENCE}`."
        ),
        "",
        (
            "Этот отчёт сравнивает три будущих варианта честно и на одной "
            "доказательной базе. Он не меняет Prompt, Context, Choice, Pack, "
            "runtime или product logic и не является разрешением на реализацию."
        ),
        "",
        (
            f"Machine-readable evidence: "
            f"[transparent JSON](./{TRANSPARENT_PATH.name}) and "
            f"[safe receipt](./{RECEIPT_PATH.name})."
        ),
        "",
        "## 1. Problem statement",
        "",
        (
            "Текущий архитектурный вопрос состоит из двух разных решений: "
            "(1) какой финансовый тип семантически правдоподобен и (2) какую "
            "полную, уже собранную кодом запись можно безопасно принять. "
            "Constructible Typed Option не доказывает plausible financial type."
        ),
        "",
        (
            "Цель — выбрать простейший профиль, который fail closed, показывает "
            "решение модели, отделяет смысл от технической сборки и не создаёт "
            "второго Packet/Pack/Choice/adapter/runtime authority."
        ),
        "",
        "## 2. Facts established by GOAL 14",
        "",
        (
            "- `multiple_compatible`: source показывает Possible cash и "
            "Possible total без явных amount-to-description связей; choices "
            "пусты; audited set = `[type_1,type_2]`."
        ),
        "",
        (
            "- `detail_vs_subtotal`: source различает detail и subtotal; "
            "choices пусты; audited set = `[type_2]`."
        ),
        "",
        (
            "- `no_registry_type`: source представляет связанную Broker fee "
            "detail строку; две записи технически собираемы; audited set = `[]`."
        ),
        "",
        (
            "GOAL 14 доказал несовпадение constructibility и plausibility, но "
            "не доказал причинность model errors. Поэтому влияние видимых "
            "choices остаётся проверяемой гипотезой, а не установленным root cause."
        ),
        "",
    ]

    lines.extend(
        _render_variant_section(
            number=3,
            title="Variant A",
            variant=variants[VARIANT_IDS[0]],
            stage2_note=(
                "Stage 2 отсутствует. `selected_choice` нужен прежде всего для "
                "singleton-type/multiple-option состояния; при одной matching "
                "option код мог бы выбрать её сам."
            ),
            assessment=(
                "Код может проверить cardinality, membership, exact local key "
                "и совпадение типа выбранной записи с singleton plausible type. "
                "Observability высокая, а изменение относительно V2.1 "
                "ограничивается additive profiles. Главный нерешённый риск: "
                "видимые choices всё ещё участвуют в type judgment."
            ),
        )
    )
    lines.extend(
        _render_variant_section(
            number=4,
            title="Variant B",
            variant=variants[VARIANT_IDS[1]],
            stage2_note=(
                "Stage 2 отсутствует. При двух complete options одного типа "
                "код намеренно завершает "
                "`single_registry_type_no_safe_record`."
            ),
            assessment=(
                "На текущих fixtures B автоматически типизирует четыре случая: "
                "`unique_cash`, `unique_printed_total`, `optional_missing`, "
                "`forbidden_neighbour`. В остальных случаях он выводит "
                "корректный code-owned reason. Безопасная недотипизация возникает "
                "только в не представленном governed evidence состоянии с "
                "несколькими same-type options. Это разумный MVP-компромисс, но "
                "не доказанная долгосрочная полнота."
            ),
        )
    )
    lines.extend(
        _render_variant_section(
            number=5,
            title="Variant C",
            variant=variants[VARIANT_IDS[2]],
            stage2_note=(
                "Stage 2 получает ровно одну уже выбранную type card, только "
                "complete options этого типа и минимальные differentiators. "
                "Schema не содержит поля типа или reason, поэтому тип нельзя "
                "переопределить."
            ),
            assessment=(
                "На десяти governed fixtures Stage 2 требуется `0/10` раз. "
                "Будущий C должен остаться внутри существующего production "
                "orchestration owner, связать оба вызова одной operation identity, "
                "сохранить оба sealed requests/outputs и учитывать каждый "
                "фактический call. Технический Stage 2 failure прерывает операцию "
                "до ArtifactStore writes; выполненный call не откатывается. "
                "Текущий one-call economy limit потребует versioned behavior "
                "change в существующем owner."
            ),
        )
    )

    lines.extend(
        [
            "## 6. Four-case simulation",
            "",
            (
                "Каждый ответ ниже — детерминированная симуляция, которая "
                "подставляет frozen audited plausible set. Это не наблюдавшийся "
                "ответ новой модели. Полные exact logical request objects находятся "
                "в transparent JSON."
            ),
            "",
        ]
    )
    for case_id in DETAILED_CASE_IDS:
        case = cases[case_id]
        lines.extend(
            [
                f"### `{case_id}`",
                "",
                "Exact source summary:",
                "",
                "```json",
                _pretty_json(case["exact_source_summary"]),
                "```",
                "",
                (
                    "Audited plausible set: "
                    f"`{_compact_json(case['audited_plausible_types'])}`; "
                    "Compiler options by type: "
                    f"`{_compact_json(case['available_complete_option_counts_by_type'])}`."
                ),
                "",
                (
                    "| Variant | What LLM sees | Stage 1 JSON | Code decision | "
                    "Stage 2 | Stage 2 JSON | Final | Calls | Possible failure |"
                ),
                "| --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
            ]
        )
        for result in case["variant_results"]:
            final = {
                "disposition": result["final_canonical_disposition"],
                **result["final_reason_or_typed_option"],
            }
            lines.append(
                "| "
                f"`{VARIANT_LABELS[result['variant_id']]}` | "
                f"`{','.join(result['llm_visible_fields'])}` | "
                f"`{_compact_json(result['stage1_response'])}` | "
                f"{result['code_decision']} | "
                f"`{str(result['stage2_required']).lower()}` | "
                f"`{_compact_json(result['stage2_response'])}` | "
                f"`{_compact_json(final)}` | "
                f"{result['llm_call_count']} | "
                f"{result['possible_failure_modes'][0]} |"
            )
        lines.extend([""])

    lines.extend(
        [
            "## 7. Ten-case mechanical simulation",
            "",
            (
                "`NEEDS_SEMANTIC_AUDIT = 0`: corrected outcome audit закрепляет "
                "plausible set для всех десяти semantic-model fixtures. "
                "`repeated_header` и `unsupported_shape` — technical preclose и "
                "в эту десятку не входят."
            ),
            "",
            (
                "| Case | Semantic state | Plausible/count | Options t1/t2 | "
                "A route/calls | B route/calls | C route/calls | Expected final | "
                "Completeness loss | Unproved assumption |"
            ),
            "| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for case_id in CASE_ORDER:
        case = cases[case_id]
        results = {
            item["variant_id"]: item for item in case["variant_results"]
        }
        counts = case["available_complete_option_counts_by_type"]
        expected = case["expected_final_answer"]
        lines.append(
            f"| `{case_id}` | `{case['expected_semantic_state']}` | "
            f"`{_compact_json(case['audited_plausible_types'])}` / "
            f"{case['plausible_type_count']} | "
            f"{counts['type_1']}/{counts['type_2']} | "
            f"`{results[VARIANT_IDS[0]]['route']}` / 1 | "
            f"`{results[VARIANT_IDS[1]]['route']}` / 1 | "
            f"`{results[VARIANT_IDS[2]]['route']}` / 1 | "
            f"`{_compact_json(expected)}` | none in governed fixture | "
            "`proposed_stage1_returns_frozen_audited_plausible_set`"
            "; A additionally assumes no choice-induced distortion"
            + " |"
        )
    lines.extend(
        [
            "",
            (
                "B и C механически совпадают на `10/10` случаях; C Stage 2 = "
                "`0/10`. Для A также получается corrected expected answer, но "
                "симуляция не доказывает, что видимые choices не изменят "
                "фактический type judgment."
            ),
            "",
            "## 8. Same-type multi-option scenario",
            "",
            (
                "В governed ten-case set не найдено состояния «один plausible "
                "type, больше одной complete option этого типа». Поэтому ниже "
                "только "
                "documentation-only thought experiment: не benchmark fixture, "
                "не product case и не frequency evidence."
            ),
            "",
            (
                "Две complete cash-записи относятся к текущей и сравнительной "
                "датам. Stipulated plausible set = `[type_1]`; option counts = "
                "`{\"type_1\":2,\"type_2\":0}`."
            ),
            "",
            "Exact Stage 1 logical request:",
            "",
            "```json",
            _pretty_json(scenario["stage1_request"]),
            "```",
            "",
            (
                "B фильтрует две matching options и безопасно завершает "
                "`single_registry_type_no_safe_record`. C запускает Stage 2."
            ),
            "",
            "Exact C Stage 2 logical request:",
            "",
            "```json",
            _pretty_json(scenario["variant_c"]["stage2_request"]),
            "```",
            "",
            "Stage 2 response sketches:",
            "",
            "```json",
            _pretty_json(
                {
                    "selected": scenario["variant_c"]["stage2_response"],
                    "closed_refusal": scenario["variant_c"][
                        "stage2_null_response"
                    ],
                }
            ),
            "```",
            "",
            (
                "Residual risk: Stage 2 может неверно связать current и "
                "comparative row. Код доказывает fixed type и membership, но не "
                "семантическую правильность выбранной записи."
            ),
            "",
            "## 9. Authority/change-surface matrix",
            "",
            (
                "`new owner required = 0` для A, B и C. `additive_profile` "
                "означает versioned profile внутри названного owner, а не новую "
                "factory или параллельный route."
            ),
            "",
            "| Concern | Existing sole owner | A | B | C | New owner |",
            "| --- | --- | --- | --- | --- | ---: |",
        ]
    )
    for row in transparent["authority_change_surface"]["rows"]:
        lines.append(
            f"| {row['concern']} | `{row['existing_owner']}` "
            f"(`{row['authority_anchor']}`) | "
            f"`{row['changes'][VARIANT_IDS[0]]}` | "
            f"`{row['changes'][VARIANT_IDS[1]]}` | "
            f"`{row['changes'][VARIANT_IDS[2]]}` | 0 |"
        )

    lines.extend(
        [
            "",
            (
                "Для C orchestration остаётся в "
                "`Gate2FinancialEvidenceProductionRuntime._decide`; Decision "
                "Evidence сохраняет обе стадии и deterministic branch; "
                "EconomyBudget считает только реально выполненные calls. "
                "Qualification coordinator GOAL 12 не становится product owner."
            ),
            "",
            "## 10. Byte/call estimates",
            "",
            (
                "Измеряется exact provider-neutral logical object "
                "`{response_schema,user_context}` как minified sorted UTF-8 JSON. "
                f"Estimator `{TOKEN_ESTIMATOR_ID}` = `ceil(bytes/4)+64`; это "
                "planning estimate, не provider tokenizer и не wire request."
            ),
            "",
            "| Case | A bytes/tokens | B bytes/tokens | C1 bytes/tokens | C2 calls |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    a_per_case = {
        item["case_id"]: item
        for item in budget_variants[VARIANT_IDS[0]]["per_case"]
    }
    b_per_case = {
        item["case_id"]: item
        for item in budget_variants[VARIANT_IDS[1]]["per_case"]
    }
    c_per_case = {
        item["case_id"]: item
        for item in budget_variants[VARIANT_IDS[2]]["per_case"]
    }
    for case_id in CASE_ORDER:
        a = a_per_case[case_id]
        b = b_per_case[case_id]
        c = c_per_case[case_id]
        lines.append(
            f"| `{case_id}` | {a['stage1_request_utf8_bytes']} / "
            f"{a['stage1_estimated_input_tokens']} | "
            f"{b['stage1_request_utf8_bytes']} / "
            f"{b['stage1_estimated_input_tokens']} | "
            f"{c['stage1_request_utf8_bytes']} / "
            f"{c['stage1_estimated_input_tokens']} | "
            f"{c['stage2_calls']} |"
        )
    lines.extend(
        [
            "",
            (
                f"A total/max: `{budget_variants[VARIANT_IDS[0]]['governed_stage1_request_utf8_bytes_total']} bytes / "
                f"{budget_variants[VARIANT_IDS[0]]['governed_stage1_estimated_input_tokens_total']} tokens`; "
                f"max `{budget_variants[VARIANT_IDS[0]]['governed_stage1_request_utf8_bytes_max']} / "
                f"{budget_variants[VARIANT_IDS[0]]['governed_stage1_estimated_input_tokens_max']}`."
            ),
            "",
            (
                f"B and current C total/max: `{budget_variants[VARIANT_IDS[1]]['governed_stage1_request_utf8_bytes_total']} bytes / "
                f"{budget_variants[VARIANT_IDS[1]]['governed_stage1_estimated_input_tokens_total']} tokens`; "
                f"max `{budget_variants[VARIANT_IDS[1]]['governed_stage1_request_utf8_bytes_max']} / "
                f"{budget_variants[VARIANT_IDS[1]]['governed_stage1_estimated_input_tokens_max']}`."
            ),
            "",
            (
                "Governed aggregate calls: A=`10`, B=`10`, C=`10` "
                "(Stage 1=`10`, Stage 2=`0`). Architectural worst per operation: "
                "A/B=`1`, C=`2`; generic ten-operation ceiling for C=`20`."
            ),
            "",
            (
                "Thought experiment C Stage 2: "
                f"`{scenario['variant_c']['stage2_request_metrics']['request_utf8_bytes']} "
                "bytes / "
                f"{scenario['variant_c']['stage2_request_metrics']['estimated_input_tokens']} "
                "estimated tokens`; both stages: `2 calls / "
                f"{transparent['byte_and_call_budget']['same_type_thought_experiment']['aggregate_estimated_input_tokens']} "
                "estimated input tokens`."
            ),
            "",
            (
                "Pinned economy policy `broker_reports_economy_model_policy_v1` "
                "v1.5.0 currently permits exactly one call per financial "
                "operation. No current price is claimed as provider truth."
            ),
            "",
            "## 11. Comparison matrix",
            "",
            (
                "Scores are a transparent 1–5 decision rubric, not measured "
                "model quality. Higher is better. Safety, responsibility "
                "separation and freedom from choice influence have higher weights "
                "than byte/token cost."
            ),
            "",
            "| Criterion | Weight | A | B | C |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in comparison["criteria"]:
        lines.append(
            f"| {row['criterion']} | {row['weight']} | "
            f"{row['scores'][VARIANT_IDS[0]]} | "
            f"{row['scores'][VARIANT_IDS[1]]} | "
            f"{row['scores'][VARIANT_IDS[2]]} |"
        )
    lines.extend(
        [
            "",
            (
                "Weighted totals: "
                f"A=`{comparison['weighted_totals'][VARIANT_IDS[0]]['score']}/160` "
                f"({comparison['weighted_totals'][VARIANT_IDS[0]]['percentage']}%); "
                f"B=`{comparison['weighted_totals'][VARIANT_IDS[1]]['score']}/160` "
                f"({comparison['weighted_totals'][VARIANT_IDS[1]]['percentage']}%); "
                f"C=`{comparison['weighted_totals'][VARIANT_IDS[2]]['score']}/160` "
                f"({comparison['weighted_totals'][VARIANT_IDS[2]]['percentage']}%)."
            ),
            "",
            "## 12. Recommendation",
            "",
            f"Recommendation: **`{RECOMMENDATION_ID}`**.",
            "",
            f"Confidence: **`{CONFIDENCE}`**.",
            "",
            (
                "B — минимальный вариант, который убирает constructible choices "
                "из type judgment, делает plausible set наблюдаемым и выводит "
                "reason в коде. Он точно воспроизводит corrected route всех "
                "десяти fixtures с одним плановым call."
            ),
            "",
            (
                "A отклонён как MVP: он сохраняет нерешённое влияние choices и "
                "смешивает type/record decisions, хотя даёт one-call "
                "same-type selection. C пока отложен: Stage 2 нужен `0/10` раз и "
                "добавляет недоказанную полноту ценой двухвызовной orchestration, "
                "policy, replay и failure accounting."
            ),
            "",
            (
                "Phased strategy не является четвёртой архитектурой: сначала B; "
                "C рассматривается только после accepted-corpus evidence "
                "материальной частоты singleton-type/multiple-option state и "
                "bounded Stage 2 qualification с безопасным net gain."
            ),
            "",
            "Evidence present: frozen audited sets, exact option counts, exact "
            "logical request budgets, zero current Stage 2 triggers and "
            "existing-owner map. Missing evidence перечислено далее.",
            "",
            "## 13. Unresolved questions",
            "",
        ]
    )
    for index, item in enumerate(
        transparent["unresolved_assumptions"],
        start=1,
    ):
        lines.extend(
            [
                f"{index}. `{item['id']}` — {item['question']}",
                "",
                f"   Missing: {item['missing_evidence']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 14. Decision boundary",
            "",
            (
                "GOAL 15 заканчивается архитектурной рекомендацией. "
                "Implementation changes, runtime activation, model qualification "
                "и production admission равны нулю. Context V2.1 по-прежнему "
                "не имеет доказанного eligible model."
            ),
            "",
            (
                "Program owner отдельно утверждает A, B, C, phased B→C или "
                "дополнительную диагностику. До такого решения нельзя изменять "
                "Prompt/Context/Choice/Pack, runtime, provider policy или начинать "
                "следующий implementation GOAL."
            ),
            "",
            "**STOP AFTER GOAL 15.**",
            "",
        ]
    )
    report = "\n".join(lines)
    _validate_repository_safe_text(report)
    return report


def _render_variant_section(
    *,
    number: int,
    title: str,
    variant: dict[str, Any],
    stage2_note: str,
    assessment: str,
) -> list[str]:
    lines = [
        f"## {number}. {title}",
        "",
        f"Working ID: `{variant['variant_id']}`.",
        "",
        "LLM decides:",
        "",
    ]
    lines.extend(f"- {item}" for item in variant["llm_responsibility"])
    lines.extend(["", "Code decides:", ""])
    lines.extend(f"- {item}" for item in variant["code_responsibility"])
    lines.extend(
        [
            "",
            "Exact proposed Stage 1 logical request "
            "(representative `unique_cash` instance):",
            "",
            "```json",
            _pretty_json(variant["logical_stage1_request_sketch"]),
            "```",
            "",
            "Exact Stage 1 response sketch:",
            "",
            "```json",
            _pretty_json(variant["logical_stage1_response_sketch"]),
            "```",
            "",
        ]
    )
    if variant["logical_stage2_request_sketch"] is None:
        lines.extend(["Stage 2: not applicable.", ""])
    else:
        lines.extend(
            [
                "Exact proposed Stage 2 logical request "
                "(documentation-only same-type scenario):",
                "",
                "```json",
                _pretty_json(variant["logical_stage2_request_sketch"]),
                "```",
                "",
                "Exact Stage 2 response sketch:",
                "",
                "```json",
                _pretty_json(variant["logical_stage2_response_sketch"]),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            stage2_note,
            "",
            "Canonical backend transformation:",
            "",
            "```json",
            _pretty_json(variant["canonical_backend_transformation"]),
            "```",
            "",
            assessment,
            "",
            "Strengths: " + "; ".join(variant["strengths"]) + ".",
            "",
            "Limitations: " + "; ".join(variant["limitations"]) + ".",
            "",
        ]
    )
    return lines


def write_or_check_outputs(
    *, outputs: dict[Path, bytes], check: bool
) -> None:
    for path, expected in outputs.items():
        if check:
            if not path.is_file() or path.read_bytes() != expected:
                raise SystemExit(
                    "type_first_semantic_decision_audit_drift:"
                    f"{path.name}"
                )
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)


def _validate_source_authorities() -> dict[str, str]:
    observed: dict[str, str] = {}
    for identity, path, expected_hash in SOURCE_AUTHORITIES:
        actual = _sha256_bytes(_repository_lf_bytes(path.read_bytes()))
        if actual != expected_hash:
            raise ValueError(
                f"source_authority_hash_invalid:{identity}:{actual}"
            )
        observed[identity] = actual
    return observed


def _repository_lf_bytes(value: bytes) -> bytes:
    if b"\r" in value.replace(b"\r\n", b""):
        raise ValueError("source_authority_lone_carriage_return")
    return value.replace(b"\r\n", b"\n")


def _validate_embedded_integrity(
    value: dict[str, Any], field: str
) -> None:
    material = copy.deepcopy(value)
    supplied = material.pop(field, None)
    if supplied != _sha256_json(material):
        raise ValueError(f"embedded_integrity_invalid:{field}")


def _validate_repository_safe_output(value: dict[str, Any]) -> None:
    forbidden = _recursive_keys(value).intersection(_FORBIDDEN_OUTPUT_KEYS)
    if forbidden:
        raise ValueError(
            "repository_safe_output_forbidden_keys:"
            + ",".join(sorted(forbidden))
        )
    _validate_repository_safe_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    )


def _validate_repository_safe_text(value: str) -> None:
    if _LOCAL_PATH_RE.search(value):
        raise ValueError("repository_safe_output_local_path")
    lowered = value.lower()
    for marker in (
        "bearer ",
        "api-key",
        "x-api-key",
        "raw_provider_envelope",
        "managed_to_local_type_mapping",
    ):
        if marker in lowered:
            raise ValueError(f"repository_safe_output_marker:{marker}")


def _recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(_recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_recursive_keys(item))
    return keys


def _with_integrity(material: dict[str, Any]) -> dict[str, Any]:
    return {
        **copy.deepcopy(material),
        "integrity_sha256": _sha256_json(material),
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_not_object:{path.name}")
    return value


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pretty_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    )


def _compact_json(value: Any) -> str:
    return _canonical_json_bytes(value).decode("utf-8")


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
