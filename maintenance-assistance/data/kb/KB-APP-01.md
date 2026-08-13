---
id: KB-APP-01
categorie: logiciels_et_applications
titre: Application qui ne démarre plus
---

# Application qui ne démarre plus

## Symptômes
Une application métier (ERP, CRM, bureautique) ne se lance plus, se ferme immédiatement,
ou affiche une erreur au démarrage.

## Procédure standard
1. Vérifier via `verifier_etat_service` si le service applicatif concerné est en incident
   (ex. `SRV-ERP`).
2. Si un incident est déjà déclaré, rattacher le ticket et informer l'utilisateur.
3. Sinon, demander : version de l'application, message d'erreur exact, dernière action avant
   le blocage, redémarrage déjà tenté ou non.
4. Proposer un redémarrage de l'application, puis du poste, en dernier recours une réinstallation
   (nécessite un technicien).

## Escalade
Si plusieurs utilisateurs du même service signalent le problème simultanément, considérer un
incident applicatif global et escalader vers l'équipe `applications`.
