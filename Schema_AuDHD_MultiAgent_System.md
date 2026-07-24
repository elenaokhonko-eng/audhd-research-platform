# AuDHD Research Multi-Agent System
## Schema Definitions & State Machine

**Version:** 1.0  
**Date:** 2026-07-23  
**Schema Language:** JSON Schema Draft 2020-12  
**State Machine:** LangGraph-compatible typed dictionary

---

## 1. MASTER STATE SCHEMA

The `ResearchState` typed dictionary is the single source of truth for all agent communication. It is checkpointed after every node execution.

```python
from typing import TypedDict, Annotated, List, Dict, Optional, Union
from operator import add

class ResearchState(TypedDict):
    # PHASE 1: HYPOTHESIS FORMALIZATION
    raw_hypothesis: str
    analyst_questions: Annotated[List[Dict], add]
    formalized_hypothesis: Optional[Dict]
    hypothesis_accepted: bool

    # PHASE 2: RESEARCH EXECUTION
    research_plan: Optional[Dict]
    research_assignments: Annotated[List[Dict], add]
    parallel_results: Annotated[List[Dict], add]
    consolidated_research: Optional[Dict]
    critic_feedback: Annotated[List[Dict], add]
    research_satisfactory: bool
    critic_iteration_count: int

    # FACTUAL GROUNDING & SAFETY GATES
    all_claims_grounded: bool
    grounding_audit_logs: Annotated[List[Dict], add]

    # PHASE 3: DOCUMENT PRODUCTION
    research_paper_draft: Optional[Dict]
    paper_critic_report: Optional[Dict]
    paper_approved: bool

    # PHASE 4: SUBSTACK PRODUCTION
    substack_draft: Optional[Dict]
    substack_critic_report: Optional[Dict]
    substack_approved: bool

    # PHASE 5: DISTRIBUTION
    publish_queue: Annotated[List[Dict], add]
    email_distribution: Optional[Dict]
    distribution_complete: bool

    # METADATA & AUDIT
    session_id: str
    created_at: str
    last_updated: str
    human_checkpoints: Annotated[List[Dict], add]
    cost_tracking: Dict
    error_log: Annotated[List[Dict], add]
```

---

## 2. JSON SCHEMA DEFINITIONS

### 2.1 RawHypothesisPayload

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://audhd-research.system/schemas/raw-hypothesis",
  "title": "RawHypothesisPayload",
  "type": "object",
  "required": ["raw_hypothesis"],
  "properties": {
    "raw_hypothesis": {
      "type": "string",
      "minLength": 50,
      "maxLength": 5000,
      "description": "Researcher initial hypothesis in natural language"
    },
    "researcher_context": {
      "type": "object",
      "properties": {
        "background": { "type": "string" },
        "prior_work": { "type": "array", "items": { "type": "string" } },
        "target_audience": {
          "type": "string",
          "enum": ["academic", "clinical", "autistic_community", "general_public", "mixed"]
        }
      }
    },
    "constraints": {
      "type": "object",
      "properties": {
        "max_study_duration": { "type": "string", "pattern": "^P(\\d+Y)?(\\d+M)?(\\d+D)?$" },
        "population_scope": { "type": "string" },
        "ethical_clearance_status": {
          "type": "string",
          "enum": ["pending", "approved", "not_required", "exempt"]
        }
      }
    }
  }
}
```

### 2.2 FormalizedHypothesisDocument

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://audhd-research.system/schemas/formalized-hypothesis",
  "title": "FormalizedHypothesisDocument",
  "type": "object",
  "required": [
    "conceptual_hypothesis",
    "operationalized_variables",
    "null_hypothesis_h0",
    "alternative_hypothesis_h1",
    "falsifiability_criteria",
    "version",
    "approval_status"
  ],
  "properties": {
    "conceptual_hypothesis": { "type": "string", "minLength": 100 },
    "operationalized_variables": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "required": ["variable_name", "conceptual_definition", "operational_definition", "data_type"],
        "properties": {
          "variable_name": { "type": "string" },
          "conceptual_definition": { "type": "string" },
          "operational_definition": { "type": "string" },
          "measurement_instrument": { "type": "string" },
          "data_type": {
            "type": "string",
            "enum": ["nominal", "ordinal", "interval", "ratio", "count", "binary"]
          },
          "units": { "type": "string" },
          "validity_evidence": { "type": "string" }
        }
      }
    },
    "null_hypothesis_h0": { "type": "string" },
    "alternative_hypothesis_h1": { "type": "string" },
    "proposed_statistical_model": { "type": "string" },
    "falsifiability_criteria": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string" }
    },
    "effect_size_prediction": { "type": "string" },
    "population_inclusion_criteria": { "type": "string" },
    "population_exclusion_criteria": { "type": "string" },
    "clarifying_questions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "question_id": { "type": "string", "format": "uuid" },
          "question_text": { "type": "string" },
          "target_ambiguity": { "type": "string" },
          "answer_required": { "type": "boolean" },
          "researcher_answer": { "type": "string" }
        }
      }
    },
    "literature_gap_analysis": {
      "type": "object",
      "properties": {
        "gaps_addressed": { "type": "array", "items": { "type": "string" } },
        "competing_theories": { "type": "array", "items": { "type": "string" } }
      }
    },
    "ethical_considerations": {
      "type": "object",
      "properties": {
        "vulnerability_flags": { "type": "array", "items": { "type": "string" } },
        "consent_requirements": { "type": "string" },
        "risk_mitigation": { "type": "array", "items": { "type": "string" } }
      }
    },
    "version": { "type": "integer", "minimum": 1 },
    "approval_status": {
      "type": "string",
      "enum": ["pending", "approved", "rejected", "needs_revision"]
    },
    "approved_at": { "type": "string", "format": "date-time" },
    "approved_by": { "type": "string" }
  }
}
```

