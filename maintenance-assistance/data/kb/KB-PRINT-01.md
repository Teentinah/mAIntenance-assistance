---
id: KB-PRINT-01
categorie: imprimantes_et_peripheriques
titre: Impression impossible
---

# Impression impossible

## Symptômes
Les documents ne s'impriment pas, restent bloqués dans la file d'attente, ou l'imprimante
réseau n'est pas détectée.

## Procédure standard
1. Vérifier via `consulter_equipement` l'état de l'imprimante réseau concernée.
2. Si l'imprimante est `hors_service`, informer l'utilisateur et proposer une imprimante de
   secours si disponible.
3. Sinon, faire vider la file d'attente d'impression côté poste utilisateur et relancer le
   spouleur d'impression.
4. Vérifier que le pilote d'imprimante correspond au modèle déclaré.

## Escalade
Une imprimante hors service depuis plus de 4 heures doit être escaladée vers l'équipe
`support_materiel`.
