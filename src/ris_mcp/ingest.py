"""Generic Judikatur ingester. Parameterised by ApplikationConfig.

Orchestrates: page through RIS search, fetch document HTML, normalise to text,
upsert into SQLite. Crash-safe (commit per page). Delta-aware via Aenderungsdatum.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
from typing import Any

from bs4 import BeautifulSoup

from .applikation import get_applikation
from .client import RisClient, SearchHit
from .store import get_sync_state, set_sync_state, upsert_decision

log = logging.getLogger(__name__)


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator="\n", strip=True)


def _row_from_hit(
    hit: SearchHit, applikation: str, court: str, full_text_html: str,
) -> dict[str, Any]:
    text = _html_to_text(full_text_html) if full_text_html else (hit.rechtssatz or "")
    return {
        "id": f"{applikation}:{hit.dokument_id}",
        "applikation": applikation,
        "court": court,
        "geschaeftszahl": hit.geschaeftszahl,
        "entscheidungsdatum": hit.entscheidungsdatum,
        "rechtssatznummer": None,
        "dokumenttyp": hit.dokumenttyp,
        "norm": hit.norm,
        "schlagworte": hit.schlagworte,
        "rechtssatz": hit.rechtssatz,
        "text": text,
        "text_html": full_text_html or None,
        "source_url": hit.document_url,
        "fetched_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "aenderungsdatum": hit.aenderungsdatum,
        "raw_json": json.dumps(hit.raw, ensure_ascii=False),
    }


async def ingest_applikation(
    client: RisClient,
    conn: sqlite3.Connection,
    *,
    applikation: str,
    delta: bool = False,
    page_size: int = 100,
) -> int:
    cfg = get_applikation(applikation)
    watermark: str | None = None
    if delta:
        state = get_sync_state(conn, applikation)
        watermark = state.get("watermark_aenderungsdatum") if state else None

    page = 1
    total = 0
    max_aenderung: str | None = watermark
    while True:
        resp = await client.search(
            applikation=applikation, page=page, page_size=page_size,
            aenderungsdatum_from=watermark,
        )
        if not resp.hits:
            break
        for hit in resp.hits:
            if not hit.geschaeftszahl:
                log.warning(
                    "ingest %s: empty geschaeftszahl for dokument_id=%s — possible parser gap",
                    applikation, hit.dokument_id,
                )
            full_html = ""
            if hit.document_url:
                try:
                    full_html = await client.fetch_document(hit.document_url)
                except Exception:
                    full_html = ""
            row = _row_from_hit(hit, applikation, cfg.court, full_html)
            upsert_decision(conn, row)
            total += 1
            if hit.aenderungsdatum and (
                max_aenderung is None or hit.aenderungsdatum > max_aenderung
            ):
                max_aenderung = hit.aenderungsdatum
        page += 1

    set_sync_state(
        conn, applikation,
        watermark=max_aenderung,
        delta=delta, full=not delta,
        total=total,
    )
    return total
