"""Outils (réels sur les données simulées) que l'agent peut appeler (exigence §3.4 / §5.2).

Chaque outil valide ses paramètres et peut échouer proprement (erreur capturée par l'agent,
jamais une exception qui remonte silencieusement). Les outils marqués `sensible=True` dans
`data/tools_spec.json` ne sont jamais exécutés directement : ils sont mis en attente de
validation humaine par l'agent (voir `app/agent.py`).
"""
from __future__ import annotations

from app.data_store import get_store


class ToolError(Exception):
    pass


def rechercher_utilisateur(query: str) -> dict:
    if not query or not query.strip():
        raise ToolError("Paramètre 'query' manquant ou vide.")
    user = get_store().find_user(query)
    if not user:
        return {"trouve": False, "message": f"Aucun utilisateur trouvé pour '{query}'."}
    return {"trouve": True, "utilisateur": user}


def consulter_equipement(equipement_id_ou_user_id: str) -> dict:
    if not equipement_id_ou_user_id or not equipement_id_ou_user_id.strip():
        raise ToolError("Paramètre 'equipement_id_ou_user_id' manquant ou vide.")
    eq = get_store().find_equipment(equipement_id_ou_user_id)
    if not eq:
        return {"trouve": False, "message": f"Aucun équipement trouvé pour '{equipement_id_ou_user_id}'."}
    return {"trouve": True, "equipement": eq}


def verifier_etat_service(service_id: str) -> dict:
    if not service_id or not service_id.strip():
        raise ToolError("Paramètre 'service_id' manquant ou vide.")
    svc = get_store().get_service(service_id)
    if not svc:
        return {"trouve": False, "message": f"Service '{service_id}' inconnu."}
    return {"trouve": True, "service": svc}


def rechercher_incidents_actifs(service_id: str | None = None, categorie: str | None = None) -> dict:
    incidents = get_store().search_active_incidents(service_id=service_id, categorie=categorie)
    return {"nombre": len(incidents), "incidents": incidents}


def creer_ticket(categorie: str, priorite: str, description: str, user_id: str | None = None) -> dict:
    if not categorie or not priorite or not description:
        raise ToolError("Paramètres 'categorie', 'priorite' et 'description' requis pour créer un ticket.")
    ticket = get_store().create_ticket(categorie=categorie, priorite=priorite, description=description, user_id=user_id)
    return {"cree": True, "ticket": ticket}


def mettre_a_jour_ticket(ticket_id: str, champs: dict) -> dict:
    if not ticket_id:
        raise ToolError("Paramètre 'ticket_id' requis.")
    ticket = get_store().update_ticket(ticket_id, champs or {})
    if not ticket:
        raise ToolError(f"Ticket '{ticket_id}' introuvable.")
    return {"mis_a_jour": True, "ticket": ticket}


def affecter_ticket(ticket_id: str, equipe: str) -> dict:
    if not ticket_id or not equipe:
        raise ToolError("Paramètres 'ticket_id' et 'equipe' requis.")
    ticket = get_store().assign_ticket(ticket_id, equipe)
    if not ticket:
        raise ToolError(f"Ticket '{ticket_id}' introuvable.")
    return {"affecte": True, "ticket": ticket}


def escalader_vers_technicien(ticket_id: str, motif: str) -> dict:
    if not ticket_id or not motif:
        raise ToolError("Paramètres 'ticket_id' et 'motif' requis.")
    ticket = get_store().escalate_ticket(ticket_id, motif)
    if not ticket:
        raise ToolError(f"Ticket '{ticket_id}' introuvable.")
    return {"escalade": True, "ticket": ticket}


def reinitialiser_mot_de_passe(user_id: str) -> dict:
    if not user_id:
        raise ToolError("Paramètre 'user_id' requis.")
    user = get_store().find_user(user_id)
    if not user:
        raise ToolError(f"Utilisateur '{user_id}' introuvable.")
    return {"reinitialise": True, "utilisateur": user["nom"], "message": "Mot de passe temporaire envoyé à l'adresse professionnelle."}


def modifier_droits_acces(user_id: str, ressource: str, droit: str) -> dict:
    if not user_id or not ressource or not droit:
        raise ToolError("Paramètres 'user_id', 'ressource' et 'droit' requis.")
    user = get_store().find_user(user_id)
    if not user:
        raise ToolError(f"Utilisateur '{user_id}' introuvable.")
    return {"modifie": True, "utilisateur": user["nom"], "ressource": ressource, "droit": droit}


TOOL_REGISTRY = {
    "rechercher_utilisateur": rechercher_utilisateur,
    "consulter_equipement": consulter_equipement,
    "verifier_etat_service": verifier_etat_service,
    "rechercher_incidents_actifs": rechercher_incidents_actifs,
    "creer_ticket": creer_ticket,
    "mettre_a_jour_ticket": mettre_a_jour_ticket,
    "affecter_ticket": affecter_ticket,
    "escalader_vers_technicien": escalader_vers_technicien,
    "reinitialiser_mot_de_passe": reinitialiser_mot_de_passe,
    "modifier_droits_acces": modifier_droits_acces,
}
