# Phase 1 — Audit du dépôt et du workspace Databricks

Fichier à placer dans `docs/phases/01-audit.md`. Lis d'abord `CLAUDE.md` et `docs/architecture.md`, puis exécute cette phase, et seulement celle-ci.

## Objectif

Établir par des tests réels ce qui est possible dans le workspace Databricks (Free Edition) et avec le fournisseur de données candidat, afin de valider ou corriger l'architecture avant d'écrire le moteur. Le livrable est `docs/workspace-audit.md`.

## Règles de cette phase

- **Rien n'est supposé.** Chaque ligne du rapport porte un statut : `OK` (testé, réussi), `KO` (testé, échoué), `NON TESTÉ` (avec la raison), et la preuve (commande lancée, extrait de sortie).
- Ne colle jamais une clé API, un jeton ou un secret dans un fichier, un log, un commit ou la sortie du rapport. Masque-les.
- Aucun code de production dans `src/atlas/` pendant cette phase. Les scripts jetables vont dans `scripts/audit/`.
- Budget d'appels au fournisseur : **40 appels maximum** au total (limite gratuite : 800 par jour et 8 par minute). Espace les appels et surveille les en-têtes de crédits restants quand ils existent.
- Si un test échoue, ne le contourne pas : consigne l'échec, la cause probable, et l'alternative envisagée.
- Si une commande dépend de la version du CLI ou de l'interface et que tu n'es pas sûr de sa syntaxe, vérifie avec `--help` plutôt que d'inventer.

## Prérequis à confirmer auprès de l'utilisateur

Demande, sans les deviner :
1. Le profil du CLI Databricks à utiliser et l'URL du workspace.
2. Si une clé Twelve Data existe déjà. Sinon, fournis la procédure de création (compte gratuit, génération de la clé) et attends.
3. Où stocker la clé : secret Databricks si disponible (voir test 2.4), sinon alternative à valider avec l'utilisateur.

## Partie A — Dépôt

| # | Test | Preuve attendue |
|---|---|---|
| A1 | Inspecter le dépôt : arborescence, `CLAUDE.md`, `databricks.yml` présent ou non, version de Python, outils de test | Liste des fichiers et versions |
| A2 | Vérifier que `.gitignore` exclut `.env`, les fichiers de profil et les artefacts locaux | Extrait du `.gitignore` |
| A3 | Rechercher des secrets déjà présents dans le dépôt | Résultat de la recherche (sans afficher de valeur) |
| A4 | Vérifier que le CLI Databricks est installé et récent ; noter la version | Sortie de `databricks --version` |

## Partie B — Workspace Databricks

| # | Test | Ce qu'il faut établir |
|---|---|---|
| B1 | Authentification et identité courante | Le CLI se connecte-t-il, avec quel utilisateur ? |
| B2 | Unity Catalog : lister les catalogues ; tenter de créer le catalogue `atlas` ; sinon, identifier où créer les schémas | Peut-on créer un catalogue, ou seulement des schémas dans un catalogue existant ? Adapter alors le nom d'espace de travail |
| B3 | Créer `bronze`, `silver`, `gold` (ou équivalents), y créer une table Delta de test, y écrire, la lire, la supprimer | Droits d'écriture et de suppression réels |
| B4 | Calcul : lancer un job minimal sur calcul serverless (par exemple un script Python qui écrit une ligne dans la table de test) | Un job planifiable fonctionne-t-il ? Durée de démarrage et d'exécution |
| B5 | Planification : créer un job avec un déclencheur planifié toutes les 15 minutes, le laisser s'exécuter 2 fois, puis le supprimer | La fréquence de 15 min est-elle acceptée et respectée ? Y a-t-il des limites de quota ? |
| B6 | Lakeflow Declarative Pipelines : tenter de créer un pipeline minimal (hors streaming continu) | Disponible ou non, et sous quelles conditions |
| B7 | Asset Bundle : valider un `databricks.yml` minimal (`bundle validate`), le déployer en `dev`, puis le détruire | Le déploiement par bundle fonctionne-t-il ? |
| B8 | Databricks Apps : lister ou créer une application minimale « hello world » | Disponible ? Quotas ? Durée de vie de l'application ? Sinon : plan B Streamlit |
| B9 | MLflow : créer une expérience, journaliser un paramètre et une métrique depuis un job | Le suivi MLflow est-il utilisable ? |
| B10 | Modèles de langage : lister les points de terminaison disponibles ; envoyer 1 requête minimale à un modèle | Quels modèles, quels quotas ? Un appel depuis un job fonctionne-t-il ? |
| B11 | Secrets : tenter de créer une portée de secrets et d'y stocker une valeur factice ; la relire depuis un job | Les secrets Databricks sont-ils disponibles ? Sinon, proposer une alternative et la soumettre à l'utilisateur |
| B12 | Limites générales : noter tout message de quota, de restriction ou de plafond rencontré | Liste des limites constatées |

