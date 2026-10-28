# Audit du workspace et du fournisseur — Phase 1

- **Date d'exécution :** mercredi 28 octobre 2026, de 21:06 à 21:35 UTC (marché Forex ouvert)
- **Workspace :** `https://dbc-2ca00ccd-e312.cloud.databricks.com` (Free Edition, AWS us-east-2), profil CLI `dbc-2ca00ccd-e312`
- **Utilisateur :** `axelcedrickaboua@gmail.com`, membre des groupes `users` et `admins`
- **Fournisseur testé :** Twelve Data, offre gratuite Basic (`plan_category: basic`, confirmé par `/api_usage`)
- **Scripts jetables :** `scripts/audit/`. Fixtures brutes, sans clé : `tests/fixtures/raw_audit/`

Statuts : `OK` = testé, réussi · `KO` = testé, échoué · `PARTIEL` = testé avec une réserve · `NON TESTÉ` = la raison est donnée.

---

## 1. Synthèse

### Partie A — Dépôt

| # | Statut | Conclusion |
|---|---|---|
| A1 | OK | Dépôt minimal (`CLAUDE.md`, `docs/`). Pas de `databricks.yml`. Python 3.15.0, uv 0.13.1, git 2.56. **pytest absent.** Sous-dossier `atlas-trading/` : dépôt git vide, sans commit. |
| A2 | KO → corrigé | Il n'y avait **aucun `.gitignore`**. J'en ai créé un (secrets, `.databrickscfg*`, `.env`, artefacts Python et MLflow). |
| A3 | OK | Aucun secret trouvé dans le dépôt (recherche par motifs, aucune valeur affichée). |
| A4 | OK | Databricks CLI **v1.22.1**, installé via winget. |

### Partie B — Workspace Databricks