### 2.3 ResearchTask

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://audhd-research.system/schemas/research-task",
  "title": "ResearchTask",
  "type": "object",
  "required": ["task_id", "task_name", "search_queries", "target_sources"],
  "properties": {
    "task_id": { "type": "string", "pattern": "^TASK-[A-Z0-9]{6}$" },
    "task_name": { "type": "string", "maxLength": 100 },
    "task_description": { "type": "string", "maxLength": 500 },
    "search_queries": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "maxLength": 500 }
    },
    "target_sources": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [
          "pubmed", "arxiv", "semantic_scholar", "google_scholar",
          "psycinfo", "cochrane", "clinicaltrials_gov", "eric",
          "biorxiv", "medrxiv"
        ]
      }
    },
    "expected_outputs": { "type": "array", "items": { "type": "string" } },
    "dependencies": { "type": "array", "items": { "type": "string" } },
    "parallel_group": { "type": "integer", "minimum": 1 },
    "token_budget": { "type": "integer", "minimum": 1000 },
    "priority": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
    "assigned_agent": { "type": "string", "format": "uuid" },
    "status": {
      "type": "string",
      "enum": ["pending", "in_progress", "completed", "failed", "retrying"]
    }
  }
}
```

### 2.4 PaperExtraction

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://audhd-research.system/schemas/paper-extraction",
  "title": "PaperExtraction",
  "type": "object",
  "required": ["paper_id", "title", "authors", "key_findings"],
  "properties": {
    "paper_id": { "type": "string", "pattern": "^PAPER-[A-Z0-9]{8}$" },
    "doi": { "type": "string", "pattern": "^10\\.\\d{4,}\\/.*$" },
    "pmid": { "type": "string", "pattern": "^\\d+$" },
    "title": { "type": "string", "maxLength": 500 },
    "authors": { "type": "array", "items": { "type": "string" } },
    "journal": { "type": "string" },
    "publication_year": { "type": "integer", "minimum": 1900, "maximum": 2030 },
    "publication_type": {
      "type": "string",
      "enum": [
        "journal_article", "preprint", "review", "meta_analysis",
        "book_chapter", "conference_paper", "dissertation"
      ]
    },
    "quality_tier": { "type": "integer", "minimum": 1, "maximum": 4 },
    "peer_reviewed": { "type": "boolean" },
    "impact_factor": { "type": "number", "minimum": 0 },
    "sample_size": { "type": "integer", "minimum": 1 },
    "population": { "type": "string" },
    "study_design": {
      "type": "string",
      "enum": [
        "RCT", "quasi_experimental", "cohort", "case_control",
        "cross_sectional", "longitudinal", "qualitative",
        "mixed_methods", "systematic_review", "meta_analysis",
        "case_study", "pilot"
      ]
    },
    "methodology_summary": { "type": "string", "maxLength": 2000 },
    "key_findings": { "type": "array", "items": { "type": "string", "maxLength": 500 } },
    "effect_sizes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "metric": { "type": "string" },
          "value": { "type": "number" },
          "confidence_interval": { "type": "string" },
          "p_value": { "type": "number", "minimum": 0, "maximum": 1 }
        }
      }
    },
    "conclusions": { "type": "string", "maxLength": 1000 },
    "limitations": { "type": "array", "items": { "type": "string" } },
    "contradictions_noted": { "type": "array", "items": { "type": "string" } },
    "citations": { "type": "array", "items": { "type": "string" } },
    "retraction_status": {
      "type": "string",
      "enum": ["clean", "retracted", "corrected", "expression_of_concern"]
    },
    "full_text_available": { "type": "boolean" },
    "open_access": { "type": "boolean" },
    "extraction_confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "extracted_by": { "type": "string", "format": "uuid" },
    "extracted_at": { "type": "string", "format": "date-time" }
  }
}
```

