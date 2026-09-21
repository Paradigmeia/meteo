# AGENTS.md — `meteo`

> **Ce fichier fait autorité sur ce repo.** Il remplace tout ce qu'un `/init` a
> pu recopier depuis un ancien `CLAUDE.md`, un ancien workflow, un dossier
> `.claude/` ou une skill. Si un autre fichier du repo dit le contraire, c'est
> celui-ci qui gagne. Si quelque chose n'est pas écrit ici, ça ne fait pas
> partie de ton travail.
>
> Tout se rédige **en français** : commentaires, docstrings, identifiants,
> titres de tests, messages de commit, documentation. Un commentaire en anglais
> détonne dans ce repo.

## 1. Ton rôle ici

Tu implémentes une issue, et **tu t'arrêtes à la pull request.**

Tu ne déclenches aucun déploiement, tu ne te connectes à aucun serveur, tu ne
lances aucun agent de review, tu ne merges pas. Ces étapes appartiennent à
d'autres, et elles ont lieu après toi (§ 13).

## 2. À lire avant de toucher au code

Dans cet ordre, sans exception :

1. `SPEC.md` — spécification fonctionnelle : contrat d'API, comportement de
   l'interface, palette de couleurs.
2. `PLAN.md` — architecture et **journal de décisions numérotées**
   (« Décision 1 » à « Décision 24 »). Le code y renvoie explicitement
   (`cf. décision 6`) : va lire la décision concernée avant de modifier un
   comportement. Le § 2 contient l'arborescence de déploiement.
3. `PROJECT.md` — statut et changelog.
4. `docs/ui-mockup.html` — la référence visuelle de l'interface.

**Ce repo n'a pas de `README.md`.** Ce n'est pas un oubli à réparer en cours de
route : si tu en as besoin, dis-le dans la PR, n'en invente pas le contenu.

**Si un autre fichier attendu manque, dis-le dans la PR.**

## 3. La marche à suivre

**Étape 1 — diagnostic, sans rien modifier.** Tu identifies les fichiers
concernés, tu expliques ce que tu comptes changer et pourquoi, et tu
t'arrêtes. Tu attends la validation avant de continuer.

**Étape 2 — exécution.** Une fois le diagnostic validé, tu implémentes.

Si en cours de route tu découvres que la spécification est incomplète, tu peux
l'amender — mais tu documentes l'écart dans la PR, dans une section
« Spec amendée pendant l'implémentation ».

## 4. Découper avant de coder

Décide du découpage **à la lecture de l'issue**, pas après avoir écrit le code.

Tu découpes en plusieurs PR si **au moins un** de ces points est vrai :

- le travail touche le backend **et** le frontend ;
- il contient au moins deux sous-fonctionnalités indépendantes ;
- le diff prévisible dépasse environ 400 lignes.

Ordre par défaut : backend rétrocompatible d'abord (déployable seul, débloque
la suite), puis l'interface minimale, puis un enrichissement par PR.

Si le travail tient en une seule PR, livre-le en **commits logiques**, un par
étape. Jamais un commit unique pour un gros diff.

## 5. Ce que tu dois avoir produit avant de t'arrêter

1. Une branche nommée `fix/67-aggregation-sql` — c'est-à-dire
   `<type>/<numéro d'issue>-<titre court>`, avec `feat`, `fix` ou `chore`.
2. Des commits logiques, **signés du modèle qui a réellement écrit le code**.
   Ne signe jamais d'un modèle que tu n'es pas : une attribution fausse rend
   les post-mortems illisibles.
3. Une pull request :
   - titre de moins de 70 caractères ;
   - corps avec une section `## Summary` et une section `## Test plan` ;
   - **`Closes #<N>`** dans le corps, pour que l'issue se ferme au merge ;
   - pas d'emoji dans les commits, sauf demande explicite.
4. **Une entrée datée dans le changelog de `PROJECT.md`** (voir § 6).
5. Les autres fichiers `.md` que ton changement impose (voir § 7).
6. **Un compte rendu posté en commentaire de la PR** (voir § 8).

## 6. Le changelog est bloquant

**Toute PR destinée à `main` ajoute une entrée datée dans le changelog de
`PROJECT.md`. Sans exception.**

Si tu te dis « il n'y a rien à logger » — correction de doc, ajout de test,
refacto interne, correction de typo — tu te trompes : écris une ou deux puces
factuelles sur ce qui a changé.

**La review refuse d'approuver une PR dont le changelog n'est pas à jour.**
Ce n'est pas une formalité : c'est un cycle de review perdu, pour rien.

