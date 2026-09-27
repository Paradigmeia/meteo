# AGENTS.md — `meteo`

<!-- bloc-agents v1.4 — source : 01-Projects/Katea - chantier/bloc-a-coller-AGENTS-repo.md
     du vault Second Brain. Ne pas modifier ce fichier en place : modifier la
     source, régénérer, repousser (Katea § 6.3). -->

> **Ce fichier fait autorité sur ce repo.** Il remplace tout ce qu'un `/init` a
> pu recopier depuis un ancien `CLAUDE.md`, un ancien workflow, un dossier
> `.claude/` ou une skill. Si un autre fichier du repo dit le contraire, c'est
> celui-ci qui gagne. Si quelque chose n'est pas écrit ici, ça ne fait pas
> partie de ton travail.

> **À qui parle ce fichier.** Le « tu » employé partout ici est
> **l'implémenteur**. Deux autres sessions ouvrent ce repo, et les exceptions
> qui les concernent sont **nommées une par une** — il n'y a pas de critère à
> interpréter :
>
> - **La session de review.** Une seule interdiction du § 9 ne la vise pas :
>   celle de lancer l'agent de review, puisqu'elle *est* la review. **Tout le
>   reste du § 9 s'applique à elle intégralement** — elle ne se connecte à aucun
>   serveur, ne lance aucune commande sur un service en production, n'appelle
>   pas le site live. Relire un diff ne demande rien de tout ça.
> - **La session de déploiement.** Deux interdictions du § 9 ne la visent pas :
>   déployer, et se connecter au serveur — **uniquement dans les conditions du
>   § 13**, qui est son règlement et qu'elle lit avant d'agir.
> - **Le merge n'est l'exception de personne.** Aucune session, quel que soit
>   son rôle, ne merge à la place d'Alexis.
>
> *Ajouté en v1.2, réécrit en v1.3. Au tour #74, deux choses ont été confondues :
> le § 9 a bloqué la session de review (à tort — elle est la review), et cette
> même session a lancé `systemctl`, `ss -ltnp` et un `curl` sur la production
> (à tort aussi — ça, le § 9 le lui interdit bel et bien). La v1.2 énonçait un
> critère (« les interdictions qui décrivent son propre travail ») assez vague
> pour couvrir les deux. D'où l'énumération : une exception qui n'est pas écrite
> n'existe pas.*

## 1. Ton rôle ici

Tu implémentes une issue, et **tu t'arrêtes à la pull request.**

Tu ne déclenches aucun déploiement **(voir § 13)**, tu ne te connectes à aucun
serveur, tu ne lances aucun agent de review, tu ne merges pas. Ces étapes
appartiennent à d'autres, et elles ont lieu après toi.

## 2. À lire avant de toucher au code

Dans cet ordre, sans exception :

1. `README.md` — ce que fait le projet ;
2. `PROJECT.md` — l'état actuel et le changelog ;
3. `SPEC.md` — le cahier des charges fonctionnel ;
4. `PLAN.md` — l'architecture technique.

La section 12 de ce fichier peut **ajouter** d'autres références propres à ce
repo, signaler qu'un des quatre n'existe pas ici, **ou donner un autre ordre de
lecture quand le repo en a un**. Elle fait foi — y compris contre l'ordre
ci-dessus.

**Si un fichier attendu manque et que la section 12 ne le mentionne pas,
dis-le dans la PR. N'invente pas son contenu.**

## 3. La marche à suivre

**Étape 1 — diagnostic, sans rien modifier.** Tu identifies les fichiers
concernés, tu expliques ce que tu comptes changer et pourquoi, et tu
t'arrêtes. Tu attends la validation avant de continuer.

**Étape 2 — exécution.** Une fois le diagnostic validé, tu implémentes.

Si en cours de route tu découvres que la spec est incomplète, tu peux
l'amender — mais tu documentes l'écart dans la PR, dans une section
« Spec amendée pendant l'implémentation ».

## 4. Découper avant de coder

Décide du découpage **à la lecture de l'issue**, pas après avoir écrit le code.

Tu découpes en plusieurs PR si **au moins un** de ces points est vrai :

- le travail touche le backend **et** le frontend ;
- il contient au moins deux sous-fonctionnalités indépendantes ;
- le diff prévisible dépasse environ 400 lignes.

Ordre par défaut : backend/API rétrocompatible d'abord (déployable seul,
débloque la suite), puis l'interface minimale, puis un enrichissement par PR.

