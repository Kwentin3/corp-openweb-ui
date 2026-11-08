"""Read-only projections of pinned LiteLLM 1.105.1 durable spend APIs.

Owner -> contract -> consumer:
native spend ledger -> session/UI or raw v2 GET -> this display projection.
Gateway-validated spend_logs_metadata.owui_budget supplies attribution, never
prices. The caller owns native WebUI authentication/Chat ACL validation and
passes its shared aiohttp session and server-held native viewer/admin key.
No provider calls, local ledger, tariff calculation or application imports.

Source: LiteLLM d665dc1a6315847fcad6cc2c1264ceb47c06abce,
spend_management_endpoints.py4505..4617. The exact session endpoint
returns uncapped counts plus rows, not session_total_spend. Admin-viewer sees
all users in a session; every row is therefore checked here, never filtered out.
Use a native proxy_admin_viewer user and a key restricted to exactly this GET
route (not key_type=read_only, which selects the info_routes preset).
The separate admin presence reader uses native /spend/logs/v2 with exact current
assignment filters and explicit UTC observation dates. One owned persisted
unknown marker proves presence; a negative search never proves known/zero cost,
history completeness, a billing period, or the reason for a native key block.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException, Inexact, localcontext
import json
import re
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from aiohttp import ClientError, ClientSession, ClientTimeout
from employee_budget_provenance import ProtocolError, validate_persisted_scope


SESSION_ROUTE = "/spend/logs/session/ui"
ADMIN_ROUTE = "/spend/logs/v2"
PAGE_SIZE = 100
MAX_PAGES = 100
MAX_PAGE_BYTES = 2 * 1024 * 1024
log = logging.getLogger(__name__)


class CostReadError(Exception):
    """Safe code only: never include endpoint bodies, URLs, keys or raw rows."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _UnstablePagination(CostReadError):
    """Discard the entire scan; native count and row reads are separate."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__("incomplete_pagination")


@dataclass(frozen=True)
class ModelCost:
    model: str
    spend: Decimal
    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class CostTotal:
    # None means no durable row; absence is never verified zero expense.
    spend: Decimal | None
    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    models: tuple[ModelCost, ...]


@dataclass(frozen=True)
class CostSnapshot:
    user_id: str
    root_chat_id: str
    root_answer_id: str
    answer: CostTotal
    chat: CostTotal
    as_of: datetime
    pending: bool
    # complete concerns ONLY the supplied observed request/call IDs. It never
    # certifies unknown/error/background calls or future work in this chat.
    complete: bool
    missing_request_ids: tuple[str, ...]
    pagination_complete: Literal[True] = True
    coverage: Literal["observed_requests_only", "observed_calls_only", "observed_requests_and_calls_only"] = "observed_requests_only"
    currency: Literal["USD"] = "USD"
    missing_call_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdminUnknownPresence:
    """An existence witness only. False means unconfirmed, never known/free."""
    user_id: str
    model: str
    observation_start: datetime
    observation_end: datetime
    unknown_confirmed: bool
    scanned_rows: int
    reason: str
    as_of: datetime
    # No result claims a complete history/financial scan, including an early
    # witness return or a negative scan that exhausted the current pages.
    pagination_complete: Literal[False] = False
    final: Literal[False] = False
    coverage: Literal["observed_native_rows_only"] = "observed_native_rows_only"


@dataclass(frozen=True)
class _Row:
    request_id: str
    call_id: str
    root_answer_id: str
    model: str
    spend: Decimal
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CostReadError(code)


def _text(value: object) -> str:
    _require(isinstance(value, str) and 0 < len(value) <= 512
             and value == value.strip() and all(ord(c) >= 32 for c in value),
             "invalid_scope")
    return value


def _reader_configuration(base_url: str, key: str, max_pages: int) -> None:
    try:
        parsed = urlsplit(base_url)
        valid_url = (parsed.scheme in ("http", "https") and bool(parsed.hostname)
                     and parsed.username is None and parsed.password is None
                     and not parsed.query and not parsed.fragment)
    except (ValueError, TypeError):
        valid_url = False
    _require(valid_url, "invalid_configuration")
    _require(isinstance(key, str) and bool(key) and "\r" not in key and "\n" not in key,
             "invalid_configuration")
    _require(type(max_pages) is int and 1 <= max_pages <= MAX_PAGES, "invalid_configuration")


def _integer(value: object, code: str = "invalid_usage") -> int:
    _require(type(value) is int and value >= 0, code)
    return value


def _call_id(value: object) -> str:
    value = _text(value)
    try:
        _require(str(UUID(value)) == value, "invalid_scope")
    except ValueError:
        raise CostReadError("invalid_scope") from None
    return value


def _money(value: object) -> Decimal:
    _require(type(value) in (int, float, str, Decimal), "invalid_spend")
    _require(len(str(value)) <= 128, "invalid_spend")
    try:
        amount = Decimal(str(value))
    except (DecimalException, ValueError):
        raise CostReadError("invalid_spend") from None
    _require(amount.is_finite() and amount >= 0, "invalid_spend")
    return amount


def _sum_spend(rows: list[_Row]) -> Decimal:
    # SpendLogs.spend is a native Float (schema.prisma707). This precision
    # covers the entire finite double range plus 10,000 rows, including tiny
    # charges alongside large ones. Never silently round malformed extremes.
    try:
        with localcontext() as context:
            context.prec = 1024
            context.traps[Inexact] = True
            return sum((row.spend for row in rows), Decimal(0))
    except DecimalException:
        raise CostReadError("invalid_spend") from None


def _usage_unavailable(metadata: dict) -> bool:
    information = metadata.get("guardrail_information")
    if information is None:
        return False
    _require(isinstance(information, list), "accounting_unavailable")
    unknown = False
    for guardrail in information:
        _require(isinstance(guardrail, dict), "accounting_unavailable")
        if guardrail.get("guardrail_name") != "owui_budget_usage":
            continue
        categories = guardrail.get("violation_categories")
        action = guardrail.get("guardrail_action")
        _require(isinstance(categories, list)
                 and all(isinstance(value, str) and bool(value) for value in categories)
                 and action in ("allow", "block", "block_failed"), "accounting_unavailable")
        if "usage_unavailable" in categories:
            _require(action in ("block", "block_failed"), "accounting_unavailable")
            unknown = True
        else:
            _require(action == "allow", "accounting_unavailable")
    return unknown


def _usage_available(metadata: dict) -> None:
    _require(not _usage_unavailable(metadata), "usage_unavailable")


def _attribution(raw: object, user_id: str, chat_id: str) -> dict:
    _require(isinstance(raw, dict), "invalid_row")
    _require(raw.get("user") == user_id and raw.get("session_id") == chat_id,
             "foreign_scope")
    metadata = raw.get("metadata")
    _require(isinstance(metadata, dict), "invalid_attribution")
    spend_metadata = metadata.get("spend_logs_metadata")
    _require(isinstance(spend_metadata, dict), "invalid_attribution")
    try:
        scope = validate_persisted_scope(spend_metadata.get("owui_budget"))
    except ProtocolError:
        raise CostReadError("invalid_attribution") from None
    _require(scope.get("user_id") == user_id and scope.get("root_chat_id") == chat_id,
             "foreign_scope")
    return scope


def _usage_numbers(raw: dict) -> tuple[int, int, int, Decimal]:
    prompt = _integer(raw.get("prompt_tokens"))
    completion = _integer(raw.get("completion_tokens"))
    total = _integer(raw.get("total_tokens"))
    _require(total == prompt + completion, "invalid_usage")
    return prompt, completion, total, _money(raw.get("spend"))


def _row(raw: object, user_id: str, chat_id: str) -> _Row:
    scope = _attribution(raw, user_id, chat_id)
    metadata = raw["metadata"]
    # This native guardrail's typed telemetry is meaningful only after the
    # existing row owner and signed scope checks. An estimated positive spend
    # cannot make its unavailable Usage a confirmed amount.
    _usage_available(metadata)
    # Native writer defaults missing cost/usage to zero (utils797..800), and
    # absent metadata.status to success1720..1731. Failure cost-debug data is
    # not guaranteed in this endpoint's whitelisted metadata. Until a native
    # zero-cost qualification exists, never present these defaults as free.
    _require(raw.get("status") == "success"
             and metadata.get("status") in (None, "success")
             and metadata.get("error_information") is None
             and metadata.get("response_cost_failure_debug_info") is None
             and metadata.get("response_cost_failure_debug_information") is None,
             "accounting_unavailable")
    prompt, completion, total, spend = _usage_numbers(raw)
    _require(spend > 0 and total > 0, "accounting_unavailable")
    return _Row(_text(raw.get("request_id")), scope["call_id"], scope["root_answer_id"], scope["model"],
                spend, prompt, completion, total)


def _total(rows: list[_Row]) -> CostTotal:
    grouped: dict[str, list[_Row]] = {}
    for row in rows:
        grouped.setdefault(row.model, []).append(row)
    models = tuple(ModelCost(model, _sum_spend(group), len(group),
                             sum(r.prompt_tokens for r in group),
                             sum(r.completion_tokens for r in group),
                             sum(r.total_tokens for r in group))
                   for model, group in sorted(grouped.items()))
    return CostTotal(_sum_spend(rows) if rows else None,
                     len(rows), sum(r.prompt_tokens for r in rows),
                     sum(r.completion_tokens for r in rows), sum(r.total_tokens for r in rows),
                     models)


async def _get_page(session: ClientSession, url: str, key: str, params: dict,
                    request_timeout: float) -> dict:
    try:
        async with session.get(url, params=params,
                               headers={"Authorization": f"Bearer {key}"},
                               allow_redirects=False,
                               timeout=ClientTimeout(total=request_timeout)) as response:
            _require(response.status == 200, "spend_api_unavailable")
            raw = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                raw.extend(chunk)
                _require(len(raw) <= MAX_PAGE_BYTES, "response_too_large")
            # Decimal parsing preserves JSON's decimal representation, rather
            # than introducing another binary-float round trip in the adapter.
            value = json.loads(raw, parse_float=Decimal)
            _require(isinstance(value, dict), "invalid_pagination")
            return value
    except CostReadError:
        raise
    except asyncio.TimeoutError:
        # Preserve the bounded-wait terminal: the caller may already hold a
        # valid pending snapshot. Other HTTP/schema errors still fail closed.
        raise
    except (ClientError, ValueError, UnicodeError, DecimalException):
        raise CostReadError("spend_api_unavailable") from None


async def _page(session: ClientSession, url: str, key: str, chat_id: str,
                page: int, request_timeout: float) -> dict:
    return await _get_page(session, url, key, {"session_id": chat_id, "page": page,
                                              "page_size": PAGE_SIZE}, request_timeout)


def _validated_page(payload: dict, page: int, max_pages: int,
                    first_counts: tuple[int, int] | None) -> tuple[list, tuple[int, int]]:
    total = _integer(payload.get("total"), "invalid_pagination")
    pages = _integer(payload.get("total_pages"), "invalid_pagination")
    _require(payload.get("total_is_capped", False) is False, "incomplete_pagination")
    _require(type(payload.get("page")) is int and payload["page"] == page
             and type(payload.get("page_size")) is int and payload["page_size"] == PAGE_SIZE
             and pages == (total + PAGE_SIZE - 1) // PAGE_SIZE, "invalid_pagination")
    _require(pages <= max_pages and total <= max_pages * PAGE_SIZE, "incomplete_pagination")
    counts = (total, pages)
    if first_counts is not None and counts != first_counts:
        raise _UnstablePagination("counts_changed")
    data = payload.get("data")
    _require(isinstance(data, list), "invalid_pagination")
    expected = min(PAGE_SIZE, max(0, total - (page - 1) * PAGE_SIZE))
    if len(data) != expected:
        raise _UnstablePagination("page_length_changed")
    return data, counts


async def _rows(session: ClientSession, url: str, key: str, user_id: str,
                chat_id: str, request_timeout: float, max_pages: int) -> list[_Row]:
    rows: list[_Row] = []
    ids: set[str] = set()
    first_counts: tuple[int, int] | None = None
    page = 1
    while True:
        payload = await _page(session, url, key, chat_id, page, request_timeout)
        data, first_counts = _validated_page(payload, page, max_pages, first_counts)
        total, pages = first_counts
        for raw in data:
            row = _row(raw, user_id, chat_id)
            _require(row.request_id not in ids, "duplicate_request_id")
            ids.add(row.request_id)
            rows.append(row)
        if page >= pages:
            _require(len(rows) == total, "incomplete_pagination")
            return rows
        page += 1


async def read_cost_snapshot(
    session: ClientSession, *, base_url: str, read_key: str, user_id: str,
    root_chat_id: str, root_answer_id: str,
    observed_request_ids: Collection[str] = (), observed_call_ids: Collection[str] = (),
    timeout_seconds: float = 10.0,
    wait_seconds: float = 0.0, poll_interval: float = 0.2, max_pages: int = MAX_PAGES,
) -> CostSnapshot:
    """Read accrued USD amounts; optionally await supplied request IDs/call nonces.

    base_url is the trusted native proxy management base (without /v1 inference
    suffix), not a URL supplied by an employee. Total operation is bounded by
    timeout_seconds; missing IDs at the bound return pending after a valid scan.
    If no valid scan completed, failures raise a safe CostReadError. Offset
    pagination is not a database snapshot: changed counts/row lengths discard
    the whole scan and may retry inside the requested wait bound. Capped,
    malformed, duplicate or foreign rows fail closed. Equal counts alone do not
    prove concurrent-write isolation.
    """
    _reader_configuration(base_url, read_key, max_pages)
    for value in (timeout_seconds, wait_seconds, poll_interval):
        _require(type(value) in (int, float) and Decimal(str(value)).is_finite(),
                 "invalid_configuration")
    _require(0 < timeout_seconds <= 60 and 0 <= wait_seconds <= timeout_seconds
             and 0 < poll_interval <= 5, "invalid_configuration")
    user_id, root_chat_id, root_answer_id = map(_text, (user_id, root_chat_id, root_answer_id))
    _require(not isinstance(observed_request_ids, (str, bytes)), "invalid_scope")
    _require(isinstance(observed_request_ids, Collection), "invalid_scope")
    _require(len(observed_request_ids) <= MAX_PAGES * PAGE_SIZE, "invalid_scope")
    expected_ids = {_text(value) for value in observed_request_ids}
    _require(len(expected_ids) <= MAX_PAGES * PAGE_SIZE, "invalid_scope")
    _require(not isinstance(observed_call_ids, (str, bytes)) and isinstance(observed_call_ids, Collection),
             "invalid_scope")
    _require(len(observed_call_ids) <= MAX_PAGES * PAGE_SIZE, "invalid_scope")
    expected_calls = {_call_id(value) for value in observed_call_ids}
    _require(len(expected_ids) + len(expected_calls) <= MAX_PAGES * PAGE_SIZE, "invalid_scope")
    coverage = ("observed_requests_and_calls_only" if expected_ids else "observed_calls_only"
                ) if expected_calls else "observed_requests_only"
    url = base_url.rstrip("/") + SESSION_ROUTE
    loop = asyncio.get_running_loop()
    wait_until = loop.time() + wait_seconds
    latest: CostSnapshot | None = None
    restarted: set[str] = set()
    try:
        async with asyncio.timeout(timeout_seconds):
            while True:
                try:
                    rows = await _rows(session, url, read_key, user_id, root_chat_id,
                                       timeout_seconds, max_pages)
                except _UnstablePagination as error:
                    if loop.time() >= wait_until:
                        raise
                    if error.reason not in restarted:
                        # Fixed stage only: no scope IDs, counts, rows or secrets.
                        log.info("Budget cost snapshot scan restarted: %s", error.reason)
                        restarted.add(error.reason)
                    await asyncio.sleep(min(poll_interval, max(0, wait_until - loop.time())))
                    continue
                by_id = {r.request_id: r for r in rows}
                _require(all(by_id[rid].root_answer_id == root_answer_id
                             for rid in expected_ids & by_id.keys()), "foreign_answer")
                _require(all(row.root_answer_id == root_answer_id for row in rows
                             if row.call_id in expected_calls), "foreign_answer")
                missing = tuple(sorted(expected_ids - by_id.keys()))
                missing_calls = tuple(sorted(expected_calls - {row.call_id for row in rows}))
                covered = bool(expected_ids or expected_calls) and not missing and not missing_calls
                latest = CostSnapshot(user_id, root_chat_id, root_answer_id,
                                      _total([r for r in rows if r.root_answer_id == root_answer_id]),
                                      _total(rows), datetime.now(timezone.utc), not covered, covered, missing,
                                      coverage=coverage, missing_call_ids=missing_calls)
                if not (expected_ids or expected_calls) or covered or loop.time() >= wait_until:
                    return latest
                await asyncio.sleep(min(poll_interval, max(0, wait_until - loop.time())))
    except asyncio.TimeoutError:
        if latest is not None:
            return latest
        raise CostReadError("spend_api_unavailable") from None


async def read_admin_unknown_presence(
    session: ClientSession, *, base_url: str, admin_key: str, user_id: str,
    model: str, assignment_hash: str, observation_start: datetime, observation_end: datetime,
    timeout_seconds: float = 10.0, max_pages: int = MAX_PAGES,
) -> AdminUnknownPresence:
    """Look for a durable unknown marker for one SERVER-OWNED current assignment.

    The caller owns admin authority and explicit aware-UTC whole-second query
    dates (native v2 requires dates and uses an inclusive end). These are query
    bounds, not verified event-time coverage or a billing month. Returned event
    timestamps are not validated here. No calendar or monetary calculation
    occurs here. The latest rows are examined first within page/byte/time bounds.

    One owned valid marker proves presence even if other rows or pagination
    are bad/capped. Without a witness, every outcome is unconfirmed/unavailable:
    retention, rotation, late writes and clock skew prevent an absence proof.
    Consumers must map True to unknown and False to unavailable, never known or
    zero. Native counters and blocked status remain separate native readbacks.
    """
    _reader_configuration(base_url, admin_key, max_pages)
    _require(type(timeout_seconds) in (int, float) and Decimal(str(timeout_seconds)).is_finite()
             and 0 < timeout_seconds <= 60, "invalid_configuration")
    user_id, model = _call_id(user_id), _text(model)
    _require(len(model) <= 256 and isinstance(assignment_hash, str)
             and re.fullmatch(r"[0-9a-f]{64}", assignment_hash) is not None, "invalid_scope")
    for boundary in (observation_start, observation_end):
        _require(isinstance(boundary, datetime) and boundary.tzinfo is not None
                 and boundary.utcoffset() == timedelta(0) and boundary.microsecond == 0,
                 "invalid_observation_range")
    _require(observation_start < observation_end, "invalid_observation_range")
    params = {"user_id": user_id, "api_key": assignment_hash, "model_group": model,
        "start_date": observation_start.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": observation_end.strftime("%Y-%m-%d %H:%M:%S"),
        "page_size": PAGE_SIZE, "sort_by": "startTime", "sort_order": "desc", "group_by_session": "false"}
    scanned = 0
    invalid_rows = False
    counts = None

    def result(confirmed: bool, reason: str) -> AdminUnknownPresence:
        return AdminUnknownPresence(user_id, model, observation_start, observation_end,
                                    confirmed, scanned, reason, datetime.now(timezone.utc))

    try:
        async with asyncio.timeout(timeout_seconds):
            for page in range(1, max_pages + 1):
                payload = await _get_page(session, base_url.rstrip("/") + ADMIN_ROUTE, admin_key,
                                          {**params, "page": page}, timeout_seconds)
                data = payload.get("data")
                _require(isinstance(data, list), "invalid_pagination")
                # An existence witness is independent of total/page metadata.
                # Even a malformed oversized list cannot cause unbounded work.
                for raw in data[:PAGE_SIZE]:
                    scanned += 1
                    try:
                        _require(isinstance(raw, dict), "invalid_row")
                        _text(raw.get("request_id"))
                        _require(raw.get("api_key") == assignment_hash and raw.get("model_group") == model,
                                 "foreign_scope")
                        _text(raw.get("model"))  # Opaque provider model, never decoded into an alias.
                        chat_id = _call_id(raw.get("session_id"))
                        scope = _attribution(raw, user_id, chat_id)
                        _require(scope["model"] == model, "foreign_scope")
                        if _usage_unavailable(raw["metadata"]):
                            return result(True, "usage_unavailable")
                    except CostReadError:
                        invalid_rows = True
                _require(payload.get("total_is_capped") is False, "incomplete_pagination")
                # Reuse the native page validator without treating the search
                # budget as a claim that all native history fits inside it.
                native_pages = _integer(payload.get("total_pages"), "invalid_pagination")
                _, counts = _validated_page(payload, page, max(max_pages, native_pages), counts)
                if page >= counts[1]:
                    return result(False, "accounting_unavailable" if invalid_rows else "not_proven")
            return result(False, "incomplete_pagination")
    except asyncio.TimeoutError:
        return result(False, "spend_api_unavailable")
    except CostReadError as error:
        return result(False, error.code)
