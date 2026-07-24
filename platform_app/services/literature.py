from dataclasses import dataclass, field
from html import unescape
from typing import Protocol
from urllib.parse import quote
from xml.etree import ElementTree

import httpx


@dataclass(slots=True)
class ScholarlyWork:
    source: str
    external_id: str
    title: str
    abstract: str | None = None
    doi: str | None = None
    publication_year: int | None = None
    source_url: str | None = None
    full_text_url: str | None = None
    is_retracted: bool = False
    authors: list[str] = field(default_factory=list)
    raw_metadata: dict = field(default_factory=dict)


class LiteratureConnector(Protocol):
    def search(self, query: str, limit: int = 20) -> list[ScholarlyWork]: ...


class ResearchHttpClient:
    def __init__(self, mailto: str | None = None, timeout: float = 30.0):
        user_agent = "audhd-research-platform/0.1"
        if mailto:
            user_agent += f" (mailto:{mailto})"
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

    def close(self) -> None:
        self.client.close()


class PubMedConnector(ResearchHttpClient):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key

    def search(self, query: str, limit: int = 20) -> list[ScholarlyWork]:
        params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": min(limit, 100)}
        if self.api_key:
            params["api_key"] = self.api_key
        search = self.client.get(f"{self.base_url}/esearch.fcgi", params=params)
        search.raise_for_status()
        ids = search.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        fetch_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
        if self.api_key:
            fetch_params["api_key"] = self.api_key
        response = self.client.get(f"{self.base_url}/efetch.fcgi", params=fetch_params)
        response.raise_for_status()
        return self._parse(response.text)

    @staticmethod
    def _parse(xml: str) -> list[ScholarlyWork]:
        root = ElementTree.fromstring(xml)
        works: list[ScholarlyWork] = []
        for article in root.findall(".//PubmedArticle"):
            citation = article.find("MedlineCitation")
            if citation is None:
                continue
            pmid = "".join(citation.findtext("PMID", default=""))
            title_node = citation.find(".//ArticleTitle")
            title = "".join(title_node.itertext()) if title_node is not None else "Untitled"
            abstracts = ["".join(node.itertext()) for node in citation.findall(".//AbstractText")]
            doi = None
            for identifier in article.findall(".//ArticleId"):
                if identifier.attrib.get("IdType") == "doi":
                    doi = identifier.text
            year_text = citation.findtext(".//PubDate/Year")
            authors = []
            for author in citation.findall(".//Author"):
                name = " ".join(filter(None, [author.findtext("ForeName"), author.findtext("LastName")]))
                if name:
                    authors.append(name)
            works.append(
                ScholarlyWork(
                    source="pubmed",
                    external_id=pmid,
                    title=unescape(title),
                    abstract="\n".join(abstracts) or None,
                    doi=doi,
                    publication_year=int(year_text) if year_text and year_text.isdigit() else None,
                    source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    authors=authors,
                )
            )
        return works


class CrossrefConnector(ResearchHttpClient):
    base_url = "https://api.crossref.org"

    def search(self, query: str, limit: int = 20) -> list[ScholarlyWork]:
        response = self.client.get(
            f"{self.base_url}/works",
            params={"query.bibliographic": query, "rows": min(limit, 100), "select": "DOI,title,author,published,URL,abstract,type"},
        )
        response.raise_for_status()
        return [self._work(item) for item in response.json()["message"]["items"]]

    def resolve_doi(self, doi: str) -> ScholarlyWork | None:
        response = self.client.get(f"{self.base_url}/works/{quote(doi, safe='')}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return self._work(response.json()["message"])

    @staticmethod
    def _work(item: dict) -> ScholarlyWork:
        date_parts = item.get("published", {}).get("date-parts", [[]])[0]
        authors = [
            " ".join(filter(None, [author.get("given"), author.get("family")]))
            for author in item.get("author", [])
        ]
        doi = item.get("DOI")
        return ScholarlyWork(
            source="crossref",
            external_id=doi or item.get("URL", ""),
            title=" ".join(item.get("title", [])) or "Untitled",
            abstract=item.get("abstract"),
            doi=doi,
            publication_year=date_parts[0] if date_parts else None,
            source_url=item.get("URL"),
            authors=authors,
            raw_metadata=item,
        )


class OpenAlexConnector(ResearchHttpClient):
    base_url = "https://api.openalex.org/works"

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key

    def search(self, query: str, limit: int = 20) -> list[ScholarlyWork]:
        params = {"search": query, "per-page": min(limit, 100)}
        if self.api_key:
            params["api_key"] = self.api_key
        response = self.client.get(self.base_url, params=params)
        response.raise_for_status()
        return [self._work(item) for item in response.json().get("results", [])]

    @staticmethod
    def _abstract(index: dict | None) -> str | None:
        if not index:
            return None
        words = [(position, word) for word, positions in index.items() for position in positions]
        return " ".join(word for _, word in sorted(words))

    @classmethod
    def _work(cls, item: dict) -> ScholarlyWork:
        primary = item.get("primary_location") or {}
        best_oa = item.get("best_oa_location") or {}
        authors = [entry.get("author", {}).get("display_name", "") for entry in item.get("authorships", [])]
        doi_url = item.get("doi")
        return ScholarlyWork(
            source="openalex",
            external_id=item["id"].rsplit("/", 1)[-1],
            title=item.get("display_name") or "Untitled",
            abstract=cls._abstract(item.get("abstract_inverted_index")),
            doi=doi_url.removeprefix("https://doi.org/") if doi_url else None,
            publication_year=item.get("publication_year"),
            source_url=primary.get("landing_page_url") or item.get("id"),
            full_text_url=best_oa.get("pdf_url") or best_oa.get("landing_page_url"),
            is_retracted=bool(item.get("is_retracted")),
            authors=[name for name in authors if name],
            raw_metadata=item,
        )


def merge_works(*collections: list[ScholarlyWork]) -> list[ScholarlyWork]:
    """Deduplicate provider results by DOI, falling back to normalized title."""
    merged: dict[str, ScholarlyWork] = {}
    for work in (item for collection in collections for item in collection):
        key = f"doi:{work.doi.lower()}" if work.doi else f"title:{' '.join(work.title.lower().split())}"
        existing = merged.get(key)
        if not existing or (not existing.abstract and work.abstract):
            merged[key] = work
    return list(merged.values())
