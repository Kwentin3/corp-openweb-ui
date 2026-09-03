from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PAIR_ROOT = (
    REPOSITORY_ROOT
    / "docs"
    / "reports"
    / "2026-09-02"
    / "artifacts"
    / "mistral-public-pairs"
)

EXPECTED_FILES = {
    ".gitattributes": "3ff20795e070d1bdac9195e89901ae2f9be851be0fab662de827355b66ffcc47",
    "README.md": "57b2b97492081aee96335b53be10811628bedb694624c3f10681166d277d3b66",
    "drivewealth/mistral-markdown.md": "384245df67e772df1cc1d8c0a06430721fab8bbe4e5b2d8a64b012d059eae399",
    "drivewealth/source.pdf": "738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57",
    "fidelity/img-0.jpeg": "1b669fc6f1d25f31511b3de2b69a2e16359340f0509115be59f07499b6b08f9b",
    "fidelity/img-1.jpeg": "471d69e259ed61018654fb9f4e46a55a70bff2019a10d901b5be913ac778bf83",
    "fidelity/img-2.jpeg": "20038d0abdbd9377a33961f8d3cca668ec9548d49c3986bece2446d2891fedf9",
    "fidelity/img-3.jpeg": "d3f4c9f2871cb6d82e2a9ff96044a4d2a3a16760b073d4ab0d3bafbeb6e95878",
    "fidelity/img-4.jpeg": "7f3c2dc4bfb5573915d32ab011c6325df9bcc1aac7331de66a3b0ed249ae5723",
    "fidelity/img-5.jpeg": "a8470376c926d1e6141718ad9a429cc75319ecb20a4f6588dc211af1a05fc44b",
    "fidelity/img-6.jpeg": "a8470376c926d1e6141718ad9a429cc75319ecb20a4f6588dc211af1a05fc44b",
    "fidelity/img-7.jpeg": "a8470376c926d1e6141718ad9a429cc75319ecb20a4f6588dc211af1a05fc44b",
    "fidelity/mistral-markdown.md": "2cb67d36948f9177e633c82369b33a8f6398d204add6295b320211ff22720f5f",
    "fidelity/source.pdf": "36a166a5a13e6d6d86b391233023f83f6f7b4d268a4a23fbae01cb81290e3b96",
}
PRIMARY_PAIR_HASHES = {
    key: EXPECTED_FILES[key]
    for key in (
        "drivewealth/source.pdf",
        "drivewealth/mistral-markdown.md",
        "fidelity/source.pdf",
        "fidelity/mistral-markdown.md",
    )
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_sha256(path: Path) -> str:
    repository_path = path.relative_to(REPOSITORY_ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f"HEAD:{repository_path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return hashlib.sha256(completed.stdout).hexdigest()


def test_public_pair_fixture_has_closed_file_allowlist_and_exact_hashes() -> None:
    actual = {
        path.relative_to(PAIR_ROOT).as_posix()
        for path in PAIR_ROOT.rglob("*")
        if path.is_file()
    }
    assert actual == set(EXPECTED_FILES)
    assert {name: _git_blob_sha256(PAIR_ROOT / name) for name in actual} == EXPECTED_FILES
    assert {
        name: _git_blob_sha256(PAIR_ROOT / name) for name in PRIMARY_PAIR_HASHES
    } == PRIMARY_PAIR_HASHES


def test_sources_are_pdfs_and_all_fidelity_image_refs_are_local_and_hashed() -> None:
    for relative_path in ("drivewealth/source.pdf", "fidelity/source.pdf"):
        assert (PAIR_ROOT / relative_path).read_bytes().startswith(b"%PDF")

    markdown_path = PAIR_ROOT / "fidelity" / "mistral-markdown.md"
    markdown = markdown_path.read_text(encoding="utf-8")
    refs = re.findall(r"!\[[^]]*\]\(([^)]+)\)", markdown)
    assert refs == [f"img-{index}.jpeg" for index in range(8)]
    for ref in refs:
        assert "://" not in ref
        assert not Path(ref).is_absolute()
        target = (markdown_path.parent / ref).resolve()
        assert target.parent == markdown_path.parent.resolve()
        assert target.is_file()
        expected = EXPECTED_FILES[f"fidelity/{ref}"]
        assert _sha256(target) == expected


def test_fixture_is_public_research_not_qualification_evidence() -> None:
    readme = (PAIR_ROOT / "README.md").read_text(encoding="utf-8").casefold()
    assert "публичн" in readme
    assert "исследовател" in readme
    assert "не квалификац" in readme
    assert "production" in readme