Nettoie après chaque test (objets créés, jobs, applications). Liste dans le rapport ce qui a été créé et supprimé.

## Partie C — Réseau et fournisseur de données

Les tests C2 à C7 s'exécutent **depuis le calcul Databricks** (job serverless), pas seulement depuis ta machine : l'accès sortant du workspace est un point bloquant possible.

| # | Test | Ce qu'il faut établir |
|---|---|---|
| C1 | Lire les conditions d'utilisation du fournisseur (page publique) et en résumer les points sur l'usage personnel, l'affichage des données, le stockage historique et la redistribution | Résumé et lien. Si ambigu : le noter et poser la question à l'utilisateur |
| C2 | Accès sortant : requête simple vers l'API du fournisseur depuis un job | Le workspace peut-il joindre le fournisseur ? |
| C3 | Couverture : demander une bougie récente pour chacun des 6 instruments de `config/universe.yml` (EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CHF, XAU/USD) | Chaque symbole est-il disponible, avec quel intervalle ? **En particulier XAU/USD** |
| C4 | Intervalles : tester 5 min, 15 min et 1 h sur EUR/USD et XAU/USD | Quels intervalles sont réellement servis ? |
| C5 | Fraîcheur : pendant une session de marché ouverte, comparer l'horodatage de la dernière bougie à l'heure UTC réelle, à 3 reprises espacées | Les données sont-elles en temps réel, retardées (de combien ?) ou en retard variable ? |
| C6 | Profondeur : demander le maximum de points par requête sur le 15 min ; mesurer la profondeur d'historique obtenue en un appel, puis en paginant | Combien de mois d'historique 15 min et 1 h sont accessibles dans le budget d'appels ? |
| C7 | Champs et qualité : volume présent ou non, bid/ask présent ou non, fuseau horaire des horodatages, format des prix, gestion des week-ends et des trous | Liste des champs réels ; le spread est-il disponible ? |
| C8 | Limites : relever les en-têtes de crédits restants, déclencher volontairement une limite de débit **une seule fois** sur la minute pour observer le code d'erreur et le comportement | Format de l'erreur et délai de reprise (pour le connecteur) |

Enregistre une copie brute (sans clé) d'une réponse par type de test dans `tests/fixtures/` : elle servira de fixture aux tests de qualité de la phase 3.

Si un symbole ou un intervalle n'est pas servi par l'offre gratuite, propose des alternatives à évaluer, sans en intégrer aucune.

## Livrable : `docs/workspace-audit.md`

Structure obligatoire :
1. **Synthèse** : une table par partie (A, B, C) avec l'identifiant du test, le statut et une ligne de conclusion.
2. **Preuves** : commandes lancées et extraits utiles, sans secret.
3. **Limites constatées** : quotas, plafonds, restrictions.
4. **Écarts avec `docs/architecture.md`** : pour chaque hypothèse de l'architecture démentie ou confirmée, la modification proposée (nom du catalogue, cadence, application ou plan B, stockage de la clé, etc.).
5. **Budget d'appels fournisseur** : nombre d'appels consommés dans cette phase.
6. **Risques ouverts** et questions pour l'utilisateur.
7. **Verdict** : l'architecture peut-elle être implémentée telle quelle, avec ajustements (lesquels), ou faut-il choisir un autre fournisseur ou une autre cible d'exécution.

Mets aussi à jour `docs/STATUS.md`.

## Critères d'acceptation

- Tous les tests A1 à C8 ont un statut et une preuve, ou une raison claire de non-exécution.
- Le rapport ne contient aucune valeur secrète (vérifiée par une recherche automatique dans le dépôt).
- Tous les objets de test créés dans le workspace sont supprimés, ou listés avec la raison de leur conservation.
- Les écarts avec l'architecture sont chiffrés ou précisés, pas décrits en termes généraux.
- Le nombre d'appels fournisseur ne dépasse pas 40.
- La réponse à la question « XAU/USD est-il servi, à quelle fraîcheur ? » est explicite.

## Ne pas faire

- Ne pas commencer la phase 2 (fondations) ni écrire le moteur quantitatif.
- Ne pas contourner une restriction du workspace ou des conditions du fournisseur.
- Ne pas déclarer « OK » un test que tu n'as pas exécuté.
- Ne pas souscrire à un abonnement payant ni créer de ressources payantes.

Termine en présentant le verdict à l'utilisateur et **attends sa validation** avant de passer à la phase 2.
