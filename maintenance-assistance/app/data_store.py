"""Chargement des données de référence et simulation d'un système de ticketing en mémoire."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(name: str):
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


class DataStore:
    """Accès en lecture aux référentiels + état mutable des tickets (simulation de DB)."""

    def __init__(self):
        self.users = _load_json("users.json")
        self.equipments = _load_json("equipments.json")
        self.services = _load_json("services.json")
        self.active_incidents = _load_json("active_incidents.json")
        self.tickets_history = _load_json("tickets_history.json")
        self.tickets_queue = _load_json("tickets_queue.json")
        self.tools_spec = _load_json("tools_spec.json")

        self._lock = Lock()
        self._tickets: dict[str, dict] = {}
        self._next_ticket_num = 2000

    # --- Référentiels (lecture) -------------------------------------------------
    def find_user(self, query: str) -> Optional[dict]:
        q = (query or "").strip().lower()
        for u in self.users:
            if q in (u["nom"].lower(), u["email"].lower(), u["user_id"].lower()) or q in u["nom"].lower():
                return u
        return None

    def find_equipment(self, equipement_id_ou_user_id: str) -> Optional[dict]:
        q = (equipement_id_ou_user_id or "").strip().lower()
        for e in self.equipments:
            if e["equipement_id"].lower() == q:
                return e
        for e in self.equipments:
            if e.get("utilisateur_id") and e["utilisateur_id"].lower() == q:
                return e
        return None

    def get_service(self, service_id: str) -> Optional[dict]:
        q = (service_id or "").strip().lower()
        for s in self.services:
            if s["service_id"].lower() == q or s["nom"].lower() == q:
                return s
        return None

    def search_active_incidents(self, service_id: str = None, categorie: str = None) -> list[dict]:
        results = self.active_incidents
        if service_id:
            results = [i for i in results if i["service_id"].lower() == service_id.lower()]
        if categorie:
            results = [i for i in results if i["categorie"].lower() == categorie.lower()]
        return results

    # --- Tickets (écriture, simulation de DB) ------------------------------------
    def create_ticket(self, categorie: str, priorite: str, description: str, user_id: str = None) -> dict:
        with self._lock:
            self._next_ticket_num += 1
            ticket_id = f"T-{self._next_ticket_num}"
            ticket = {
                "ticket_id": ticket_id,
                "categorie": categorie,
                "priorite": priorite,
                "description": description,
                "user_id": user_id,
                "statut": "ouvert",
                "equipe": None,
            }
            self._tickets[ticket_id] = ticket
            return ticket

    def update_ticket(self, ticket_id: str, champs: dict) -> Optional[dict]:
        with self._lock:
            t = self._tickets.get(ticket_id)
            if not t:
                return None
            t.update(champs)
            return t

    def assign_ticket(self, ticket_id: str, equipe: str) -> Optional[dict]:
        return self.update_ticket(ticket_id, {"equipe": equipe, "statut": "affecte"})

    def escalate_ticket(self, ticket_id: str, motif: str) -> Optional[dict]:
        return self.update_ticket(ticket_id, {"statut": "escalade", "motif_escalade": motif})

    def get_ticket(self, ticket_id: str) -> Optional[dict]:
        return self._tickets.get(ticket_id)


_store: Optional[DataStore] = None


def get_store() -> DataStore:
    global _store
    if _store is None:
        _store = DataStore()
    return _store
