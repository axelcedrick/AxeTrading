# Secrets — procédure de configuration

Les secrets vivent **uniquement** dans les secret scopes Databricks (testé en phase 1, B11).
Ils ne sont jamais écrits dans le dépôt, les notebooks, les prompts, les journaux ni les commits.
Claude (ou tout autre assistant) ne voit jamais la valeur : c'est toi qui la saisis.

| Élément | Valeur |
|---|---|
| Scope | `atlas` (variable de bundle `secret_scope`) |
| Clé du fournisseur | `twelvedata_api_key` (variable `provider_secret_key`) |
| Lecture dans le code | `atlas.common.secrets.get_secret(scope, key)`, seul point d'accès |
| Masquage | toute valeur lue est remplacée par `***` dans les journaux (`atlas.common.logging`) |

Les trois environnements (dev, test, prod) partagent le même scope : il n'y a qu'une clé fournisseur et un
seul utilisateur sur la Free Edition. Pour des clés distinctes par environnement, créer `atlas-test` ou
`atlas-prod` et surcharger `secret_scope` dans la cible correspondante de `databricks.yml`.

## 1. Créer le scope (une fois)

```powershell
databricks secrets create-scope atlas -p dbc-2ca00ccd-e312
```

## 2. Enregistrer la clé Twelve Data (PowerShell)

**Ne pas utiliser la saisie interactive de `put-secret` sous Windows** : en phase 1, elle a inséré un
caractère nul invisible devant la clé (33 caractères au lieu de 32), et toutes les requêtes ont été rejetées.

```powershell
$s = Read-Host "Cle Twelve Data" -AsSecureString
$k = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
databricks secrets put-secret atlas twelvedata_api_key --string-value $k.Trim() -p dbc-2ca00ccd-e312
Remove-Variable k, s
```

La clé ne passe pas par l'historique du shell. Elle apparaît brièvement dans la ligne de commande du processus
`databricks` : ne pas lancer cette commande sur une machine partagée.

## 3. Vérifier (sans afficher la valeur)

```powershell
databricks secrets list-secrets atlas -p dbc-2ca00ccd-e312
databricks bundle run atlas_foundations_check -t dev
```

Le contrôle `secret` doit être `OK`. Une valeur vide, ou contenant un espace ou un caractère de contrôle,
est refusée explicitement (`SecretError`), jamais corrigée en silence.

## 4. Rotation

1. Générer une nouvelle clé dans le tableau de bord Twelve Data (*API Keys*).
2. La saisir avec la procédure du §2 : `put-secret` remplace la valeur existante.
3. Relancer `atlas_foundations_check`, puis révoquer l'ancienne clé chez Twelve Data.
4. En cas de fuite supposée : révoquer d'abord, puis faire la rotation, puis lancer `uv run python scripts/check_secrets.py`
   et rechercher dans l'historique git (`git log -p | findstr <début de la clé>`, en local uniquement).

## 5. Ménage après la phase 1

Le scope `atlas-audit` (créé pour l'audit) contient encore une copie de la clé. Une fois `atlas` vérifié :

```powershell
databricks secrets delete-scope atlas-audit -p dbc-2ca00ccd-e312
```

## Garde-fous automatiques

- `scripts/check_secrets.py` : recherche de jetons, clés dans des URL, affectations de secrets. Lancé par
  `tests/unit/test_no_secrets.py` et par le hook `.githooks/pre-commit`.
- `.gitignore` exclut `.env*`, `.databrickscfg*`, `.databricks/`.
