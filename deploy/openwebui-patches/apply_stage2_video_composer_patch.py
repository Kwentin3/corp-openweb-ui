#!/usr/bin/env python3
"""Fail-fast, pinned v0.9.6 composer handoff for video intake."""

from __future__ import annotations

import argparse
from pathlib import Path


API_OLD = 'if(i)throw i;return l},m=async(o,r)=>'
API_NEW = ('if(i)throw i;if(e&&l&&l.meta?.content_type?.startsWith("video/"))'
           '{if(l.data?.status==="failed")throw l.data.error||"Не удалось подготовить аудио";'
           'const prepared=await B(o,l.id);if(prepared?.data?.status!=="completed"||'
           '!prepared?.meta?.content_type?.startsWith("audio/"))throw "Подготовка аудио не завершилась";'
           'return prepared}return l},m=async(o,r)=>')

WAIT_OLD = ('if(r(Ee).length>0&&r(Ee).filter(er=>er.type!=="image"&&er.status==="uploading").length>0)'
            '{ht.error(C().t("Oops! There are files still uploading. Please wait for the upload to complete."));return}')
WAIT_NEW = ('if(r(Ee).length>0&&r(Ee).filter(er=>er.type!=="image"&&er.status==="uploading").length>0)'
            '{if(vs.__stage2_wait)return;vs.__stage2_wait=true;'
            'const pending=r(Ee).filter(er=>er.type!=="image"&&er.status==="uploading").map(er=>er.itemId);'
            'ht.info("Подготавливаем аудио. Сообщение отправится автоматически.");'
            'try{await new Promise((resolve,reject)=>{const limit=Date.now()+7200000;'
            'const timer=setInterval(()=>{const current=r(Ee);'
            'if(pending.some(id=>!current.some(item=>item.itemId===id))){clearInterval(timer);reject(Error("Подготовка файла не удалась"));return}'
            'if(pending.every(id=>current.some(item=>item.itemId===id&&item.status==="uploaded"))){clearInterval(timer);resolve();return}'
            'if(Date.now()>limit){clearInterval(timer);reject(Error("Подготовка файла заняла слишком много времени"))}},250)})}'
            'catch(error){ht.error(String(error));vs.__stage2_wait=false;return}'
            'vs.__stage2_wait=false}')

DRAFT_OLD_1 = 'submit:async wt=>{hi(i()),(wt.detail||r(Ee).length>0)'
DRAFT_NEW_1 = 'submit:async wt=>{r(Ee).some(x=>x.status==="uploading")||hi(i()),(wt.detail||r(Ee).length>0)'
DRAFT_OLD_2 = 'submit:async Yt=>{hi(),(Yt.detail||r(Ee).length>0)'
DRAFT_NEW_2 = 'submit:async Yt=>{r(Ee).some(x=>x.status==="uploading")||hi(),(Yt.detail||r(Ee).length>0)'
ITEM_OLD = 'vt.status="uploaded",vt.file=bt,vt.id=bt.id,'
ITEM_NEW = 'vt.status="uploaded",vt.file=bt,vt.id=bt.id,vt.name=bt.filename??vt.name,vt.size=bt.meta?.size??vt.size,'


def replace_once(source: str, old: str, new: str, label: str) -> tuple[str, str]:
    if source.count(new) == 1:
        return source, "already_patched"
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: expected exactly one pinned v0.9.6 signature")
    return source.replace(old, new), "patched"


def patch(root: Path, dry_run: bool = False) -> tuple[str, str]:
    api_path = root / "C7Lxt8YS.js"
    chat_path = root / "B56SVFjv.js"
    api, api_status = replace_once(api_path.read_text(encoding="utf-8"), API_OLD, API_NEW, "file API")
    chat = chat_path.read_text(encoding="utf-8")
    statuses = []
    for old, new, label in (
        (WAIT_OLD, WAIT_NEW, "pending send"),
        (DRAFT_OLD_1, DRAFT_NEW_1, "chat draft"),
        (DRAFT_OLD_2, DRAFT_NEW_2, "new chat draft"),
        (ITEM_OLD, ITEM_NEW, "prepared attachment label"),
    ):
        chat, status = replace_once(chat, old, new, label)
        statuses.append(status)
    if len({api_status, *statuses}) != 1:
        raise RuntimeError("Incomplete composer patch")
    if not dry_run:
        api_path.write_text(api, encoding="utf-8")
        chat_path.write_text(chat, encoding="utf-8")
    return api_status, statuses[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/app/build/_app/immutable/chunks")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print("stage2-video-composer-v1:", patch(Path(args.root), args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
