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
import ast
import hashlib
import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException, Inexact, localcontext
import json
import re
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit
from uuid import UUID

from aiohttp import ClientError, ClientSession, ClientTimeout
from employee_budget_provenance import ProtocolError, validate_persisted_scope

if TYPE_CHECKING:
    from employee_budget_admin_contract import EmployeeBudget


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
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class CostTotal:
    # None means no durable row; absence is never verified zero expense.
    spend: Decimal | None
    calls: int
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
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
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


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


def _usage_numbers(raw: dict) -> tuple[int | None, int | None, int | None, Decimal]:
    # Native money is authoritative independently of optional token telemetry.
    values = tuple(value if type(value) is int and value >= 0 else None
                   for value in (raw.get("prompt_tokens"), raw.get("completion_tokens"), raw.get("total_tokens")))
    if all(value is not None for value in values) and values[2] != values[0] + values[1]:
        values = (None, None, None)
    return *values, _money(raw.get("spend"))


def _row(raw: object, user_id: str, chat_id: str) -> _Row:
    scope = _attribution(raw, user_id, chat_id)
    metadata = raw["metadata"]
    # The native ledger owns cost, without an application guardrail witness.
    # Explicit failures remain unsuitable. Native default all-zero cost/usage
    # is ambiguous; it must not turn unavailable accounting into a free answer.
    _require(raw.get("status") == "success"
             and metadata.get("status") in (None, "success")
             and metadata.get("error_information") is None
             and metadata.get("response_cost_failure_debug_info") is None
             and metadata.get("response_cost_failure_debug_information") is None,
             "accounting_unavailable")
    prompt, completion, total, spend = _usage_numbers(raw)
    _require(spend > 0 or total is not None and total > 0, "accounting_unavailable")
    return _Row(_text(raw.get("request_id")), scope["call_id"], scope["root_answer_id"], scope["model"],
                spend, prompt, completion, total)