Si le travail tient en une seule PR, livre-le en **commits logiques**, un par
étape. Jamais un commit unique pour un gros diff.

## 5. Ce que tu dois avoir produit avant de t'arrêter

1. **Les types autorisés — une seule liste, pour les branches et pour les
   commits : `feat`, `fix`, `chore`, `test`, `docs`.**

   | | Forme | Exemple |
   |---|---|---|
   | Branche | `<type>/<N>-titre-court` | `test/74-icone-hors-ligne` |
   | Commit | `<type>(#<N>): résumé` | `test(#74): verrouille l'icône hors ligne` |

   `<N>` est le numéro de l'issue. Les deux colonnes tirent du **même**
   ensemble de types : un type valable en commit l'est en branche, et
   réciproquement.

   **Une seule exception à la référence d'issue** : le commit qui met à jour le
   changelog. Il accompagne la PR, il ne porte pas un travail distinct, donc il
   n'a pas de `(#N)` — sa forme exacte est donnée au § 12. C'est la seule.

   *Écrit ainsi en v1.2, complété en v1.3. Avant, les types de branche vivaient
   ici et les types de commit ailleurs dans le fichier — les deux listes ont
   divergé sans que personne le voie (`test` accepté en commit, refusé en
   branche), et la review du tour #74 a posé un bloquant là-dessus. `docs` a
   rejoint la liste en v1.3 : il était le type le plus utilisé de `meteo`
   (17 commits typés sur 31) tout en étant absent de la liste — la fusion des
   deux listes l'avait rendu visible. Une seule liste ne peut pas diverger
   d'elle-même, mais elle peut encore être incomplète.*
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

## 7. Les autres `.md` à mettre à jour

En plus du changelog, qui est toujours obligatoire :

| Ce que tu changes | Fichier à toucher en plus |
|---|---|
| Correction de bug simple, refacto interne, correction de doc, ajout de test | — |
| Nouvelle fonctionnalité dans un lot existant | `SPEC.md` |
| Nouveau lot, ou ré-architecture | `PLAN.md` + `SPEC.md` |
| Décision technique d'architecture | `PLAN.md` |
| Abandon d'un lot | `SPEC.md` (statut « Abandonné » + raison + date) |

Une décision d'architecture annulée plus tard ne se supprime pas : elle
descend dans la section « Décisions abandonnées » de `PLAN.md`, avec sa date.

La review refuse aussi d'approuver si un de ces fichiers manque à l'appel.

## 8. Le compte rendu

À poster en commentaire de la PR, **à chaque cycle** — y compris après une
correction demandée par la review. Le fait que la review se passe ailleurs ne
t'en dispense pas.

Il décrit **ce que tu as réellement exécuté**, pas ce que tu aurais pu faire.

- Toute commande que tu cites a été lancée, et sa sortie est copiée du
  terminal.
- Toute affirmation sur l'état du système a été mesurée.
- Ce que tu n'as pas pu vérifier toi-même, tu le dis explicitement. C'est une
  qualité, pas un aveu.
- **Ce qui a coincé** — une commande qui a échoué, un aller-retour, une piste
  abandonnée, une règle de ce fichier que tu as trouvée contradictoire — même si
  tu t'en es sorti seul. Un compte rendu qui ne montre que le résultat rend les
  frictions invisibles, et ce sont elles qui font évoluer le dispositif.

## 9. Ce que tu ne fais jamais

*Section adressée à l'implémenteur — voir « À qui parle ce fichier » en tête.*

- Tu ne **merges** jamais. Le merge est un geste humain.
- Tu ne **déploies** jamais, et tu ne lances aucune commande de déploiement —
  ni les scripts de déploiement de ce repo, nommés au § 12 (voir § 13).
- Tu ne te connectes à **aucun serveur** : pas de SSH, pas de `pm2`, pas de
  `systemctl`, pas de migration de base de données en production.
- Tu n'appelles pas le **site en production** : pas de `curl`, pas de requête
  vers l'URL publique, **même en lecture seule**. Ce que tu livres se vérifie en
  local ; l'état de la production relève du § 13.
  *Ajouté en v1.4. L'encadré en tête disait déjà que la session de review n'y a
  pas droit — en s'appuyant sur un § 9 qui ne l'écrivait pas. L'interdiction
  existait pour un seul lecteur et pour aucun autre.*
