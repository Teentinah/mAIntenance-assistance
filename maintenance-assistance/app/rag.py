"""Recherche documentaire (RAG) sur la base de connaissances.

Approche volontairement simple et explicable : indexation TF-IDF des sections de chaque
fiche de la base de connaissances, recherche par similarité cosinus, réponse extractive
(les passages retrouvés sont montrés tels quels, avec leur source) plutôt que reformulée
par un LLM. Cela évite le risque d'hallucination et rend chaque réponse vérifiable.

Si aucun passage ne dépasse le seuil de confiance, la réponse est signalée comme incertaine
(exigence du sujet §3.3 et §5.1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import RagResult, SourceCitee

KB_DIR = Path(__file__).resolve().parent.parent / "data" / "kb"

SIMILARITY_THRESHOLD = 0.18  # en dessous : réponse jugée non soutenue par les sources

FRENCH_STOPWORDS = [
    "au", "aux", "avec", "ce", "ces", "cette", "dans", "de", "des", "du", "elle", "en",
    "et", "eux", "il", "ils", "je", "la", "le", "les", "leur", "leurs", "lui", "ma", "mais",
    "me", "meme", "mes", "moi", "mon", "ne", "nos", "notre", "nous", "on", "ou", "où", "par",
    "pas", "plus", "pour", "qu", "que", "qui", "sa", "se", "ses", "son", "sur", "ta", "te",
    "tes", "toi", "ton", "tu", "un", "une", "vos", "votre", "vous", "d", "l", "c", "s", "n",
    "y", "à", "est", "sont", "etre", "avoir", "a", "ont", "si", "car", "donc", "or", "ni",
]


@dataclass
class Chunk:
    doc_id: str
    titre: str
    categorie: str
    section: str
    texte: str


def _parse_kb_file(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    meta = {}
    body = raw
    if raw.startswith("---"):
        end = raw.find("---", 3)
        front = raw[3:end].strip().splitlines()
        for line in front:
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = raw[end + 3:]
    return meta, body


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Découpe le corps markdown en sections par titre `## `."""
    sections = []
    current_title = "Introduction"
    current_lines: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = m.group(1).strip()
            current_lines = []
        elif line.startswith("# "):
            continue
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return [(t, c) for t, c in sections if c]


class RagEngine:
    def __init__(self, kb_dir: Path = KB_DIR):
        self.chunks: list[Chunk] = []
        for path in sorted(kb_dir.glob("*.md")):
            meta, body = _parse_kb_file(path)
            for section_title, section_text in _split_sections(body):
                self.chunks.append(
                    Chunk(
                        doc_id=meta.get("id", path.stem),
                        titre=meta.get("titre", path.stem),
                        categorie=meta.get("categorie", ""),
                        section=section_title,
                        texte=section_text,
                    )
                )
        corpus = [f"{c.titre} {c.section} {c.texte}" for c in self.chunks]
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            min_df=1,
            stop_words=FRENCH_STOPWORDS,
        )
        self.matrix = self.vectorizer.fit_transform(corpus) if corpus else None

    def search(self, query: str, top_k: int = 3, categorie: str | None = None) -> list[SourceCitee]:
        if self.matrix is None or not query.strip():
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix)[0]

        ranked = sorted(range(len(self.chunks)), key=lambda i: sims[i], reverse=True)
        results = []
        for i in ranked:
            chunk = self.chunks[i]
            if categorie and chunk.categorie and chunk.categorie != categorie:
                continue
            if sims[i] <= 0:
                continue
            results.append(
                SourceCitee(
                    doc_id=chunk.doc_id,
                    titre=f"{chunk.titre} — {chunk.section}",
                    extrait=chunk.texte[:400],
                    score=round(float(sims[i]), 4),
                )
            )
            if len(results) >= top_k:
                break
        return results

    def answer(self, query: str, categorie: str | None = None, top_k: int = 3) -> RagResult:
        sources = self.search(query, top_k=top_k, categorie=categorie)
        if not sources or sources[0].score < SIMILARITY_THRESHOLD:
            return RagResult(reponse=None, sources=sources, incertain=True)

        reponse = "\n\n".join(f"[{s.doc_id}] {s.extrait}" for s in sources)
        return RagResult(reponse=reponse, sources=sources, incertain=False)


_engine: RagEngine | None = None


def get_rag_engine() -> RagEngine:
    global _engine
    if _engine is None:
        _engine = RagEngine()
    return _engine
