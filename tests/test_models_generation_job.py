from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool
from app.models import GenerationJob


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_generation_job_persists_with_defaults():
    s = _session()
    job = GenerationJob(kind="cook_have", params_json="{}", prompt="p")
    s.add(job); s.commit(); s.refresh(job)
    assert job.id is not None
    assert job.status == "running"
    assert job.result_json is None
    got = s.exec(select(GenerationJob).where(GenerationJob.kind == "cook_have")).first()
    assert got.prompt == "p"
