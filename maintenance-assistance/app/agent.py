"""Agent : sélection raisonnée des outils, validation des paramètres, gestion des erreurs,
contrôle du nombre d'actions et confirmation humaine pour les opérations sensibles (§5.2).

La sélection des outils est pilotée par des règles explicites plutôt que par un LLM afin de
rester déterministe et auditable pour un prototype de hackathon ; chaque décision peut être
retracée à la règle qui l'a produite.
"""
from __future__ import annotations

from app.models import ClassificationResult, DiagnosticInfo, SecurityFlags, ToolCall
from app.security import is_tool_sensitive
from app.tools import TOOL_REGISTRY, ToolError

MAX_TOOL_CALLS = 6

CATEGORY_SERVICE_MAP = {
    "comptes_et_authentification": "SRV-AUTH",
    "reseau_et_connectivite": "SRV-NET",
    "logiciels_et_applications": "SRV-ERP",
    "imprimantes_et_peripheriques": "SRV-PRINT",
}


class Agent:
    """Orchestrateur d'appels d'outils avec garde-fous (limite d'actions, validation humaine)."""

    def __init__(self):
        self.calls: list[ToolCall] = []

    def _call(self, nom: str, parametres: dict, force_pending: bool = False) -> ToolCall:
        if len(self.calls) >= MAX_TOOL_CALLS:
            call = ToolCall(
                nom=nom, parametres=parametres, statut="refuse",
                resultat={"raison": f"Limite de {MAX_TOOL_CALLS} appels d'outils atteinte."},
            )
            self.calls.append(call)
            return call

        sensible = is_tool_sensitive(nom)
        if sensible or force_pending:
            call = ToolCall(
                nom=nom, parametres=parametres, statut="en_attente_validation",
                validation_humaine_requise=True,
                resultat={"raison": "Opération sensible : exécution différée jusqu'à validation humaine."},
            )
            self.calls.append(call)
            return call

        fn = TOOL_REGISTRY.get(nom)
        if fn is None:
            call = ToolCall(nom=nom, parametres=parametres, statut="erreur", resultat={"erreur": "Outil inconnu."})
            self.calls.append(call)
            return call

        try:
            resultat = fn(**parametres)
            call = ToolCall(nom=nom, parametres=parametres, statut="succes", resultat=resultat)
        except ToolError as exc:
            call = ToolCall(nom=nom, parametres=parametres, statut="erreur", resultat={"erreur": str(exc)})
        except Exception as exc:  # noqa: BLE001 - toute erreur d'appel doit être tracée, pas lever
            call = ToolCall(nom=nom, parametres=parametres, statut="erreur", resultat={"erreur": f"Erreur inattendue: {exc}"})
        self.calls.append(call)
        return call

    def run(
        self,
        classification: ClassificationResult,
        diagnostic: DiagnosticInfo,
        security: SecurityFlags,
        ticket_texte: str,
        rag_incertain: bool = False,
    ) -> dict:
        """Exécute la séquence d'outils pertinente et retourne la décision de l'agent."""
        notes: list[str] = []

        # --- Cas 1 : instruction malveillante détectée -> aucune action, refus + escalade sécurité
        if security.injection_detectee:
            notes.append("Instructions suspectes détectées dans le ticket : aucune action automatique exécutée.")
            self._call("rechercher_incidents_actifs", {"categorie": "cybersecurite"})
            return {
                "action": "action_refusee",
                "validation_humaine_requise": True,
                "notes": notes,
            }

        # --- Consultation : utilisateur
        if diagnostic.utilisateur:
            self._call("rechercher_utilisateur", {"query": diagnostic.utilisateur})

        # --- Consultation : équipement (seulement si un identifiant concret a été détecté)
        if diagnostic.equipement and "non précisé" not in diagnostic.equipement:
            self._call("consulter_equipement", {"equipement_id_ou_user_id": diagnostic.equipement})

        # --- Consultation : état du service associé à la catégorie
        service_id = CATEGORY_SERVICE_MAP.get(classification.categorie.value)
        if service_id:
            self._call("verifier_etat_service", {"service_id": service_id})

        # --- Consultation : incidents actifs de la même catégorie
        incidents_call = self._call("rechercher_incidents_actifs", {"categorie": classification.categorie.value})
        incidents = (incidents_call.resultat or {}).get("incidents", []) if incidents_call.statut == "succes" else []

        # --- Décision -----------------------------------------------------------------
        if diagnostic.informations_manquantes:
            notes.append("Informations insuffisantes pour proposer une résolution fiable.")
            return {"action": "demande_information", "validation_humaine_requise": False, "notes": notes}

        requires_validation = security.action_sensible

        if incidents:
            notes.append(f"Incident actif détecté ({incidents[0]['incident_id']}) : ticket rattaché plutôt que dupliqué.")
            ticket_call = self._call("creer_ticket", {
                "categorie": classification.categorie.value,
                "priorite": classification.priorite.value,
                "description": ticket_texte,
            })
            ticket_id = _ticket_id_from_call(ticket_call)
            if ticket_id:
                self._call("affecter_ticket", {"ticket_id": ticket_id, "equipe": incidents[0]["equipe"]})
                self._call("escalader_vers_technicien", {"ticket_id": ticket_id, "motif": f"Rattachement à {incidents[0]['incident_id']}"})
            return {"action": "escalade", "validation_humaine_requise": requires_validation, "notes": notes}

        if requires_validation:
            notes.append("Catégorie ou paramètres sensibles : escalade avec validation humaine requise avant toute action.")
            ticket_call = self._call("creer_ticket", {
                "categorie": classification.categorie.value,
                "priorite": classification.priorite.value,
                "description": ticket_texte,
            })
            ticket_id = _ticket_id_from_call(ticket_call)
            if ticket_id:
                self._call("escalader_vers_technicien", {"ticket_id": ticket_id, "motif": "Opération sensible nécessitant validation humaine"})
            return {"action": "escalade", "validation_humaine_requise": True, "notes": notes}

        if rag_incertain:
            notes.append("Aucune source documentaire suffisamment pertinente trouvée : escalade plutôt qu'une résolution non soutenue.")
            ticket_call = self._call("creer_ticket", {
                "categorie": classification.categorie.value,
                "priorite": classification.priorite.value,
                "description": ticket_texte,
            })
            ticket_id = _ticket_id_from_call(ticket_call)
            if ticket_id:
                self._call("affecter_ticket", {"ticket_id": ticket_id, "equipe": classification.equipe})
                self._call("escalader_vers_technicien", {"ticket_id": ticket_id, "motif": "Réponse documentaire insuffisamment soutenue par les sources"})
            return {"action": "escalade", "validation_humaine_requise": False, "notes": notes}

        # --- Cas standard : résolution autonome possible
        ticket_call = self._call("creer_ticket", {
            "categorie": classification.categorie.value,
            "priorite": classification.priorite.value,
            "description": ticket_texte,
        })
        ticket_id = _ticket_id_from_call(ticket_call)
        if ticket_id:
            self._call("affecter_ticket", {"ticket_id": ticket_id, "equipe": classification.equipe})
        notes.append("Aucun incident global ni élément sensible détecté : traitement standard.")
        return {"action": "resolution", "validation_humaine_requise": False, "notes": notes}


def _ticket_id_from_call(call: ToolCall) -> str | None:
    if call.statut == "succes" and call.resultat:
        return call.resultat.get("ticket", {}).get("ticket_id")
    return None