### 2.5 ConsolidatedResearchReport

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://audhd-research.system/schemas/consolidated-report",
  "title": "ConsolidatedResearchReport",
  "type": "object",
  "required": ["report_id", "hypothesis_reference", "thematic_clusters", "hypothesis_assessment"],
  "properties": {
    "report_id": { "type": "string", "format": "uuid" },
    "hypothesis_reference": { "type": "string" },
    "executive_summary": { "type": "string", "maxLength": 2000 },
    "thematic_clusters": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["cluster_id", "cluster_name", "supporting_papers", "evidence_quality"],
        "properties": {
          "cluster_id": { "type": "string" },
          "cluster_name": { "type": "string" },
          "cluster_description": { "type": "string" },
          "supporting_papers": { "type": "array", "items": { "type": "string" } },
          "key_findings": { "type": "array", "items": { "type": "string" } },
          "evidence_quality": { "type": "string", "enum": ["high", "moderate", "low", "very_low"] },
          "consistency": { "type": "string", "enum": ["consistent", "inconsistent", "mixed"] }
        }
      }
    },
    "contradiction_matrix": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "claim_a": { "type": "string" },
          "paper_a_id": { "type": "string" },
          "claim_b": { "type": "string" },
          "paper_b_id": { "type": "string" },
          "resolution": { "type": "string" },
          "resolution_rationale": { "type": "string" }
        }
      }
    },
    "aggregate_analysis": {
      "type": "object",
      "properties": {
        "total_papers_reviewed": { "type": "integer" },
        "tier_1_count": { "type": "integer" },
        "tier_2_count": { "type": "integer" },
        "tier_3_count": { "type": "integer" },
        "tier_4_count": { "type": "integer" },
        "sample_size_range": { "type": "string" },
        "study_designs": { "type": "array", "items": { "type": "string" } }
      }
    },
    "meta_analysis_data": {
      "type": "object",
      "properties": {
        "feasible": { "type": "boolean" },
        "forest_plot_data": { "type": "object" },
        "heterogeneity_i2": { "type": "number", "minimum": 0, "maximum": 100 }
      }
    },
    "gap_analysis": {
      "type": "object",
      "properties": {
        "gaps_identified": { "type": "array", "items": { "type": "string" } },
        "recommendations_for_future_research": { "type": "array", "items": { "type": "string" } }
      }
    },
    "hypothesis_assessment": {
      "type": "object",
      "required": ["coverage_score", "h1_supported", "confidence_level"],
      "properties": {
        "coverage_score": { "type": "number", "minimum": 0, "maximum": 1 },
        "h1_supported": {
          "type": "string",
          "enum": ["strongly", "partially", "weakly", "not_supported"]
        },
        "h0_addressed": { "type": "boolean" },
        "confidence_level": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    }
  }
}
```

### 2.6 CriticReport

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://audhd-research.system/schemas/critic-report",
  "title": "CriticReport",
  "type": "object",
  "required": ["report_id", "iteration", "overall_score", "verdict"],
  "properties": {
    "report_id": { "type": "string", "format": "uuid" },
    "iteration": { "type": "integer", "minimum": 1, "maximum": 3 },
    "overall_score": { "type": "number", "minimum": 0, "maximum": 100 },
    "weighted_score": { "type": "number", "minimum": 0, "maximum": 100 },
    "verdict": { "type": "string", "enum": ["pass", "revise", "fail"] },
    "dimension_scores": {
      "type": "object",
      "properties": {
        "methodological_rigor": { "type": "number", "minimum": 0, "maximum": 100 },
        "evidence_quality": { "type": "number", "minimum": 0, "maximum": 100 },
        "logical_coherence": { "type": "number", "minimum": 0, "maximum": 100 },
        "hypothesis_coverage": { "type": "number", "minimum": 0, "maximum": 100 },
        "scientific_novelty": { "type": "number", "minimum": 0, "maximum": 100 }
      }
    },
    "critical_issues": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["severity", "category", "description"],
        "properties": {
          "severity": { "type": "string", "enum": ["critical", "major", "minor"] },
          "category": { "type": "string", "enum": ["methodology", "evidence", "logic", "coverage", "ethics", "formatting"] },
          "description": { "type": "string" },
          "affected_papers": { "type": "array", "items": { "type": "string" } },
          "recommended_action": { "type": "string" }
        }
      }
    },
    "citation_verification": {
      "type": "object",
      "properties": {
        "spot_check_count": { "type": "integer" },
        "accuracy_rate": { "type": "number", "minimum": 0, "maximum": 1 },
        "failed_verifications": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "cited_claim": { "type": "string" },
              "paper_id": { "type": "string" },
              "issue": { "type": "string" }
            }
          }
        }
      }
    },
    "publication_bias_assessment": {
      "type": "object",
      "properties": {
        "funnel_plot_feasible": { "type": "boolean" },
        "egger_test_result": { "type": "string" },
        "bias_risk": { "type": "string", "enum": ["low", "moderate", "high"] }
      }
    },
    "feedback_for_manager": { "type": "string" },
    "previous_issues_regressed": { "type": "array", "items": { "type": "string" } },
    "human_escalation_required": { "type": "boolean" }
  }
}
```

