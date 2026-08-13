---
id: KB-NET-04
categorie: reseau_et_connectivite
titre: Incident réseau global (bâtiment ou site)
---

# Incident réseau global

## Symptômes
Plusieurs utilisateurs signalent une perte ou une forte dégradation de la connexion réseau
au même moment, souvent dans le même bâtiment ou le même service.

## Procédure standard
1. Vérifier `rechercher_incidents_actifs` pour un incident réseau déjà déclaré (service `SRV-NET`).
2. Si un incident global est actif, rattacher le ticket à cet incident plutôt que de créer un
   doublon, et informer l'utilisateur du délai estimé de résolution.
3. Ce type d'incident impacte l'activité : la priorité doit être fixée à **haute** ou **critique**
   selon le nombre d'utilisateurs affectés.
4. Escalader vers l'équipe `infrastructure` via `escalader_vers_technicien`.

## SLA
Un incident réseau global doit être pris en charge par un technicien sous 30 minutes.
