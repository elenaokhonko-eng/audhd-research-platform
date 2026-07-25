from enum import StrEnum


class WorkflowStage(StrEnum):
    SUBMITTED = "submitted"
    FORMALIZING = "formalizing_hypothesis"
    HYPOTHESIS_REVIEW = "awaiting_hypothesis_approval"
    RETRIEVING = "retrieving_scientific_sources"
    SYNTHESIZING = "synthesizing_and_verifying"
    REPORTING = "generating_scientific_report"
    PDF_QA = "rendering_and_reviewing_pdf"
    ADAPTING = "adapting_substack_article"
    VISUALS = "generating_visual_assets"
    CONTENT_REVIEW = "awaiting_content_approval"
    DRAFTING = "creating_substack_draft"
    PUBLISH_REVIEW = "awaiting_publish_approval"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


HUMAN_GATES = {
    WorkflowStage.HYPOTHESIS_REVIEW,
    WorkflowStage.CONTENT_REVIEW,
    WorkflowStage.PUBLISH_REVIEW,
}

STAGE_ORDER = list(WorkflowStage)

NEXT_STAGE = {
    stage: STAGE_ORDER[index + 1]
    for index, stage in enumerate(STAGE_ORDER[:-2])
}


def can_advance(current: WorkflowStage, target: WorkflowStage) -> bool:
    """Only permit the declared next step, retrying a stage, or failure."""
    return target in {current, NEXT_STAGE.get(current), WorkflowStage.FAILED}
