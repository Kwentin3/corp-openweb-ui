from __future__ import annotations

import copy

import pytest

from openwebui_filters.stage2_audio_context_filter import Filter


def protocol(segments, text="Unused fallback text."):
    return Filter()._format_transcript({"result": {"text": text, "segments": segments}})


def test_mixed_speakers_preserve_every_nonempty_segment_in_source_order():
    segments = [
        {"speaker": "agent", "text": "Добрый день.", "start": 1, "end": 3},
        {"text": "Не потеряйте эту реплику.", "start": 3, "end": 4},
        {"speaker": "agent", "text": "У меня  два вопроса.", "start": 4, "end": 5},
        {"speaker": "", "text": "И ещё один.", "start": 5},
        {"speaker": "client", "text": "Слушаю вас.", "start": 6, "end": 7},
        {"speaker": None, "text": "Последняя реплика.", "end": 9},
    ]
    before = copy.deepcopy(segments)
    assert protocol(segments) == (
        "[00:01-00:03] Спикер 1:\nДобрый день.\n\n"
        "[00:03-00:04] Спикер не определён:\nНе потеряйте эту реплику.\n\n"
        "[00:04-00:05] Спикер 1:\nУ меня  два вопроса.\n\n"
        "[00:05] Спикер не определён:\nИ ещё один.\n\n"
        "[00:06-00:07] Спикер 2:\nСлушаю вас.\n\n"
        "[?-00:09] Спикер не определён:\nПоследняя реплика."
    )
    assert segments == before


def test_adjacent_same_speaker_segments_retain_each_provided_time_boundary():
    assert protocol([
        {"speaker": "speaker_0", "text": "First sentence.", "start": 1, "end": 3},
        {"speaker": "speaker_0", "text": "Second sentence.", "start": 3, "end": 5},
        {"speaker": "speaker_1", "text": "Reply.", "start": 5, "end": 6},
    ]) == (
        "[00:01-00:03] Спикер 1:\nFirst sentence.\n\n"
        "[00:03-00:05] Спикер 1:\nSecond sentence.\n\n"
        "[00:05-00:06] Спикер 2:\nReply."
    )


def test_segments_without_speakers_keep_timestamps_and_explicit_unknown_identity():
    assert protocol([
        {"text": "At the start.", "start_seconds": 0, "end_seconds": 60},
        {"text": "After an hour.", "start_seconds": 3601, "end_seconds": 3602},
        {"text": "No time supplied."},
    ]) == (
        "[00:00-01:00] Спикер не определён:\nAt the start.\n\n"
        "[1:00:01-1:00:02] Спикер не определён:\nAfter an hour.\n\n"
        "Спикер не определён:\nNo time supplied."
    )


def test_zero_speaker_id_is_known_and_not_confused_with_missing_speaker():
    assert protocol([
        {"speaker": 0, "text": "Known zero."},
        {"text": "Unknown."},
        {"speaker": "0", "text": "Same known speaker."},
        {"speaker": 1, "text": "Known one."},
    ]) == (
        "Спикер 1:\nKnown zero.\n\n"
        "Спикер не определён:\nUnknown.\n\n"
        "Спикер 1:\nSame known speaker.\n\n"
        "Спикер 2:\nKnown one."
    )


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf"), "NaN", "Infinity", "broken", -1, True, None])
def test_invalid_timestamps_do_not_crash_or_invent_missing_boundaries(invalid):
    filter_ = Filter()
    assert filter_._format_seconds(invalid) == ""
    assert protocol([
        {"text": "No valid start.", "start_seconds": invalid, "end_seconds": 8},
        {"text": "No valid end.", "start_seconds": 9, "end_seconds": invalid},
        {"text": "No valid time.", "start_seconds": invalid, "end_seconds": invalid},
    ]) == (
        "[?-00:08] Спикер не определён:\nNo valid start.\n\n"
        "[00:09] Спикер не определён:\nNo valid end.\n\n"
        "Спикер не определён:\nNo valid time."
    )


def test_available_legacy_timestamp_aliases_survive_empty_canonical_fields():
    assert protocol([
        {"text": "Aliases.", "start_seconds": None, "start": 1, "end_seconds": float("nan"), "end": 2},
        {"text": "Canonical wins.", "start_seconds": 4, "start": 1, "end_seconds": 5, "end": 2},
    ]) == (
        "[00:01-00:02] Спикер не определён:\nAliases.\n\n"
        "[00:04-00:05] Спикер не определён:\nCanonical wins."
    )


@pytest.mark.parametrize("segments", [None, [], {}, [None, "invalid", {}, {"text": "  "}]])
def test_no_nonempty_segments_preserves_full_plain_text_without_invented_labels(segments):
    plain = "First paragraph.\n\nSecond paragraph with exact words, dates: 20.10.2026."
    assert protocol(segments, text=plain) == plain


def test_long_plain_fallback_is_complete_after_readability_paragraph_breaks():
    words = [f"word{index}" for index in range(800)]
    result = protocol(None, text=" ".join(words))
    assert result.split() == words
    assert "Спикер" not in result


def test_malformed_and_empty_items_do_not_hide_valid_segments():
    assert protocol([
        None, {}, {"text": " "}, {"speaker": "a", "text": "First."},
        "invalid", {"speaker": "a", "text": "Second."}, {"text": "Third."},
    ]) == "Спикер 1:\nFirst.\n\nСпикер 1:\nSecond.\n\nСпикер не определён:\nThird."
