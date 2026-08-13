"""Classification des tickets : catégorie, priorité, équipe, confiance.

Approche hybride volontairement simple (le sujet ne récompense pas la complexité pour
elle-même) :
  1. Un score par règles (mots-clés métier par catégorie) — rapide, explicable, robuste
     même avec très peu de données.
  2. Un score par similarité (TF-IDF caractères, robuste aux fautes de frappe) contre
     l'historique de tickets déjà étiquetés (`data/tickets_history.json`) — capture les
     formulations non couvertes par les règles.
Les deux scores sont combinés (moyenne pondérée) pour produire une confiance par catégorie.
Si la meilleure confiance est trop faible, le ticket est signalé comme hors distribution
et classé "autre_ou_indetermine" (exigence §3.1).

La priorité est déduite du vote des voisins les plus proches dans l'historique, puis
rehaussée par des règles de sécurité non négociables (ex: cybersécurité => haute minimum).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.data_store import get_store
from app.models import Categorie, ClassificationResult, Priorite

CATEGORY_TEAM_MAP = {
    "comptes_et_authentification": "comptes_et_acces",
    "reseau_et_connectivite": "infrastructure",
    "materiel_informatique": "support_materiel",
    "logiciels_et_applications": "applications",
    "imprimantes_et_peripheriques": "support_materiel",
    "droits_acces": "comptes_et_acces",
    "cybersecurite": "cybersecurite",
    "autre_ou_indetermine": "support_client",
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "comptes_et_authentification": [
        "mot de passe", "mdp", "connecter", "connexion impossible", "compte verrouille",
        "compte bloque", "session", "identifiant", "authentification", "deconnecte",
        "compte desactive", "reinitialiser",
    ],
    "reseau_et_connectivite": [
        "reseau", "internet", "wifi", "vpn", "connexion internet", "cable", "deconnexion",
        "lenteur reseau", "ping", "debit",
    ],
    "materiel_informatique": [
        "ordinateur", "pc ", "poste", "ecran noir", "ecran reste noir", "aucun signal",
        "s'allume plus", "allume plus", "redemarre", "portable", "laptop", "clavier",
        "souris", "batterie", "ventilateur", "bruit", "panne",
    ],
    "logiciels_et_applications": [
        "application", "logiciel", "erp", "crm", "excel", "outlook", "plante", "crash",
        "demarre plus", "mise a jour", "bug", "erreur", "ecran blanc", "serveur",
        "inaccessible", "base de donnees",
    ],
    "imprimantes_et_peripheriques": [
        "imprimante", "imprimer", "impression", "scanner", "numeriser", "toner",
        "cartouche", "file d'attente",
    ],
    "droits_acces": [
        "acces", "droits", "autorisation", "partage", "dossier partage", "permission",
        "droits administrateur", "acces refuse",
    ],
    "cybersecurite": [
        "phishing", "suspect", "virus", "antivirus", "malware", "hameconnage", "pirate",
        "compromis", "fenetres pub", "popup", "lien suspect", "mail bizarre", "louche",
        "ransomware",
    ],
}

URGENCY_KEYWORDS_HIGH = [
    "urgent", "urgence", "production", "immediat", "toute la production", "tout le service",
    "tout le monde", "impossible de travailler", "arret", "cloture", "personne ne peut",
    "totalement bloque", "totalement inaccessible",
]
URGENCY_KEYWORDS_CRITICAL = [
    "arret de la production", "arret de la ligne", "production a l'arret", "tout le batiment",
    "brule", "odeur de brule", "toute l'entreprise",
]

CONFIDENCE_HORS_DISTRIB_THRESHOLD = 0.20


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text


def _rule_scores(norm_text: str) -> dict[str, float]:
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if _normalize(kw) in norm_text)
        scores[cat] = min(1.0, hits / 1.5)  # ~1-2 mots-clés spécifiques touchés => score plein
    scores.setdefault("autre_ou_indetermine", 0.0)
    return scores


class TicketClassifier:
    def __init__(self):
        store = get_store()
        self.history = store.tickets_history
        texts = [_normalize(t["texte"]) for t in self.history]
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        self.matrix = self.vectorizer.fit_transform(texts) if texts else None

    def _similarity_scores(self, norm_text: str, k: int = 5):
        if self.matrix is None:
            return {}, [], []
        q_vec = self.vectorizer.transform([norm_text])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        ranked_idx = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:k]
        neighbors = [(self.history[i], float(sims[i])) for i in ranked_idx if sims[i] > 0]

        cat_scores: dict[str, list[float]] = defaultdict(list)
        for ticket, sim in neighbors:
            cat_scores[ticket["categorie"]].append(sim)
        agg = {cat: max(vals) for cat, vals in cat_scores.items()}
        return agg, neighbors, ranked_idx

    def classify(self, texte: str) -> ClassificationResult:
        norm_text = _normalize(texte)
        rule_scores = _rule_scores(norm_text)
        sim_scores, neighbors, _ = self._similarity_scores(norm_text)

        combined: dict[str, float] = {}
        all_cats = set(rule_scores) | set(sim_scores) | {c.value for c in Categorie}
        for cat in all_cats:
            r = rule_scores.get(cat, 0.0)
            s = sim_scores.get(cat, 0.0)
            # Les règles priment quand elles matchent (métier explicite) ; la similarité
            # comble les cas non couverts par les mots-clés.
            combined[cat] = 0.7 * r + 0.3 * s

        best_cat = max(combined, key=combined.get)
        best_score = combined[best_cat]

        hors_distribution = best_score < CONFIDENCE_HORS_DISTRIB_THRESHOLD
        if hors_distribution:
            best_cat = "autre_ou_indetermine"
            best_score = combined.get("autre_ou_indetermine", 0.05) or 0.05

        # --- Priorité : vote des voisins + règles d'urgence non négociables -----------
        neighbor_priorities = Counter(t["priorite"] for t, _ in neighbors if t["categorie"] == best_cat)
        if not neighbor_priorities:
            neighbor_priorities = Counter(t["priorite"] for t, _ in neighbors)
        priorite = neighbor_priorities.most_common(1)[0][0] if neighbor_priorities else "basse"

        if any(_normalize(kw) in norm_text for kw in URGENCY_KEYWORDS_CRITICAL):
            priorite = "critique"
        elif any(_normalize(kw) in norm_text for kw in URGENCY_KEYWORDS_HIGH):
            priorite = _max_priority(priorite, "haute")

        if best_cat == "cybersecurite":
            priorite = _max_priority(priorite, "haute")

        equipe = CATEGORY_TEAM_MAP.get(best_cat, "support_client")

        methode = "hybride (règles métier + similarité TF-IDF sur historique)"
        return ClassificationResult(
            categorie=Categorie(best_cat),
            priorite=Priorite(priorite),
            equipe=equipe,
            confiance=round(min(0.98, max(0.05, best_score)), 3),
            hors_distribution=hors_distribution,
            methode=methode,
            scores_categorie={k: round(v, 3) for k, v in combined.items()},
        )


_PRIORITY_ORDER = ["basse", "moyenne", "haute", "critique"]


def _max_priority(a: str, b: str) -> str:
    return a if _PRIORITY_ORDER.index(a) >= _PRIORITY_ORDER.index(b) else b


_classifier: TicketClassifier | None = None


def get_classifier() -> TicketClassifier:
    global _classifier
    if _classifier is None:
        _classifier = TicketClassifier()
    return _classifier
