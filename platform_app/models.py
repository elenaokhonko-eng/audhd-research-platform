import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from platform_app.workflow import WorkflowStage


class Base(DeclarativeBase):
    pass


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300))
    hypothesis: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(80), default=WorkflowStage.SUBMITTED)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="run")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="run")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), index=True)
    gate: Mapped[str] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(30))
    reviewer: Mapped[str] = mapped_column(String(200))
    comment: Mapped[str | None] = mapped_column(Text)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped[ResearchRun] = relationship(back_populates="approvals")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(60))
    object_key: Mapped[str] = mapped_column(String(700), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped[ResearchRun] = relationship(back_populates="artifacts")


class LiteratureDocument(Base):
    __tablename__ = "literature_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    doi: Mapped[str | None] = mapped_column(String(300), unique=True)
    source_url: Mapped[str] = mapped_column(Text)
    publication_year: Mapped[int | None]
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    rights: Mapped[dict] = mapped_column(JSON, default=dict)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class LiteratureChunk(Base):
    __tablename__ = "literature_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("literature_documents.id"), index=True)
    section: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    extraction_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class ClinicalSubject(Base):
    __tablename__ = "clinical_subjects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pseudonym: Mapped[str] = mapped_column(String(100), unique=True)
    source_system: Mapped[str] = mapped_column(String(200))
    consent_basis: Mapped[str] = mapped_column(String(300))
    consent_version: Mapped[str] = mapped_column(String(100))
    reidentification_key_reference: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicalObservation(Base):
    __tablename__ = "clinical_observations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinical_subjects.id"), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concept_code: Mapped[str] = mapped_column(String(200), index=True)
    value_json: Mapped[dict] = mapped_column(JSON)
    source_note_reference: Mapped[str | None] = mapped_column(String(700))
    quality_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


class Concept(Base):
    __tablename__ = "concepts"

    code: Mapped[str] = mapped_column(String(200), primary_key=True)
    label: Mapped[str] = mapped_column(String(300))
    definition: Mapped[str] = mapped_column(Text)
    ontology: Mapped[str] = mapped_column(String(100))
    external_mappings: Mapped[dict] = mapped_column(JSON, default=dict)


class SourceClaim(Base):
    __tablename__ = "source_claims"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("literature_documents.id"), index=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("literature_chunks.id"), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    quotation: Mapped[str | None] = mapped_column(Text)
    numeric_assertions: Mapped[list] = mapped_column(JSON, default=list)
    verification_status: Mapped[str] = mapped_column(String(40), default="pending")
    verification_details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_runs.id"), index=True)
    actor: Mapped[str] = mapped_column(String(300))
    action: Mapped[str] = mapped_column(String(120), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
