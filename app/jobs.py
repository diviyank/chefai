"""Background generation jobs: run an opaque work() in a daemon thread and persist
the outcome to GenerationJob. No knowledge of LLM or parsing — the caller supplies
work(). Keeps prompt_builder/response_parser pure and routers thin."""
import json
import threading
from datetime import datetime
from typing import Callable

from sqlmodel import Session, select

from .db import get_engine
from .models import GenerationJob

FALLBACK_NOTICE = "Génération directe indisponible — copiez le prompt ci-dessous."


def latest(session: Session, kind: str) -> GenerationJob | None:
    return session.exec(
        select(GenerationJob)
        .where(GenerationJob.kind == kind)
        .order_by(GenerationJob.id.desc())
    ).first()


def _run(job_id: int, work: Callable[[], dict]) -> None:
    with Session(get_engine()) as s:
        job = s.get(GenerationJob, job_id)
        if job is None:
            return
        try:
            job.result_json = json.dumps(work())
            job.status = "done"
        except Exception:  # LLMError / ParseError / anything -> graceful fallback
            job.status = "error"
            job.notice = FALLBACK_NOTICE
        job.updated_at = datetime.utcnow()
        s.add(job)
        s.commit()


def _spawn(job_id: int, work: Callable[[], dict]) -> None:
    threading.Thread(target=_run, args=(job_id, work), daemon=True).start()


def start(kind: str, params: dict, prompt: str, work: Callable[[], dict],
          runner: Callable[[int, Callable[[], dict]], None] | None = None) -> GenerationJob:
    """Insert a running row, kick off work() (threaded by default), return the row
    (detached) for immediate rendering."""
    if runner is None:
        runner = _spawn
    with Session(get_engine()) as s:
        job = GenerationJob(kind=kind, status="running",
                            params_json=json.dumps(params), prompt=prompt)
        s.add(job)
        s.commit()
        s.refresh(job)
        s.expunge(job)
    runner(job.id, work)
    return job


def mark_stale_running() -> None:
    """Startup cleanup: a process that died mid-job leaves orphaned 'running' rows
    that would poll forever. Flip them to error."""
    with Session(get_engine()) as s:
        for job in s.exec(select(GenerationJob).where(GenerationJob.status == "running")):
            job.status = "error"
            job.notice = FALLBACK_NOTICE
            s.add(job)
        s.commit()
