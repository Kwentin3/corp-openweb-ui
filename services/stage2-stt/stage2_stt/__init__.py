"""Stage 2 STT backend sidecar domain."""

__all__ = ["create_app"]


def create_app(*args, **kwargs):
    from stage2_stt.app import create_app as _create_app

    return _create_app(*args, **kwargs)
