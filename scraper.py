"""
Async scraper service — orchestrates URL discovery, page fetching,
field extraction, and real-time progress reporting via job_store.

run_scrape(job_id) is the single entry point called from main.py as an
asyncio background Task.  It never returns hardcoded course data; every
field value originates from a live httpx GET to coventry.ac.uk.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from bs4 import BeautifulSoup

import job_store
from discovery import discover_course_urls, HEADERS
from extractors import extract_all_fields
from models import CourseRecord, ScrapeEvent

logger = logging.getLogger(__name__)

# ── Environment-configurable settings ─────────────────────────────────────────
# These are also read by pydantic-settings in main.py; the defaults here
# serve as a fallback when scraper_service is imported standalone.
TARGET_COUNT: int = int(os.getenv("TARGET_COUNT", "5"))
REQUEST_DELAY: float = float(os.getenv("REQUEST_DELAY", "1.5"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(
    job_id: str,
    message: str,
    level: str = "info",
    progress: int = 0,
    course: CourseRecord | None = None,
    event_type: str = "log",
) -> None:
    """Append a ScrapeEvent to job_store and log it locally."""
    event = ScrapeEvent(
        type=event_type,  # type: ignore[arg-type]
        message=message,
        level=level,  # type: ignore[arg-type]
        progress=progress,
        course=course,
    )
    job_store.append_event(job_id, event)
    logger.info("[%s] %s", level.upper(), message)


# ── Main scrape coroutine ─────────────────────────────────────────────────────

async def run_scrape(job_id: str) -> None:
    """
    Full scrape pipeline for a single job.

    1. Mark job as running.
    2. Discover course URLs via discovery.discover_course_urls().
    3. For each URL: fetch the page, parse HTML, extract all 27 fields,
       build a CourseRecord, store it, emit progress events.
    4. Mark job as done (or error).

    All HTTP requests use httpx.AsyncClient with a browser-like User-Agent.
    A polite asyncio.sleep(REQUEST_DELAY) is inserted between page fetches.
    """
    job_store.set_status(job_id, "running", mark_started=True)
    _log(job_id, "Scrape job started — fetching Coventry postgraduate courses…", "info", 0)

    timeout = httpx.Timeout(30.0, connect=10.0)
    limits = httpx.Limits(max_connections=5, max_keepalive_connections=3)

    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=timeout,
            limits=limits,
            follow_redirects=True,
        ) as client:

            # ── Step 1: URL discovery ─────────────────────────────────────────
            _log(job_id, "Discovering course URLs from A-Z listing page…", "info", 2)
            urls = await discover_course_urls(client, target_count=TARGET_COUNT)

            if not urls:
                raise RuntimeError("No course URLs discovered — check discovery.py selectors.")

            _log(
                job_id,
                f"Found {len(urls)} course URL(s) to scrape.",
                "success",
                5,
            )
            for i, u in enumerate(urls, 1):
                _log(job_id, f"  [{i}] {u}", "dim", 5)

            total = len(urls)

            # ── Step 2: Per-URL scraping ──────────────────────────────────────
            for idx, url in enumerate(urls, 1):
                pct_start = 5 + int((idx - 1) / total * 85)
                pct_end   = 5 + int(idx / total * 85)

                _log(
                    job_id,
                    f"[{idx}/{total}] Fetching: {url}",
                    "info",
                    pct_start,
                )

                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    _log(
                        job_id,
                        f"HTTP {exc.response.status_code} for {url} — skipping.",
                        "warn",
                        pct_start,
                    )
                    continue
                except httpx.RequestError as exc:
                    _log(
                        job_id,
                        f"Request error for {url}: {exc} — skipping.",
                        "warn",
                        pct_start,
                    )
                    continue

                _log(job_id, f"  Page fetched ({len(response.content):,} bytes). Parsing…", "dim", pct_start)

                soup = BeautifulSoup(response.text, "lxml")
                fields = extract_all_fields(soup, url)
                course = CourseRecord(**fields)

                job_store.add_result(job_id, course)

                # Emit a "course" event so the frontend can show live cards.
                _log(
                    job_id,
                    f"Scraped: {course.program_course_name or url}",
                    "success",
                    pct_end,
                    course=course,
                    event_type="course",
                )

                # Progress event (separate, for progress bar)
                job_store.append_event(
                    job_id,
                    ScrapeEvent(type="progress", message="", level="info", progress=pct_end, course=None),
                )

                # Polite delay between requests (skip after last URL)
                if idx < total:
                    _log(
                        job_id,
                        f"  Waiting {REQUEST_DELAY}s before next request…",
                        "dim",
                        pct_end,
                    )
                    await asyncio.sleep(REQUEST_DELAY)

            # ── Step 3: Finalize ──────────────────────────────────────────────
            result_count = len(job_store.get_job(job_id).results)  # type: ignore[union-attr]
            _log(
                job_id,
                f"Scrape complete! {result_count} course(s) extracted successfully.",
                "success",
                100,
            )
            _log(job_id, "Results available via GET /api/results/{job_id}", "info", 100)

            job_store.set_status(job_id, "done", mark_finished=True)

            # Final SSE "done" event — closes the stream on the client side.
            job_store.append_event(
                job_id,
                ScrapeEvent(type="done", message="Scrape finished.", level="success", progress=100),
            )

    except Exception as exc:  # noqa: BLE001
        err_msg = f"Scrape failed: {exc}"
        logger.exception(err_msg)
        _log(job_id, f"{err_msg}", "error", 0)
        job_store.set_status(job_id, "error", error=err_msg, mark_finished=True)
        job_store.append_event(
            job_id,
            ScrapeEvent(type="error", message=err_msg, level="error", progress=0),
        )
