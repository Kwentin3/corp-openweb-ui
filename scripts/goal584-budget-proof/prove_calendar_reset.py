#!/usr/bin/env python3
"""Dedicated disposable native calendar reset worker; never reuse WebUI DBs.

Future isolated runtime only: one native API-created user/key, two synthetic
calls and the unmodified global ResetBudgetJob. No migration, SQL writes,
manual spend/cache reset, host-clock/TTL patch, or new server is implemented.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import time
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import Request
from uuid import uuid4
from zoneinfo import ZoneInfo

from prove_native_budgets import CALL_COST, NativeProof, ProofError, close_amount, require
from prove_gateway_auth import read_private, write_private


REVISION = "d665dc1a6315847fcad6cc2c1264ceb47c06abce"
NATIVE_HASHES = {
    "proxy/common_utils/reset_budget_job.py": "405c9cd5a2add9cfe369c4d1b7c9ca6ebe6d34a3df1b1f7ea1c9c952dc376e59",
    "proxy/common_utils/timezone_utils.py": "8b69b0e528e84a22f5fc9ba05ed5f1eac42e6aff21476869436495b728dfe2b9",
    "proxy/proxy_server.py": "227a704e5c9e7bdd0569f80d520aa670bde32397d0983e165089c63dcb775b4e",
    "proxy/utils.py": "f2b56f6e501ee6cfedbf4e9d79a19cee594fb797f1c3d2f2fd80a37faaf6a77f",
    "litellm_core_utils/duration_parser.py": "c221af0f06a57013acdfe26948253ee79a775fc0c1e2f2ffb3c55ead35876d2f",
    "proxy/db/db_transaction_queue/pod_lock_manager.py": "c266b41e646d1e3c0a76a34668374d20ffbf8999bcba25e4eece479d15356f24",
    "repositories/unit_of_work.py": "cfc02011078a7ac3eca9be882d76b7325d49963cb79a60a755ce4bc17221b689",
    "caching/redis_cache.py": "e2f31ca00e4c2e6b5279cd9055154ab49009381a7c48ce692ca0bb88474e1cd9",
    "proxy/auth/auth_checks.py": "3dd17fd821a4d762248670fc993c1e8e0ae038ce3268ce2e84e870debcd27d4d",
    "proxy/common_utils/user_api_key_cache.py": "b0ab2f8f2d79935561d5f3f22936f876a52bec6a8d4b00251719759dfff6e9ca",
}
OTHER_TABLES = ("LiteLLM_TeamTable", "LiteLLM_BudgetTable", "LiteLLM_BudgetWindowSpend",
                "LiteLLM_EndUserTable", "LiteLLM_OrganizationTable", "LiteLLM_ProjectTable",
                "LiteLLM_TagTable", "LiteLLM_ModelAccessGroupBudgetTable")
TABLES = ("LiteLLM_UserTable", "LiteLLM_VerificationToken", "LiteLLM_SpendLogs", *OTHER_TABLES)
COUNTS_SQL = " UNION ALL ".join('SELECT \'' + name + '\' AS name, count(*)::int AS n FROM "' + name + '"' for name in TABLES)
ROWS_SQL = "SELECT jsonb_build_object(" + ",".join(
    "'" + label + "',COALESCE((SELECT jsonb_agg(to_jsonb(r)) FROM \"" + table + "\" r),'[]'::jsonb)"
    for label, table in zip(("users", "keys", "journal"), TABLES[:3])) + ") AS payload"


class ClockMeta(type):
    def __instancecheck__(cls, value):
        return isinstance(value, datetime)


def clock_at(at):
    class Frozen(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None):
            return at.astimezone(tz) if tz else at.replace(tzinfo=None)
        @classmethod
        def utcnow(cls):
            return at.astimezone(timezone.utc).replace(tzinfo=None)
    return Frozen


def timestamp(value):
    if isinstance(value,str):
        require(re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?",value) is not None,
                "Native reset timestamp is not an ISO datetime")
        try:result=datetime.fromisoformat(value.replace("Z","+00:00"))
        except ValueError:raise ProofError("Native reset timestamp is invalid") from None
    else:result=value
    require(isinstance(result, datetime), "Native reset timestamp is not a datetime")
    # Exact pinned ResetBudgetJob._as_utc contract: naive native values are UTC,
    # never host-local or the configured Moscow wall-clock timezone.
    if result.tzinfo is None:result=result.replace(tzinfo=timezone.utc)
    require(result.utcoffset() is not None,"Native reset timestamp has no UTC offset")
    return result.astimezone(timezone.utc)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def require_isolated(args, attest, config, env=os.environ):
    require(re.fullmatch(r"goal584-calendar-[0-9a-f]{12}", args.project) is not None
            and attest.get("project") == env.get("PROOF_CALENDAR_PROJECT") == args.project,
            "Calendar reset requires its own attested disposable project")
    for field in ("proxy_container_id", "postgres_container_id", "redis_container_id"):
        require(re.fullmatch(r"[0-9a-f]{64}", attest.get(field, "")) is not None, "Calendar container attestation missing")
    require(env.get("HOSTNAME") == attest["proxy_container_id"][:12], "Calendar worker is outside its attested container")
    require(re.fullmatch(r"[0-9a-f]{40}", attest.get("redis_run_id", "")) is not None, "Calendar Redis identity missing")
    require(not any(args.private_state.parent.glob("*webui*")) and not (args.private_state.parent / "gateway-state.private.json").exists(),
            "Calendar reset refuses the accepted WebUI/gateway fixture")
    general, settings = config["general_settings"], config["litellm_settings"]
    database = general["database_url"]
    require(database == env.get("DATABASE_URL") and urlsplit(database).hostname == "postgres"
            and urlsplit(database).path == "/goal584_calendar", "Calendar reset requires its dedicated native DB")
    require(general.get("disable_reset_budget") is True and general.get("custom_auth") is None
            and general.get("store_model_in_db") in (None, False)
            and general.get("coordination_redis") == {"host": "redis", "port": 6379}, "Unexpected calendar native config owner")
    require(settings.get("timezone") == "Europe/Moscow" and settings.get("budget_reset_time") == "00:00"
            and settings.get("budget_rollover", False) is False and settings.get("num_retries") == 0,
            "Calendar settings must precede native budget creation")
    require(settings.get("enable_redis_auth_cache") in (None,False),"Calendar profile requires unchanged worker-local bare-auth caches")
    models = config["model_list"]
    require({model["model_name"] for model in models} == {"goal584-a", "goal584-b"}
            and all(model["litellm_params"]["api_base"] == "http://provider:8000/v1"
                    and model["litellm_params"]["model"] == "openai/goal584-fake-" + model["model_name"][-1]
                    for model in models), "Calendar proof refuses a non-synthetic provider route")


def population(counts, snapshot, payer=None, key_hash=None):
    require(set(counts) == set(TABLES) and all(type(counts[name]) is int and counts[name] >= 0 for name in TABLES),
            "Calendar global population read is incomplete")
    require(all(counts[name] == 0 for name in OTHER_TABLES), "Calendar job would sweep unrelated budget owners")
    expected = 0 if payer is None else 1
    require(counts[TABLES[0]] == counts[TABLES[1]] == expected and counts[TABLES[2]] <= (0 if payer is None else 2),
            "Calendar requires only its own payer/key/journal population")
    if payer is not None:
        require(len(snapshot["users"]) == len(snapshot["keys"]) == 1
                and snapshot["users"][0]["user_id"] == snapshot["keys"][0]["user_id"] == payer
                and snapshot["keys"][0]["token"] == key_hash
                and snapshot["users"][0].get("models") == snapshot["keys"][0].get("models") == ["goal584-a"]
                and not snapshot["users"][0].get("teams")
                and all(snapshot["keys"][0].get(field) is None for field in ("team_id","project_id","organization_id","budget_id","expires"))
                and all(row.get("user") == payer and row.get("api_key") == key_hash for row in snapshot["journal"]),
                "Calendar native population contains a foreign identity")


async def read_db(db, payer=None, key_hash=None):
    rows = await db.writer_db.query_raw(COUNTS_SQL)
    counts = {row["name"]: row["n"] for row in rows}
    # Reject a foreign population before loading any full rows into this proof.
    population(counts, {"users": [], "keys": [], "journal": []}) if payer is None else require(
        all(counts.get(name) == 0 for name in OTHER_TABLES) and counts.get(TABLES[0]) == counts.get(TABLES[1]) == 1
        and counts.get(TABLES[2], 3) <= 2, "Calendar native population is not isolated")
    raw = await db.writer_db.query_raw(ROWS_SQL)
    snapshot = raw[0]["payload"]
    snapshot = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
    population(counts, snapshot, payer, key_hash)
    return snapshot


def money_snapshot(snapshot, spend, reset_at, *, journal_count):
    require(len(snapshot["journal"]) == journal_count, "Calendar native financial journal count differs")
    for row in (*snapshot["users"], *snapshot["keys"]):
        require(close_amount(row["spend"], spend) and Decimal(str(row["max_budget"])) == Decimal(".20")
                and row["budget_duration"] == "1mo" and timestamp(row["budget_reset_at"]) == reset_at,
                "Calendar native cap/spend/period/reset differs")


def reset_delta(before, after, new_reset):
    require(before["journal"] == after["journal"], "Native calendar reset changed financial history")
    for kind in ("users", "keys"):
        old, new = before[kind][0], after[kind][0]
        require(Decimal(str(new["spend"])) == 0 and timestamp(new["budget_reset_at"]) == new_reset
                and {key:value for key,value in old.items() if key not in ("spend", "budget_reset_at", "updated_at", "last_active")}
                == {key:value for key,value in new.items() if key not in ("spend", "budget_reset_at", "updated_at", "last_active")},
                "Native calendar reset changed unrelated identity/cap/lifetime state")


def public_snapshot(snapshot):
    return {"users":[{key:row[key] for key in ("user_id","max_budget","spend","budget_duration","budget_reset_at")} for row in snapshot["users"]],
            "keys":[{key:row[key] for key in ("user_id","token","max_budget","spend","total_spend","budget_duration","budget_reset_at")} for row in snapshot["keys"]],
            "journal_sha256":fingerprint(snapshot["journal"]),"journal_count":len(snapshot["journal"])}


class CalendarProof(NativeProof):
    """Reuse native inference transport with this fixture's calendar readback."""

    reset_at = None

    def persisted(self):
        require(len(self.users) == 1 and set(self.keys) == {(self.users[0], "goal584-a")}
                and self.reset_at is not None and len(self.expected) in (1, 2),
                "Calendar inference readback requires its one payer/model/period")
        user = self.users[0]
        key = self.keys[user, "goal584-a"]

        def journal_ready():
            rows = self.logs(user)
            require(len(rows) <= len(self.expected), "Calendar native journal contains unexpected rows")
            found = set()
            for row in rows:
                meta = row.get("metadata") or {}
                meta = json.loads(meta) if isinstance(meta, str) else meta
                lineage = meta.get("spend_logs_metadata") or {}
                root = lineage.get("root_answer_id")
                require(root in self.expected and root not in found, "Calendar journal root is foreign or duplicated")
                expected = self.expected[root]
                require(expected["user"] == row.get("user") == user
                        and expected["model"] == row.get("model_group") == "goal584-a"
                        and row.get("api_key") == key["hash"]
                        and lineage.get("chat_id") == expected["chat_id"]
                        and lineage.get("call_kind") == "synthetic_chat"
                        and row.get("request_id") == expected["provider_response_id"]
                        and (row.get("prompt_tokens"), row.get("completion_tokens"), row.get("total_tokens")) == (10, 5, 15)
                        and close_amount(row.get("spend"), CALL_COST),
                        "Calendar native journal identity/lineage/usage/cost differs")
                found.add(root)
            return rows if len(found) == len(self.expected) else None

        rows = self.poll("calendar native journal", journal_ready)
        self.receipt["calendar_journal_count"] = len(rows)

    def calendar_api_readback(self):
        # Call once after the existing DB/Redis settlement, never poll an API
        # cache until it expires. Journal persistence alone precedes settlement.
        user = self.users[0]
        key = self.keys[user, "goal584-a"]
        api_user = self.user_info(user)
        api_key = self.ok("GET", "/key/info", query={"key": key["hash"]})["info"]
        for info in (api_user, api_key):
            require(info.get("user_id") == user and info.get("models") == ["goal584-a"]
                    and close_amount(info.get("max_budget"), CALL_COST)
                    and close_amount(info.get("spend"), CALL_COST)
                    and info.get("budget_duration") == "1mo"
                    and timestamp(info.get("budget_reset_at")) == self.reset_at,
                    "Calendar immediate native API period/cap/identity differs")
        require(not api_user.get("teams") and all(api_key.get(field) is None for field in
                ("team_id", "project_id", "organization_id", "budget_id", "expires"))
                and close_amount(api_key.get("total_spend"), len(self.expected) * CALL_COST),
                "Calendar native API scope/lifetime differs")
        self.receipt["calendar_inference_readback"] = {
            "journal_count": self.receipt["calendar_journal_count"], "period_spend_usd": str(CALL_COST),
            "lifetime_spend_usd": str(len(self.expected) * CALL_COST),
            "budget_duration": "1mo", "budget_reset_at": self.reset_at.isoformat(),
            "user_id": user, "key_hash": key["hash"], "models": ["goal584-a"]}


