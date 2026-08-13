"""Garde-fous de sécurité : détection de prompt injection, données personnelles,
et règles de validation humaine sur les actions sensibles (exigences §6 du sujet).
"""
from __future__ import annotations

import re
import unicodedata

from app.data_store import get_store
from app.models import SecurityFlags

INJECTION_PATTERNS = [
    r"ignore\s+(toutes\s+les\s+|tes\s+)?instructions",
    r"ignore\s+les\s+consignes",
    r"tu\s+es\s+maintenant\s+en\s+mode",
    r"mode\s+(developpeur|admin|administrateur)\s+sans\s+restriction",
    r"sans\s+(passer\s+par\s+la\s+)?validation",
    r"desactiver?\s+la\s+validation",
    r"en\s+tant\s+qu[' ]administrateur.*je\s+(t'ordonne|exige)",
    r"\[system\]",
    r"nouvelle\s+regle\s*:",
    r"donne[- ]moi\s+(la\s+)?liste\s+de(s)?\s+(tous\s+les\s+)?mots\s+de\s+passe",
    r"mots\s+de\s+passe\s+en\s+clair",
    r"supprime\s+tous\s+les\s+comptes",
    r"acces\s+admin.*immediatement",
    r"execute\s+la\s+commande\s+suivante",
    r"je\s+confirme\s+par\s+ce\s+ticket",
    r"sans\s+lui\s+demander",
]

PII_PATTERNS = [
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # email
    r"\b0\d{9}\b",  # numéro de téléphone (format MG/FR 10 chiffres)
    r"\b\d{2}[/.-]\d{2}[/.-]\d{4}\b",  # date de naissance potentielle
]

SENSITIVE_CATEGORIES = {"cybersecurite"}


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text


def detect_injection(texte: str) -> tuple[bool, list[str]]:
    norm = _normalize(texte)
    matched = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, norm):
            matched.append(pattern)
    return (len(matched) > 0, matched)


def detect_pii(texte: str) -> bool:
    for pattern in PII_PATTERNS:
        if re.search(pattern, texte):
            return True
    return False


def is_tool_sensitive(tool_name: str) -> bool:
    store = get_store()
    for spec in store.tools_spec:
        if spec["nom"] == tool_name:
            return bool(spec.get("sensible", False))
    return False


def requires_human_validation(categorie: str, tool_name: str | None = None) -> bool:
    if categorie in SENSITIVE_CATEGORIES:
        return True
    if tool_name and is_tool_sensitive(tool_name):
        return True
    return False


def evaluate_security(texte: str, categorie: str) -> SecurityFlags:
    injection, indices = detect_injection(texte)
    pii = detect_pii(texte)
    action_sensible = requires_human_validation(categorie)
    return SecurityFlags(
        injection_detectee=injection,
        indices=indices,
        action_sensible=action_sensible or injection,
        donnees_personnelles_detectees=pii,
    )