| # | Statut | Conclusion |
|---|---|---|
| B1 | OK | Authentification OAuth OK, rôle admin. Une erreur passagère du trousseau Windows est apparue au premier appel (voir §3). |
| B2 | OK (avec réserve) | `databricks catalogs create atlas` (API REST) **échoue** : il n'y a pas d'emplacement de stockage au niveau du metastore. En revanche, **`CREATE CATALOG atlas` en SQL réussit** (stockage par défaut). Le nom `atlas` reste donc possible. |
| B3 | OK | Schémas `bronze`, `silver` et `gold` créés. Table Delta créée, écrite, lue, supprimée. Volume Unity Catalog créé et écrit depuis un job. |
| B4 | OK | Job serverless (`spark_python_task`) écrivant dans la table : SUCCÈS. Environ 3 s de mise en place, 30 s de script, 75 à 100 s par tâche au total (installation de l'environnement comprise). |
| B5 | OK | Job planifié `0 0/15 * * * ?` (UTC) : 2 exécutions PERIODIC, à **21:15:07** et **21:30:07**, environ 20 s chacune. Le planificateur déclenche environ 7 s après le quart d'heure. Aucun message de quota. |
| B6 | OK | Pipeline Lakeflow Declarative serverless, en mode déclenché (vue matérialisée SQL) : COMPLETED en 56 s, dont 35 s d'attente de ressources. |
| B7 | OK | `bundle validate`, puis `deploy -t dev`, `run` (SUCCESS en 18 s) et `destroy` : tout fonctionne. |
| B8 | OK | App « hello world » : calcul ACTIVE environ 2 min 45 après la création, déploiement en 10 s, HTTP 200 avec authentification, 302 vers OAuth sans authentification. Taille de calcul `MEDIUM`. |
| B9 | OK | MLflow 3.17.2 depuis un job : expérience, paramètre, métrique et artefact enregistrés puis relus. |
| B10 | OK | 12 points de terminaison Foundation Model prêts (liste au §2). 1 requête à `databricks-meta-llama-3-1-8b-instruct` depuis un job : réponse « Pong », 20 jetons, 2,2 s. Quotas non publiés. |
| B11 | OK | Scope de secrets créé, valeur factice relue depuis un job (égalité vérifiée). Clé fournisseur relue (32 caractères). Un incident de saisie a été corrigé, voir §6. |
| B12 | OK | Limites relevées au §3. |

### Partie C — Réseau et fournisseur (tous les appels sont partis d'un job serverless)

| # | Statut | Conclusion |
|---|---|---|
| C1 | PARTIEL | Conditions lues. **Basic = usage interne, « non-display », non commercial.** Les matières premières sont présentées comme une fonction de l'offre Grow. Questions ouvertes au §6. |
| C2 | OK | `api.twelvedata.com` est joignable depuis le serverless (HTTP 200 avec clé, 401 JSON sans clé). |
| C3 | OK | Les 6 instruments sont servis en 15 min. **XAU/USD est servi sur Basic** (`type: Precious Metal`). |
| C4 | OK | 5 min, 15 min et 1 h servis pour EUR/USD et XAU/USD. |
| C5 | OK | 3 mesures. **Quasi temps réel** : la dernière bougie 1 min est disponible 61 à 79 s après sa clôture pour EUR/USD, 30 à 64 s pour XAU/USD. Réserve : mesures faites en séance asiatique, sur une fenêtre de 9 minutes. |
| C6 | OK | 5 000 points par appel. En 15 min, cela fait environ 52 jours par appel. En 1 h, environ 208 jours. L'historique 15 min d'EUR/USD remonte au 2020-01-30. |
| C7 | OK | Champs `datetime, open, high, low, close` uniquement. **Ni volume, ni bid/ask** (même dans `/quote`). **Des bougies sont émises le week-end.** Le fuseau par défaut n'est pas UTC. |
| C8 | OK | En-têtes `Api-Credits-Used/Left/Request` présents. Le 9ᵉ appel de la minute renvoie **HTTP 429** avec `code: 429` et un message explicite. |

---

## 2. Preuves (extraits, sans secret)

**A1 / A4**
```
Python 3.15.0 · uv 0.13.1 · pip 26.2.1 · git 2.56.0.windows.2 · pytest: command not found
Databricks CLI v1.22.1
```

**B1** — `databricks current-user me` → `active: true`, e-mail `axelcedrickaboua@gmail.com`, groupes `users` et `admins`.
Metastore : `metastore_aws_us_east_2`, `cloud: aws`, `region: us-east-2`, aucun `storage_root`.

**B2**
```
$ databricks catalogs create atlas
Error: Metastore storage root URL does not exist. Default Storage is enabled in your account. You can use the UI
to create a new catalog using Default Storage, or please provide a storage location for the catalog ...
$ (SQL warehouse) CREATE CATALOG IF NOT EXISTS atlas  → state=SUCCEEDED 7.8s
$ SHOW CATALOGS → atlas, samples, system, workspace
```
Catalogues existants avant l'audit : `system`, `samples`, `workspace`.
SQL warehouse : `Serverless Starter Warehouse`, 2X-Small, le seul du workspace.

**B3** — `CREATE SCHEMA atlas.{bronze,silver,gold}`, `CREATE TABLE atlas.bronze.audit_test USING DELTA`, `INSERT`, `SELECT`, `CREATE/DROP TABLE atlas.silver.audit_drop` : tous `SUCCEEDED`. `DESCRIBE DETAIL` : format `delta`, deletion vectors, row tracking et liquid clustering activés par défaut.

**B4** — run `331932626405436`, tâche `b4_write` : `{"status":"OK","rows_in_table":2,"spark_version":"4.2.0","elapsed_s":29.91}`

**B5** — job `186905000538574` :
```
B5 804222721696688 PERIODIC SUCCESS 21:15:07 run_ms 19504
B5 124570230996293 PERIODIC SUCCESS 21:30:07 run_ms 20745
```

**B6** — événements du pipeline : `WAITING_FOR_RESOURCES 21:12:57` → `RUNNING 21:13:44` → `COMPLETED 21:13:51`. La vue `atlas.silver.audit_mv` a été lue : 2 lignes.

**B7**
```
Validation OK!
Resources: 1 created ... "[dev axelcedrickaboua] atlas-audit-bundle-job" TERMINATED SUCCESS — hello from atlas audit bundle
Destroy: 1 deleted
```

**B8** — `atlas-audit-hello` : `compute_status ACTIVE` à 21:15:49 (création à 21:13:04), déploiement `SNAPSHOT` → `App started successfully`.
`curl` avec jeton → `hello from atlas audit app`, HTTP 200. Sans jeton → HTTP 302 vers `/oidc/oauth2/v2.0/authorize`.

**B9** — `{"mlflow_version":"3.17.2","params":{"audit_param":"phase1"},"metrics":{"audit_metric":0.42}}`

**B10** — points de terminaison (tous `READY`) :
- discussion (`llm/v1/chat`) : `databricks-gpt-oss-120b`, `databricks-gpt-oss-20b`, `databricks-qwen3-next-80b-a3b-instruct`, `databricks-qwen35-122b-a10b`, `databricks-gemma-3-12b`, `databricks-meta-llama-3-1-8b-instruct`, `databricks-meta-llama-3-3-70b-instruct`, `databricks-llama-4-maverick`, `databricks-deepseek-v4-flash-0731` ;
- plongements vectoriels (embeddings) : `databricks-gte-large-en`, `databricks-bge-large-en`, `databricks-qwen3-embedding-0-6b`.

Appel : `{"answer":"Pong","usage":{"completion_tokens":3,"prompt_tokens":17,"total_tokens":20},"elapsed_s":2.18}`

**B11** — `{"dummy_matches":true,"provider_key_present":true}`. Diagnostic de la clé (classes de caractères seulement) :
- 1ʳᵉ saisie : `{"length":33,"non_alnum_positions":[[0,"U+0000:Cc"]]}` → rejetée ;
- 2ᵉ saisie : `{"length":32,"non_alnum_positions":[]}` → OK.

**C2** — avec la clé mal saisie, Cloudflare renvoie `400 Bad Request` (HTML, `Server: cloudflare`). Sans clé : `{"code":401,"message":"**apikey** parameter is incorrect or not specified..."}`. Avec la bonne clé : HTTP 200.

**C3** (`outputsize=2`, fuseau par défaut, appels entre 21:21 et 21:23 UTC environ)

| Symbole | `meta.type` | Dernière bougie (fuseau par défaut) | close |
|---|---|---|---|
| EUR/USD | Physical Currency | 2026-10-29 08:15:00 | 1.1155 |
| GBP/USD | Physical Currency | 2026-10-29 08:15:00 | 1.33231 |
| USD/JPY | Physical Currency | 2026-10-29 08:15:00 | 157.81772 |
| AUD/USD | Physical Currency | 2026-10-29 08:15:00 | 0.70561 |
| USD/CHF | Physical Currency | 2026-10-29 08:15:00 | 0.82801 |
| XAU/USD | Precious Metal | 2026-10-29 08:15:00 | 4067.99176 |

L'heure « 08:15 le 29 » correspond à 21:15 UTC le 28, soit un **décalage de +11 h**. `meta` n'indique aucun fuseau. Il faut donc **toujours passer `timezone=UTC`**.

**C4** (`timezone=UTC`) — EUR/USD 5 min : dernière bougie 21:20. EUR/USD 1 h : 21:00. XAU/USD 5 min : 21:20. XAU/USD 1 h : 21:00. Tous `status: ok`.
**La bougie en cours de formation est renvoyée** : la bougie 5 min de 21:20 a été reçue vers 21:22, et la bougie 15 min de 21:15 vers 21:24.

**C5** — bougies 1 min, `timezone=UTC`

| Mesure | Symbole | Heure de la requête (UTC) | Dernière bougie (ouverture) | Retard après la clôture de cette bougie |
|---|---|---|---|---|
| 1 | EUR/USD | 21:23:18 | 21:21 | 79 s |
| 1 | XAU/USD | 21:23:30 | 21:22 | 31 s |
| 2 | EUR/USD | 21:26:18 | 21:24 | 79 s |
| 2 | XAU/USD | 21:26:29 | 21:25 | 30 s |
| 3 | EUR/USD | 21:32:01 | 21:30 | 61 s |
| 3 | XAU/USD | 21:32:04 | 21:30 | 64 s |

En 1 min, la bougie en cours n'est pas renvoyée. Le retard est d'**environ 1 min** pour XAU/USD et **d'environ 1 à 1 min 20** pour EUR/USD. Pour du 15 min, c'est négligeable.

**C6** — EUR/USD, `outputsize=5000`, pagination par `end_date`

| Intervalle | Page | Points | Plus récent → plus ancien | Trous | Doublons |
|---|---|---|---|---|---|
| 15 min | 1 | 5 000 | 2026-10-28 21:15 → 2026-09-06 19:30 | 0 | 0 |
| 15 min | 2 | 5 000 | 2026-09-06 19:30 → 2026-07-16 17:45 | 0 | 0 |
| 1 h | 1 | 5 000 | 2026-10-28 21:00 → 2026-04-03 13:00 | 1 (2 h, le samedi 2026-04-04 entre 14:00 et 16:00) | 0 |

`/earliest_timestamp` EUR/USD 15 min → `2020-01-30 18:00:00`.
Remarque : la page 2 commence sur la bougie la plus ancienne de la page 1, car `end_date` est inclusif. Il y a donc un chevauchement d'une bougie. À dédupliquer (clé naturelle `silver.candles`).

**C7**
- Champs de `time_series` : `datetime, open, high, low, close`. **Pas de `volume`** sur le Forex ni sur XAU/USD.
- Champs de `/quote` : `symbol, name, exchange, datetime, timestamp, last_quote_at, open, high, low, close, previous_close, change, percent_change, is_market_open, fifty_two_week`. **Pas de bid ni d'ask.**
- Prix : chaînes de caractères avec 5 décimales sur tous les instruments observés, y compris USD/JPY (`157.81772`) et XAU/USD (`4067.99176`). Ces valeurs vont au-delà du pip usuel : il faut convertir en `decimal` ou `double` et définir `pip_size` et `price_decimals` dans `silver.instruments`, plutôt que de les déduire de la réponse.
- **Week-end :** entre le vendredi 2026-10-23 20:00 et le dimanche 2026-10-25 22:30 UTC, il y a **203 bougies 15 min**, aucune plate, avec des variations réelles. Exemple : samedi 21:15, O 1.12029 H 1.12033 L 1.12021 C 1.1203. Le Forex interbancaire est fermé à ce moment-là : ce sont des cotations hors séance, non négociables.

**C8**
```
burst 1..8 : HTTP 200, Api-Credits-Used 1→8, Api-Credits-Left 7→0
burst 9    : HTTP 429, {"code":429,"message":"You have run out of API credits for the current minute. 9 API credits
             were used, with the current limit being 8. Wait for the next minute ..."}
/api_usage : {"current_usage":4,"plan_limit":8,"daily_usage":18,"plan_daily_limit":800,"plan_category":"basic"}
```
Reprise : à la minute suivante, d'après le message. Les 8 requêtes rejetées par Cloudflare (400) n'ont **pas** été décomptées : `daily_usage` valait 18 après 18 réponses 200.

**Recherche automatique de secrets dans le dépôt (après rédaction)** :
- motifs `api_key|apikey|token|secret|password = ...` : aucun résultat ;
- `apikey=` dans une URL : aucun résultat ;
- jetons `dapi…` : aucun résultat ;
- chaînes alphanumériques de 32 caractères : 1 seul résultat, dans l'en-tête Cloudflare `Report-To` de `c3_USDCHF_15min.json` (paramètre de l'URL de rapport réseau NEL). Ce n'est pas une clé.