### 2.7 SubstackArticle

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://audhd-research.system/schemas/substack-article",
  "title": "SubstackArticle",
  "type": "object",
  "required": ["article_id", "headline", "tldr", "content_markdown"],
  "properties": {
    "article_id": { "type": "string", "format": "uuid" },
    "headline": { "type": "string", "maxLength": 100 },
    "subtitle": { "type": "string", "maxLength": 200 },
    "tldr": {
      "type": "object",
      "required": ["summary", "key_points"],
      "properties": {
        "summary": { "type": "string", "maxLength": 150 },
        "key_points": {
          "type": "array",
          "maxItems": 5,
          "items": { "type": "string", "maxLength": 100 }
        },
        "estimated_read_time": { "type": "string" },
        "deep_dive_time": { "type": "string" }
      }
    },
    "content_markdown": { "type": "string" },
    "deep_dive_sections": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "section_id": { "type": "string" },
          "section_title": { "type": "string" },
          "content": { "type": "string" },
          "collapsed_by_default": { "type": "boolean", "default": true }
        }
      }
    },
    "images": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "image_id": { "type": "string" },
          "url": { "type": "string", "format": "uri" },
          "alt_text": { "type": "string", "maxLength": 125 },
          "caption": { "type": "string" },
          "placement": { "type": "string", "enum": ["header", "inline", "footer"] }
        }
      }
    },
    "tags": { "type": "array", "items": { "type": "string" } },
    "research_paper_reference": { "type": "string", "format": "uuid" },
    "cta": {
      "type": "object",
      "properties": {
        "subscribe_prompt": { "type": "string" },
        "share_prompt": { "type": "string" },
        "comment_prompt": { "type": "string" }
      }
    },
    "accessibility": {
      "type": "object",
      "properties": {
        "dyslexia_font_available": { "type": "boolean" },
        "high_contrast_available": { "type": "boolean" },
        "screen_reader_optimized": { "type": "boolean" }
      }
    }
  }
}
```

---

## 3. STATE MACHINE DEFINITION

```python
from langgraph.graph import StateGraph, END
from typing import Literal

