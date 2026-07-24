from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy import Select, select
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
        statement: Select = (
            select(LiteratureChunk, LiteratureDocument, distance.label("distance"))
            .join(LiteratureDocument, LiteratureDocument.id == LiteratureChunk.document_id)
            .where(LiteratureChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(min(limit, 50))
        )
        if verified_only:
            statement = statement.where(LiteratureDocument.verified.is_(True))
        results = self.session.execute(statement).all()
        return [
            RetrievalHit(
                document_id=str(document.id),
                chunk_id=str(chunk.id),
                title=document.title,
                doi=document.doi,
                text=chunk.text,
                page_start=chunk.page_start,
                score=round(1 - float(item.distance), 4),
            )
            for item in results
            for chunk, document in [(item[0], item[1])]
        ]
