from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_app.database import get_session
from platform_app.models import Artifact, ResearchRun
from platform_app.auth import Principal, local_principal, roles_for_email
from platform_app.repository import ResearchRunRepository, WorkflowConflict
from platform_app.settings import get_settings
from platform_app.workflow import STAGE_ORDER, WorkflowStage
from platform_app.services.storage import ArtifactStorage

app = FastAPI(title="AuDHD Research Platform API", version="0.1.0")


class RunCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    hypothesis: str = Field(min_length=20)


class ApprovalCreate(BaseModel):
    artifact_id: UUID
    comment: str | None = None


def get_principal(x_authenticated_email: str | None = Header(default=None)) -> Principal:
    settings = get_settings()
    if settings.trusted_auth_proxy:
        if not x_authenticated_email:
            raise HTTPException(status_code=401, detail="Missing authenticated identity")
        return Principal(x_authenticated_email, roles_for_email(x_authenticated_email, settings))
    try:
        return local_principal(settings)
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs", status_code=201)
def create_run(
    payload: RunCreate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> dict:
    principal.require("researcher", "admin")
    run = ResearchRunRepository(session).create(payload.title, payload.hypothesis, principal.email)
    return {"id": str(run.id), "stage": run.stage}


@app.get("/runs")
def list_runs(session: Session = Depends(get_session), principal: Principal = Depends(get_principal)) -> list[dict]:
    principal.require("researcher", "reviewer", "admin")
    runs = session.query(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(100).all()
    return [{"id": str(run.id), "title": run.title, "stage": run.stage, "updated_at": run.updated_at} for run in runs]


@app.get("/runs/{run_id}")
def get_run(run_id: UUID, session: Session = Depends(get_session)) -> dict:
    run = session.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")
    return {"id": str(run.id), "title": run.title, "hypothesis": run.hypothesis, "stage": run.stage}


@app.post("/runs/{run_id}/advance/{target}")
def advance_run(
    run_id: UUID,
    target: WorkflowStage,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> dict:
    principal.require("researcher", "admin")
    try:
        run = ResearchRunRepository(session).advance(run_id, target, principal.email)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Research run not found") from error
    except WorkflowConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": str(run.id), "stage": run.stage, "version": run.version}


@app.post("/runs/{run_id}/approve/{gate}", status_code=201)
def approve_run(
    run_id: UUID,
    gate: WorkflowStage,
    payload: ApprovalCreate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> dict:
    principal.require("reviewer", "admin", "publisher")
    try:
        artifact = session.get(Artifact, payload.artifact_id)
        if not artifact or artifact.run_id != run_id:
            raise HTTPException(status_code=400, detail="Approval artifact does not belong to this research run")
        snapshot = ArtifactStorage(get_settings()).get(artifact.object_key)
        approval = ResearchRunRepository(session).approve(
            run_id, gate, principal.email, snapshot, artifact.id, payload.comment
        )
    except WorkflowConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    target = STAGE_ORDER[STAGE_ORDER.index(gate) + 1]
    ResearchRunRepository(session).advance(run_id, target, principal.email)
    from platform_app.worker import advance_research_run

    task = advance_research_run.delay(str(run_id))
    return {"id": str(approval.id), "snapshot_hash": approval.snapshot_hash, "next_stage": target.value, "task_id": task.id}


@app.get("/workflow/stages")
def workflow_stages() -> list[str]:
    return [stage.value for stage in STAGE_ORDER]


@app.post("/runs/{run_id}/execute", status_code=202)
def execute_run(run_id: UUID, principal: Principal = Depends(get_principal)) -> dict:
    principal.require("researcher", "admin")
    from platform_app.worker import advance_research_run

    task = advance_research_run.delay(str(run_id))
    return {"task_id": task.id, "run_id": str(run_id)}


@app.get("/runs/{run_id}/artifacts")
def list_artifacts(
    run_id: UUID,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> list[dict]:
    principal.require("researcher", "reviewer", "admin", "publisher")
    artifacts = session.query(Artifact).filter(Artifact.run_id == run_id).order_by(Artifact.created_at.desc()).all()
    return [{"id": str(item.id), "kind": item.kind, "sha256": item.sha256, "metadata": item.metadata_json} for item in artifacts]


@app.get("/artifacts/{artifact_id}/content")
def artifact_content(
    artifact_id: UUID,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> Response:
    principal.require("researcher", "reviewer", "admin", "publisher")
    artifact = session.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    content = ArtifactStorage(get_settings()).get(artifact.object_key)
    return Response(content=content, media_type=artifact.metadata_json.get("content_type", "application/octet-stream"))
