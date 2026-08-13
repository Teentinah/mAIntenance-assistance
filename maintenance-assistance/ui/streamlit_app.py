"""Interface de démonstration Streamlit — mAIntenance & Assistance.

Thème visuel ISPM (vert / noir / blanc), construit avec du HTML/CSS injecté par-dessus
les composants Streamlit natifs.

Lancement : streamlit run ui/streamlit_app.py
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from app.data_store import get_store
from app.observability import Tracer
from app.pipeline import process_ticket

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

st.set_page_config(page_title="mAIntenance & Assistance — ISPM", layout="wide")


def _md(raw: str) -> None:
    """Injecte du HTML brut de façon fiable.

    st.markdown applique d'abord un parseur CommonMark : toute ligne indentée de 4 espaces
    ou plus y est interprétée comme un bloc de code (et affichée telle quelle) plutôt que
    comme du HTML. Comme nos fragments sont écrits avec l'indentation du code Python source,
    on neutralise ce piège en retirant l'indentation de chaque ligne avant l'injection.
    """
    cleaned = "\n".join(line.strip() for line in raw.strip("\n").split("\n"))
    st.markdown(cleaned, unsafe_allow_html=True)


# ============================================================================
# Thème : CSS + logo
# ============================================================================
@st.cache_data
def _load_css() -> str:
    return (ASSETS_DIR / "theme.css").read_text(encoding="utf-8")


@st.cache_data
def _logo_base64() -> str:
    data = (ASSETS_DIR / "logo_ispm.png").read_bytes()
    return base64.b64encode(data).decode("ascii")


st.markdown(f"<style>{_load_css()}</style>", unsafe_allow_html=True)
LOGO_B64 = _logo_base64()

SCENARIOS_GUIDE = {
    "Scénario 1 — Incident courant": (
        "Un problème connu, bien décrit. L'assistant doit identifier la procédure "
        "correspondante et guider jusqu'à la résolution."
    ),
    "Scénario 2 — Incident urgent": (
        "Un problème qui bloque une activité importante ou plusieurs personnes. "
        "L'assistant doit détecter une priorité haute et vérifier les incidents actifs."
    ),
    "Scénario 3 — Demande incomplète": (
        "Une description trop vague pour établir un diagnostic fiable. "
        "L'assistant doit poser des questions ciblées avant toute solution."
    ),
    "Scénario 4 — Demande sensible ou malveillante": (
        "Une tentative de manipuler l'assistant ou de provoquer une action dangereuse. "
        "L'assistant doit refuser et exiger une validation humaine."
    ),
}

ACTION_META = {
    "resolution": {"label": "Résolution", "css": "resolution", "badge": "badge-success"},
    "demande_information": {"label": "Demande d'information", "css": "demande_information", "badge": "badge-warning"},
    "escalade": {"label": "Escalade", "css": "escalade", "badge": "badge-info"},
    "action_refusee": {"label": "Action refusée", "css": "action_refusee", "badge": "badge-danger"},
}

if "ticket_counter" not in st.session_state:
    st.session_state.ticket_counter = 0
if "last_decision" not in st.session_state:
    st.session_state.last_decision = None
if "history" not in st.session_state:
    st.session_state.history = []


def _next_ticket_id() -> str:
    st.session_state.ticket_counter += 1
    return f"TCK-{st.session_state.ticket_counter:04d}"


def _stat_cards_html(cards: list[tuple]) -> str:
    """cards: liste de (label, value, sub, accent) -> HTML compact (une seule ligne)."""
    inner = "".join(
        f'<div class="ispm-stat-card" style="--ispm-accent:{accent}">'
        f'<div class="stat-label">{label}</div>'
        f'<div class="stat-value">{value}</div>'
        f'<div class="stat-sub">{sub}</div></div>'
        for label, value, sub, accent in cards
    )
    return f'<div class="ispm-stats">{inner}</div>'


# ============================================================================
# Composants HTML
# ============================================================================
def render_header(subtitle: str):
    _md(f"""
        <div class="ispm-header">
          <div class="ispm-brand">
            <img class="ispm-logo" src="data:image/png;base64,{LOGO_B64}" />
            <div>
              <p class="ispm-title">mA<span>I</span>ntenance &amp; Assistance</p>
              <div class="ispm-subtitle">{subtitle}</div>
              <div class="ispm-tags">
                <span class="ispm-tag">Comprendre</span>
                <span class="ispm-tag">Diagnostiquer</span>
                <span class="ispm-tag">Assister</span>
                <span class="ispm-tag">Résoudre</span>
              </div>
            </div>
          </div>
          <div class="ispm-status"><span class="dot"></span> Pipeline opérationnel</div>
        </div>
    """)


def render_stats():
    history = st.session_state.history
    n_total = len(history)
    n_resolus = sum(1 for d in history if d.action.value == "resolution")
    n_attente = sum(1 for d in history if d.action.value == "demande_information")
    n_equipes = len({d.equipe for d in history}) if history else 0

    cards = [
        ("Tickets traités", n_total, "session en cours", "var(--ispm-green)"),
        ("Résolus automatiquement", n_resolus, f"{(n_resolus / n_total * 100) if n_total else 0:.0f}% du total", "var(--ispm-green-dark)"),
        ("En attente d'info", n_attente, "action requise", "var(--ispm-amber)"),
        ("Équipes sollicitées", n_equipes, "sur 5 équipes support", "var(--ispm-black)"),
    ]
    _md(_stat_cards_html(cards))


def render_scenario_guide():
    st.markdown("###### Scénarios à démontrer")
    st.caption("Écris un ticket dans le champ ci-dessous.")
    cols = st.columns(4)
    for col, (name, description) in zip(cols, SCENARIOS_GUIDE.items()):
        short = name.split("—")[1].strip()
        with col:
            _md(f"""
                <div class="ispm-card" style="min-height:128px;">
                <h4>{short}</h4>
                <div style="font-size:0.8rem; line-height:1.5;">{description}</div>
                </div>
            """)


def render_decision(decision):
    meta = ACTION_META.get(decision.action.value, {"label": decision.action.value, "css": "escalade", "badge": "badge-info"})

    col1, col2, col3 = st.columns([1.15, 1.15, 0.85], gap="medium")

    # --- Colonne 1 : ticket + réponse (style chat) ---------------------------------
    with col1:
        _md('<div class="ispm-card"><h4>Ticket et réponse</h4></div>')
        resume_text = decision.resume.split("]", 1)[-1].strip()
        _md(f"""
            <div class="ispm-bubble ispm-bubble-user">
            <span class="who">Utilisateur · {decision.ticket_id}</span>
            {resume_text}
            </div>
            <div class="ispm-bubble ispm-bubble-assistant">
            <span class="who">Assistant mAIntenance</span>
            {decision.diagnostic}
            </div>
        """)
        b1, b2, b3 = st.columns(3)
        b1.markdown(f'<span class="badge badge-info">{decision.categorie.value}</span>', unsafe_allow_html=True)
        b2.markdown(f'<span class="badge badge-info">{decision.priorite.value.upper()}</span>', unsafe_allow_html=True)
        b3.markdown(f'<span class="badge badge-info">{decision.equipe}</span>', unsafe_allow_html=True)

        if decision.informations_manquantes:
            _md('<div class="ispm-card" style="margin-top:0.8rem;"><h4>Informations demandées</h4></div>')
            for q in decision.etapes_resolution:
                st.markdown(f"- {q}")

    # --- Colonne 2 : synthèse du diagnostic -----------------------------------------
    with col2:
        _md('<div class="ispm-card"><h4>Synthèse du diagnostic</h4></div>')
        _md(f"""
            <div style="font-size:0.88rem; line-height:1.6; margin-top:-0.6rem;">
            <b>Confiance</b> — {decision.confiance:.0%}
            <div style="background:#eef1f0;border-radius:6px;height:8px;margin:6px 0 10px 0;">
            <div style="background:var(--ispm-green);width:{decision.confiance * 100:.0f}%;height:8px;border-radius:6px;"></div>
            </div>
            </div>
        """)
        st.markdown("**Étapes / réponse proposée**")
        if decision.etapes_resolution:
            for step in decision.etapes_resolution:
                st.markdown(f"- {step}")
        else:
            st.markdown("_Aucune étape générée._")

        st.markdown("**Sources consultées**")
        if decision.sources:
            chips = "".join(f'<span class="badge badge-success">{s}</span> ' for s in decision.sources)
            _md(chips)
        else:
            confiance_tag = "badge-warning" if decision.incertain else "badge-info"
            _md(f'<span class="badge {confiance_tag}">Aucune source suffisamment pertinente</span>')

        st.markdown("**Outils utilisés**")
        if decision.outils_utilises:
            chips = "".join(f'<span class="badge badge-dark">{t}</span> ' for t in decision.outils_utilises)
            _md(chips)
        else:
            st.markdown("_Aucun outil appelé._")

    # --- Colonne 3 : décision + timeline ---------------------------------------------
    with col3:
        _md(f"""
            <div class="ispm-decision {meta['css']}">
            <div class="d-title">{meta['label']}</div>
            <span class="badge {meta['badge']}">{decision.priorite.value.upper()}</span>
            </div>
        """)
        if decision.validation_humaine_requise:
            st.warning("Validation humaine requise avant toute exécution.")
        if decision.securite.injection_detectee:
            st.error(f"Instructions suspectes détectées ({len(decision.securite.indices)} indice(s)).")
        if decision.incertain:
            st.info("Réponse non suffisamment soutenue par les sources.")

        with st.expander("Voir le ticket complet (JSON)"):
            st.json(decision.model_dump(mode="json"))


# ============================================================================
# Pages
# ============================================================================
def page_nouveau_ticket():
    render_header("Assistant intelligent de support informatique, du diagnostic à la résolution")
    render_stats()
    render_scenario_guide()

    _md('<div class="ispm-card" style="margin-top:0.8rem; margin-bottom:0;"><h4>Nouveau ticket</h4></div>')
    texte = st.text_area(
        "Description du ticket (langage naturel)",
        key="ticket_text",
        height=110,
        placeholder="Décrivez le problème rencontré...",
        label_visibility="collapsed",
    )
    analyser = st.button("Analyser le ticket", type="primary")

    if analyser:
        if not texte or not texte.strip():
            st.error("Merci de saisir une description de ticket.")
        else:
            ticket_id = _next_ticket_id()
            with st.spinner("Analyse en cours (compréhension → diagnostic → RAG → agent)..."):
                decision = process_ticket(ticket_id, texte)
            st.session_state.last_decision = decision
            st.session_state.history.append(decision)

    if st.session_state.last_decision is not None:
        st.markdown("---")
        render_decision(st.session_state.last_decision)

    _md("""
        <div class="ispm-footer">Sécurisé · Contrôlé · Traçable &nbsp;—&nbsp;
        <b>mAIntenance &amp; Assistance</b> · Hackathon AI Engineering &amp; ML · ISPM</div>
    """)


def page_historique():
    render_header("Historique des tickets traités durant cette session")
    if not st.session_state.history:
        st.info("Aucun ticket traité pour l'instant.")
        return
    rows = []
    for d in st.session_state.history:
        rows.append({
            "ticket_id": d.ticket_id,
            "resume": d.resume,
            "categorie": d.categorie.value,
            "priorite": d.priorite.value,
            "equipe": d.equipe,
            "action": d.action.value,
            "confiance": d.confiance,
            "validation_humaine": d.validation_humaine_requise,
            "incertain": d.incertain,
        })
    _md('<div class="ispm-card"><h4>Tickets traités</h4></div>')
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_observabilite():
    render_header("Traces, latence, erreurs et coût estimé de chaque étape du pipeline")
    events = Tracer.load_all_from_disk()
    if not events:
        st.info("Aucune trace enregistrée pour l'instant. Traitez un ticket pour générer des traces.")
        return

    df = pd.DataFrame(events)
    n_total, n_tickets = len(df), df["ticket_id"].nunique()
    latence_moy = df["duration_ms"].mean()
    n_err = int((df["status"] == "erreur").sum())

    cards = [
        ("Étapes tracées", n_total, "cumulées", "var(--ispm-green)"),
        ("Tickets traités", n_tickets, "toutes sessions", "var(--ispm-green-dark)"),
        ("Latence moyenne", f"{latence_moy:.1f} ms", "par étape", "var(--ispm-black)"),
        ("Erreurs", n_err, "sur le pipeline", "var(--ispm-red)" if n_err else "var(--ispm-green)"),
    ]
    _md(_stat_cards_html(cards))

    col1, col2 = st.columns(2)
    with col1:
        _md('<div class="ispm-card"><h4>Latence moyenne par étape (ms)</h4></div>')
        st.bar_chart(df.groupby("step")["duration_ms"].mean().sort_values(ascending=False))
    with col2:
        _md('<div class="ispm-card"><h4>Coût estimé cumulé</h4></div>')
        st.metric("Coût total estimé", f"{df['cout_estime_ar'].sum():,.2f} Ar".replace(",", " "))
        st.caption("Pipeline 100% local (aucun appel LLM externe) : coût réel nul. Le champ est prêt pour un calcul basé sur les tokens (convertis en Ariary) si un LLM externe est branché.")

    _md('<div class="ispm-card"><h4>Journal détaillé</h4></div>')
    ticket_filter = st.selectbox("Filtrer par ticket", ["Tous"] + sorted(df["ticket_id"].unique().tolist()))
    view = df if ticket_filter == "Tous" else df[df["ticket_id"] == ticket_filter]
    st.dataframe(
        view[["ticket_id", "step", "status", "duration_ms", "cout_estime_ar", "error"]].sort_values("ticket_id"),
        use_container_width=True, hide_index=True,
    )
    with st.expander("Voir une trace complète (entrées/sorties)"):
        idx = st.number_input("Index de ligne", min_value=0, max_value=len(view) - 1, value=0)
        st.json(view.iloc[int(idx)].to_dict())


def page_evaluation():
    render_header("Résultats mesurés — classification, sécurité, RAG, scénarios obligatoires")
    results_path = Path(__file__).resolve().parent.parent / "evaluation" / "results.json"
    if not results_path.exists():
        st.warning("Aucun résultat d'évaluation trouvé. Lancez `python evaluation/evaluate.py` puis rechargez cette page.")
        return
    import json
    results = json.loads(results_path.read_text(encoding="utf-8"))

    cls, sec, rag, scn = results["classification"], results["securite"], results["rag"], results["scenarios_obligatoires"]
    cards = [
        ("Accuracy catégorie", f"{cls['accuracy_categorie']:.0%}", f"{cls['n_exemples']} tickets de test", "var(--ispm-green)"),
        ("F1 détection injection", f"{sec['f1']:.0%}", f"{sec['n_exemples']} cas de sécurité", "var(--ispm-black)"),
        ("RAG recall@3", f"{rag['recall_at_3']:.0%}", f"{rag['n_requetes_evaluees']} requêtes", "var(--ispm-green-dark)"),
        ("Scénarios conformes", f"{scn['n_conformes']}/{scn['n_total']}", "obligatoires du sujet", "var(--ispm-amber)"),
    ]
    _md(_stat_cards_html(cards))

    _md('<div class="ispm-card"><h4>Scénarios obligatoires</h4></div>')
    st.dataframe(pd.DataFrame(scn["details"]), use_container_width=True, hide_index=True)

    with st.expander("Résultats bruts complets (JSON)"):
        st.json(results)


def page_donnees():
    render_header("Référentiels utilisés par le pipeline (données fictives)")
    store = get_store()
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Utilisateurs", "Équipements", "Services", "Incidents actifs", "Outils"])
    with tab1:
        st.dataframe(pd.DataFrame(store.users), use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(pd.DataFrame(store.equipments), use_container_width=True, hide_index=True)
    with tab3:
        st.dataframe(pd.DataFrame(store.services), use_container_width=True, hide_index=True)
    with tab4:
        st.dataframe(pd.DataFrame(store.active_incidents), use_container_width=True, hide_index=True)
    with tab5:
        st.dataframe(pd.DataFrame(store.tools_spec), use_container_width=True, hide_index=True)


PAGES = {
    "Nouveau ticket": page_nouveau_ticket,
    "Historique": page_historique,
    "Observabilité": page_observabilite,
    "Évaluation": page_evaluation,
    "Données de référence": page_donnees,
}

if "nav_choice" not in st.session_state:
    st.session_state.nav_choice = "Nouveau ticket"

with st.sidebar:
    _md(f"""
        <div class="ispm-sidebar-brand">
        <div class="ispm-logo-badge"><img src="data:image/png;base64,{LOGO_B64}" /></div>
        <div>
        <div class="brand-name">ISPM</div>
        <div class="brand-tagline">Fahaizana · Fampandrosoana · Fihavanana</div>
        </div>
        </div>
    """)
    st.markdown("---")
    for name in PAGES:
        is_active = st.session_state.nav_choice == name
        if st.button(name, key=f"nav_{name}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state.nav_choice = name
            st.rerun()
    choice = st.session_state.nav_choice
    st.markdown("---")
    _md("""
        <div style="font-size:0.72rem; color:#bcd9c8; line-height:1.6;">
        <b>Hackathon AI Engineering &amp; ML</b><br/>
        Durée : 8h30 – 16h30<br/>
        Équipes : 2 à 7 étudiants
        </div>
    """)

PAGES[choice]()
