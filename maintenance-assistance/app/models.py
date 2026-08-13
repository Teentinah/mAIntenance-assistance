"""Schémas de données (sorties structurées) partagés par tout le pipeline."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Categorie(str, Enum):
    comptes_et_authentification = "comptes_et_authentification"
    reseau_et_connectivite = "reseau_et_connectivite"
    materiel_informatique = "materiel_informatique"
    logiciels_et_applications = "logiciels_et_applications"
    imprimantes_et_peripheriques = "imprimantes_et_peripheriques"
    droits_acces = "droits_acces"
    cybersecurite = "cybersecurite"
    autre_ou_indetermine = "autre_ou_indetermine"


class Priorite(str, Enum):
    basse = "basse"
    moyenne = "moyenne"
    haute = "haute"
    critique = "critique"


class Action(str, Enum):
    resolution = "resolution"
    demande_information = "demande_information"
    escalade = "escalade"
    action_refusee = "action_refusee"


class ClassificationResult(BaseModel):
    """Résultat de l'étape de compréhension / classification du ticket."""

    categorie: Categorie
    priorite: Priorite
    equipe: str
    confiance: float = Field(ge=0.0, le=1.0)
    hors_distribution: bool = False
    methode: str = Field(description="Méthode utilisée pour produire ce résultat (règles, similarité, hybride...)")
    scores_categorie: dict[str, float] = Field(default_factory=dict)


class DiagnosticInfo(BaseModel):
    """Informations extraites du ticket et informations manquantes."""

    utilisateur: Optional[str] = None
    equipement: Optional[str] = None
    application_ou_service: Optional[str] = None
    symptomes: list[str] = Field(default_factory=list)
    moment_apparition: Optional[str] = None
    impact_activite: Optional[str] = None
    manipulations_effectuees: Optional[str] = None
    informations_manquantes: list[str] = Field(default_factory=list)
    questions_ciblees: list[str] = Field(default_factory=list)


class SourceCitee(BaseModel):
    doc_id: str
    titre: str
    extrait: str
    score: float


class RagResult(BaseModel):
    reponse: Optional[str] = None
    sources: list[SourceCitee] = Field(default_factory=list)
    incertain: bool = True


class ToolCall(BaseModel):
    nom: str
    parametres: dict
    resultat: Optional[dict] = None
    statut: str = "en_attente"  # en_attente | succes | erreur | refuse
    validation_humaine_requise: bool = False
    duree_ms: Optional[float] = None


class SecurityFlags(BaseModel):
    injection_detectee: bool = False
    indices: list[str] = Field(default_factory=list)
    action_sensible: bool = False
    donnees_personnelles_detectees: bool = False


class TicketDecision(BaseModel):
    """Sortie structurée finale, conforme au schéma imposé par le sujet."""

    ticket_id: str
    resume: str
    categorie: Categorie
    priorite: Priorite
    equipe: str
    confiance: float = Field(ge=0.0, le=1.0)
    informations_manquantes: list[str] = Field(default_factory=list)
    diagnostic: str
    etapes_resolution: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    outils_utilises: list[str] = Field(default_factory=list)
    action: Action
    validation_humaine_requise: bool = False
    incertain: bool = False
    securite: SecurityFlags = Field(default_factory=SecurityFlags)
