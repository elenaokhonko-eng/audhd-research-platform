from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from platform_app.models import LiteratureChunk, LiteratureDocument
from platform_app.settings import Settings


@dataclass(slots=True)
class RetrievalHit:
    document_id: str
    chunk_id: str
    title: str
    doi: str | None
    text: str
    page_start: int | None
    score: float


class EmbeddingProvider:
    def __init__(self, settings: Settings):
        self.model = settings.embedding_model
        self.client = OpenAI(api_key=settings.embedding_api_key, base_url=settings.embedding_base_url)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


class LiteratureRag:
    def __init__(self, session: Session, embeddings: EmbeddingProvider):
        self.session = session
        self.embeddings = embeddings

    def search(self, query: str, limit: int = 10, verified_only: bool = True) -> list[RetrievalHit]:
        vector = self.embeddings.embed([query])[0]
        distance = LiteratureChunk.embedding.cosine_distance(vector)
        vector_statement: Select = (
            select(LiteratureChunk, LiteratureDocument, distance.label("distance"))
            .join(LiteratureDocument, LiteratureDocument.id == LiteratureChunk.document_id)
            .where(LiteratureChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(min(limit, 50))
        )
        if verified_only:
            vector_statement = vector_statement.where(LiteratureDocument.verified.is_(True))
        vector_results = self.session.execute(vector_statement).all()

        query_expression = func.plainto_tsquery("english", query)
        rank = func.ts_rank_cd(func.to_tsvector("english", LiteratureChunk.text), query_expression)
        keyword_statement = (
            select(LiteratureChunk, LiteratureDocument, rank.label("rank"))
            .join(LiteratureDocument, LiteratureDocument.id == LiteratureChunk.document_id)
            .where(func.to_tsvector("english", LiteratureChunk.text).op("@@")(query_expression))
            .order_by(rank.desc())
            .limit(min(limit * 3, 50))
        )
        if verified_only:
            keyword_statement = keyword_statement.where(LiteratureDocument.verified.is_(True))
        keyword_results = self.session.execute(keyword_statement).all()

        fused: dict[str, dict] = {}
        for rank_index, row in enumerate(vector_results, 1):
            chunk, document, _ = row
            fused[str(chunk.id)] = {"chunk": chunk, "document": document, "score": 1 / (60 + rank_index)}
        for rank_index, row in enumerate(keyword_results, 1):
            chunk, document, _ = row
            item = fused.setdefault(str(chunk.id), {"chunk": chunk, "document": document, "score": 0.0})
            item["score"] += 1 / (60 + rank_index)
        ranked = sorted(fused.values(), key=lambda item: item["score"], reverse=True)[:limit]
        return [RetrievalHit(document_id=str(item["document"].id), chunk_id=str(item["chunk"].id), title=item["document"].title, doi=item["document"].doi, text=item["chunk"].text, page_start=item["chunk"].page_start, score=round(item["score"], 6)) for item in ranked]
