# mAIntenance & Assistance

Assistant intelligent de support informatique — du diagnostic à la résolution.
Prototype réalisé dans le cadre du hackathon ISPM *AI Engineering & Machine Learning*.

## Lancement rapide

```powershell
# Windows (PowerShell)
.\run.ps1
```

```bash
# Linux / macOS
./run.sh
```

Ou manuellement :

```bash
pip install -r requirements.txt
streamlit run ui/streamlit_app.py
```

L'interface s'ouvre sur `http://localhost:8501`. Le panneau **Nouveau ticket** affiche une
**file d'attente de tickets déjà reçus** (`data/tickets_queue.json`, 8 tickets), dont 4
correspondent explicitement aux scénarios obligatoires du sujet (badges « Scénario 1 » à
« Scénario 4 ») : il suffit de cliquer sur *Traiter ce ticket* pour lancer le pipeline complet
sur un cas prêt à l'emploi, sans ressaisie manuelle. La file peut être réinitialisée à tout
moment (bouton *Réinitialiser la file*) pour rejouer la démonstration. La saisie libre d'un
nouveau ticket reste disponible en dessous.

Pour lancer l'évaluation automatisée :

```bash
python evaluation/evaluate.py
```

Les résultats sont écrits dans `evaluation/results.json` et affichés dans l'onglet
**Évaluation** de l'interface.

## Architecture

```
ticket (texte libre)
   │
   ▼
1. Compréhension / classification   app/classifier.py
   │  catégorie · priorité · équipe · confiance · hors-distribution
   ▼
2. Diagnostic                       app/diagnostic.py
   │  entités extraites, informations manquantes, questions ciblées
   ▼
3. Sécurité (garde-fous)            app/security.py
   │  détection d'injection, actions sensibles, données personnelles
   ▼
4. Recherche documentaire (RAG)     app/rag.py
   │  passages pertinents + citation de sources, ou incertitude signalée
   ▼
5. Agent + outils                   app/agent.py + app/tools.py
   │  sélection/validation d'outils, limite d'appels, validation humaine
   ▼
6. Sortie structurée                app/models.py (TicketDecision)
```

`app/pipeline.py` orchestre ces six étapes et les instrumente via `app/observability.py`
(latence, entrées/sorties, erreurs, coût estimé — journalisés dans `logs/traces.jsonl`).

```
maintenance-assistance/
├── app/                  # cœur du pipeline (aucune dépendance à l'UI)
│   ├── models.py         # schémas pydantic (sorties structurées)
│   ├── data_store.py     # chargement des référentiels + tickets simulés
│   ├── classifier.py     # classification catégorie/priorité/équipe
│   ├── diagnostic.py     # extraction d'entités + questions ciblées
│   ├── rag.py             # recherche documentaire TF-IDF + citation
│   ├── security.py       # détection d'injection, garde-fous
│   ├── tools.py           # implémentation des outils (consultation/action)
│   ├── agent.py            # orchestrateur d'appels d'outils
│   ├── observability.py    # traçage (latence, erreurs, coût)
│   └── pipeline.py         # assemblage bout-en-bout
├── data/                  # données de référence (fictives)
│   ├── users.json, equipments.json, services.json, active_incidents.json
│   ├── tickets_history.json   # historique étiqueté (classification par similarité)
│   ├── tickets_queue.json     # file d'attente de tickets déjà reçus, à traiter en démo
│   ├── tools_spec.json        # spécification des outils
│   ├── kb/*.md                 # base de connaissances (procédures)
│   └── eval/                    # jeux de test étiquetés
├── evaluation/evaluate.py       # script de mesure des performances
├── ui/streamlit_app.py          # interface de démonstration
├── logs/traces.jsonl            # journal d'observabilité (généré à l'exécution)
├── requirements.txt
├── run.ps1 / run.sh
└── README.md
```

## Choix techniques et justification

Le sujet précise explicitement qu'aucun point n'est réservé à l'usage d'un modèle de Machine
Learning entraîné, et qu'une approche simple mais bien maîtrisée est valorisée. Le prototype
adopte donc une **approche hybride 100% locale**, sans dépendance à une API LLM externe :

- **Classification** : combinaison d'un score par règles métier (mots-clés) et d'un score de
  similarité (TF-IDF caractères) contre l'historique de tickets étiquetés. Les règles priment
  quand elles matchent (explicable, robuste avec peu de données) ; la similarité comble les
  formulations non couvertes. Un score combiné trop faible déclenche la détection *hors
  distribution* (catégorie `autre_ou_indetermine`).
- **RAG** : indexation TF-IDF (mots + bigrammes, stop-words français) des sections de chaque
  fiche de la base de connaissances. Réponse **extractive** (les passages sont montrés tels
  quels, jamais reformulés) : élimine le risque d'hallucination et rend chaque affirmation
  vérifiable. Sous un seuil de similarité, la réponse est signalée incertaine.
- **Agent** : sélection d'outils pilotée par règles explicites (pas de LLM à function-calling)
  pour rester déterministe et auditable dans un contexte de hackathon. Chaque décision est
  traçable à la règle qui l'a produite.
- **Sécurité** : détection de prompt injection par expressions régulières sur un corpus de
  formulations d'attaque typiques, complétée par une liste d'actions et de catégories
  systématiquement soumises à validation humaine.

Cette approche est volontairement simple à auditer et à démontrer en 8h. Le pipeline est
conçu pour qu'un LLM réel (via API) puisse remplacer n'importe quel module (classification,
génération de réponse RAG, sélection d'outils) sans changer les interfaces — voir
`app/observability.py::ESTIMATED_COST_PER_STEP` pour le point de branchement du calcul de coût.

## Résultats mesurés (voir `evaluation/results.json`)

| Axe | Résultat |
|---|---|
| Classification — catégorie | 93 % (14/15) |
| Classification — priorité | 80 % (12/15) |
| Détection de prompt injection | Précision 100 % / Rappel 100 % (8 cas) |
| RAG — recall@3 | 77 % |
| Scénarios obligatoires conformes | 4/4 |

## Limites connues

- La classification par mots-clés est sensible au vocabulaire couvert ; des formulations très
  éloignées du corpus d'entraînement peuvent être mal classées (cf. `erreurs` dans
  `evaluation/results.json`).
- La détection de prompt injection repose sur des motifs connus ; une attaque reformulée de
  façon très indirecte pourrait ne pas être détectée (pas de couverture exhaustive garantie).
- Le RAG est extractif et n'effectue pas de synthèse inter-documents ; une question à cheval
  sur plusieurs fiches obtient une réponse juxtaposée plutôt que fusionnée.
- Les données (utilisateurs, équipements, incidents) sont entièrement fictives et générées pour
  la démonstration.
- Le simulateur de ticketing est en mémoire (non persistant entre redémarrages du serveur).

Voir aussi `RAPPORT_TECHNIQUE.md` pour le détail par axe d'évaluation.