**Fixtures enregistrées** (`tests/fixtures/raw_audit/`) : `c3_*_15min.json` (6), `c4_{EURUSD,XAUUSD}_{5min,1h}.json`, `c5_*_1min_s1.json`, `c6_EURUSD_15min_p1.json`, `c6_EURUSD_1h_p1.json`, `c6_earliest_EURUSD_15min.json`, `c7_quote_EURUSD.json`, `c8_api_usage.json`, `c8_rate_limit_error.json`, `audit_calls_ledger.json` (journal des 37 appels). La clé passe en en-tête HTTP et n'apparaît jamais dans les URL. Toute occurrence de la clé est remplacée avant l'écriture.

---

## 3. Limites constatées

**Mesurées pendant l'audit**
- Création de catalogue impossible par l'API REST sans `MANAGED LOCATION`. Elle fonctionne en SQL.
- Un seul SQL warehouse (2X-Small). Le premier démarrage d'une requête prend environ 13 s (warehouse arrêté).
- Démarrage serverless : 3 s de mise en place, mais 75 à 100 s par tâche lorsque l'environnement installe une dépendance (`mlflow`). Sans dépendance : environ 20 s (B5, B7).
- Pipeline : environ 35 s d'attente de ressources avant exécution.
- App : environ 2 min 45 de mise à disposition du calcul.
- Fournisseur : 8 crédits par minute (429 au 9ᵉ), 800 par jour, 5 000 points par requête au maximum, 1 crédit par requête de série.
- Outils locaux : le trousseau Windows a renvoyé `OS keyring unreachable: The parameter is incorrect` une fois. L'erreur ne s'est pas reproduite à la tentative suivante. Git Bash convertit les chemins `/Workspace/...` : il faut utiliser `MSYS_NO_PATHCONV=1` ou PowerShell.