Format :

```
### AAAA-MM-JJ — Titre court (PR #N, issue #M)

- Ce qui a été livré
```

La mise à jour de `PROJECT.md` se commite à part :
`docs: update PROJECT.md [meteo]`.

## 7. Les autres `.md` à mettre à jour

En plus du changelog, qui est toujours obligatoire :

| Ce que tu changes | Fichier à toucher en plus |
|---|---|
| Correction de bug simple, refacto interne, correction de doc, ajout de test | — |
| Nouvelle fonctionnalité dans un lot existant | `SPEC.md` |
| Nouveau lot, ou ré-architecture | `PLAN.md` + `SPEC.md` |
| Décision technique d'architecture | `PLAN.md` — **une nouvelle décision numérotée**, à la suite des 24 existantes |
| Abandon d'un lot | `SPEC.md` (statut « Abandonné » + raison + date) |

Une décision d'architecture annulée plus tard ne se supprime pas : elle
descend dans la section « Décisions abandonnées » de `PLAN.md`, avec sa date.

La review refuse aussi d'approuver si un de ces fichiers manque à l'appel.

## 8. Le compte rendu

À poster en commentaire de la PR, **à chaque cycle** — y compris après une
correction demandée par la review. Le fait que la review se passe ailleurs ne
t'en dispense pas.

Il décrit **ce que tu as réellement exécuté**, pas ce que tu aurais pu faire,
et il dit en français : ce qui a été fait, ce qui a coincé, et ce dont tu n'es
pas sûr.

- Toute commande que tu cites a été lancée, et sa sortie est copiée du
  terminal.
- Toute affirmation sur l'état du système a été mesurée.
- Ce que tu n'as pas pu vérifier toi-même, tu le dis explicitement. C'est une
  qualité, pas un aveu.

## 9. Ce que tu ne fais jamais

- Tu ne **merges** jamais. Le merge est un geste humain.
- Tu ne **déploies** jamais, et tu ne lances aucune commande de déploiement —
  ni `scripts/install.sh`, ni `scripts/update.sh` (voir § 13).
- Tu ne te connectes à **aucun serveur** : pas de SSH, pas de `systemctl`, pas
  de migration de base de données en production.
- Tu ne lances pas l'**agent de review**. Ce n'est pas ton rôle et ça fausse
  la relecture.
- Tu ne touches pas aux **secrets** : `API_KEY`, `.env`, credentials.
- Tu ne crées ni ne supprimes de repo, tu ne supprimes pas `main`, tu ne fais
  jamais de `push --force` sur `main`.
- Tu ne modifies jamais le repo `Paradigmeia/workflow-dev`.

Si l'issue qu'on te confie demande l'une de ces choses, **tu ne la fais pas :
tu le signales.** Elle a été mal routée.

## 10. Permissions et accès aux fichiers

Un accès permanent (« autoriser toujours ») se limite au **dossier de ce
projet**. Jamais au dossier personnel de l'utilisateur : c'est là que vivent
les jetons d'authentification.

Pour tout le reste, demande au cas par cas.

## 11. Une session par issue

Tu travailles une issue par session. Tu ne cumules pas une initialisation de
projet et une implémentation dans la même session : le contexte se remplit et
la qualité se dégrade.

---

## 12. Propre à ce repo

### Le projet

Tableau de bord familial (Ascain) qui suit température et humidité depuis des
capteurs Shelly H&T Gen3, plus la météo locale Open-Meteo.

- **Backend** : FastAPI en fichier unique + aiosqlite (SQLite).
- **Frontend** : React + Vite, page unique, **sans routeur**.

### Commandes

**Backend** (`backend/`)

- Installation : `python3 -m venv venv && venv/bin/pip install -r requirements-dev.txt`
- Lancement : `venv/bin/uvicorn main:app --port 8042` — lit `backend/.env`
  (`API_KEY`, `DATABASE_PATH`, `PORT`)
- Tests : `venv/bin/pytest` (fichier unique `test_main.py`)
- **Aucun linter ni vérificateur de types configuré côté backend.**

**Frontend** (`frontend/`)

- `npm ci`, puis `npm run dev | build | test | lint`
- Le serveur de développement **n'a pas de proxy** : les requêtes sont
  relatives (`/api/...`). Pour taper sur un backend local, poser
  `VITE_API_URL=http://127.0.0.1:8042` dans `frontend/.env.local`.

### Routes et architecture

