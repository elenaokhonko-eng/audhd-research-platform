from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_app.database import get_session
from platform_app.models import ResearchRun
from platform_app.workflow import STAGE_ORDER

app = FastAPI(title="AuDHD Research Platform API", version="0.1.0")


class RunCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    hypothesis: str = Field(min_length=20)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs", status_code=201)
def create_run(payload: RunCreate, session: Session = Depends(get_session)) -> dict:
    run = ResearchRun(title=payload.title, hypothesis=payload.hypothesis)
    session.add(run)
    session.commit()
    return {"id": str(run.id), "stage": run.stage}


@app.get("/runs/{run_id}")
def get_run(run_id: UUID, session: Session = Depends(get_session)) -> dict:
    run = session.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")
    return {"id": str(run.id), "title": run.title, "hypothesis": run.hypothesis, "stage": run.stage}


@app.get("/workflow/stages")
def workflow_stages() -> list[str]:
    return [stage.value for stage in STAGE_ORDER]