async def qualify(args, attest, receipt, secrets):
    receipt["phase"]="native_source_settings"
    import litellm
    from litellm.proxy import proxy_server as ps
    from litellm.proxy.common_utils import reset_budget_job as job_module, timezone_utils as tz_module
    from litellm.proxy.utils import PrismaClient
    from litellm.constants import DEFAULT_MANAGEMENT_OBJECT_IN_MEMORY_CACHE_TTL
    require(version("litellm") == "1.105.1" and ps.prisma_client is None, "Calendar helper requires the pinned standalone process")
    package = Path(litellm.__file__).parent
    require(all(hashlib.sha256((package / name).read_bytes()).hexdigest() == digest for name,digest in NATIVE_HASHES.items()),
            "Calendar native owner source differs from the pinned audit")
    require(not os.environ.get("LITELLM_CONFIG_BUCKET_NAME") and not args.private_state.exists(), "Calendar requires fresh local state/config")
    config = await ps.proxy_config.get_config(config_file_path="/proof/config.yaml")
    require_isolated(args, attest, config)
    native_cache_ttl=min(ps.UserAPIKeyCacheTTLEnum.in_memory_cache_ttl.value,DEFAULT_MANAGEMENT_OBJECT_IN_MEMORY_CACHE_TTL)
    require(native_cache_ttl>0 and config["general_settings"].get("user_api_key_cache_ttl") in (None,native_cache_ttl),
            "Calendar warm-worker profile refuses changed native auth TTLs")
    settings = tz_module.BudgetResetSettings(timezone="Europe/Moscow", reset_time_of_day=tz_module.parse_budget_reset_time("00:00"))
    ZoneInfo(settings.timezone)
    require(litellm.budget_rollover is False, "Native calendar rollover must be disabled")
    receipt["phase"]="native_owner_wiring"
    redis = ps.proxy_config._init_coordination_redis(config=config)
    require(redis is not None and redis.namespace is None, "Calendar requires native dedicated coordination Redis")
    ps._set_redis_usage_cache(redis)
    ps.proxy_logging_obj.update_values(redis_cache=redis)
    lock = ps.proxy_logging_obj.db_spend_update_writer.pod_lock_manager
    require(ps.spend_counter_cache.redis_cache is redis and lock.redis_cache is redis, "Native reset cache/lease wiring differs")
    db = PrismaClient(database_url=config["general_settings"]["database_url"], proxy_logging_obj=ps.proxy_logging_obj)
    payer, key_hash = str(uuid4()), None
    proof = CalendarProof("http://127.0.0.1:4000", secrets[0], 60, receipt)
    proof.users = [payer]
    receipt.update(users=[payer],project=args.project,auth_route="native_stock_virtual_key")
    def provider_rows():
        with proof.opener.open(Request("http://provider:8000/__proof/requests"),timeout=5) as result:
            raw=result.read(4*1024*1024+1)
        require(len(raw)<=4*1024*1024,"Calendar provider evidence exceeded bound")
        data=json.loads(raw)
        require(data.get("synthetic") is True and isinstance(data.get("requests"),list),"Calendar provider is not the isolated synthetic owner")
        return data["requests"]
    try:
        receipt["phase"]="connect_isolated_owners"
        await db.connect()
        require(await redis.ping() and redis.redis_client.info("server")["run_id"] == attest["redis_run_id"],
                "Calendar Redis does not match the dedicated project attestation")
        receipt["phase"]="empty_population"
        await read_db(db)  # Must be empty BEFORE any budget creation.
        require(provider_rows()==[],"Calendar requires a fresh dedicated provider")
        receipt["phase"]="native_schema"
        proof.schema()
        receipt["phase"]="native_user_create"
        proof.ok("POST", "/user/new", body={"user_id":payer,"user_role":"internal_user","models":["goal584-a"],
            "max_budget":.20,"budget_duration":"1mo","auto_create_key":False,"send_invite_email":False})
        state={"schema":1,"proof":"goal584-calendar","project":args.project,"payer_id":payer,"stage":"user_created"}
        write_private(args.private_state,state)
        receipt["phase"]="native_key_create"
        created=proof.ok("POST","/key/generate",body={"user_id":payer,"models":["goal584-a"],"max_budget":.20,
            "budget_duration":"1mo","duration":None,"key_alias":args.project,"allowed_routes":["llm_api_routes"]})
        token=created["key"]; secrets.append(token); key_hash=hashlib.sha256(token.encode()).hexdigest()
        state.update(key=token,key_hash=key_hash,stage="key_created");write_private(args.private_state,state)
        proof.keys[payer,"goal584-a"]={"token":token,"alias":args.project,"hash":key_hash,"cap":Decimal(".20")}
        receipt["phase"]="created_profile_readback"
        initial=await read_db(db,payer,key_hash)
        receipt["created_profile"]=public_snapshot(initial)
        receipt["phase"]="created_reset_decode"
        boundary=timestamp(initial["users"][0]["budget_reset_at"])
        receipt["phase"]="created_reset_calendar"
        local=boundary.astimezone(ZoneInfo("Europe/Moscow"))
        require((local.day,local.hour,local.minute,local.second,local.microsecond)==(1,0,0,0,0), "Native 1mo creation is not Moscow midnight")
        receipt["phase"]="created_budget_zero"
        money_snapshot(initial,Decimal(0),boundary,journal_count=0)
        proof.reset_at=boundary
        old_request_started=time.monotonic()
        receipt["phase"]="old_period_inference"
        proof.infer(payer,"goal584-a")
        counter_keys=("spend:user:"+payer,"spend:key:"+key_hash)
        async def settled(expected_count):
            deadline=time.monotonic()+60
            while True:
                current=await read_db(db,payer,key_hash)
                values=[await redis.async_get_cache(key=name) for name in counter_keys]
                if (len(current["journal"])==expected_count and all(close_amount(row["spend"],Decimal(".20"))
                        for row in (*current["users"],*current["keys"])) and all(value is not None and close_amount(value,Decimal(".20")) for value in values)):
                    return current
                require(time.monotonic()<deadline,"Calendar native DB/cache counters did not settle")
                await asyncio.sleep(.1)
        receipt["phase"]="old_period_settlement"
        before=await settled(1)
        receipt["phase"]="old_period_api_readback"
        proof.calendar_api_readback()
        receipt["before_reset"]=public_snapshot(before)
        receipt["phase"]="old_period_financial_assertions"
        money_snapshot(before,Decimal(".20"),boundary,journal_count=1)
        require(Decimal(str(before["journal"][0]["spend"]))==Decimal(".20"),"Native old-period event cost differs")
        next_local=local.replace(year=local.year+(local.month==12),month=1 if local.month==12 else local.month+1)
        next_boundary=next_local.astimezone(timezone.utc)
        receipt["phase"]="job_configuration"
        job=job_module.ResetBudgetJob(proxy_logging_obj=ps.proxy_logging_obj,prisma_client=db,reset_settings=settings,pod_lock_manager=lock)
        ps.prisma_client=db  # This helper's native process only, never live-server globals.
        receipt["sweeps"]=[]
        after_reset=None
        for label,at in (("before",boundary-timedelta(seconds=1)),("exact",boundary),("after",boundary+timedelta(seconds=1)),("repeat",boundary+timedelta(seconds=1))):
            receipt["phase"]={"before":"native_reset_before","exact":"native_reset_exact",
                              "after":"native_reset_after","repeat":"native_reset_repeat"}[label]
            await read_db(db,payer,key_hash)  # Global job safety guard before EVERY sweep.
            require(await redis.async_get_cache(lock.get_redis_lock_key(job_module.RESET_BUDGET_JOB_NAME)) is None,
                    "Native reset lease is already owned; no bypass or deletion allowed")
            with patch.object(job_module,"datetime",clock_at(at)),patch.object(tz_module,"datetime",clock_at(at)):
                await asyncio.wait_for(job.reset_budget(),timeout=30)
            observed=await read_db(db,payer,key_hash)
            receipt["sweeps"].append({"case":label,"clock_utc":at.isoformat(),"native":public_snapshot(observed)})
            if label in ("before","exact"):
                require(observed==before,"Native scalar budget reset ran before strict due cutoff")
                values=[await redis.async_get_cache(key=name) for name in counter_keys]
                require(all(value is not None and close_amount(value,Decimal(".20")) for value in values),
                        "Native cache counter changed before strict due cutoff")
            else:
                reset_delta(before,observed,next_boundary)
                values=[await redis.async_get_cache(key=name) for name in counter_keys]
                require(all(value is None for value in values),"Native scalar reset left shared cached spend")
                if label=="repeat":require(public_snapshot(observed)==public_snapshot(after_reset),"Native repeated reset changed already-advanced financial state")
                after_reset=observed
            require(await redis.async_get_cache(lock.get_redis_lock_key(job_module.RESET_BUDGET_JOB_NAME)) is None,"Native reset lease was not released")
        # Do not refresh live API/auth caches, restart the worker or clear Redis
        # between the native reset and this actual admission on the same worker.
        receipt["phase"]="warm_worker_admission"
        require(time.monotonic()-old_request_started<native_cache_ttl,"Calendar observation outlived native auth TTL before next admission")
        proof.reset_at=next_boundary
        proof.infer(payer,"goal584-a")
        admitted_after=time.monotonic()-old_request_started
        require(admitted_after<native_cache_ttl,"Calendar next admission cannot be attributed before native auth TTL expiry")
        receipt["phase"]="new_period_settlement"
        final=await settled(2)
        receipt["phase"]="new_period_api_readback"
        proof.calendar_api_readback()
        receipt["after_admission"]=public_snapshot(final)
        receipt["phase"]="final_financial_assertions"
        money_snapshot(final,Decimal(".20"),next_boundary,journal_count=2)
        require(before["journal"][0] in final["journal"] and all(Decimal(str(row["spend"]))==Decimal(".20") for row in final["journal"])
                and close_amount(final["keys"][0]["total_spend"],Decimal(".40")), "Calendar next call lost historical/lifetime native cost")
        require(len({row["request_id"] for row in final["journal"]})==2
                and {row["request_id"] for row in final["journal"]}=={row["provider_response_id"] for row in receipt["calls"]},
                "Calendar actual response/native journal identities differ")
        physical=provider_rows()
        require(len(physical)==2 and {row["id"] for row in physical}=={row["request_id"] for row in final["journal"]}
                and all(row.get("body",{}).get("model")=="goal584-fake-a"
                        and row.get("usage")=={"prompt_tokens":10,"completion_tokens":5,"total_tokens":15} for row in physical),
                "Calendar actual provider calls/usage differ from native events")
        require(time.monotonic()-old_request_started<native_cache_ttl,"Calendar readback outlived unchanged native auth TTL")
        receipt.update(payer_id=payer,key_hash=key_hash,boundary_utc=boundary.isoformat(),next_boundary_utc=next_boundary.isoformat(),
            old_journal_sha256=fingerprint(before["journal"]),new_journal_sha256=fingerprint(final["journal"]),
            physical_successful_calls=2,actual_warm_worker_admission_after_reset=True,native_total_spend_usd=str(final["keys"][0]["total_spend"]))
        receipt.update(native_api_readback_observations=2,old_call_to_next_response_seconds=admitted_after,
                       unchanged_native_auth_ttl_seconds=native_cache_ttl,bare_auth_invalidation_claimed=False)
        state.update(stage="qualified_job_only",boundary=boundary.isoformat(),next_boundary=next_boundary.isoformat());write_private(args.private_state,state)
        receipt["phase"]="qualified_job_only"
    finally:
        ps.prisma_client=None
        try:await db.disconnect()
        finally:await redis.disconnect()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True)
    for name in ("attestation","private-state","receipt"):parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args()
    receipt={"schema":1,"proof":"goal584-native-calendar-reset","passed":False,"native_revision":REVISION,
             "not_qualified":["live_scheduler_tick","multiworker_L1","stale_positive_db_floor","cross_process_bare_auth_invalidation",
                              "overdue_advance","inflight_boundary_crossing","WebUI","gateway_hook","production","paid_provider"]}
    secrets=[os.environ.get("PROOF_MASTER_KEY","")]
    try:
        require(len({path.resolve() for path in (args.attestation,args.private_state,args.receipt)})==3,"Calendar evidence/state paths overlap")
        asyncio.run(qualify(args,read_private(args.attestation),receipt,secrets))
        receipt["passed"]=True
    except ProofError as error:
        receipt.update(failure=str(error),failure_phase=receipt.get("phase","initialization"))
    except Exception as error:
        receipt.update(failure="Native calendar proof failed: "+type(error).__name__,failure_phase=receipt.get("phase","initialization"))
    rendered=json.dumps(receipt,indent=2,allow_nan=False)
    require(not any(secret and secret in rendered for secret in secrets),"Credential-bearing calendar receipt suppressed")
    write_private(args.receipt,receipt)
    print(rendered)
    return 0 if receipt["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