- Tu ne lances pas l'**agent de review**. Ce n'est pas ton rôle et ça fausse
  la relecture.
- Tu ne touches pas aux **secrets** : jetons, `.env`, credentials, clés.
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

## 12. Propre à ce repo

- **Commande de test** : backend `venv/bin/pytest` (depuis `backend/`, fichier
  unique `test_main.py`) ; frontend `npm test` (depuis `frontend/`).
- **Commande de lint** : frontend `npm run lint`. **Aucun linter ni typecheck
  backend n'est configuré** — n'en invente pas un, et ne présente pas son
  absence comme une erreur.
- **Environnement à activer avant de lancer quoi que ce soit** :
  backend `python3 -m venv venv && venv/bin/pip install -r requirements-dev.txt`,
  puis tout passer par `venv/bin/…` (jamais le Python du système) ;
  lancement local `venv/bin/uvicorn main:app --port 8042`, qui lit `backend/.env`
  (`API_KEY`, `DATABASE_PATH`, `PORT`). Frontend : `npm ci`, puis
  `npm run dev` (serveur de développement) ou `npm run build`.
- **Fichiers de référence de ce repo** (complète et corrige la liste du § 2,
  **ordre de lecture compris**) :
  - **il n'y a pas de `README.md` dans ce repo.** Ne le signale pas comme un
    fichier manquant, c'est l'état normal ici ;
  - **l'ordre de lecture de ce repo**, qui remplace celui du § 2 :
    1. `SPEC.md` — le cahier des charges fonctionnel : **contrat d'API,
       comportement de l'interface, palette de couleurs** ;
    2. `PLAN.md` — l'architecture et le journal de décisions ;
    3. `PROJECT.md` — l'état actuel et le changelog ;
    4. `docs/ui-mockup.html` — la maquette de référence de l'interface.
  - `docs/ui-mockup.html` est donc la quatrième référence propre à ce repo, celle
    que le § 2 ne connaît pas ;
  - **`PLAN.md` porte un journal de décisions numérotées** (« Décision 1 à 24 »)
    que le code cite en commentaire (`cf. décision 6`). Avant de toucher à un
    comportement, lis la décision concernée. Et quand la ligne « Décision
    technique d'architecture » du § 7 s'applique, ce n'est pas une note libre :
    tu ajoutes **une nouvelle décision numérotée, à la suite des 24 existantes**.
    Le § 2 de `PLAN.md` porte aussi l'arborescence de déploiement.
- **Règles de rédaction propres à ce repo** : **tout en français** — code,
  commentaires, docstrings, identifiants, titres de tests, messages de commit,
  documentation, **comptes rendus et commentaires de PR**. Un commentaire ou un
  message de commit en anglais détonne ici.
  Garde l'habitude du repo : des tests explicatifs, à plusieurs assertions, qui
  citent l'issue qu'ils protègent.
- **Ce que fait ce projet** : tableau de bord familial (Ascain) qui suit
  température et humidité par pièce depuis des sondes Shelly H&T Gen3, plus la
  météo locale Open-Meteo.
- **Repères d'architecture** (le détail fait foi dans `PLAN.md`) : backend
  FastAPI en un seul fichier (`backend/main.py`) + aiosqlite ; frontend React +
  Vite, page unique, **sans router** — `App.jsx` change de vue
  (Dashboard/Détail/Analyse) par état, et les hooks de données interrogent
  l'API toutes les 30 s.
