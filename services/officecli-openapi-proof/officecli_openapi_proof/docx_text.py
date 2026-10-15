"""Compare the native DOCX text before and after requested formatting."""
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from .officecli import OfficeCliFailure

WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def body_paragraphs(path: Path) -> tuple[str, ...]:
    try:
        with ZipFile(path) as package:
            document = ElementTree.fromstring(package.read('word/document.xml'))
        body = document.find(WORD + 'body')
        if body is None:
            raise ValueError('missing body')
        return tuple(text for paragraph in body.iter(WORD + 'p')
                     if (text := ''.join(part.text or '' for part in paragraph.iter(WORD + 't'))).strip())
    except (BadZipFile, KeyError, ElementTree.ParseError, ValueError) as error:
        raise OfficeCliFailure('native DOCX text could not be checked') from error


def require_preserved_text(source: tuple[str, ...], result: tuple[str, ...]) -> None:
    """Formatting may insert requested fields, preserving every source paragraph in order."""
    if not source:
        raise OfficeCliFailure('native source import produced no document text')
    failure = ('formatting changed, removed, reordered or duplicated prepared text; '
               'use formatting properties and append the requested fields; no document was published')
    result_counts = Counter(result)
    if any(result_counts[text] != count for text, count in Counter(source).items()):
        raise OfficeCliFailure(failure)
    position = 0
    for text in source:
        try:
            position = result.index(text, position) + 1
        except ValueError as error:
            raise OfficeCliFailure(failure) from error
