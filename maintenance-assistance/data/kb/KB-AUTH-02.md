---
id: KB-AUTH-02
categorie: comptes_et_authentification
titre: Compte verrouillé après tentatives échouées
---

# Compte verrouillé

## Symptômes
Le compte se verrouille automatiquement après 5 tentatives de connexion échouées (politique
Active Directory). L'utilisateur reçoit le message "Ce compte a été désactivé, contactez votre
administrateur".

## Procédure standard
1. Confirmer l'identité de l'utilisateur.
2. Vérifier via `rechercher_utilisateur` que le champ `statut_compte` est bien `verrouille`.
3. Le déverrouillage est une opération sensible : elle nécessite une **validation humaine**
   avant application, même si la demande semble légitime.
4. Une fois validé, déverrouiller le compte et informer l'utilisateur des bonnes pratiques
   de mot de passe.

## Remarque de sécurité
Un déverrouillage systématique sans vérification peut être exploité par un attaquant tentant
un accès frauduleux. Toujours croiser avec l'historique de connexion.
