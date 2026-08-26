from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, MutableMapping

from services.export_service import (
    build_excel_report,
    build_pdf_report,
)


REPORT_EXPORT_CACHE_SESSION_KEY = (
    "_mdrrmo_report_export_cache"
)
REPORT_EXPORT_CACHE_VERSION = 1


class ReportExportCacheError(Exception):
    """Raised when a report snapshot cannot be safely cached."""


@dataclass(frozen=True)
class ReportExportBundle:
    cache_version: int
    snapshot_id: int
    snapshot_sha256: str
    excel_bytes: bytes
    pdf_bytes: bytes


def _snapshot_identity(
    record: dict[str, object],
) -> tuple[int, str]:
    try:
        snapshot_id = int(
            record["id"]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise ReportExportCacheError(
            "The selected report snapshot has no valid ID."
        ) from error

    snapshot_sha256 = str(
        record.get(
            "snapshot_sha256",
            "",
        )
    ).strip()

    if not snapshot_sha256:
        raise ReportExportCacheError(
            "The selected report snapshot has no integrity hash."
        )

    return (
        snapshot_id,
        snapshot_sha256,
    )


def get_report_export_bundle(
    record: dict[str, object],
    state: MutableMapping[str, object],
    *,
    excel_builder: Callable[
        [dict[str, object]],
        bytes,
    ] = build_excel_report,
    pdf_builder: Callable[
        [dict[str, object]],
        bytes,
    ] = build_pdf_report,
) -> ReportExportBundle:
    """
    Build report exports once for the currently selected immutable snapshot.

    The caller supplies the user's Streamlit Session State. Only one snapshot
    bundle is retained, bounding per-session memory use while eliminating
    repeated Excel/PDF regeneration on ordinary reruns of the same report.
    """
    (
        snapshot_id,
        snapshot_sha256,
    ) = _snapshot_identity(
        record
    )

    cached = state.get(
        REPORT_EXPORT_CACHE_SESSION_KEY
    )

    if (
        isinstance(
            cached,
            ReportExportBundle,
        )
        and cached.cache_version
        == REPORT_EXPORT_CACHE_VERSION
        and cached.snapshot_id
        == snapshot_id
        and cached.snapshot_sha256
        == snapshot_sha256
    ):
        return cached

    excel_bytes = excel_builder(
        record
    )
    pdf_bytes = pdf_builder(
        record
    )

    if not isinstance(
        excel_bytes,
        bytes,
    ):
        raise ReportExportCacheError(
            "Excel export generation returned invalid data."
        )

    if not isinstance(
        pdf_bytes,
        bytes,
    ):
        raise ReportExportCacheError(
            "PDF export generation returned invalid data."
        )

    bundle = ReportExportBundle(
        cache_version=
            REPORT_EXPORT_CACHE_VERSION,
        snapshot_id=
            snapshot_id,
        snapshot_sha256=
            snapshot_sha256,
        excel_bytes=
            excel_bytes,
        pdf_bytes=
            pdf_bytes,
    )

    state[
        REPORT_EXPORT_CACHE_SESSION_KEY
    ] = bundle

    return bundle