# NODE DEFINITIONS
def hypothesis_analyst(state):
    """AGENT-01: Formalize raw hypothesis"""
    pass

def human_gate_cp01(state):
    """HITL Checkpoint: Hypothesis Approval"""
    pass

def research_director(state):
    """AGENT-02: Decompose into parallel tasks"""
    pass

def junior_research_pool(state):
    """AGENT-03: Execute parallel research (mapped)"""
    pass

def research_manager(state):
    """AGENT-04: Consolidate findings"""
    pass

def hallucination_verifier(state):
    """AGENT-13: Validate factual grounding and eliminate hallucinations"""
    pass

def research_critic(state):
    """AGENT-05: Adversarial validation"""
    pass

def route_after_critic(state) -> Literal["revise", "proceed", "escalate"]:
    if state["critic_iteration_count"] >= 3:
        return "escalate"
    elif state["research_satisfactory"]:
        return "proceed"
    else:
        return "revise"

def human_gate_cp02(state):
    """HITL Checkpoint: Post-Critic Escalation"""
    pass

def research_editor(state):
    """AGENT-06: Produce multi-format paper"""
    pass

def paper_critic(state):
    """AGENT-07: Validate publication standards"""
    pass

def route_after_paper_critic(state) -> Literal["revise", "proceed"]:
    return "proceed" if state["paper_approved"] else "revise"

def substack_writer(state):
    """AGENT-08: Create article"""
    pass

def visual_graphics_service(state):
    """AGENT-09: Generate visuals (called as tool)"""
    pass

def substack_critic(state):
    """AGENT-10: Audience-fit validation"""
    pass

def human_gate_cp03(state):
    """HITL Checkpoint: Pre-publish Approval"""
    pass

def substack_publisher(state):
    """AGENT-11: Schedule and publish"""
    pass

def email_distributor(state):
    """AGENT-12: Send to paid subscribers"""
    pass

# GRAPH CONSTRUCTION
workflow = StateGraph(ResearchState)

# Phase 1: Hypothesis
workflow.add_node("analyst", hypothesis_analyst)
workflow.add_node("cp01", human_gate_cp01)
workflow.add_edge("analyst", "cp01")

# Phase 2: Research
workflow.add_node("director", research_director)
workflow.add_node("junior_research", junior_research_pool)
workflow.add_node("manager", research_manager)
workflow.add_node("verifier", hallucination_verifier)
workflow.add_node("critic", research_critic)
workflow.add_node("cp02", human_gate_cp02)

workflow.add_edge("cp01", "director")
workflow.add_edge("director", "junior_research")
workflow.add_edge("junior_research", "manager")
workflow.add_edge("manager", "verifier")
workflow.add_edge("verifier", "critic")

# Critic loop with conditional routing
workflow.add_conditional_edges(
    "critic",
    route_after_critic,
    {
        "revise": "manager",
        "proceed": "editor",
        "escalate": "cp02"
    }
)
workflow.add_edge("cp02", "editor")

# Phase 3: Document Production
workflow.add_node("editor", research_editor)
workflow.add_node("paper_critic", paper_critic)
workflow.add_edge("editor", "paper_critic")
workflow.add_conditional_edges(
    "paper_critic",
    route_after_paper_critic,
    {
        "revise": "editor",
        "proceed": "substack_writer"
    }
)

# Parallel: Email distribution
workflow.add_node("email_agent", email_distributor)
workflow.add_edge("paper_critic", "email_agent")

# Phase 4: Substack
workflow.add_node("substack_writer", substack_writer)
workflow.add_node("substack_critic", substack_critic)
workflow.add_node("cp03", human_gate_cp03)
workflow.add_node("publisher", substack_publisher)

workflow.add_edge("substack_writer", "substack_critic")
workflow.add_edge("substack_critic", "cp03")
workflow.add_edge("cp03", "publisher")

# Terminal
workflow.add_edge("publisher", END)
workflow.add_edge("email_agent", END)

