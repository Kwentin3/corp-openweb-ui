"""Narrow, lossless OOXML canonicalization before OfficeCLI edits.

This is intentionally not a document repair engine.  It changes only known
serialization defects that have no user-visible meaning: child ordering where
OOXML mandates one, explicit ``w:noWrap w:val=\"false\"`` (absence means false),
and the undeclared VML ``type`` attribute on ``v:shapetype``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
V = "{urn:schemas-microsoft-com:vml}"

_ORDERS = {
    "sectPr": "headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange".split(),
    "tcPr": "cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark headers cellIns cellDel cellMerge tcPrChange".split(),
    "pPr": "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange".split(),
    "tblCellMar": "top left bottom right".split(),
    "tblStylePr": "pPr rPr tblPr trPr tcPr".split(),
}


@dataclass(frozen=True)
class DocxNormalizationReceipt:
    changed_parts: tuple[str, ...]
    reordered_elements: int
    removed_false_no_wrap: int
    removed_vml_shapetype_type: int

    @property
    def applied(self) -> bool:
        return bool(self.changed_parts)


def normalize_known_noncanonical_docx(source: Path, destination: Path) -> DocxNormalizationReceipt:
    """Copy ``source`` to ``destination``, canonicalizing only whitelisted XML."""
    changed_parts: list[str] = []
    reordered = removed_no_wrap = removed_vml_type = 0
    try:
        with ZipFile(source) as input_zip, ZipFile(destination, "w", ZIP_DEFLATED) as output_zip:
            for entry in input_zip.infolist():
                raw = input_zip.read(entry.filename)
                if entry.filename.startswith("word/") and entry.filename.endswith(".xml"):
                    root = etree.fromstring(raw)
                    changed = False
                    for tag, ordered_names in _ORDERS.items():
                        positions = {W + name: index for index, name in enumerate(ordered_names)}
                        for parent in root.findall(".//" + W + tag):
                            children = list(parent)
                            canonical = [item[1] for item in sorted(enumerate(children), key=lambda item: (positions.get(item[1].tag, 10_000), item[0]))]
                            if children != canonical:
                                parent[:] = canonical
                                reordered += 1
                                changed = True
                    for no_wrap in root.findall(".//" + W + "noWrap"):
                        if no_wrap.get(W + "val") == "false":
                            no_wrap.getparent().remove(no_wrap)
                            removed_no_wrap += 1
                            changed = True
                    for shape_type in root.findall(".//" + V + "shapetype"):
                        if "type" in shape_type.attrib:
                            del shape_type.attrib["type"]
                            removed_vml_type += 1
                            changed = True
                    if changed:
                        raw = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
                        changed_parts.append(entry.filename)
                output_zip.writestr(entry, raw)
    except BadZipFile:
        destination.write_bytes(source.read_bytes())
    return DocxNormalizationReceipt(tuple(changed_parts), reordered, removed_no_wrap, removed_vml_type)
