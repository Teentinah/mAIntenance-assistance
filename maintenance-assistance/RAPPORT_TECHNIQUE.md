# Rapport technique — mAIntenance & Assistance

## 1. Approche choisie pour analyser et router les tickets

La classification (catégorie, priorité, équipe) repose sur une approche **hybride** :

1. **Score par règles métier** : chaque catégorie est associée à une liste de mots-clés et
   expressions caractéristiques (ex. « mot de passe », « compte verrouillé » pour
   `comptes_et_authentification`). Le score est la proportion de mots-clés détectés.
2. **Score par similarité** : le texte du ticket est comparé, via TF-IDF sur n-grammes de
   caractères (2 à 4), à `data/tickets_history.json` (44 tickets étiquetés, volontairement
   bruités : fautes, formulations vagues, catégories déséquilibrées). Le vote des k plus
   proches voisins (k=5) donne un second score par catégorie, robuste aux fautes de frappe
   grâce aux n-grammes de caractères.
3. Les deux scores sont combinés (0.7 règles / 0.3 similarité — les règles priment car plus
   explicables et fiables avec un historique de cette taille). La catégorie au score combiné
   le plus élevé est retenue ; si ce score reste sous 0.20, le ticket est classé
   `autre_ou_indetermine` et marqué **hors distribution**.
4. La **priorité** est déduite du vote de priorité des voisins les plus proches, puis
   rehaussée par des règles non négociables (mots d'urgence explicites, catégorie
   `cybersecurite` toujours au moins « haute »).
5. L'**équipe** découle directement de la catégorie retenue (mapping fixe, cohérent avec les
   fiches de la base de connaissances).

Ce choix (plutôt qu'un modèle de ML entraîné end-to-end) a été retenu car le volume de
données disponible est faible (quelques dizaines de tickets), et parce que le sujet valorise
explicitement une approche simple et bien justifiée plutôt qu'une complexité mal maîtrisée.
La méthode reste facilement remplaçable par un classifieur supervisé (scikit-learn) si un
corpus plus large était disponible, sans changer l'interface `TicketClassifier.classify()`.

## 2. Fonctionnement du système RAG

- **Ingestion** : chaque fiche Markdown de `data/kb/` (front-matter `id`/`categorie`/`titre` +
  sections `## Symptômes`, `## Procédure standard`, `## Escalade`...) est découpée en chunks
  par section.
- **Indexation** : `TfidfVectorizer` (mots + bigrammes, stop-words français personnalisés) sur
  l'ensemble des chunks.
- **Recherche** : similarité cosinus entre la requête (texte du ticket) et les chunks,
  filtrage optionnel par catégorie, retour des `top_k=3` meilleurs passages.
- **Réponse** : **extractive** — les passages retrouvés sont renvoyés tels quels avec leur
  identifiant de document (`KB-AUTH-01`, etc.), jamais reformulés par génération libre. Ce
  choix élimine le risque d'hallucination et rend chaque affirmation vérifiable à sa source.
- **Incertitude** : si le meilleur score de similarité est sous le seuil (0.18), la réponse
  est marquée `incertain=True`, aucune source n'est citée en sortie structurée, et l'agent
  bascule automatiquement l'action vers `escalade` plutôt que `resolution` (voir `app/agent.py`,
  paramètre `rag_incertain`).

## 3. Outils accessibles à l'agent

| Outil | Type | Sensible (validation humaine) |
|---|---|---|
| `rechercher_utilisateur` | consultation | non |
| `consulter_equipement` | consultation | non |
| `verifier_etat_service` | consultation | non |
| `rechercher_incidents_actifs` | consultation | non |
| `creer_ticket` | action | non |
| `mettre_a_jour_ticket` | action | non |
| `affecter_ticket` | action | non |
| `escalader_vers_technicien` | action | non (c'est l'action de mise en sécurité elle-même) |
| `reinitialiser_mot_de_passe` | action | **oui** |
| `modifier_droits_acces` | action | **oui** |

La sélection des outils est pilotée par des règles explicites dans `app/agent.py` (pas de
function-calling LLM) : consultation systématique du contexte (utilisateur, équipement,
service, incidents actifs), puis décision d'action selon le résultat du diagnostic, de la
sécurité et du RAG. Chaque appel est validé (paramètres requis), exécuté avec capture
d'erreur (`ToolError` dédiée), et enregistré avec ses paramètres/résultat/statut
(`succes`/`erreur`/`refuse`/`en_attente_validation`). Un plafond de **6 appels par ticket**
(`MAX_TOOL_CALLS`) empêche les boucles incontrôlées.

