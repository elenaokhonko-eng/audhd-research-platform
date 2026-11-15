import type { EvidenceStatus, ResearchStage } from "../data";

export function EvidenceBadge({ status }: { status: EvidenceStatus }) {
  return (
    <span className={`badge evidence-${slug(status)}`}>
      <span aria-hidden="true">●</span> {status}
    </span>
  );
}

export function StageBadge({ stage }: { stage: ResearchStage }) {
  return (
    <span className="badge stage-badge">
      <span aria-hidden="true">◇</span> {stage}
    </span>
  );
}

function slug(value: string) {
  return value.toLowerCase().replaceAll(" ", "-");
}
