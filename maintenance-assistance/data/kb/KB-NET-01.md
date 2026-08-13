---
id: KB-NET-01
categorie: reseau_et_connectivite
titre: Perte de connexion réseau (poste isolé)
---

# Perte de connexion réseau - poste isolé

## Symptômes
Un seul poste perd la connexion réseau (filaire ou WiFi), les autres postes du même bâtiment
fonctionnent normalement.

## Procédure standard
1. Demander à l'utilisateur de vérifier le câble réseau / la connexion WiFi.
2. Redémarrer l'adaptateur réseau (désactiver/réactiver) ou effectuer un `ipconfig /release` puis
   `ipconfig /renew`.
3. Vérifier via `consulter_equipement` que le poste est bien référencé et opérationnel.
4. Si le problème persiste, vérifier `verifier_etat_service` sur le service `SRV-NET`.
5. Si aucun incident global n'est déclaré, créer un ticket standard priorité moyenne.

## Escalade
Si plusieurs utilisateurs du même bâtiment signalent le même problème, considérer un
incident réseau global (voir KB-NET-04) et vérifier `rechercher_incidents_actifs`.