# Compile with checkpointing
app = workflow.compile(checkpointer=checkpointer)
```

---

## 4. INTER-AGENT MESSAGE PROTOCOL

All inter-agent communication uses the following envelope format:

```json
{
  "message_id": "uuid",
  "timestamp": "ISO 8601",
  "from_agent": "AGENT-XX",
  "to_agent": "AGENT-YY",
  "message_type": "handoff | query | response | critique | approval | rejection",
  "payload": { },
  "metadata": {
    "session_id": "uuid",
    "pipeline_phase": "hypothesis | research | document | substack | distribution",
    "priority": "critical | high | normal | low",
    "ttl_seconds": 3600
  }
}
```

### Handoff Protocol Matrix

| From | To | Document Type | Validation Required |
|---|---|---|---|
| A01 | A02 | FormalizedHypothesisDocument | Schema validation + human approval |
| A02 | A03 | ResearchTask[] | Task schema + budget check |
| A03 | A04 | PaperExtraction[] | Schema validation + dedup check |
| A04 | A13 | ConsolidatedResearchReport | Verify citations & textual grounding |
| A13 | A05 | VerifiedResearchReport | Grounding validation report pass |
| A05 | A04 | CriticReport (revise) | Iteration count < 3 |
| A05 | A06 | VerifiedResearchReport + approval | Score >= 80 |
| A06 | A13 | ResearchPaperDraft (all formats) | Factual quotation audit |
| A13 | A07 | VerifiedResearchPaperDraft | Safety & citation certification |
| A07 | A06 | ValidationReport (revise) | P0 criteria check |
| A07 | A08 | VerifiedResearchPaperDraft + approval | Hard gate pass |
| A07 | A12 | VerifiedResearchPaperDraft + approval | Trigger email parallel |
| A08 | A13 | SubstackArticle | Auditing claims & simplified stats |
| A13 | A10 | VerifiedSubstackArticle | Grounding certification report |
| A10 | A11 | VerifiedSubstackArticle + approval | CP-03 human gate |
| A09 | A06 | VisualAssets[] | Data-derived check |
| A09 | A08 | VisualAssets[] | Theme compliance |

---

## 5. ERROR HANDLING SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgentError",
  "type": "object",
  "required": ["error_id", "agent_id", "error_type", "severity"],
  "properties": {
    "error_id": { "type": "string", "format": "uuid" },
    "session_id": { "type": "string", "format": "uuid" },
    "agent_id": { "type": "string", "pattern": "^AGENT-[0-9]{2}$" },
    "error_type": {
      "type": "string",
      "enum": [
        "schema_validation_failed",
        "api_rate_limit",
        "api_timeout",
        "model_hallucination",
        "citation_not_found",
        "pdf_parsing_failed",
        "token_budget_exceeded",
        "human_gate_timeout",
        "publishing_failed",
        "email_delivery_failed"
      ]
    },
    "severity": {
      "type": "string",
      "enum": ["fatal", "error", "warning", "info"]
    },
    "message": { "type": "string" },
    "context": { "type": "object" },
    "retry_count": { "type": "integer", "minimum": 0 },
    "max_retries": { "type": "integer", "minimum": 0 },
    "resolution": {
      "type": "string",
      "enum": ["pending", "auto_resolved", "human_required", "escalated", "abandoned"]
    }
  }
}
```

---

## 6. COST TRACKING SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CostTracking",
  "type": "object",
  "properties": {
    "session_id": { "type": "string" },
    "total_cost_usd": { "type": "number" },
    "total_tokens": { "type": "integer" },
    "agent_breakdown": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": { "type": "string" },
          "model": { "type": "string" },
          "input_tokens": { "type": "integer" },
          "output_tokens": { "type": "integer" },
          "cost_usd": { "type": "number" },
          "iterations": { "type": "integer" }
        }
      }
    },
    "api_costs": {
      "type": "object",
      "properties": {
        "academic_apis": { "type": "number" },
        "image_generation": { "type": "number" },
        "email_delivery": { "type": "number" },
        "storage": { "type": "number" }
      }
    }
  }
}
```

---

## 7. VERSIONING & MIGRATION

| Schema Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-07-23 | Initial release |

All schema changes follow semantic versioning:
- **Major**: Breaking changes to required fields
- **Minor**: New optional fields added
- **Patch**: Documentation corrections, no structural changes

Migration strategy: Blue-green deployment with schema validation at each node entry.