**Documentées (pages officielles Free Edition, mises à jour en octobre 2026, non mesurées ici)**
- Calcul serverless uniquement, sous « fair usage policy ». En cas de dépassement, le calcul est **coupé pour le reste de la journée**, voire du mois. Aucun quota chiffré n'est publié.
- **5 tâches de job simultanées au maximum par compte.**
- **3 apps au maximum, arrêt automatique 24 h après chaque démarrage ou déploiement.**
- **1 pipeline actif par type de pipeline.**
- Accès Internet sortant « limité à un ensemble de domaines de confiance » (liste non publiée). `api.twelvedata.com` est joignable, d'après le test C2.
- **Usage non commercial uniquement.** Comptes inactifs « pendant une période prolongée » susceptibles d'être supprimés. Pas de SLA.
- Nombre de points de terminaison de modèles actifs limité. Pas de GPU ni de débit provisionné. Débits des Foundation Model APIs non publiés.

---

## 4. Écarts avec `docs/architecture.md`

| Hypothèse de l'architecture | Résultat | Modification proposée |
|---|---|---|
| Catalogue `atlas` | Confirmé, mais seulement en SQL | Phase 2 : créer le catalogue par une tâche SQL `CREATE CATALOG IF NOT EXISTS atlas`. Vérifier si le bundle peut déclarer un catalogue sans emplacement géré. Les schémas restent déclarés dans le bundle. |
| Micro-batch toutes les 15 min | Confirmé (déclenchement environ 7 s après le quart d'heure) | Planifier vers **:01 / :16 / :31 / :46**, soit environ 60 à 80 s après la clôture, pour laisser publier la bougie terminée (C5). |
| 576 appels par jour en live (6 × 96) | Confirmé pour le 15 min seul | Si le 1 h est interrogé séparément : +144, soit **720 par jour (90 %)**. Proposition : **agréger le 1 h depuis le 15 min** (déterministe et testé), pour rester à 576 appels par jour et garder 224 appels par jour pour le backfill et les reprises. |
| Fraîcheur « à vérifier » | Quasi temps réel, retard d'environ 30 à 80 s sur le 1 min | Compatible avec le 15 min. Fixer le seuil « cotation périmée » par configuration, par exemple un retard supérieur à 2 intervalles. Remesurer en séances Londres et New York. |
| Bougie incomplète | **L'API renvoie la bougie en cours** en 5 min, 15 min et 1 h | `is_complete = bar_close_ts <= request_ts`, calculé à l'ingestion. Le test de garde-fou §4 du CLAUDE.md est indispensable dès la phase 3. |
| Fuseau UTC | Le fuseau par défaut **n'est pas UTC** (+11 h observé) et `meta` ne l'indique pas | Toujours envoyer `timezone=UTC`, l'enregistrer dans `request_params`, et refuser une réponse sans ce paramètre. |
| Calendrier de sessions (§6) | **Des bougies existent le week-end**, avec des variations réelles | Calendrier Forex 24 h / 5 j obligatoire dès la phase 3. Ajouter un drapeau de qualité `OFF_SESSION`. Exclure ces bougies des indicateurs, setups et backtests (elles fausseraient l'ATR et les gaps du lundi). |
| Volume nullable | Confirmé : champ absent | `volume` reste `NULL` pour le Forex et XAU/USD. |
| Spread par hypothèses | Confirmé : ni bid ni ask, même dans `/quote` | `silver.cost_assumptions` avec `source = 'hypothèse'`, à signaler dans les backtests. |
| Backfill peu coûteux | Confirmé | 15 min depuis 2020-01-30 : environ 48 appels par instrument, soit **environ 290 appels pour 6 instruments**. 1 h (si l'historique remonte aussi loin, non testé) : environ 12 appels par instrument, soit environ 72. 5 min : environ 17 jours par appel, donc environ 140 appels par instrument depuis 2020, soit **environ 850 pour 6**, plus d'une journée de quota. À étaler sur 4 à 5 jours en parallèle du live, ou à limiter à 2 ans. |
| Pagination | `end_date` inclusif | Une bougie de chevauchement par page : dédoublonnage par clé naturelle (déjà prévu avec le MERGE). |
| Databricks Apps (sinon Streamlit) | Disponible | Garder Apps. Contraintes : 3 apps au maximum, **arrêt automatique sous 24 h** (redémarrage manuel ou planifié). **Les conditions Twelve Data posent problème pour l'affichage**, voir §6. |
| Stockage de la clé | Secrets Databricks OK | `atlas-audit/twelvedata_api_key` existe déjà. Phase 2 : scope définitif (par exemple `atlas`), à saisir avec la procédure du §6. |
| Modèles de langage | 12 points de terminaison | Phase 7 : choix du modèle à faire, avec des débits à mesurer. |
| Arborescence `atlas-ai-trading/` | Le dossier présent s'appelle `atlas-trading/`. Le renommage a été refusé (accès refusé, dossier probablement verrouillé). | À décider en phase 2 : renommer le dossier et y déplacer `CLAUDE.md` et `docs/`, ou garder la racine `AxeTrading`. |
| Outils de test | pytest absent | Phase 2 : `pyproject.toml` avec pytest (via uv). |

---

## 5. Budget d'appels fournisseur

| Lot | Appels envoyés | Résultat | Décomptés par Twelve Data |
|---|---|---|---|
| Série principale, 1ʳᵉ tentative (clé mal saisie) | 8 | 400 Cloudflare | non (`daily_usage`) |
| Diagnostics sans clé | 2 | 401 | sans objet (aucune clé) |
| Série principale (C2–C4, C5#1, C6, C7, C8) | 18 | 200 | oui |
| C5 mesure 2 | 2 | 200 | oui |
| C8 rafale (dont C5 mesure 3) | 9 | 8 × 200, 1 × 429 | oui |
| **Total** | **39 / 40** | | environ 29 |

---

## 6. Risques ouverts et questions pour toi

1. **Affichage des données (bloquant pour la phase 8).** L'offre Basic est décrite comme « Internal non-display usage ». L'affichage interne commence à l'offre Grow (prix affiché : 79 $ par mois, mais 29 $ dans d'autres pages du même site, c'est contradictoire). Les conditions autorisent les « Derived Data » qui ne permettent pas de reconstituer les données d'origine. Trois options :
   (a) n'afficher que des données dérivées (scores, signaux), sans prix bruts ;
   (b) passer à une offre payante ;
   (c) changer de fournisseur pour l'affichage.
   → Quel est ton choix ? Je recommande de poser la question à `support@twelvedata.com` avant la phase 8.
2. **XAU/USD sur Basic.** Il est servi techniquement, mais la page des tarifs range les « commodities » dans l'offre Grow. Le service pourrait cesser, ou ne pas être couvert par la licence. → À confirmer auprès du support.
3. **Durée de conservation de l'historique.** Les conditions interdisent de stocker au-delà des « permitted timeframes specified in the Documentation ». Je n'ai pas lu cette documentation, donc ce point n'est **pas vérifié**. → À lire avant le backfill de la phase 3.
4. **Usage non commercial** : c'est le cas à la fois pour la Free Edition et pour l'offre Basic. C'est compatible avec un usage personnel. Toute exploitation commerciale imposerait de changer les deux.
5. **Cotations du week-end** : risque de faux signaux et de faux gaps si elles ne sont pas filtrées (voir §4).
6. **Fraîcheur mesurée sur une seule fenêtre** (séance asiatique, 9 minutes). La surveillance des retards prévue en phase 3 devra la confirmer en séances Londres et New York.
7. **Coupure de quota Free Edition** : non chiffrée, avec un risque d'arrêt du calcul pour la journée. Le live, le backfill et l'app partagent ce budget. Il faudra mesurer la consommation pendant les 7 jours de la phase 3.
8. **Saisie du secret sous Windows** : la saisie interactive de `put-secret` a inséré un caractère nul. La procédure fiable est la suivante :
   ```powershell
   $s = Read-Host "Cle" -AsSecureString
   $k = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
   databricks secrets put-secret <scope> <cle> --string-value $k.Trim() -p dbc-2ca00ccd-e312
   Remove-Variable k, s
   ```
   Le connecteur doit **refuser** une clé non alphanumérique, sans la corriger.
9. **Profils CLI** : `databricks auth profiles` liste 3 autres profils sur le même hôte (`axelcedrickabouagmail.com`, `DEV`, et un doublon), affichés `Valid: NO`. Ils sont inoffensifs, mais à nettoyer pour éviter les confusions.

---

## 7. Objets créés et supprimés

| Objet | Créé | Supprimé |
|---|---|---|
| Catalogue `atlas` (schémas `bronze`, `silver`, `gold`, tables `audit_test` et `audit_calls`, volume `audit_fixtures`, vue `audit_mv`) | oui | oui (`DROP CATALOG atlas CASCADE`) |
| Job `atlas-audit-platform-and-provider` (1026152939776729) | oui | oui |
| Job planifié `atlas-audit-schedule-15min` (186905000538574) | oui | oui |
| Exécutions ponctuelles (`jobs submit`) : diag, diag2, provider-main, fresh2, burst | oui | historique d'exécution seulement, aucun job persistant |
| Pipeline `atlas-audit-pipeline` | oui | oui |
| Bundle `atlas-audit-bundle` (job et fichiers) | oui | oui (`bundle destroy`). Le dossier `/Workspace/Users/.../.bundle` reste, vide. |
| App `atlas-audit-hello` | oui | oui |
| Expérience MLflow `atlas-audit-mlflow` | oui | oui (corbeille MLflow) |
| Scope de secrets `atlas-audit-dummy` | oui | oui |
| Dossier workspace `atlas_audit/` (scripts, code de l'app) | oui | oui |
| **Scope `atlas-audit` (clé Twelve Data)** | par toi | **conservé** : il servira en phase 2 |

État final vérifié : aucun job, aucun pipeline, aucune app. Catalogues présents : `system`, `samples`, `workspace`.

---

## 8. Verdict

**L'architecture est réalisable, avec des ajustements. Il n'est pas nécessaire de changer de fournisseur ni de cible d'exécution pour les phases 2 à 7.**

Tout ce dont le MVP a besoin a été testé et fonctionne dans la Free Edition : Unity Catalog, Delta, jobs serverless planifiés toutes les 15 min, Lakeflow, Asset Bundles, Apps, MLflow, modèles de langage, secrets, et accès sortant vers Twelve Data. Côté fournisseur, Twelve Data Basic sert les 6 instruments, **XAU/USD compris, en quasi temps réel (environ 1 min de retard)**, en 5 min, 15 min et 1 h, avec un historique 15 min depuis janvier 2020.

Ajustements obligatoires :
1. Créer le catalogue en SQL.
2. Toujours envoyer `timezone=UTC`.
3. Marquer la bougie en cours comme incomplète.
4. Mettre en place un calendrier de sessions et le drapeau `OFF_SESSION` (bougies du week-end).
5. Construire le 1 h par agrégation du 15 min.
6. Planifier les jobs environ 1 min après la clôture du quart d'heure.
7. Étaler le backfill 5 min.

**Réserve contractuelle :** l'affichage de prix bruts dans l'app (phase 8) et la couverture de XAU/USD ne sont pas clairement couverts par la licence Basic. Ces deux points doivent être tranchés avant la phase 8 (voir §6, questions 1 à 3). Ils ne bloquent pas les phases 2 et 3, qui ne font que du traitement interne sans affichage, sous réserve de la question 3 sur la conservation.
