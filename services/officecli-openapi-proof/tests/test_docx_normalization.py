from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

from officecli_openapi_proof.docx_normalization import normalize_known_noncanonical_docx

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V = "urn:schemas-microsoft-com:vml"


def _write_fixture(path: Path) -> None:
    document = f'''<w:document xmlns:w="{W}"><w:body><w:tbl><w:tr><w:tc><w:tcPr><w:tcW/><w:textDirection/><w:noWrap w:val="false"/></w:tcPr><w:p><w:pPr><w:jc/><w:spacing/></w:pPr><w:r><w:t>unchanged text</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:sectPr><w:docGrid/><w:titlePg/></w:sectPr></w:body></w:document>'''
    header = f'''<w:hdr xmlns:w="{W}" xmlns:v="{V}"><w:p><w:r><w:pict><v:shapetype type="#_x0000_t75"/></w:pict></w:r></w:p></w:hdr>'''
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/header1.xml", header)


def test_normalizes_only_known_noncanonical_ooxml_representation(tmp_path: Path) -> None:
    source, normalized = tmp_path / "source.docx", tmp_path / "normalized.docx"
    _write_fixture(source)
    receipt = normalize_known_noncanonical_docx(source, normalized)

    with ZipFile(normalized) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
        header = etree.fromstring(archive.read("word/header1.xml"))
    ns = {"w": W, "v": V}
    assert document.xpath("string(.//w:t)", namespaces=ns) == "unchanged text"
    assert [node.tag.rsplit("}", 1)[-1] for node in document.xpath(".//w:tcPr/*", namespaces=ns)] == ["tcW", "textDirection"]
    assert [node.tag.rsplit("}", 1)[-1] for node in document.xpath(".//w:sectPr/*", namespaces=ns)] == ["titlePg", "docGrid"]
    assert header.xpath(".//v:shapetype/@type", namespaces=ns) == []
    assert receipt.applied
    assert receipt.removed_false_no_wrap == 1
    assert receipt.removed_vml_shapetype_type == 1
