#!/usr/bin/env python3
"""Install fail-closed Broker Reports intake hooks into pinned OpenWebUI v0.9.6.

The patch is deliberately signature-based.  A changed upstream import, router
registration, Action entry point or retrieval choke point fails the image build
instead of silently dropping the privacy boundary.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path


PATCH_ID = "broker-reports-private-intake-v1"


@dataclass(frozen=True)
class Replacement:
    name: str
    path: str
    old: str
    new: str


REPLACEMENTS = (
    Replacement(
        "main_router_import",
        "main.py",
        """from open_webui.routers import (
    analytics,
    audio,
    auths,""",
        """from open_webui.routers import (
    analytics,
    audio,
    broker_reports_intake,
    auths,""",
    ),
    Replacement(
        "main_router_registration",
        "main.py",
        """app.include_router(groups.router, prefix='/api/v1/groups', tags=['groups'])
app.include_router(files.router, prefix='/api/v1/files', tags=['files'])
app.include_router(functions.router, prefix='/api/v1/functions', tags=['functions'])""",
        """app.include_router(groups.router, prefix='/api/v1/groups', tags=['groups'])
app.include_router(files.router, prefix='/api/v1/files', tags=['files'])
app.include_router(
    broker_reports_intake.router,
    prefix='/api/v1/broker-reports',
    tags=['broker-reports'],
)  # broker-reports-private-intake-v1 FACTORY_REQUIRED
app.include_router(functions.router, prefix='/api/v1/functions', tags=['functions'])""",
    ),
    Replacement(
        "main_action_guard",
        "main.py",
        """@app.post('/api/chat/actions/{action_id}')
async def chat_action(request: Request, action_id: str, form_data: dict, user=Depends(get_verified_user)):
    try:
        model_item = form_data.pop('model_item', {})""",
        """@app.post('/api/chat/actions/{action_id}')
async def chat_action(
    request: Request,
    action_id: str,
    form_data: dict,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        await broker_reports_intake.guard_protected_action_form(
            action_id,
            form_data,
            user=user,
            db=db,
        )  # broker-reports-private-intake-v1 FACTORY_REQUIRED
        await db.rollback()  # release the short receipt-read transaction before Action work
        model_item = form_data.pop('model_item', {})""",
    ),
    Replacement(
        "retrieval_guard_import",
        "routers/retrieval.py",
        """from open_webui.models.files import FileModel, Files, FileUpdateForm
from open_webui.models.knowledge import Knowledges

# Document loaders""",
        """from open_webui.models.files import FileModel, Files, FileUpdateForm
from open_webui.models.knowledge import Knowledges
from open_webui.routers import broker_reports_intake

# Document loaders""",
    ),
    Replacement(
        "retrieval_single_guard",
        "routers/retrieval.py",
        """    if file:
        try:
            collection_name = form_data.collection_name""",
        """    if file:
        # broker-reports-private-intake-v1 FORBIDDEN: guard before the
        # processing try/except so rejection cannot write a native failure state.
        broker_reports_intake.assert_native_processing_allowed(file)
        try:
            collection_name = form_data.collection_name""",
    ),
    Replacement(
        "retrieval_batch_guard",
        "routers/retrieval.py",
        """            if db_file.user_id != user.id and user.role != 'admin':
                file_errors.append(
                    BatchProcessFilesResult(
                        file_id=file.id,
                        status='failed',
                        error='Permission denied: not file owner',
                    )
                )
                continue

            text_content = file.data.get('content', '')""",
        """            if db_file.user_id != user.id and user.role != 'admin':
                file_errors.append(
                    BatchProcessFilesResult(
                        file_id=file.id,
                        status='failed',
                        error='Permission denied: not file owner',
                    )
                )
                continue

            # broker-reports-private-intake-v1 FORBIDDEN: validate the DB row,
            # never the client-supplied FileModel used by this upstream endpoint.
            broker_reports_intake.assert_native_processing_allowed(db_file)
            text_content = file.data.get('content', '')""",
    ),
)


def _validate_feature_modules(root: Path) -> None:
    router_path = root / "routers" / "broker_reports_intake.py"
    contract_path = root / "routers" / "broker_reports_intake_contract.py"
    for path in (router_path, contract_path):
        if not path.is_file():
            raise RuntimeError(f"Required closed-world module is absent: {path}")
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    router_text = router_path.read_text(encoding="utf-8")
    forbidden_runtime_dependencies = (
        "ASYNC_VECTOR_DB_CLIENT",
        "process_uploaded_file",
        "open_webui.models.knowledge",
        "open_webui.retrieval",
        "open_webui.routers.retrieval",
    )
    present = [token for token in forbidden_runtime_dependencies if token in router_text]
    if present:
        raise RuntimeError(
            "Broker Reports intake module imports a forbidden native pipeline dependency: "
            + ", ".join(present)
        )


def patch_backend(root: Path, *, dry_run: bool) -> str:
    _validate_feature_modules(root)
    texts: dict[Path, str] = {}
    states: list[str] = []

    for replacement in REPLACEMENTS:
        path = root / replacement.path
        if not path.is_file():
            raise RuntimeError(f"Pinned OpenWebUI source file is absent: {path}")
        text = texts.setdefault(path, path.read_text(encoding="utf-8"))
        old_count = text.count(replacement.old)
        new_count = text.count(replacement.new)
        if old_count == 1 and new_count == 0:
            states.append("old")
        elif old_count == 0 and new_count == 1:
            states.append("new")
        else:
            raise RuntimeError(
                f"{replacement.name}: unexpected signature counts "
                f"old={old_count} new={new_count} in {path}"
            )

    if len(set(states)) != 1:
        raise RuntimeError(
            f"Refusing a partially patched OpenWebUI backend: states={states}"
        )

    if states[0] == "new":
        return "already_patched"

    for replacement in REPLACEMENTS:
        path = root / replacement.path
        texts[path] = texts[path].replace(replacement.old, replacement.new)

    if not dry_run:
        for path, text in texts.items():
            path.write_text(text, encoding="utf-8")
    return "would_patch" if dry_run else "patched"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-root", default="/app/backend/open_webui")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.backend_root)
    if not root.is_dir():
        raise RuntimeError(f"OpenWebUI backend root does not exist: {root}")

    status = patch_backend(root, dry_run=args.dry_run)
    print(f"{PATCH_ID}: {status} {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
