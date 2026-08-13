"""Pipeline bout-en-bout : ticket en langage naturel -> décision structurée (Fig. 1 du sujet).

compréhension -> diagnostic -> RAG -> agent/outils -> sortie structurée,
avec observabilité et garde-fous intégrés à chaque étape.
"""
from __future__ import annotations

import re

from app.agent import Agent
from app.classifier import get_classifier
from app.diagnostic import diagnose
from app.models import Action, TicketDecision
from app.observability import get_tracer, new_trace_id
from app.rag import get_rag_engine
from app.security import evaluate_security

STEP_RESOLUTION = re.compile(r"^\s*\d+\.\s+(.*)")


def _extract_steps(rag_reponse: str | None) -> list[str]:
    if not rag_reponse:
        return []
    steps = []
    for line in rag_reponse.splitlines():
        m = STEP_RESOLUTION.match(line)
        if m:
            steps.append(m.group(1).strip())
    return steps


def _build_resume(texte: str, categorie: str, priorite: str) -> str:
    snippet = texte.strip().replace("\n", " ")
    if len(snippet) > 160:
        snippet = snippet[:157] + "..."
    return f"[{categorie} / {priorite}] {snippet}"


def _build_diagnostic_text(diag) -> str:
    parts = []
    if diag.utilisateur:
        parts.append(f"utilisateur: {diag.utilisateur}")
    if diag.equipement:
        parts.append(f"équipement: {diag.equipement}")
    if diag.application_ou_service:
        parts.append(f"application/service: {diag.application_ou_service}")
    if diag.symptomes:
        parts.append(f"symptômes: {', '.join(diag.symptomes)}")
    if diag.moment_apparition:
        parts.append(f"apparu: {diag.moment_apparition}")
    if diag.impact_activite:
        parts.append(f"impact: {diag.impact_activite}")
    if diag.manipulations_effectuees:
        parts.append(f"déjà tenté: {diag.manipulations_effectuees}")
    return "; ".join(parts) if parts else "Aucune information exploitable extraite automatiquement."


def process_ticket(ticket_id: str, texte: str) -> TicketDecision:
    tracer = get_tracer()
    trace_id = new_trace_id()

    with tracer.step(trace_id, ticket_id, "comprehension", input_data=texte) as span:
        classification = get_classifier().classify(texte)
        span["output"] = classification

    with tracer.step(trace_id, ticket_id, "diagnostic", input_data={"texte": texte, "categorie": classification.categorie.value}) as span:
        diag = diagnose(texte, classification.categorie.value)
        span["output"] = diag

    with tracer.step(trace_id, ticket_id, "securite", input_data=texte) as span:
        security = evaluate_security(texte, classification.categorie.value)
        span["output"] = security

    with tracer.step(trace_id, ticket_id, "rag", input_data=texte) as span:
        rag_result = get_rag_engine().answer(texte, categorie=classification.categorie.value)
        span["output"] = rag_result

    with tracer.step(trace_id, ticket_id, "agent_outils", input_data={"categorie": classification.categorie.value}) as span:
        agent = Agent()
        decision = agent.run(
            classification=classification,
            diagnostic=diag,
            security=security,
            ticket_texte=texte,
            rag_incertain=rag_result.incertain and not diag.informations_manquantes and not security.injection_detectee,
        )
        span["output"] = {"decision": decision, "appels": [c.model_dump() for c in agent.calls]}

    with tracer.step(trace_id, ticket_id, "sortie_structuree") as span:
        final_categorie = classification.categorie
        final_priorite = classification.priorite
        final_equipe = classification.equipe

        if security.injection_detectee:
            # Une tentative de manipulation de l'assistant est en soi un incident de
            # cybersécurité, indépendamment du sujet apparent du ticket.
            from app.models import Categorie, Priorite
            final_categorie = Categorie.cybersecurite
            final_priorite = Priorite.critique
            final_equipe = "cybersecurite"

        action_str = decision["action"]
        etapes = []
        if action_str == "resolution":
            etapes = _extract_steps(rag_result.reponse) or ["Consulter la procédure documentée ci-dessus et appliquer les étapes standard."]
        elif action_str == "demande_information":
            etapes = diag.questions_ciblees
        else:  # escalade ou action_refusee
            etapes = list(decision.get("notes", [])) or ["Ticket transmis à un technicien pour prise en charge manuelle."]

        outils_utilises = [c.nom for c in agent.calls]
        sources = [] if rag_result.incertain else sorted({s.doc_id for s in rag_result.sources})

        ticket_decision = TicketDecision(
            ticket_id=ticket_id,
            resume=_build_resume(texte, final_categorie.value, final_priorite.value),
            categorie=final_categorie,
            priorite=final_priorite,
            equipe=final_equipe,
            confiance=classification.confiance,
            informations_manquantes=diag.informations_manquantes,
            diagnostic=_build_diagnostic_text(diag),
            etapes_resolution=etapes,
            sources=sources,
            outils_utilises=outils_utilises,
            action=Action(action_str),
            validation_humaine_requise=decision["validation_humaine_requise"],
            incertain=rag_result.incertain,
            securite=security,
        )
        span["output"] = ticket_decision

    return ticket_decision