- `GET|POST /api/releve/{slug}` — webhook Shelly, authentifié. Le POST utilise
  l'en-tête `X-API-Key` et exige `temp` ; le GET porte la clé dans l'URL
  (contrainte du firmware) et reçoit température et humidité en **deux
  événements séparés**, en envoyant littéralement `"null"` ou une chaîne vide
  pour une mesure absente.
- `GET /api/sondes`, `GET /api/releves/{slug}` (`?period=` ou `?from=&to=`,
  plafonné à 365 jours), `GET /api/meteo` — **publiques par conception** ; le
  CORS n'autorise que `https://meteo.paradigme.me`.
- Frontend : `App.jsx` bascule entre les vues (Dashboard / Détail / Analyse)
  par état, sans routeur. Les hooks de données interrogent toutes les 30 s.
  Les graphiques sont du SVG écrit à la main (`chartUtils.js`,
  `HistoriqueChart.jsx`, `AnalyseChart.jsx`) — **pas de Chart.js**, malgré ce
  que dit `SPEC.md`. Les icônes sont des SVG Tabler inlinés, et la CSP nginx
  est `'self'` uniquement : **n'ajoute jamais une ressource ou une URL
  externe.**

### Invariants critiques — les pièges que personne ne redécouvrira seul

- **Dates.** `releves.recu_le` est du TEXT, comparé lexicographiquement par
  SQLite. Écris toujours de l'ISO-8601 UTC suffixé `+00:00`
  (`datetime.now(timezone.utc).isoformat()`), **jamais `Z`**, et normalise en
  UTC les bornes d'un intervalle libre avant `isoformat()` (`_parse_recu_le`).
  Les tests le vérifient.
- **Flottants non finis.** Pydantic accepte `NaN` et `±inf`. **Une seule**
  valeur non finie stockée casse la sérialisation JSON de **toute** la réponse
  en lecture. On borne à l'écriture (`models.py` : température −100..100,
  humidité bornée 0..100 avec ±5 de tolérance) et on neutralise à la lecture
  (`_finite_or_none`, `_walk_non_finite`).
- **Shelly n'émet qu'une fois et ne réessaie jamais** — une donnée perdue l'est
  définitivement. L'unique worker uvicorn ne doit pas se bloquer sur une
  lecture lourde : l'agrégation tourne volontairement en SQL (`_aggregate_sql`,
  Décision 24), avec repli Python (`_aggregate`).
- **Tests backend** (`test_main.py`) : poser `API_KEY` et `DATABASE_PATH` dans
  le module `config` **avant** d'importer `main`. La base de test est partagée
  par tout le module : donne à chaque test son propre slug de sonde
  (`_sonde_de_test`) et des fenêtres UTC disjointes. La fixture automatique
  `_refuse_le_repli_silencieux` fait échouer tout test qui glisserait
  silencieusement sur le repli Python de l'agrégation.
- **Tests frontend** : les fichiers `*.test.jsx` colocalisés doivent commencer
  par `// @vitest-environment jsdom`.

### Commits

Préfixe conventionnel + référence d'issue, résumé en français :
`fix(#67): …`, `feat(#60): …`, `test(#67): …`, `chore(#38): …`.

Garde l'habitude du repo : des tests explicatifs, à assertions multiples, qui
citent l'issue qu'ils protègent.

---

## 13. Le déploiement — qui, et comment

**Ce n'est pas ton affaire pendant une session d'implémentation.** Cette
section existe pour que personne n'improvise.

Le déploiement est exécuté par **Claude Code**, sur **feu vert explicite
d'Alexis**, donné dans la session au moment voulu. Un merge n'autorise pas un
déploiement. Jamais avant un APPROVE de la review, jamais sans retour arrière
préparé **et testé**.

Il tourne **sur le serveur uniquement**, dans `/home/debian/meteo`, via
`scripts/update.sh` — qui enchaîne `git pull`, `npm ci`, `npm test`, build,
puis `systemctl restart maison-temp`, et vérifie le service et l'API à la fin.
`scripts/install.sh` ne sert qu'à la première installation.

Particularité de ce repo : `update.sh` **se relance lui-même** après le pull,
par conception — bash lit un script par position d'octet, et continuer après un
pull qui a décalé les lignes ferait exécuter un mélange des deux versions (ça
s'est produit au déploiement du 2026-08-29).

Autre particularité : `meteo` tourne sous **systemd**, avec un
`systemctl restart`. Contrairement à un `pm2 reload`, **il y a une courte
coupure** au redémarrage.
