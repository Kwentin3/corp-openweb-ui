#!/usr/bin/env python3
"""Delete one owned synthetic chat and compare actual native PostgreSQL rows.

Host stdlib coordinator; run only after the existing disposable proof phases.
No inference, reset, repair, new ledger, or direct database mutation is issued.
Full raw rows and saved chat are retained only in --private-output (0600),
under PROOF_PRIVATE_DIR from --env-file and outside uploaded --output.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, build_opener
from uuid import UUID

from prove_native_budgets import NoRedirects, ProofError, require


ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 1000
BODY_FIELDS = ("messages", "response", "proxy_server_request")
CREDENTIAL = re.compile(r"(?:sk-|gw-)[A-Za-z0-9_-]{24,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
STATE_PROJECTION = '''import json
from pathlib import Path
raw = Path('/proof-private/webui-state.private.json').read_bytes()
assert len(raw) <= 2097152
s = json.loads(raw)
assert s['schema'] == 1 and s['stage'] == 'setup_complete'
assert s['admin_fixture']['stage'] == s['bootstrap_fixture']['stage'] == 'setup_complete'
assert s['service_fixture']['stage'] == 'qualified_direct_title'
assert s['service_fixture']['task_config_restored'] is True
assert len(s['users']) == 2
print(json.dumps({'run_id': s['run_id'], 'staff_ids': [u['id'] for u in s['users']],
 'personal_ids': [u['id'] for u in s['users']] + [s['admin']['id'], s['bootstrap_fixture']['employee']['id']],
 'service_id': s['service_fixture']['payer_id']}))'''
PROVIDER_IDS = '''import json, urllib.request
raw = urllib.request.urlopen('http://127.0.0.1:8000/__proof/requests', timeout=5).read(8388609)
assert len(raw) <= 8388608
d = json.loads(raw)
assert d['synthetic'] is True and len(d['requests']) <= 1000
print(json.dumps([r['id'] for r in d['requests']]))'''
VALIDATE_ROOTS = '''import json, sys
from litellm.proxy.types_utils.utils import get_instance_fn
validate_persisted_scope = get_instance_fn('provenance.validate_persisted_scope', config_file_path='/proof/config.yaml')
data = json.loads(sys.argv[1])
assert 0 < len(data) <= 1000
print(json.dumps([{'request_id': x['request_id'], 'scope': validate_persisted_scope(x['scope'])} for x in data]))'''


def canonical(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    require(valid, "Noncanonical fixture UUID")
    return value


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def decode(raw):
    require(len(raw) <= MAX_BYTES, "Native observation exceeded byte bound")
    try:
        return json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise ProofError("Native observation was not finite JSON") from None


def native_url(value):
    try:
        u = urlsplit(value)
        address = ipaddress.ip_address(u.hostname or "")
        valid = (u.scheme == "http" and isinstance(address, ipaddress.IPv4Address) and address.is_private
                 and u.port == 8080 and u.path in ("", "/") and not u.username and not u.password
                 and not u.query and not u.fragment)
    except ValueError:
        valid = False
    require(valid, "Target must be the disposable private WebUI IPv4:8080")
    return value.rstrip("/")


def private_paths(env_file, accounts, output, private_output):
    """Bind raw evidence to the pre-existing private fixture root, never artifacts."""
    require(env_file.is_file() and env_file.stat().st_size <= 65536, "Private fixture env file unavailable")
    values = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        require(separator and name not in values, "Fixture env format is ambiguous")
        values[name] = value
    configured = Path(values.get("PROOF_PRIVATE_DIR", ""))
    require(configured.is_absolute() and configured.is_dir(), "Fixture private root unavailable")
    root = configured.resolve()
    public, raw, handoff = output.resolve(), private_output.resolve(), accounts.resolve()
    require((not output.exists() or output.is_dir()) and not (public / "ledger-retention.safe.json").exists(),
            "Safe retention receipt must have a new writable directory destination")
    require(raw != root and raw.is_relative_to(root) and raw.parent.is_dir()
            and handoff.is_relative_to(root) and accounts.is_file(), "Private evidence or handoff escaped fixture root")
    require(not public.is_relative_to(root) and not root.is_relative_to(public)
            and not env_file.resolve().is_relative_to(public), "Raw private evidence overlaps uploaded output")
    require(raw not in (handoff, env_file.resolve()) and not private_output.exists(), "Private evidence must be a new distinct file")
    if raw.is_relative_to(ROOT):
        try:
            ignored = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", str(raw.relative_to(ROOT))],
                                     cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.SubprocessError):
            raise ProofError("Cannot verify the in-workspace private evidence ignore") from None
        require(ignored.returncode == 0, "In-workspace raw evidence must be Git-ignored")
    if os.name == "posix":
        require(stat.S_IMODE(root.stat().st_mode) & 0o077 == 0
                and all(stat.S_IMODE(path.stat().st_mode) & 0o077 == 0 for path in (env_file, accounts)),
                "Fixture credentials/root permissions are not private")
    return root


def write_private(handle, observations):
    handle.seek(0)
    handle.write(encoded(observations))
    handle.truncate()
    handle.flush()
    os.fsync(handle.fileno())


def snapshot_sql(payers):
    ids = sorted({canonical(value) for value in payers})
    require(len(ids) == 5, "Expected four personal payers and one service payer")
    predicate = ",".join("'" + value + "'" for value in ids)
    parts = []
    for label, table, owner, identity in (("journal", "LiteLLM_SpendLogs", "user", "request_id"),
                                          ("users", "LiteLLM_UserTable", "user_id", "user_id"),
                                          ("keys", "LiteLLM_VerificationToken", "user_id", "token")):
        condition = '"' + owner + '" IN (' + predicate + ')'
        parts.extend(["'" + label + "_count', (SELECT count(*) FROM \"" + table + '\" WHERE ' + condition + ')',
                      "'" + label + "', COALESCE((SELECT jsonb_agg(to_jsonb(r) ORDER BY r.\"" + identity
                      + '\") FROM (SELECT * FROM "' + table + '" WHERE ' + condition
                      + ' ORDER BY "' + identity + '" LIMIT ' + str(MAX_ROWS + 1) + ") r), '[]'::jsonb)"])
    return ("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='5s'; "
            "WITH observation AS (SELECT jsonb_build_object(" + ",".join(parts) + ") AS payload) "
            "SELECT CASE WHEN octet_length(payload::text) <= " + str(MAX_BYTES)
            + " THEN payload ELSE jsonb_build_object('oversize',true) END FROM observation; COMMIT;")


def money(value):
    try:
        result = Decimal(str(value))
    except (ValueError, InvalidOperation):
        raise ProofError("Native financial amount missing") from None
    require(result.is_finite() and result >= 0, "Native financial amount invalid")
    return result


def normalize_snapshot(snapshot, payers):
    require(isinstance(snapshot, dict) and set(snapshot) == {"journal", "journal_count", "users", "users_count", "keys", "keys_count"},
            "Raw DB observation is incomplete or oversized")
    result = {}
    for table, identity in (("journal", "request_id"), ("users", "user_id"), ("keys", "token")):
        rows = snapshot[table]
        require(isinstance(rows, list) and type(snapshot[table + "_count"]) is int
                and len(rows) == snapshot[table + "_count"] <= MAX_ROWS, "Raw native rows were truncated")
        require(all(isinstance(row, dict) and isinstance(row.get(identity), str)
                    and 0 < len(row[identity]) <= 256 for row in rows), "Raw native row identity missing")
        require(len({row[identity] for row in rows}) == len(rows), "Duplicate raw native row identity")
        for row in rows:
            owner = row.get("user" if table == "journal" else "user_id")
            require(canonical(owner) in payers, "Raw row escaped selected fixture payer scope")
            money(row.get("spend"))
            if table == "journal":
                require(set(BODY_FIELDS) <= row.keys() and {"api_key", "metadata", "session_id", "model_group"} <= row.keys(),
                        "Raw cost row lost body or attribution columns")
            else:
                require({"max_budget", "budget_duration", "budget_reset_at", "models"} <= row.keys(), "Native counter state incomplete")
                money(row["max_budget"])
        result[table] = sorted(rows, key=lambda row: row[identity])
    require({row["user_id"] for row in result["users"]} == set(payers) and len(result["keys"]) == 9,
            "Expected complete five-payer/nine-key fixture counters")
    require(all(re.fullmatch(r"[0-9a-f]{64}", row["token"]) for row in result["keys"]), "Native key ID was not a hash")
    require(bool(result["journal"]), "Native fixture journal is empty")
    return result


def unwrapped(value):
    for _ in range(10):
        if not isinstance(value, str):
            return value
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return value
        if decoded == value:
            return value
        value = decoded
    raise ProofError("Native nested JSON exceeded depth bound")


def privacy_check(rows, private_texts):
    """Inspect every raw column/value, including recursively encoded JSON strings."""
    require(bool(private_texts) and all(isinstance(text, str) and text for text in private_texts), "Saved private source text unavailable")
    remaining = 100000
    def inspect(value, depth=0):
        nonlocal remaining
        remaining -= 1
        require(remaining >= 0 and depth <= 24, "Raw privacy scan exceeded structural bound")
        if isinstance(value, str):
            require(not CREDENTIAL.search(value), "Full credential found in raw selected cost rows")
            require(not any(value == text or len(text) >= 32 and text in value for text in private_texts),
                    "Chosen chat text found in raw selected cost rows")
            nested = unwrapped(value)
            if nested != value:
                inspect(nested, depth + 1)
        elif isinstance(value, dict):
            for key, child in value.items():
                # Scan names too, but short content matches only actual values.
                require(not CREDENTIAL.search(key), "Credential-bearing raw cost column/key")
                inspect(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                inspect(child, depth + 1)
    for row in rows:
        require(all(unwrapped(row[field]) in (None, {}, [], "") for field in BODY_FIELDS),
                "Native raw cost body fields contain stored prompt/response data")
        inspect(row)


def candidate_roots(snapshot, actor):
    candidates = []
    keys = {row["token"]: row for row in snapshot["keys"]}
    for row in snapshot["journal"]:
        if row["user"] != actor or money(row["spend"]) <= 0:
            continue
        metadata = unwrapped(row["metadata"])
        scope = (metadata.get("spend_logs_metadata") or {}).get("owui_budget") if isinstance(metadata, dict) else None
        if isinstance(scope, dict) and scope.get("category") == "personal":
            key = keys.get(row["api_key"])
            require(scope.get("user_id") == actor and scope.get("chat_id") == row["session_id"]
                    and scope.get("model") == row["model_group"] and key is not None
                    and key["user_id"] == actor and key["models"] == [scope["model"]],
                    "Native personal root attribution conflicts")
            candidates.append({"request_id": row["request_id"], "scope": scope})
    require(candidates, "No paid personal root exists for the authenticated actor")
    return candidates


def owned_chat(saved, scope, actor):
    chat_id, answer_id = canonical(scope["root_chat_id"]), canonical(scope["root_answer_id"])
    require(isinstance(saved, dict) and saved.get("id") == chat_id and saved.get("user_id") == actor
            and scope["user_id"] == actor and scope["chat_id"] == chat_id and scope["answer_id"] == answer_id,
            "Selected paid chat is not the actor's canonical personal root")
    require(not (saved.get("meta") or {}).get("internal"), "Only the ordinary fixture chat may be deleted")
    history = ((saved.get("chat") or {}).get("history") or {}).get("messages")
    require(isinstance(history, dict) and 0 < len(history) <= 100, "Saved native chat history missing or oversized")
    answer = history.get(answer_id)
    require(isinstance(answer, dict) and answer.get("id") == answer_id and answer.get("role") == "assistant"
            and answer.get("done") is True and not answer.get("error") and answer.get("content") == "Proof"
            and (answer.get("user_id") or actor) == actor, "Paid native root answer is not the completed synthetic fixture answer")
    texts = set()
    def content_text(value):
        if isinstance(value, str) and value:
            texts.add(value)
        elif isinstance(value, list):
            for part in value:
                content_text(part)
        elif isinstance(value, dict):
            # Content objects are private too; include their string values.
            for child in value.values():
                content_text(child)
    for message in history.values():
        require(isinstance(message, dict), "Malformed native saved message")
        canonical(message.get("id"))
        if message.get("role") == "user":
            require((message.get("user_id") or actor) == actor, "Native chat contains a foreign user message")
        content_text(message.get("content"))
    require(any(message.get("role") == "user" and message.get("content") == "Hi" for message in history.values()),
            "Selected native chat is not the existing synthetic Hi fixture")
    return sorted(texts)


def compare_snapshots(before, after):
    require(encoded(before["journal"]) == encoded(after["journal"]), "Chat deletion changed raw native cost rows/history")
    require(encoded(before["users"]) == encoded(after["users"]) and encoded(before["keys"]) == encoded(after["keys"]),
            "Chat deletion changed native payer/key identities, amounts or state")


class Fixture:
    def __init__(self, env_file):
        self.command = ["docker", "compose", "--env-file", str(env_file.resolve()), "-f", "compose/goal584.native-budget-proof.yml",
                        "-f", "compose/goal584.webui-proof.yml"]

    def observe(self, command, label):
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=45)
        except (OSError, subprocess.SubprocessError):
            raise ProofError("Native read-only observation command failed: " + label) from None
        if result.returncode != 0:
            # Never echo raw command/output: native failures can include private
            # rows or credentials. Classify only fixed, known exception markers.
            known = ((b"ModuleNotFoundError", "module_not_found"), (b"AssertionError", "fixture_assertion"),
                     (b"syntax error", "sql_syntax"), (b"does not exist", "missing_native_object"))
            code = next((value for marker, value in known if marker in result.stderr), "unclassified")
            raise ProofError("Native read-only observation failed: " + label + "/" + code
                             + " (exit " + str(result.returncode) + ")")
        return decode(result.stdout)

    def projection(self):
        return self.observe(self.command + ["exec", "-T", "proxy", "python", "-B", "-c", STATE_PROJECTION], "fixture_state")

    def snapshot(self, payers):
        sql = snapshot_sql(payers)
        raw = self.observe(self.command + ["exec", "-T", "postgres", "psql", "-U", "goal584", "-d", "goal584",
                                           "-X", "-A", "-t", "-q", "-v", "ON_ERROR_STOP=1", "-c", sql], "raw_db_snapshot")
        return raw

    def provider(self):
        ids = self.observe(self.command + ["exec", "-T", "provider", "python", "-B", "-c", PROVIDER_IDS], "provider_ids")
        require(isinstance(ids, list) and len(ids) <= MAX_ROWS and len(set(ids)) == len(ids)
                and all(isinstance(value, str) and re.fullmatch(r"chatcmpl-goal584-[0-9a-f]{32}", value) for value in ids),
                "Provider ID observation is malformed")
        return sorted(ids)

    def validate_roots(self, candidates):
        result = self.observe(self.command + ["exec", "-T", "proxy", "python", "-B", "-c", VALIDATE_ROOTS,
                                             encoded(candidates).decode("utf-8")], "persisted_scope_validation")
        require(result == candidates, "Native persisted-scope owner changed the selected roots")
        return result

    def target(self, base_url):
        try:
            result = subprocess.run(self.command + ["ps", "-q", "webui"], cwd=ROOT, capture_output=True, timeout=15)
            container = result.stdout.decode("ascii").strip()
        except (OSError, UnicodeError, subprocess.SubprocessError):
            raise ProofError("Disposable WebUI container identity unavailable") from None
        require(result.returncode == 0 and re.fullmatch(r"[0-9a-f]{64}", container), "Expected one disposable WebUI container")
        networks = self.observe(["docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", container], "target_networks")
        require(isinstance(networks, dict) and urlsplit(base_url).hostname in {v.get("IPAddress") for v in networks.values()},
                "WebUI URL is outside this disposable Compose owner")


class Session:
    def __init__(self, base_url):
        self.base_url, self.token = native_url(base_url), None
        self.opener = build_opener(ProxyHandler({}), NoRedirects())

    def request(self, method, path, body=None):
        require(method in ("GET", "POST", "DELETE") and path.startswith("/api/"), "Unsupported native fixture HTTP operation")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(self.base_url + path, method=method, headers=headers, data=None if body is None else encoded(body))
        try:
            response = self.opener.open(request, timeout=20)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, OSError):
            raise ProofError("Native WebUI transport failed") from None
        with response:
            return response.code, decode(response.read(MAX_BYTES + 1))

    def login(self, account):
        status, version = self.request("GET", "/api/version")
        require(status == 200 and version.get("version") == "0.12.2", "Expected the pinned native WebUI")
        status, signed = self.request("POST", "/api/v1/auths/signin", {"email": account["email"], "password": account["password"]})
        require(status == 200 and signed.get("id") == account["id"] and signed.get("role") == "user"
                and isinstance(signed.get("token"), str) and signed["token"], "Fresh ordinary-user login failed")
        self.token = signed["token"]
        status, actual = self.request("GET", "/api/v1/auths/")
        require(status == 200 and actual.get("id") == account["id"] and actual.get("role") == "user", "Fresh native session readback differs")


def run(args, receipt=None):
    receipt = {} if receipt is None else receipt
    receipt["stage"] = "validate_private_paths"
    private_paths(args.env_file, args.accounts, args.output, args.private_output)
    base_url = native_url(args.base_url)
    accounts = decode(args.accounts.read_bytes()).get("users")
    require(isinstance(accounts, list) and len(accounts) == 2, "Expected the existing two-staff private handoff")
    actor = accounts[0]
    actor_id = canonical(actor.get("id"))
    require(all(isinstance(actor.get(field), str) and actor[field] for field in ("email", "password"))
            and actor["email"].endswith("@example.com"), "Only the disposable synthetic employee may log in")
    fixture, session = Fixture(args.env_file), Session(base_url)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    private = {}
    fd = os.open(args.private_output, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        write_private(handle, private)
        receipt["stage"] = "bind_disposable_target"
        fixture.target(base_url)
        receipt["stage"] = "read_fixture_state"
        projection = fixture.projection()
        require(isinstance(projection, dict) and re.fullmatch(r"goal584-webui-[0-9a-f]{12}", projection.get("run_id", ""))
                and projection.get("staff_ids") == [canonical(a["id"]) for a in accounts], "Private fixture/staff source binding differs")
        personal = projection.get("personal_ids")
        require(isinstance(personal, list) and len(personal) == len(set(personal)) == 4
                and actor_id in personal, "Four distinct personal fixture payers required")
        payers = {canonical(value) for value in personal} | {canonical(projection.get("service_id"))}
        require(len(payers) == 5, "Service payer must be separate from all personal budgets")
        receipt["stage"] = "fresh_native_login"
        session.login(actor)
        receipt["stage"] = "read_initial_provider_ids"
        provider_before = fixture.provider()
        receipt["stage"] = "read_initial_raw_financial_rows"
        private["before"] = fixture.snapshot(payers)
        write_private(handle, private)
        before = normalize_snapshot(private["before"], payers)
        receipt["stage"] = "validate_persisted_personal_roots"
        candidates = fixture.validate_roots(candidate_roots(before, actor_id))
        receipt["stage"] = "select_owned_completed_paid_chat"
        selected = None
        for candidate in candidates[:64]:
            scope = candidate["scope"]
            if scope["chat_id"] != scope["root_chat_id"] or scope["answer_id"] != scope["root_answer_id"]:
                continue
            chat_id = canonical(scope["root_chat_id"])
            status, saved = session.request("GET", "/api/v1/chats/" + chat_id)
            if status in (403, 404):
                continue
            require(status == 200, "Native paid chat read failed")
            texts = owned_chat(saved, scope, actor_id)
            status, tasks = session.request("GET", "/api/tasks/chat/" + chat_id)
            require(status == 200 and isinstance(tasks.get("task_ids"), list) and not tasks["task_ids"],
                    "Selected chat has active native tasks")
            selected = (chat_id, scope, texts)
            private.update(saved_chat=saved, selected_root=candidate, provider_ids_before=provider_before)
            write_private(handle, private)
            break
        require(selected is not None, "No completed owned synthetic paid chat was available")
        chat_id, scope, texts = selected
        receipt["stage"] = "check_initial_raw_privacy"
        privacy_check(before["journal"], texts + [actor["password"], session.token])
        receipt["stage"] = "delete_selected_native_chat"
        status, deleted = session.request("DELETE", "/api/v1/chats/" + chat_id)
        require(status == 200 and deleted is True, "Native chat deletion did not confirm success")
        private["delete_http_status"] = status
        write_private(handle, private)
        receipt["stage"] = "read_deleted_chat"
        status, _ = session.request("GET", "/api/v1/chats/" + chat_id)
        require(status in (403, 404), "Native saved chat remains accessible after deletion")
        private["deleted_chat_get_status"] = status
        receipt["stage"] = "read_final_raw_financial_rows"
        private["after"] = fixture.snapshot(payers)
        write_private(handle, private)
        after = normalize_snapshot(private["after"], payers)
        receipt["stage"] = "read_final_provider_ids"
        provider_after = fixture.provider()
        private["provider_ids_after"] = provider_after
        write_private(handle, private)
        receipt["stage"] = "compare_retained_rows_and_raw_privacy"
        compare_snapshots(before, after)
        privacy_check(after["journal"], texts + [actor["password"], session.token])
        require(provider_before == provider_after, "Chat deletion caused a provider dispatch")
        receipt["stage"] = "qualified_retention"
        return {"passed": True, "actor_id": actor_id, "deleted_chat_id": chat_id, "paid_root_answer_id": scope["root_answer_id"],
                "selected_payer_ids": sorted(payers), "native_delete_http_status": 200, "deleted_chat_get_status": status,
                "raw_cost_rows": len(before["journal"]), "native_payers": len(before["users"]), "native_keys": len(before["keys"]),
                "all_raw_rows_and_counters_unchanged": True, "raw_body_fields_empty": True,
                "exact_saved_content_values_and_full_credentials_absent": True,
                "native_request_ids_sha256": digest([row["request_id"] for row in before["journal"]]),
                "raw_before_sha256": digest(before), "raw_after_sha256": digest(after),
                "provider_calls_before": len(provider_before), "provider_calls_after": len(provider_after),
                "provider_ids_unchanged": True, "provider_ids_sha256": digest(provider_before),
                "read_only_sql_sha256": hashlib.sha256(snapshot_sql(payers).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    for name in ("env-file", "accounts", "output", "private-output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": "goal584-native-chat-delete-ledger-retention", "passed": False,
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "scope": "All raw rows owned by five disposable payers; empty native body columns; recursive exact saved content values, substrings of at least 32 characters and full credentials",
               "not_qualified": ["short_saved_content_embedded_in_other_strings", "global_cost_database_privacy", "unattributed_failure_cancel_rows", "production", "paid_provider", "background_lifecycle"]}
    output_valid = False
    try:
        private_paths(args.env_file, args.accounts, args.output, args.private_output)
        output_valid = True
        receipt.update(run(args, receipt))
    except ProofError as error:
        receipt["failure"] = str(error)
    except Exception as error:
        receipt["failure"] = "Retention proof failed: " + type(error).__name__
    receipt.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if output_valid:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "ledger-retention.safe.json").write_bytes(encoded(receipt) + b"\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