## 4. Stratégie d'évaluation

Trois jeux de test dédiés, disjoints de l'historique servant à la classification :

- `data/eval/test_tickets.json` (15 tickets étiquetés) → accuracy catégorie/priorité/équipe,
  matrice de confusion, liste des erreurs commentées.
- `data/eval/security_cases.json` (8 cas) → précision/rappel/F1 de la détection de prompt
  injection.
- Requêtes RAG dérivées du même jeu de test → recall@3 (le bon document apparaît-il dans le
  top-3 ?) et taux de détection des questions hors-sujet.
- 4 scénarios obligatoires du sujet rejoués en bout en bout via `process_ticket()`, avec
  assertion sur l'action finale attendue.

`python evaluation/evaluate.py` exécute ces quatre évaluations et écrit
`evaluation/results.json` (repris dans l'onglet **Évaluation** de l'interface).

**Résultats obtenus** : accuracy catégorie 93 %, priorité 80 %, détection d'injection
100 %/100 % (précision/rappel), RAG recall@3 77 %, 4/4 scénarios obligatoires conformes.

## 5. Mécanismes de sécurité

- **Détection de prompt injection** : expressions régulières sur des formulations d'attaque
  typiques (« ignore les instructions », « tu es maintenant en mode... », « sans validation »,
  « [SYSTEM] », demandes de mots de passe en clair...). Si détectée, le ticket est
  **reclassé en `cybersecurite` / priorité `critique`** indépendamment de son sujet apparent,
  **aucune action automatique n'est exécutée** (`action_refusee`), et une validation humaine
  est systématiquement requise.
- **Validation humaine obligatoire** pour : toute la catégorie `cybersecurite`, et les outils
  `reinitialiser_mot_de_passe` / `modifier_droits_acces` — ces derniers ne sont jamais exécutés
  directement par l'agent, seulement mis `en_attente_validation`.
- **Détection de données personnelles** (email, téléphone, date) à titre d'alerte
  d'observabilité (`donnees_personnelles_detectees`).
- **Escalade par défaut en cas d'incertitude** : une réponse RAG non suffisamment soutenue par
  les sources ne débouche jamais sur une résolution automatique.
- **Limite du nombre d'appels d'outils** par ticket pour contenir tout comportement en boucle.

## 6. File d'attente de démonstration

Le sujet précise que l'équipe dispose d'un historique/flux de tickets déjà reçus, et pas
seulement d'une page de saisie vide. L'interface charge donc `data/tickets_queue.json` (8
tickets simulant un flux réel : canal de soumission, heure de réception) dans une file
affichée sur la page **Nouveau ticket**. Quatre de ces tickets sont explicitement étiquetés
(champ `scenario`) et correspondent aux 4 scénarios obligatoires du §8 du sujet ; les quatre
autres couvrent des catégories additionnelles (logiciel, droits d'accès, matériel,
imprimante) pour varier la démonstration. Cliquer sur *Traiter ce ticket* exécute
`process_ticket()` exactement comme pour une saisie manuelle et retire le ticket de la file ;
un bouton *Réinitialiser la file* permet de rejouer la démonstration à l'identique.

## 7. Limites connues du prototype

- Classification par mots-clés + similarité : performante sur le vocabulaire couvert par
  `tickets_history.json`, mais peut se tromper sur des formulations très différentes
  (ex. ticket E-13 mêlant vocabulaire technique « base de données » et intention malveillante :
  la classification seule le range en `logiciels_et_applications` ; c'est le module de
  sécurité, exécuté en parallèle, qui corrige la décision finale — séparation des
  responsabilités assumée plutôt que corrigée par surapprentissage de règles ad hoc).
- Le RAG est extractif : pas de synthèse inter-documents, pas de reformulation naturelle du
  passage retrouvé.
- La détection d'injection est fondée sur des motifs connus (regex) : une formulation très
  indirecte ou dans une langue différente pourrait passer inaperçue.
- Le jeu de données est entièrement fictif et de taille réduite (44 tickets historiques, 15
  tickets de test) — cohérent avec un format hackathon de 8h, mais insuffisant pour garantir
  une généralisation à grande échelle.
- Le magasin de tickets est simulé en mémoire (non persistant), conformément au périmètre
  « outils réels ou simulés » demandé par le sujet.
