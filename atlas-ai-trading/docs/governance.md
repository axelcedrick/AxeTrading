# Gouvernance — qui peut lire et écrire quoi

État constaté le 2026-10-28 sur la Free Edition (lectures seules : `SHOW GRANTS`, liste des groupes et des
principaux de service, ACL des secrets). Aucun droit n'a été modifié pendant la phase 2.

## Constat

| Élément | État |
|---|---|
| Utilisateurs | 1 (`axelcedrickaboua@gmail.com`), membre de `users` et `admins` |
| Groupes | `users`, `admins` (pas de console de compte ni de SCIM sur la Free Edition) |
| Principaux de service | aucun (celui de l'app de test de la phase 1 a été supprimé avec elle) |
| Droits sur `atlas_dev` | aucun droit explicite : seul le propriétaire (l'utilisateur) y accède |
| Secrets | scope `atlas-audit` : `MANAGE` pour l'utilisateur seul |
| Lignage | fourni par Unity Catalog sur les tables créées (non vérifié dans l'interface) |

## Modèle de moindre privilège retenu

| Acteur | Bronze | Silver | Gold | Secrets | Remarque |
|---|---|---|---|---|---|
| Jobs d'ingestion (phase 3) | écriture (ajout seul) | écriture (MERGE) | écriture `data_quality_metrics`, `pipeline_runs` | lecture de la clé fournisseur | |
| Jobs quant/backtest (phases 4–5) | — | lecture | écriture des tables de leur phase | — | |
| Moteur de risque | — | lecture | écriture `risk_decisions` | — | indépendant des agents IA |
| Agents IA (phase 7) | — | **lecture seule** | lecture, plus écriture de leurs seuls rapports | **aucun** | ne peuvent ni modifier les données de référence, ni contourner le risque, ni transmettre d'ordre |
| Application (phase 8) | — | lecture | lecture, plus écriture de `audit_log` | — | via le principal de service de l'app |
| Utilisateur | tout | tout | tout | `MANAGE` | administrateur unique |

## Ce qui est applicable ou non sur la Free Edition

- **Applicable :** `GRANT` / `REVOKE` Unity Catalog sur catalogue, schéma et table ; ACL de secret scopes ;
  séparation des environnements par catalogue (`atlas_dev`, `atlas_test`, `atlas_prod`).
- **Limité :** un seul utilisateur humain, donc la séparation des rôles humains est théorique. Les jobs
  tournent sous l'identité de l'utilisateur (pas de `run_as` vers un principal de service dédié en phase 2).
- **Non applicable :** console de compte, SSO/SCIM, politiques de calcul, plusieurs workspaces (audit, §3).
- **À traiter plus tard :**
  - phase 7 : créer un principal de service « agents » avec `USE CATALOG`, `USE SCHEMA` et `SELECT` uniquement, sans accès aux secrets ;
  - phase 8 : borner le principal de service de l'app de la même manière ;
  - dans les deux cas, vérifier sur le workspace que ces droits sont réellement appliqués.