def _total(rows: list[_Row]) -> CostTotal:
    def tokens(group, field):
        values = [getattr(row, field) for row in group]
        return sum(values) if all(value is not None for value in values) else None

    grouped: dict[str, list[_Row]] = {}
    for row in rows:
        grouped.setdefault(row.model, []).append(row)
    models = tuple(ModelCost(model, _sum_spend(group), len(group),
                             tokens(group, "prompt_tokens"),
                             tokens(group, "completion_tokens"),
                             tokens(group, "total_tokens"))
                   for model, group in sorted(grouped.items()))
    return CostTotal(_sum_spend(rows) if rows else None,
                     len(rows), tokens(rows, "prompt_tokens"),
                     tokens(rows, "completion_tokens"), tokens(rows, "total_tokens"),
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


async def read_unknown_presence(
    session: ClientSession, *, base_url: str, admin_key: str,
    states: Mapping[str, EmployeeBudget], timeout_seconds: float = 5.0, max_pages: int = 2,
) -> dict[str, dict[str, dict]]:
    """Bounded presence-only reads of caller-verified native budget DTOs.

    The caller retains authentication/model ACL and current assignment ownership.
    Historical query bounds are not a billing month. False or failed reads never
    establish known cost, zero, completeness or available funds.
    """
    _reader_configuration(base_url, admin_key, max_pages)
    _require(type(timeout_seconds) in (int, float) and Decimal(str(timeout_seconds)).is_finite()
             and 0 < timeout_seconds <= 60, "invalid_configuration")
    _require(isinstance(states, Mapping), "invalid_scope")
    for uid, state in states.items():
        _call_id(uid)
        models = [model.model for model in state.models]
        _require(state.user_id == uid and len(models) == len(set(models)), "invalid_scope")
    observations = {uid: {} for uid in states}
    start = datetime(1970, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    end = now.replace(microsecond=0) + timedelta(seconds=bool(now.microsecond))
    semaphore = asyncio.Semaphore(4)

    async def observe(uid, model):
        try:
            async with semaphore:
                value = await read_admin_unknown_presence(session, base_url=base_url, admin_key=admin_key,
                    user_id=uid, model=model.model, assignment_hash=model.key_hash,
                    observation_start=start, observation_end=end,
                    timeout_seconds=timeout_seconds, max_pages=max_pages)
            if (type(value) is AdminUnknownPresence and value.user_id == uid and value.model == model.model
                    and value.observation_start == start and value.observation_end == end
                    and type(value.unknown_confirmed) is bool and isinstance(value.as_of, datetime)
                    and value.as_of.tzinfo is not None and value.as_of.utcoffset() == timedelta(0)):
                observations[uid][model.model] = {"unknown_confirmed": value.unknown_confirmed,
                                                 "as_of": value.as_of.isoformat()}
        except Exception:
            # Failed/unsupported evidence stays unavailable; no raw native data escapes.
            pass

    tasks = [asyncio.create_task(observe(uid, model)) for uid, state in states.items() for model in state.models]
    if tasks:
        try:
            await asyncio.wait(tasks, timeout=timeout_seconds)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    return observations


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


def _overview_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None
        return parsed.astimezone(timezone.utc) if parsed is not None and parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _overview_rate(value):
    try:
        return _money(value) if type(value) in (str, int, float, Decimal) else None
    except CostReadError:
        return None


def _financial_refusal(metadata):
    """Read explicit provider payment refusal; never infer an account balance."""
    info = metadata.get("error_information")
    if not isinstance(info, dict) or not info.get("llm_provider"):
        return False
    # Native402 is Payment Required even when SDK transport omits its body.
    # Generic rate limits and native employee budget denials do not qualify.
    code = info.get("error_code")
    if type(code) in (str, int) and code in ("402", 402):
        return True
    message = info.get("error_message")
    if not isinstance(message, str) or len(message) > 32768:
        return False
    # LiteLLM prefixes the upstream JSON with its exception/provider name.
    # Decode one object rather than searching quoted words in echoed input.
    try:
        body = message[message.index("{"):]
        try:
            payload, _ = json.JSONDecoder().raw_decode(body)
        except ValueError:
            # SDK error strings also use Python's dictionary representation.
            # Parse bounded literal data only; never execute provider text.
            # Pinned Router appends this explanation to exception.message.
            # SDK dict repr is one literal; the native prose is not part of it.
            payload = ast.literal_eval(body.split("\n\nLiteLLM: model group ", 1)[0])
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return False
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return False
    codes = {"insufficient_quota", "insufficient_balance", "balance_not_enough",
             "credit_balance_too_low", "billing_hard_limit_reached", "insufficient_credits",
             "payment_required", "credit_balance_exhausted"}
    return any(isinstance(error.get(key), str) and error[key] in codes for key in ("code", "type"))


def _overview_event(raw, deployment):
    """Representation of one native event, never a credential or error body."""
    if not isinstance(raw, dict) or raw.get("model_id") != deployment["id"]:
        return None
    observed = _overview_time(raw.get("endTime"))
    started = _overview_time(raw.get("startTime"))
    metadata = raw.get("metadata")
    if observed is None or started is None or started > observed or not isinstance(metadata, dict):
        return None
    if raw.get("cache_hit") not in (False, "False", "false"):
        return None
    if raw.get("status") == "failure" and _financial_refusal(metadata):
        return (observed, started, "financial_refusal", raw)
    if (raw.get("status") != "success" or metadata.get("status") not in (None, "success")
            or metadata.get("error_information") is not None
            or type(metadata.get("attempted_fallbacks")) is not int
            or metadata["attempted_fallbacks"] != 0):
        return None
    try:
        _, _, total, spend = _usage_numbers(raw)
    except CostReadError:
        return None
    if spend <= 0:
        return None
    return (observed, started, "success", raw)


async def read_admin_overview(session: ClientSession, *, base_url: str, admin_key: str,
                              models: dict, configsnapshots: dict) -> dict:
    """Native applied prices and bounded provider observations for admin display.

    Reads are at most model/info, cost-map/source and two spend pages in five
    seconds. No background polling, charges, account journal or enforcement.
    Account ids are protected model metadata, otherwise exact deployment ids.
    Explicit deployment ids must be immutable across credential changes; absent
    that deployment-lifecycle guarantee a later success cannot clear a refusal.
    """
    _reader_configuration(base_url, admin_key, 2)
    _require(isinstance(models, dict) and 0 < len(models) <= 100
             and all(isinstance(k, str) and isinstance(v, str) for k, v in models.items())
             and isinstance(configsnapshots, dict), "invalid_configuration")
    now = datetime.now(timezone.utc)
    as_of = now.isoformat()
    prices = [{"id": wire, "label": label, "input_per_million": None,
               "output_per_million": None, "cache_per_million": None,
               "as_of": None, "source": "unknown", "changed": False}
              for wire, label in models.items()]
    result = {"prices": prices, "accounts": [], "as_of": as_of,
              "coverage": "observed_native_rows_only", "complete": False}
    try:
        async with asyncio.timeout(5):
            catalog = await _get_page(session, base_url.rstrip("/") + "/model/info", admin_key, {}, 5)
            rows = catalog.get("data")
            _require(isinstance(rows, list) and len(rows) <= 1000, "invalid_native_models")
            deployments = {}
            for raw in rows:
                if not isinstance(raw, dict) or raw.get("model_name") not in models:
                    continue
                info = raw.get("model_info")
                if not isinstance(info, dict):
                    continue
                identity = info.get("id")
                if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", identity):
                    continue
                account = info.get("owui_billing_account_id", identity)
                if not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", account):
                    continue
                _require(identity not in deployments and len(deployments) < 100, "ambiguous_native_deployment")
                deployments[identity] = {"id": identity, "account": account, "wire": raw["model_name"],
                    "info": info, "events": [],
                    "grouped": "owui_billing_account_id" in info,
                    "immutable": info.get("owui_billing_immutable_deployment_id") is True}
            for deployment in deployments.values():
                if any(a["id"] == deployment["account"] for a in result["accounts"]):
                    continue
                account = deployment["account"]
                snapshot = configsnapshots.get(account)
                snapshot = snapshot if isinstance(snapshot, dict) else {}
                revision = hashlib.sha256(json.dumps({"account_id": account, "snapshot": snapshot},
                    sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                balance = {field: snapshot.get(field) for field in
                           ("amount", "currency", "observed_at", "actor", "source")} if snapshot else None
                label = deployment["info"].get("owui_billing_account_label")
                label = label if isinstance(label, str) and 0 < len(label) <= 128 and all(ord(c) >= 32 for c in label) else models[deployment["wire"]]
                result["accounts"].append({"id": account, "label": label, "status": "unknown",
                    "event_at": None, "balance": balance, "revision": revision})
            try:
                source = await _get_page(session, base_url.rstrip("/") + "/model/cost_map/source", admin_key, {}, 5)
            except CostReadError:
                source = {}
            loaded = _overview_time(source.get("loaded_at"))
            source_kind = source.get("source") if source.get("source") in ("local", "remote") else "unknown"
            for price in prices:
                selected = [d for d in deployments.values() if d["wire"] == price["id"]]
                for public, field in (("input_per_million", "input_cost_per_token"),
                                      ("output_per_million", "output_cost_per_token"),
                                      ("cache_per_million", "cache_read_input_token_cost")):
                    rates = [_overview_rate(d["info"].get(field)) for d in selected]
                    if rates and all(rate is not None and rate == rates[0] for rate in rates):
                        price[public] = str(rates[0] * 1_000_000)
                price.update(as_of=loaded.isoformat() if loaded else None, source=source_kind)
            if not deployments:
                return result
            counts, seen = None, set()
            for page_number in (1, 2):
                params = {"page": page_number, "page_size": PAGE_SIZE,
                          "start_date": (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
                          "end_date": now.strftime("%Y-%m-%d %H:%M:%S"),
                          "sort_by": "startTime", "sort_order": "desc"}
                if len(deployments) == 1:
                    params["model_id"] = next(iter(deployments))
                payload = await _get_page(session, base_url.rstrip("/") + ADMIN_ROUTE, admin_key, params, 5)
                native_pages = _integer(payload.get("total_pages"), "invalid_pagination")
                data, counts = _validated_page(payload, page_number, max(2, native_pages), counts)
                for raw in data:
                    _require(isinstance(raw, dict), "invalid_native_row")
                    request_id = _text(raw.get("request_id"))
                    _require(request_id not in seen, "unstable_native_rows")
                    seen.add(request_id)
                    deployment = deployments.get(raw.get("model_id"))
                    if deployment is not None:
                        event = _overview_event(raw, deployment)
                        if event is not None and now - timedelta(days=7) <= event[1] <= event[0] <= now:
                            deployment["events"].append(event)
                if page_number >= counts[1]:
                    result["complete"] = True
                    break
            # Incomplete observation never announces recovery or absence of a
            # refusal; known evidence remains available in the native journal.
            if not result["complete"]:
                return result
            for account in result["accounts"]:
                members = [d for d in deployments.values() if d["account"] == account["id"]]
                events = [(event, deployment) for deployment in members for event in deployment["events"]]
                successes = [event for event, _ in events if event[2] == "success"]
                refusals = []
                for failure, failed_deployment in events:
                    if failure[2] != "financial_refusal":
                        continue
                    recovered = any(success[2] == "success" and success[1] > failure[0]
                        and failed_deployment["immutable"] and paid_deployment["immutable"]
                        and (paid_deployment["id"] == failed_deployment["id"]
                             or failed_deployment["grouped"] and paid_deployment["grouped"])
                        for success, paid_deployment in events)
                    if not recovered:
                        refusals.append(failure)
                for deployment in members:
                    events = sorted(deployment["events"], key=lambda e: e[0])
                    # Compare only qualified native billed rates for the same
                    # deployment; it is an observed difference, not a timeline.
                    for event in reversed(events):
                        if event[2] != "success":
                            continue
                        if loaded is not None and event[0] >= loaded:
                            continue  # Compare with usage before this catalog load.
                        metadata = event[3]["metadata"].get("spend_logs_metadata")
                        billed = metadata.get("owui_billed_token_rates") if isinstance(metadata, dict) else None
                        rates = billed.get("rates") if isinstance(billed, dict) and billed.get("availability") == "available" else None
                        if not isinstance(rates, dict):
                            continue
                        fields = ("input_cost_per_token", "output_cost_per_token")
                        old = [_overview_rate(rates.get(field)) for field in fields]
                        current = [_overview_rate(deployment["info"].get(field)) for field in fields]
                        if all(rate is not None for rate in old + current) and old != current:
                            next(p for p in prices if p["id"] == deployment["wire"])["changed"] = True
                        break
                event = max(refusals or successes, key=lambda e: e[0], default=None)
                if event is not None:
                    account.update(status="financial_refusal" if refusals else "success", event_at=event[0].isoformat())
            return result
    except (CostReadError, asyncio.TimeoutError):
        for account in result["accounts"]:
            account.update(status="unknown", event_at=None)
        result["complete"] = False
        return result
