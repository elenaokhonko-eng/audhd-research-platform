export type EvidenceStatus =
  | "Established"
  | "Supported"
  | "Emerging"
  | "Hypothesis"
  | "Community observation";

export type ResearchStage =
  | "Prioritization"
  | "Scoping"
  | "Evidence mapping"
  | "Analysis"
  | "Published";

export type ResearchQuestion = {
  slug: string;
  title: string;
  topic: string;
  lifeStage: string;
  stage: ResearchStage;
  status: EvidenceStatus;
  why: string;
  updated: string;
};

export const researchQuestions: ResearchQuestion[] = [
  {
    slug: "hormones-medication-response",
    title:
      "How do hormonal transitions interact with executive function and medication response in AuDHD?",
    topic: "Hormones & life stages",
    lifeStage: "Adulthood",
    stage: "Evidence mapping",
    status: "Emerging",
    why: "Many people report meaningful changes across menstrual, perimenopausal and menopausal transitions, while the evidence remains fragmented across disciplines.",
    updated: "2 August 2026",
  },
  {
    slug: "autonomic-metabolic-patterns",
    title:
      "Which autonomic and metabolic patterns recur across co-occurring autism and ADHD?",
    topic: "Metabolism & body systems",
    lifeStage: "Across the lifespan",
    stage: "Scoping",
    status: "Hypothesis",
    why: "Energy regulation, interoception, sleep and stress physiology are often studied separately, although they may form interacting systems.",
    updated: "2 August 2026",
  },
  {
    slug: "burnout-depression-differentiation",
    title:
      "How should autistic burnout be differentiated from depressive episodes in research and care?",
    topic: "Development & adaptation",
    lifeStage: "Adulthood",
    stage: "Evidence mapping",
    status: "Supported",
    why: "Overlapping outward signs can conceal different mechanisms, contexts and support needs.",
    updated: "1 August 2026",
  },
  {
    slug: "interoception-energy-regulation",
    title:
      "What mechanisms could link interoception, stress physiology and energy regulation in AuDHD?",
    topic: "Biology",
    lifeStage: "Across the lifespan",
    stage: "Prioritization",
    status: "Community observation",
    why: "Recurring lived reports can identify useful questions, but observation must remain visibly separate from tested evidence.",
    updated: "31 July 2026",
  },
  {
    slug: "developmental-compensation",
    title:
      "How do autistic and ADHD traits compensate for—or amplify—one another across development?",
    topic: "Origins & development",
    lifeStage: "Childhood to adulthood",
    stage: "Scoping",
    status: "Hypothesis",
    why: "Trait interaction may help explain delayed recognition, uneven functioning and changing support needs.",
    updated: "29 July 2026",
  },
  {
    slug: "sensory-medication-response",
    title:
      "What is known about changes in sensory processing during ADHD medication treatment?",
    topic: "Medication response",
    lifeStage: "Across the lifespan",
    stage: "Analysis",
    status: "Emerging",
    why: "Research often measures attention outcomes without capturing possible sensory or autonomic changes.",
    updated: "26 July 2026",
  },
];

export type EvidenceItem = {
  slug: string;
  title: string;
  summary: string;
  topic: string;
  status: EvidenceStatus;
  stage: ResearchStage;
  access: "Public" | "Member";
  type: string;
  updated: string;
};

export const evidenceItems: EvidenceItem[] = [
  {
    slug: "opening-evidence-map",
    title: "AuDHD biology: an opening evidence map",
    summary:
      "The project’s starting map of candidate biological systems, evidence gaps and questions requiring careful synthesis.",
    topic: "Biology",
    status: "Emerging",
    stage: "Scoping",
    access: "Public",
    type: "Project overview",
    updated: "2 August 2026",
  },
  {
    slug: "hormones-executive-function",
    title: "Hormonal transitions, executive function and medication response",
    summary:
      "A developing synthesis connecting endocrine transitions with cognition, sensory load and treatment variability.",
    topic: "Hormones",
    status: "Emerging",
    stage: "Evidence mapping",
    access: "Member",
    type: "Evidence map",
    updated: "2 August 2026",
  },
  {
    slug: "autonomic-energy-regulation",
    title: "Autonomic function, metabolism and energy regulation",
    summary:
      "A question-led research map separating recurring community observations from mechanisms already studied.",
    topic: "Metabolism",
    status: "Hypothesis",
    stage: "Prioritization",
    access: "Public",
    type: "Research agenda",
    updated: "31 July 2026",
  },
  {
    slug: "burnout-differentiation",
    title: "Burnout and depression: a differentiation evidence map",
    summary:
      "An evidence-translation project examining overlapping signs, distinct contexts and important uncertainties.",
    topic: "Development",
    status: "Supported",
    stage: "Evidence mapping",
    access: "Member",
    type: "Clinician brief",
    updated: "30 July 2026",
  },
  {
    slug: "trait-interaction-development",
    title: "Trait interaction and developmental compensation",
    summary:
      "A proposed framework for investigating how autistic and ADHD traits may mask, balance or amplify each other.",
    topic: "Origins",
    status: "Hypothesis",
    stage: "Scoping",
    access: "Public",
    type: "Concept note",
    updated: "29 July 2026",
  },
  {
    slug: "sensory-medication-map",
    title: "Sensory experience during ADHD medication treatment",
    summary:
      "A developing map of outcomes often missed when treatment studies focus mainly on attention and productivity.",
    topic: "Medication",
    status: "Emerging",
    stage: "Analysis",
    access: "Member",
    type: "Evidence map",
    updated: "26 July 2026",
  },
];