- **Invariants critiques** :
  - `releves.recu_le` est du TEXT que SQLite compare **lexicographiquement**.
    Écris toujours de l'ISO-8601 UTC suffixé `+00:00`
    (`datetime.now(timezone.utc).isoformat()`), **jamais `Z`**, et normalise les
    bornes libres en UTC avant `isoformat()` (`_parse_recu_le`). Des tests le
    verrouillent.
  - **Flottants non finis** : Pydantic accepte `NaN`/`±inf`, et une seule valeur
    non finie stockée casse la sérialisation JSON de **toute** la réponse de
    lecture. On borne à l'écriture (`models.py` : température −100..100,
    humidité ramenée dans 0..100 avec ±5 de tolérance) et on neutralise à la
    lecture (`_finite_or_none`, `_walk_non_finite`).
  - **Shelly émet chaque événement une seule fois et ne réessaie jamais** : une
    donnée perdue l'est définitivement. Le worker uvicorn est unique et ne doit
    pas se bloquer sur une lecture lourde — l'agrégation se fait volontairement
    en SQL (`_aggregate_sql`, Décision 24), avec repli Python (`_aggregate`).
  - **Tests backend** (`test_main.py`) : définis `API_KEY` et `DATABASE_PATH`
    dans le module `config` **avant** d'importer `main`. La base de test est
    partagée par tout le module : donne à chaque test son propre slug de sonde
    (`_sonde_de_test`) et des fenêtres UTC disjointes. La fixture autouse
    `_refuse_le_repli_silencieux` fait échouer tout test qui glisserait sans
    bruit sur le repli Python.
  - **Tests unitaires frontend** : les fichiers `*.test.jsx` colocalisés doivent
    commencer par `// @vitest-environment jsdom`.
  - **La CSP nginx est à `'self'` uniquement** : n'ajoute **jamais** d'asset ni
    d'URL externe. Les icônes sont des SVG Tabler inline ; les graphiques sont du
    SVG écrit à la main (`chartUtils.js`, `HistoriqueChart.jsx`,
    `AnalyseChart.jsx`) — **pas de Chart.js**, malgré ce que dit `SPEC.md`.
  - **Le webhook de la sonde** `GET|POST /api/releve/{slug}` est authentifié. Le
    POST passe par l'en-tête `X-API-Key` et exige `temp` ; le GET porte la clé
    dans l'URL (contrainte du firmware) et reçoit température et humidité en
    **deux événements séparés**, en envoyant la chaîne littérale `"null"` ou une
    chaîne vide pour une mesure absente. Ne « corrige » pas cette asymétrie.
  - `GET /api/sondes`, `GET /api/releves/{slug}` (`?period=` ou `?from=&to=`,
    plafonné à 365 jours) et `GET /api/meteo` sont **publics par conception** ;
    CORS n'autorise que `https://meteo.paradigme.me`.
- **Particularités connues** :
  - le serveur de dev frontend n'a **pas de proxy** : les fetches sont relatifs
    (`/api/...`) sauf si `frontend/.env.local` définit
    `VITE_API_URL=http://127.0.0.1:8042` — pointe-le sur le backend qui tourne ;
  - le `gh` de cette machine ne gère pas les Projects (API GraphQL dépréciée) :
    `gh pr edit` échoue. Mets le corps de la PR à jour autrement et dis-le dans
    ton compte rendu ;
  - `meteo` tourne sous **systemd**, pas sous `pm2` — la mention de `pm2` au
    § 9 ne concerne pas ce repo.
- **Ce qui, dans ce repo, appartient au serveur et pas à toi** — ce sont les
  « scripts de déploiement de ce repo » que le § 9 t'interdit de lancer :
  `scripts/install.sh` (une seule fois) et `scripts/update.sh`, exécutés **sur le
  serveur, à `/home/debian/meteo`, jamais en local** ; le service systemd
  `maison-temp.service` ; la configuration `nginx/maison-temp.conf`.
- **Format du commit de changelog** : la mise à jour de `PROJECT.md` se commite
  à part : `docs: update PROJECT.md [meteo]`.

## 13. Le déploiement — qui, et comment

**Ce n'est pas ton affaire pendant une session d'implémentation.** Cette
section existe pour que personne n'improvise — et pour que la session qui
déploie trouve ses règles dans le repo au lieu de les redécouvrir.

Le déploiement est exécuté par **Claude Code**, sur **feu vert explicite
d'Alexis**, donné dans la session au moment voulu. **Un merge n'autorise pas un
déploiement.** Jamais avant un APPROVE de la review, jamais sans retour arrière
préparé **et testé**.

Il tourne **sur le serveur uniquement**, dans `/home/debian/meteo`, via
`scripts/update.sh` — qui enchaîne `git pull`, `npm ci`, `npm test`, build,
puis `systemctl restart maison-temp`, et vérifie le service et l'API à la fin.
`scripts/install.sh` ne sert qu'à la première installation.

**Particularités de déploiement de ce repo** — à lire avant d'exécuter quoi que
ce soit :

- `update.sh` **se relance lui-même** après le pull, par conception — bash lit
  un script par position d'octet, et continuer après un pull qui a décalé les
  lignes ferait exécuter un mélange des deux versions (ça s'est produit au
  déploiement du 2026-08-29).
- `meteo` tourne sous **systemd**, avec un `systemctl restart`. Contrairement à
  un `pm2 reload`, **il y a une courte coupure** au redémarrage.
