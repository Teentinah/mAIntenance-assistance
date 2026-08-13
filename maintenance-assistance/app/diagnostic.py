"""Extraction d'informations de diagnostic et détection des informations manquantes.

Exigence §3.2 : identifier utilisateur, équipement, application/service, symptômes, moment
d'apparition, impact sur l'activité, manipulations déjà effectuées ; poser des questions
ciblées quand les informations sont insuffisantes plutôt que de proposer une solution
prématurée.
"""
from __future__ import annotations

import re
import unicodedata

from app.data_store import get_store
from app.models import DiagnosticInfo

# Champs requis selon la catégorie : au-delà du symptôme et du moment, certaines catégories
# nécessitent en plus un équipement ou un utilisateur identifié pour permettre l'action.
REQUIRED_FIELDS_BY_CATEGORY = {
    "comptes_et_authentification": ["utilisateur", "symptomes"],
    "reseau_et_connectivite": ["symptomes", "moment_apparition"],
    "materiel_informatique": ["equipement", "symptomes"],
    "logiciels_et_applications": ["application_ou_service", "symptomes"],
    "imprimantes_et_peripheriques": ["equipement", "symptomes"],
    "droits_acces": ["utilisateur", "application_ou_service"],
    "cybersecurite": ["symptomes", "moment_apparition"],
    "autre_ou_indetermine": ["symptomes"],
}

QUESTIONS = {
    "utilisateur": "Merci de préciser le nom, l'identifiant ou l'adresse e-mail de l'utilisateur concerné.",
    "equipement": "Quel équipement est concerné (poste fixe, portable, identifiant si connu) ?",
    "application_ou_service": "Quelle application ou quel service est concerné précisément ?",
    "symptomes": "Pouvez-vous décrire précisément ce qui se passe (message d'erreur, comportement observé) ?",
    "moment_apparition": "Depuis quand rencontrez-vous ce problème ?",
    "impact_activite": "Ce problème vous empêche-t-il de travailler normalement ? Combien de personnes sont concernées ?",
}

EQUIPMENT_ID_PATTERN = re.compile(r"\b(PC|LAP|IMP)-\d{3,4}\b", re.IGNORECASE)

APPLICATION_KEYWORDS = [
    "erp", "crm", "outlook", "excel", "word", "vpn", "wifi", "messagerie", "imprimante",
    "windows", "antivirus", "scanner",
]

TEMPORAL_PATTERNS = [
    r"depuis\s+ce\s+matin", r"depuis\s+hier(\s+soir)?", r"depuis\s+\d+\s*(min(ute)?s?|heures?|jours?)",
    r"il\s+y\s+a\s+\d+\s*(min(ute)?s?|heures?|jours?)", r"ce\s+matin", r"hier\s+soir",
    r"depuis\s+la\s+mise\s+a\s+jour", r"depuis\s+la\s+derniere\s+mise\s+a\s+jour",
]

IMPACT_PATTERNS = [
    r"tout\s+le\s+(service|batiment|monde)", r"personne\s+ne\s+peut", r"impossible\s+de\s+travailler",
    r"production\s+a\s+l['e]arret", r"arret\s+de\s+la\s+(ligne|production)", r"plusieurs\s+(collegues|utilisateurs|personnes)",
    r"cloture", r"bloque[e]?", r"urgent",
]

MANIPULATION_PATTERNS = [
    r"j['e]ai\s+deja\s+(essaye|tente|redemarre)", r"deja\s+redemarre", r"redemarrage\s+deja\s+fait",
    r"sans\s+succes", r"j['e]ai\s+tente\s+de",
]

SYMPTOM_KEYWORDS = [
    "plante", "crash", "ecran noir", "ecran blanc", "ne demarre plus", "ne s'allume plus",
    "n'imprime plus", "bloque", "lent", "lenteur", "deconnecte", "erreur", "mot de passe",
    "verrouille", "hors service", "coupure", "impossible", "ralenti", "bruit", "odeur",
    "fenetres pub", "popup", "processus inconnu", "desactive", "comportement bizarre",
    "comportement anormal", "suspect", "virus", "phishing", "aucune connexion",
    "perte de connexion", "ne fonctionne plus", "panne",
]


def _normalize(text: str) -> str:
    text = text.lower()
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _find_user_mention(texte: str):
    store = get_store()
    norm_text = _normalize(texte)
    for u in store.users:
        prenom_nom = _normalize(u["nom"])
        parts = prenom_nom.split()
        if prenom_nom in norm_text or any(p in norm_text.split() for p in parts if len(p) > 3):
            return u["nom"]
    return None


def _find_equipment_mention(texte: str):
    m = EQUIPMENT_ID_PATTERN.search(texte)
    if m:
        return m.group(0).upper()
    norm = _normalize(texte)
    if "portable" in norm or "laptop" in norm:
        return "ordinateur portable (identifiant non précisé)"
    if "imprimante" in norm:
        return "imprimante (identifiant non précisé)"
    if "poste" in norm or "ordinateur" in norm or "pc" in norm.split():
        return "poste de travail (identifiant non précisé)"
    return None


def _find_application(texte: str):
    norm = _normalize(texte)
    for kw in APPLICATION_KEYWORDS:
        if kw in norm:
            return kw
    return None


def _find_matches(texte: str, patterns: list[str]) -> list[str]:
    norm = _normalize(texte)
    found = []
    for p in patterns:
        m = re.search(p, norm)
        if m:
            found.append(m.group(0))
    return found


def _find_symptoms(texte: str) -> list[str]:
    norm = _normalize(texte)
    return [kw for kw in SYMPTOM_KEYWORDS if kw in norm]


def diagnose(texte: str, categorie: str) -> DiagnosticInfo:
    utilisateur = _find_user_mention(texte)
    equipement = _find_equipment_mention(texte)
    application = _find_application(texte)
    symptomes = _find_symptoms(texte)

    moments = _find_matches(texte, TEMPORAL_PATTERNS)
    impacts = _find_matches(texte, IMPACT_PATTERNS)
    manipulations = _find_matches(texte, MANIPULATION_PATTERNS)

    found = {
        "utilisateur": utilisateur,
        "equipement": equipement,
        "application_ou_service": application,
        "symptomes": symptomes,
        "moment_apparition": moments[0] if moments else None,
        "impact_activite": ", ".join(impacts) if impacts else None,
    }

    required = REQUIRED_FIELDS_BY_CATEGORY.get(categorie, ["symptomes"])
    missing = []
    for field in required:
        value = found.get(field)
        empty = value is None or (isinstance(value, list) and not value)
        if empty:
            missing.append(field)

    questions = [QUESTIONS[f] for f in missing]

    return DiagnosticInfo(
        utilisateur=utilisateur,
        equipement=equipement,
        application_ou_service=application,
        symptomes=symptomes,
        moment_apparition=found["moment_apparition"],
        impact_activite=found["impact_activite"],
        manipulations_effectuees=", ".join(manipulations) if manipulations else None,
        informations_manquantes=missing,
        questions_ciblees=questions,
    )
