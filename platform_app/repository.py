import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_app.models import Approval, AuditEvent, ResearchRun
from platform_app.workflow import HUMAN_GATES, WorkflowStage, can_advance


class WorkflowConflict(ValueError):
    pass


def _stable_hash(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResearchRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, title: str, hypothesis: str, actor: str) -> ResearchRun:
        run = ResearchRun(title=title, hypothesis=hypothesis)
        self.session.add(run)
        self.session.flush()
        self.audit(run.id, actor, "run.created", {"title": title, "stage": run.stage})
        self.session.commit()
        return run

    def get(self, run_id: UUID, *, lock: bool = False) -> ResearchRun | None:
        query = select(ResearchRun).where(ResearchRun.id == run_id)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def advance(self, run_id: UUID, target: WorkflowStage, actor: str) -> ResearchRun:
        run = self.get(run_id, lock=True)
        if not run:
            raise KeyError(run_id)
        current = WorkflowStage(run.stage)
        if current in HUMAN_GATES and not self._has_approval(run_id, current):
            raise WorkflowConflict(f"{current} requires approval before advancing")
        if not can_advance(current, target):
            raise WorkflowConflict(f"Invalid workflow transition: {current} -> {target}")
        previous = run.stage
        run.stage = target.value
        run.version += 1
        self.audit(run.id, actor, "run.transitioned", {"from": previous, "to": target.value})
        self.session.commit()
        return run

    def approve(
        self,
        run_id: UUID,
        gate: WorkflowStage,
        reviewer: str,
        snapshot: str | bytes,
        artifact_id: UUID | None = None,
        comment: str | None = None,
    ) -> Approval:
        run = self.get(run_id, lock=True)
        if not run or WorkflowStage(run.stage) != gate or gate not in HUMAN_GATES:
            raise WorkflowConflict("Approval does not match the run's active human gate")
        snapshot_bytes = snapshot.encode("utf-8") if isinstance(snapshot, str) else snapshot
        snapshot_hash = hashlib.sha256(snapshot_bytes).hexdigest()
        approval = Approval(
            run_id=run_id,
            artifact_id=artifact_id,
            gate=gate.value,
            decision="approved",
            reviewer=reviewer,
            comment=comment,
            snapshot_hash=snapshot_hash,
        )
        self.session.add(approval)
        self.audit(run_id, reviewer, "run.approved", {"gate": gate.value, "snapshot_hash": snapshot_hash, "artifact_id": str(artifact_id) if artifact_id else None})
        self.session.commit()
        return approval

    def audit(self, run_id: UUID | None, actor: str, action: str, payload: dict) -> AuditEvent:
        previous = self.session.scalar(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(1))
        event_payload = {
            "run_id": str(run_id) if run_id else None,
            "actor": actor,
            "action": action,
            "payload": payload,
            "timestamp": datetime.now(UTC).isoformat(),
            "previous_hash": previous.event_hash if previous else None,
        }
        event = AuditEvent(
            run_id=run_id,
            actor=actor,
            action=action,
            payload=payload,
            previous_hash=event_payload["previous_hash"],
            event_hash=_stable_hash(event_payload),
        )
        self.session.add(event)
        return event

    def _has_approval(self, run_id: UUID, gate: WorkflowStage) -> bool:
        statement = select(Approval.id).where(
            Approval.run_id == run_id,
            Approval.gate == gate.value,
            Approval.decision == "approved",
        )
        return self.session.scalar(statement) is not None
