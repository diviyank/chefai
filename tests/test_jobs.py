import json
import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
import app.db as db
from app import jobs
from app.models import GenerationJob


@pytest.fixture
def engine(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(db, "get_engine", lambda: eng)
    monkeypatch.setattr(jobs, "get_engine", lambda: eng)
    return eng


def _sync_runner(job_id, work):
    jobs._run(job_id, work)  # run inline, no thread


def test_start_done_stores_result(engine):
    job = jobs.start("cook_have", {"a": 1}, "prompt", lambda: {"recipes": []},
                     runner=_sync_runner)
    with Session(engine) as s:
        row = s.get(GenerationJob, job.id)
        assert row.status == "done"
        assert json.loads(row.result_json) == {"recipes": []}


def test_start_error_stores_notice(engine):
    def boom():
        raise RuntimeError("nope")
    job = jobs.start("plan", {}, "prompt", boom, runner=_sync_runner)
    with Session(engine) as s:
        row = s.get(GenerationJob, job.id)
        assert row.status == "error"
        assert row.notice == jobs.FALLBACK_NOTICE


def test_latest_returns_newest_per_kind(engine):
    jobs.start("cook_have", {}, "p1", lambda: {"n": 1}, runner=_sync_runner)
    jobs.start("cook_have", {}, "p2", lambda: {"n": 2}, runner=_sync_runner)
    jobs.start("plan", {}, "p3", lambda: {"n": 3}, runner=_sync_runner)
    with Session(engine) as s:
        assert json.loads(jobs.latest(s, "cook_have").result_json) == {"n": 2}
        assert json.loads(jobs.latest(s, "plan").result_json) == {"n": 3}
        assert jobs.latest(s, "nutrition") is None


def test_mark_stale_running_flips_running_to_error(engine):
    with Session(engine) as s:
        s.add(GenerationJob(kind="cook_have", status="running")); s.commit()
    jobs.mark_stale_running()
    with Session(engine) as s:
        assert jobs.latest(s, "cook_have").status == "error"
