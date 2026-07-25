import re
import unicodedata
from dataclasses import dataclass, field

from platform_app.services.literature import CrossrefConnector, ScholarlyWork

NUMBER_PATTERN = re.compile(r"(?<!\w)[+-]?(?:\d+(?:\.\d+)?|\.\d+)%?(?!\w)")
WORD_PATTERN = re.compile(r"[a-z0-9]+")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return " ".join(WORD_PATTERN.findall(value))


def numbers(value: str) -> set[str]:
    return {match.group(0).lstrip("+") for match in NUMBER_PATTERN.finditer(value)}


@dataclass(slots=True)
class VerificationResult:
    status: str
    doi_resolves: bool
    quotation_grounded: bool | None
    numbers_grounded: bool
    lexical_support: float
    reasons: list[str] = field(default_factory=list)


class ClaimVerifier:
    """Conservative deterministic gate; uncertain claims require human review."""

    def __init__(self, crossref: CrossrefConnector):
        self.crossref = crossref

    def verify(
        self,
        claim: str,
        source_text: str,
        work: ScholarlyWork,
        quotation: str | None = None,
    ) -> VerificationResult:
        reasons: list[str] = []
        doi_resolves = bool(work.doi and self.crossref.resolve_doi(work.doi))
        if not doi_resolves:
            reasons.append("DOI is missing or did not resolve through Crossref")

        normalized_source = normalize_text(source_text)
        quotation_grounded = None
        if quotation:
            quotation_grounded = normalize_text(quotation) in normalized_source
            if not quotation_grounded:
                reasons.append("Quotation was not found in the stored source passage")

        claim_numbers = numbers(claim)
        source_numbers = numbers(source_text)
        numbers_grounded = claim_numbers.issubset(source_numbers)
        if not numbers_grounded:
            reasons.append(f"Unsupported numerical tokens: {sorted(claim_numbers - source_numbers)}")

        claim_words = set(normalize_text(claim).split())
        source_words = set(normalized_source.split())
        lexical_support = len(claim_words & source_words) / max(len(claim_words), 1)
        if lexical_support < 0.65:
            reasons.append("Claim has insufficient lexical support in the cited passage")

        verified = (
            doi_resolves
            and numbers_grounded
            and quotation_grounded is not False
            and lexical_support >= 0.65
            and not work.is_retracted
        )
        if work.is_retracted:
            reasons.append("Source is marked as retracted")
        return VerificationResult(
            status="verified" if verified else "needs_review",
            doi_resolves=doi_resolves,
            quotation_grounded=quotation_grounded,
            numbers_grounded=numbers_grounded,
            lexical_support=round(lexical_support, 3),
            reasons=reasons,
        )
