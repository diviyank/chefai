import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ..db import get_session
from ..main import templates
from .. import jobs

router = APIRouter()


def render_panel(request: Request, kind: str, job, *, session=None, **extra) -> HTMLResponse:
    """Build the template context for a panel from a job row (or None)."""
    result = json.loads(job.result_json) if job and job.result_json else None
    params = json.loads(job.params_json) if job and job.params_json else {}
    prompt = job.prompt if job else ""
    if job and job.status == "error" and prompt:
        # The error panel renders this prompt for copy-paste, so invite clarifying
        # questions just like the sync copy-paste path does.
        from .. import prompt_builder as pb
        prompt = pb.with_clarifying_questions(prompt)
    ctx = {
        "request": request, "kind": kind, "job": job,
        "result": result, "params": params,
        "prompt": prompt,
        "notice": job.notice if job else None,
    }
    from .. import panels
    ctx.update(panels.extra_context(kind, params, result))
    if kind == "plan" and result and result.get("ps_id") and session is not None:
        from ..models import PlanningSession
        ps = session.get(PlanningSession, result["ps_id"])
        if ps:
            ctx.update({"ps": ps, "plans": ps.proposals_json, "reroll": True})
    ctx.update(extra)
    return templates.TemplateResponse("partials/_panel.html", ctx)


@router.get("/jobs/{kind}/panel", response_class=HTMLResponse)
def panel(kind: str, request: Request, session: Session = Depends(get_session)):
    return render_panel(request, kind, jobs.latest(session, kind), session=session)
