import re
from dataclasses import dataclass
from datetime import datetime

DIRECT_IDENTIFIER_FIELDS = {
    "name", "full_name", "given_name", "family_name", "email", "phone", "address",
    "passport", "national_id", "medical_record_number", "nric", "date_of_birth",
}
IDENTIFIER_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone": re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"),
    "singapore_nric_fin": re.compile(r"\b[STFGM]\d{7}[A-Z]\b", re.I),
}


@dataclass(slots=True)
class ClinicalIngestionResult:
    accepted: bool
    reasons: list[str]
    normalized: dict | None = None


def validate_clinical_observation(payload: dict) -> ClinicalIngestionResult:
    reasons: list[str] = []
    present = DIRECT_IDENTIFIER_FIELDS.intersection(key.lower() for key in payload)
    if present:
        reasons.append(f"Direct identifier fields are prohibited: {sorted(present)}")
    required = {"pseudonym", "concept_code", "value", "consent_basis", "source_system"}
    missing = required - payload.keys()
    if missing:
        reasons.append(f"Missing required fields: {sorted(missing)}")
    for key, value in payload.items():
        if isinstance(value, str):
            for label, pattern in IDENTIFIER_PATTERNS.items():
                if pattern.search(value):
                    reasons.append(f"Potential {label} detected in field '{key}'")
    if reasons:
        return ClinicalIngestionResult(False, reasons)
    normalized = {
        "pseudonym": str(payload["pseudonym"]),
        "concept_code": str(payload["concept_code"]),
        "value": payload["value"],
        "observed_at": payload.get("observed_at"),
        "consent_basis": str(payload["consent_basis"]),
        "source_system": str(payload["source_system"]),
        "ingested_at": datetime.utcnow().isoformat() + "Z",
    }
    return ClinicalIngestionResult(True, [], normalized)
