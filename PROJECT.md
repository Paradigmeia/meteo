# PROJECT.md — maison-temp

## Références

- [SPEC.md](SPEC.md) : cahier des charges fonctionnel
- [PLAN.md](PLAN.md) : architecture technique, arborescence, décisions

## État du projet

| LOT | Contenu | Statut | PR | Branch |
|---|---|---|---|---|
| LOT 1 | Backend FastAPI — réception webhooks + SQLite | ✅ Livré | #5 | lot1-backend |
| LOT 2 | Frontend React — dashboard temps réel | ✅ Livré | #6 | lot2-frontend |
| LOT 3 | Frontend React — historique + graphiques | 🗄️ Abandonné — absorbé par LOT 2 (2026-05-30) | — | — |
| LOT 4 | Déploiement OVH — Nginx + systemd + HTTPS | ✅ Livré | #7 | lot4-deploy |
| LOT 5 | Frontend React — vue Analyse desktop (multi-courbes, expert) | ✅ Livré | #20, #22, #25, #29, #32 | feat/5-vue-analyse (+ une branche par issue) |

Légende : 🔲 À faire · 🔄 En cours · ✅ Livré · ⚠️ Dette technique · 🗄️ Abandonné

### Features hors LOT

| Feature | Statut | PR | Issue |
|---|---|---|---|
| Alertes seuil (ex: gel extérieur) | 🔲 À faire (v2) | — | — |
| Auth dashboard (si accès public élargi) | 🔲 À faire (v2) | — | — |

---

## Changelog

### 2026-08-30 — Issue #59 : la fenêtre validée n'était pas la fenêtre lue

- **Cause** : `/api/releves/{slug}?from=&to=` construisait ses bornes avec
  `isoformat()`, qui conserve le décalage horaire reçu, et SQLite les comparait
  comme du texte à une colonne stockée en `+00:00`. Le décalage s'écrivant après
  les chiffres comparés — et `+`/`-` s'ordonnant tous deux avant le `.` des
  microsecondes — il ne comptait pour rien : la requête lisait la fenêtre telle
  qu'elle s'écrit. Mesuré en production, deux écritures des **mêmes instants** :
  6 points en `Z`, 2 points en `+02:00`
- **`main.py`** : `start.astimezone(timezone.utc).isoformat()`, idem pour `end`.
  Le plafond de #37, qui raisonnait déjà sur de vrais instants, valide désormais
  la fenêtre réellement lue — l'écart pouvait atteindre 26 h entre `-12:00` et
  `+14:00`, soit 366 jours lus pour 365 validés
- **Le piège du correctif était le format de sortie** : normaliser en `Z` aurait
  cassé la comparaison dans l'autre sens, `Z` s'ordonnant après le `.` des
  microsecondes. Un test dédié pose ses deux lignes sur la seconde exacte des
  bornes — seul endroit où le suffixe est atteint par la comparaison — et attrape
  les deux conséquences : borne basse exclue, borne haute incluse à tort
- **Ce que le correctif ne touche pas, dit explicitement** : le `ORDER BY recu_le
  DESC` de `/api/sondes`, que la décision 21 renvoyait à cette issue, reste
  lexicographique. Il est correct tant que toute ligne s'écrit en `+00:00` — un
  invariant que rien ne gardait, et qu'un test épingle maintenant sur les deux
  chemins d'écriture (webhook GET et POST)
- **Un test écrit puis rendu décisif** : la borne sans fuseau ne prouvait rien,
  la machine tournant en UTC — `astimezone` sur un naïf y donne le même résultat
  qu'une normalisation correcte. Il force désormais l'heure locale du processus à
  +14:00. Sans ça, il passait quoi qu'on écrive
- **Deux tests fusionnés en un test paramétré** : les décalages positif et négatif
  mouraient sur exactement les mêmes mutations. Les garder séparés laissait croire
  qu'ils couvraient des choses différentes
- **Tests** : 71 backend (6 ajoutés). **Neuf mutations, toutes attrapées** :
  correctif retiré (3 échecs) · borne basse seule normalisée (3) · borne haute
  seule (3) · normalisation en `Z` (1) · `replace(tzinfo=utc)` au lieu
  d'`astimezone` (3) · conversion de signe inversé (3) · `_parse_recu_le` cesse
  d'étiqueter les naïfs (4) · `_now_iso` en heure locale (1) · `_now_iso` en `Z` (1)
- **Vérifié sur une copie de la base de production** (8 134 relevés) : les trois
  écritures des mêmes instants rendent 6 points chacune, contre 6/2/2 avant. Et en
  non-régression, les 24 requêtes que l'interface émet réellement — six périodes
  prédéfinies et deux plages libres en `Z`, sur les trois sondes — rendent des
  réponses **octet pour octet identiques** avant et après. Aucun traceback
- PLAN.md v1.14 → v1.15 (décision 22). SPEC.md inchangée

### 2026-08-30 — Issue #43 : `/api/sondes` jetait le timestamp qu'il venait de calculer

- **Cause** : `get_sondes` calculait le plus récent des deux horodatages puis
  construisait le modèle avec `recu_le_temp or recu_le_hum`, qui renvoie toujours
  celui de la température dès qu'il existe. Une sonde dont seule l'humidité
  remonte encore — cas déjà vu ici, les deux events Shelly étant des actions
  séparées — affichait un horodatage figé et un badge « Hors ligne » indu alors
  que des données arrivaient
- **`main.py`** : `recu_le` est le maximum des deux, comparé sur les `datetime`
  et non sur les chaînes ISO. `recu_le_temp` rejoint `recu_le_hum` dans la
  réponse : `recu_le` étant un maximum, il ne dit plus de quand date chaque
  grandeur
- **`SondeCard.jsx`** : le marqueur d'âge qui n'existait que pour l'humidité vaut
  pour les deux grandeurs. Sans lui, le correctif backend aurait remplacé un
  badge indu par un silence — la card aurait paru saine avec une température
  vieille de plusieurs mois
- **Tests** : 8 backend et 16 frontend (8 cas × les deux dispositions de card).
  Suites à 65 et 54. Six mutations vérifiées de chaque côté, toutes attrapées
- **Corrigé après review** : le marqueur cassait la mise en page à 375 px — et
  les deux sondes actives étant seules dans leur section, 100 % des cards sont
  rendues en pleine largeur, la disposition la plus dégradée. Deux tests ne
  distinguaient pas une inversion température/humidité. La justification
  « comparaison sur les `datetime` » n'était couverte par aucun test. Et
  `toFixed` sur une température absente faisait disparaître le dashboard
- **Vérifié visuellement à 375 px**, avant et après : hauteurs de card mesurées,
  absence de débordement horizontal, captures des quatre états dans les deux
  dispositions

### 2026-08-30 — Issue #48 : le déploiement s'arrêtait avant son verdict

- **Cause** : `scripts/update.sh` se termine par `sudo systemctl restart
  maison-temp` puis deux contrôles de santé. Hors terminal interactif, `sudo` ne
  peut pas demander de mot de passe et, sous `set -e`, le script sort en erreur
  juste avant d'afficher son verdict — alors que le pull, les tests et le build
  se sont bien passés. Il fallait refaire les vérifications à la main
- **Règle sudo** : `/etc/sudoers.d/maison-temp` en `0440`, limitée à
  `systemctl restart maison-temp`. Posée sur le serveur, et désormais posée aussi
  par `scripts/install.sh` — sans quoi une machine reconstruite repartirait avec
  le défaut
- **`install.sh`** cherche `systemctl` dans les répertoires système, dans
  l'ordre du `secure_path` de `sudo` : le `PATH` de `debian` commence par deux
  répertoires qu'il peut écrire, un `command -v` y aurait pris un homonyme et
  posé un `NOPASSWD` sur un binaire réinscriptible. Le fichier est validé par
  `visudo -cf` avant d'être posé (une erreur de syntaxe dans `sudoers.d`
  verrouille `sudo`) et posé atomiquement, `install` écrivant sinon dans le
  fichier de destination
- **Deux justifications initiales étaient fausses, la review les a prises en
  défaut** : « une règle sans chemin serait contournable via le `PATH` » —
  `visudo` refuse une commande non qualifiée, le cas n'existe pas — et le
  contrôle final par `sudo -l`, qui ne pouvait pas échouer puisqu'il répond
  « autorisée ? » et non « autorisée sans mot de passe ». Le contrôle exécute
  désormais la commande après `sudo -k`, et il est rendu avec les autres smoke
  tests
- **Portée** : `debian` avait déjà `(ALL : ALL) ALL`. La règle n'ajoute aucun
  droit, elle retire l'exigence de mot de passe sur une commande. Vérifié en
  production : la seule règle `NOPASSWD` du projet est celle-ci, aucune ne porte
  sur nginx
- **PLAN.md** : § Configuration (la règle) et décision 20 (le raisonnement)

### 2026-08-30 — Issue #44 : une clé API non-ASCII renvoyait 500 au lieu de 401

- **Cause** : `secrets.compare_digest` refuse les chaînes non-ASCII et lève une
  `TypeError`. Les deux points de contrôle lui passaient la valeur reçue telle
  quelle. Un accent dans une clé — un doigt qui ripe dans la configuration d'un
  boîtier Shelly suffit — transformait un refus propre en erreur serveur, sur un
  chemin d'authentification et sans être authentifié
- **`main.py`** : `_key_is_valid` compare les encodages UTF-8. Temps constant
  conservé (c'est la forme naturelle de `compare_digest`, qui travaille sur des
  octets), et une clé non-ASCII est traitée pour ce qu'elle est : invalide. Les
  deux contrôles, jusqu'ici dupliqués à l'identique, sont factorisés — le défaut
  existait en deux exemplaires
- **Le chemin par en-tête est atteignable** malgré les apparences : un client
  refuse d'émettre un en-tête non-ASCII, mais un en-tête transporte des octets,
  que Starlette décode en latin-1. Le test l'exerce avec des octets bruts
- **Un garde-fou écrit puis retiré** : le `try/except UnicodeEncodeError` initial
  n'était atteignable par **aucun des deux appelants** — une séquence invalide
  dans une URL est remplacée par U+FFFD, un en-tête est décodé en latin-1.
  Vérifié sur `%ED%A0%80` et `%FF%FE` avant de le supprimer plutôt que de le
  garder pour la forme. La formulation initiale (« aucune entrée ») était trop
  large : un corps JSON peut porter un demi-codet isolé, cf. #62
- **Trouvé au passage** : rien ne testait le cas d'une `API_KEY` non renseignée,
  où `compare_digest("", "")` aurait accepté une clé vide. Le contrôle existait,
  il est maintenant tenu par un test
- **Tests** : 57 (6 ajoutés), dont un qui vérifie que **toutes** les clés fausses
  donnent le même statut, quel que soit leur alphabet — un statut qui varie selon
  la forme de la clé est un canal d'information. Le jeu de clés fausses passe sur
  les **deux** endpoints : sans ça, toute l'authentification par en-tête ne
  tenait qu'à une seule assertion
- **Corrections après review adversariale** (PR #61) : trois entrées ajoutées au
  jeu de clés fausses (`test`, `test-ke`, `test-keyX`) — sans elles, une
  comparaison tronquée aux 4 premiers octets passait les 57 tests, alors que
  c'est précisément la famille que `compare_digest` est censée traiter. Les
  chiffres de mutation étaient sous-comptés (mesurés avant l'ajout des derniers
  tests) et le commentaire du test par en-tête décrivait un mécanisme inexact :
  le client de test relit les octets en iso-8859-1 et les ré-encode, la fonction
  reçoit `clÃ©-Ã©` et non `clé-é` — non-ASCII dans les deux cas, donc le test
  reste valide, mais pas pour la raison écrite
- **Mutations, toutes tuées** (mesurées sur la suite finale) : toute clé refusée
  (14 échecs) · toute clé acceptée (6) · contrôle retiré du webhook GET (5) ·
  comparaison de chaînes (4) · contrôle retiré de `require_api_key` (2) ·
  troncature à 4 octets (1) · préfixe accepté (1) · contrôle d'`API_KEY` vide
  retiré (1). **Un mutant survit et c'est irréductible** : remplacer
  `compare_digest` par `==` ne change aucun comportement observable — la
  résistance aux attaques temporelles est une propriété du code, pas de ses
  réponses. L'ordre des arguments est dans le même cas, il est consigné en
  commentaire faute de pouvoir être testé
- PLAN.md v1.11 → v1.12 (décision 19). SPEC.md inchangée

### 2026-08-30 — Issue #37 : plafond sur la plage libre, lecture publique actée

- **Cause** : `/api/releves/{slug}?from=&to=` n'imposait aucune borne à l'écart
  entre les deux dates. `?from=1970-01-01&to=2100-01-01` faisait lire toutes les
  lignes de la sonde et les agréger en mémoire, sur une route non authentifiée et
  sans coût pour l'appelant
- **`main.py`** : `MAX_RANGE_HOURS = PERIOD_HOURS["1an"]`, 400 au-delà. Le message
  donne ce qui a été demandé **et** ce qui est admis, sans quoi l'appelant ne sait
  pas de combien resserrer. Borne inclusive : un an pile passe
- **`analyseUtils.js` / `useAnalyseReleves.js` / `AnalyseView.jsx`** : garde-fou
  client aligné sur le même plafond. Sans lui, une sélection de dates trop large
  partait quand même et l'échec remontait dans le bandeau générique de #36 —
  « certaines données n'ont pas pu être chargées », inactionnable là où le
  problème est la sélection de l'utilisateur. Un message dédié le dit, et la
  requête n'est pas envoyée
- **Duplication de la constante assumée** entre back et front : pas de schéma
  partagé dans ce projet, et l'introduire pour une constante serait
  disproportionné. Un test épingle la valeur des deux côtés
- **L'issue était imprécise sur un point** : la requête est indexée
  (`idx_releves_sonde_date`), il n'y avait donc pas de scan de table complet. Le
  coût réel est la lecture et l'agrégation des lignes de la plage — modeste
  aujourd'hui (8 090 relevés sur trois mois), croissant avec l'historique
- **Seconde moitié de l'issue** : les routes de lecture (`/api/sondes`,
  `/api/releves`, `/api/meteo`) sont actées dans SPEC §6 comme publiques **par
  conception** et non par omission, avec ce qu'elles exposent et la condition
  pour changer cela (l'auth prévue en v2)
- **Corrections après review adversariale** (PR #58), quatre défauts réels :
  - **le graphique restait dessiné avec les relevés de la plage précédente**
    quand le bandeau s'affichait, sur un axe ne correspondant à aucune des dates
    saisies. Le résultat du hook est désormais dérivé (constante figée) plutôt
    que laissé tel quel — le vider dans l'effet aurait provoqué un rendu en
    cascade, que le linter refuse
  - **le message serveur se contredisait** entre 365 j et 365 j + 12 h :
    « 365 jours demandés, maximum 365 jours ». `math.ceil` au lieu d'un arrondi
  - **le garde-fou client n'était couvert par aucun test** : le retirer du hook
    ou masquer le bandeau ne faisait échouer aucune des 29 vérifications. Mon
    tableau de mutations annonçait « garde-fou client neutralisé → 2 échecs » ;
    il mesurait en réalité la neutralisation de `isRangeTooLong`, pas du câblage
  - **la borne serveur n'était épinglée que par en dessous** : la relâcher d'un
    jour laissait 49/49 au vert
  - au passage, la zone du graphique conseillait « Cochez au moins une donnée »
    alors que la sonde est cochée — contresens corrigé par un message contextuel
- **jsdom et `@testing-library/react` introduits** : la décision 14 s'en était
  passée parce qu'elle testait de la géométrie pure. Ici le défaut était dans le
  câblage, qu'aucun test de fonction pure ne pouvait attraper
- **Tests** : 51 côté backend (6 ajoutés), 38 côté frontend (16 ajoutés).
  Mutations, toutes tuées : plafond retiré (2) · borne rendue exclusive (1) ·
  plafond relâché d'un jour (2) · arrondi au lieu de `ceil` (1) · garde-fou
  retiré du hook (2) · dérivation retirée (2) · données non vidées (1) · panne
  annoncée au lieu d'une saisie (1) · bandeau masqué (2) · message vidé de son
  mode d'emploi (1) · limite chiffrée retirée (1) · message contextuel du
  graphique retiré (1) · constante client divergente (2). **Deux mutants
  survivent et sont équivalents** : hisser le contrôle hors de la branche des
  plages libres (`8760 > 8760` est faux) et retirer `tooLong` des dépendances de
  l'effet (il dérive de dépendances déjà présentes)
- **Vérifié en navigateur** : plage de six ans saisie dans l'interface → 2 courbes
  avant, 0 après, bandeau affiché, **aucune requête envoyée** pendant les
  3 secondes suivantes (pas de boucle de rafraîchissement)
- **Non traité, signalé en review** : le filtre SQL compare des chaînes ISO avec
  leur décalage horaire, alors que le plafond raisonne sur des instants — une
  plage exprimée en `+02:00` ne lit pas la même fenêtre que la même en `Z`.
  Défaut préexistant, sans effet sur l'interface (qui n'émet que du `Z`), gardé
  hors de cette PR pour ne pas en élargir le périmètre
- SPEC.md v1.7 → v1.8 (§6). PLAN.md v1.10 → v1.11 (décision 18)

### 2026-08-30 — Issue #35 : la clé d'API sort des logs

- **Cause** : le webhook Shelly passe la clé en query string (contrainte firmware,
  décision 6), et le trade-off était assumé depuis juin. La mesure a montré qu'il
  reposait sur une sous-estimation : **8 243 lignes** dans `access.log`, un
  fichier qui n'est **jamais tourné** — `logrotate` est bien configuré en `daily`
  / `rotate 14` mais aucun timer ne l'exécute sur cette machine, et le fichier est
  continu depuis le 8 mars (88 Mo, 557 853 lignes). Six mois d'exposition, pas
  deux semaines. S'y ajoutent deux canaux non identifiés au départ : uvicorn, qui
  journalise la ligne de requête complète (~107 occurrences en 24 h dans un
  journal systemd de 3 Go sans rétention), et `error_log`, qui écrit l'URI dans
  son contexte `request:`/`upstream:` sur tout `[error]` — un 502 suffit
- **`nginx/maison-temp.conf`** : `location /api/releve/` dédiée, avec un
  `log_format` qui écrit `$uri` au lieu de `$request`. Préfixe plus long que
  `/api/` donc prioritaire ; `/api/releves/` (lecture, au pluriel) ne correspond
  pas et garde sa journalisation complète, n'ayant pas de secret à cacher
- **`maison-temp.service`** : `--no-access-log` sur uvicorn. Ces lignes faisaient
  double emploi avec celles de nginx pour tout ce qui vient de l'extérieur. Nuance
  relevée en review : `install.sh` et `update.sh` appellent `127.0.0.1:8042`
  directement, en contournant nginx — ces requêtes-là ne laissent désormais plus
  aucune trace. Elles ne portent pas de clé, le compromis reste favorable, mais il
  n'est pas gratuit
- **`error_log` du webhook relevé à `crit`** : les lignes `[error]` qui portaient
  l'URI complète disparaissent pour cette location. On garde le fait (le 502
  figure dans `access.log`, chemin masqué), on perd le détail de la cause
- **Bloc port 80** : même format de journalisation, une action configurée en
  `http://` se faisant rediriger avec sa clé dans la ligne de log
- **`location ^~`** et non `location` simple : sans le `^~`, une location regex
  ajoutée plus tard l'emporterait sur le préfixe et ferait disparaître le
  masquage sans un mot de `nginx -t`
- **`access_log off` écarté** : on perdrait la trace que le webhook a été appelé,
  utile pour diagnostiquer une sonde muette
- **Vérifié en bac à sable** sur la configuration exacte : webhook journalisé
  `GET /api/releve/salon` sans paramètres (401 sur clé bidon, donc le proxy
  marche), lecture au pluriel toujours complète, clé de test absente du log,
  uvicorn ne journalisant plus la requête (instance de test avec le drapeau), et
  **les six en-têtes de sécurité toujours présents sur la nouvelle location** —
  le piège `add_header` de la décision 16 aurait suffi à les faire disparaître
- **Ce que ça ne règle pas** : Cloudflare journalise l'URL complète de son côté,
  hors de portée d'un correctif nginx
- **Les logs déjà écrits contiennent la clé** : le masquage ne vaut que pour
  l'avenir. Procédure de rotation ajoutée dans PLAN.md, à exécuter pour clore
  vraiment le sujet — elle demande de reconfigurer les deux URL actions de chaque
  boîtier Shelly, donc une intervention manuelle
- **Déploiement** : la conf nginx et l'unité systemd ne sont pas déployées par
  `update.sh`. Après merge : `git pull`, puis copie de la conf + `nginx -t` +
  `reload`, et `daemon-reload` + `restart` pour le service
- **Corrections après review adversariale** (PR #56) : trois canaux d'écriture
  restaient ouverts — `error_log`, le bloc port 80, et une location regex future
  qui aurait silencieusement repris la main. Tous traités et vérifiés backend
  arrêté, le cas qui les déclenche. Deux erreurs de ma part dans la première
  version : le chiffre de 14 522 venait d'une commande dont la branche `sudo`
  avait échoué en silence, laissant compter un motif plus large qui incluait les
  lectures au pluriel — le vrai compte est 8 243 ; et la procédure de rotation
  pointait `/home/debian/meteo/.env` au lieu de `backend/.env`, ce qui aurait fait
  échouer toutes les écritures en 401 sans message explicite. Un `.env` orphelin
  en 644 portant une clé différente traîne d'ailleurs à ce chemin, sa suppression
  est ajoutée à la procédure
- PLAN.md v1.9 → v1.10 (décision 17, et décision 6 annotée : son « acceptable »
  est révisé). SPEC.md inchangée

### 2026-08-29 — Issue #49 : CSP et en-têtes de sécurité

- **`nginx/maison-temp.conf`** : ajout de `Content-Security-Policy`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `X-Frame-Options: DENY`, et `includeSubDomains` sur le `Strict-Transport-Security`
  existant
- **Politique `'self'` partout, sans aucune exception**, rendue possible par la
  PR #51 qui a supprimé la dernière ressource tierce
- **Le `'unsafe-inline'` que l'issue croyait nécessaire ne l'est pas.** Elle
  supposait que `style-src` bloquerait les 43 `style={{ … }}` des composants.
  React les applique par le CSSOM (`style.setProperty`), pas par
  `setAttribute('style', …)` : l'attribut apparaît dans le DOM mais n'a jamais
  été « posé », et la CSP ne contrôle que la pose. La première version de cette
  PR embarquait donc une ouverture gratuite — la seule de toute la politique
- **Piège `add_header` consigné dans le fichier** : il n'est pas cumulatif dans
  nginx, un `add_header` dans un `location` annule tous ceux hérités du `server`
- **Vérifié sans toucher la production** : configuration lancée dans une instance
  nginx de test sur port haut avec certificat auto-signé, servant le vrai `dist/`
  et proxifiant la vraie API — `nginx -t` passe, les six en-têtes sont relevés sur
  `/` comme sur `/api/`, ce qui confirme l'héritage. Puis les trois vues
  parcourues sous Chromium : **zéro violation CSP, zéro erreur console, zéro
  requête échouée**, 31 icônes rendues aux bonnes tailles (12 à 54 px, aucune de
  largeur nulle). Vérifié aussi que Cloudflare n'injecte aucun script dans la page
  (`cdn-cgi`, Rocket Loader) et ne pose pas de CSP concurrente qui s'intersecterait
- **Ce que ça vaut, honnêtement** : peu de chose aujourd'hui. Sans authentification
  et avec des températures pour seul contenu, il n'y a ni session à voler ni action
  privilégiée à déclencher. L'intérêt est d'être le filet d'une ressource tierce
  compromise, et de rendre sûre par défaut l'authentification prévue en v2
- **Déploiement manuel** : `update.sh` ne déploie pas la conf nginx, seul
  `install.sh` le fait. Après merge :
  `sudo cp nginx/maison-temp.conf /etc/nginx/sites-available/maison-temp && sudo nginx -t && sudo systemctl reload nginx`
- **Correction d'une erreur des trois entrées précédentes** : elles affirmaient
  qu'aucun navigateur n'était disponible sur la machine. C'est faux — Chromium est
  installé via Playwright (`~/.cache/ms-playwright/`). Seuls le `PATH` et les
  `node_modules` du projet avaient été regardés. Les vérifications déclarées
  impossibles pour #30, #50 et celle-ci étaient faisables depuis le début ; celles
  de cette entrée ont été faites, et l'affichage des icônes de #50 est confirmé
  au passage
- **Reste à voir en conditions réelles** : les glyphes `haze` (WMO 2) et
  `droplets` (51/53/55), la météo étant au ciel dégagé pendant les contrôles ;
  et le comportement derrière Cloudflare, dont les pages d'erreur (502, challenge)
  n'héritent d'aucun en-tête de l'origine — la politique a un trou exactement
  quand l'origine est en panne, et il n'y a rien à y faire
- PLAN.md v1.8 → v1.9 (décision 16). SPEC.md inchangée : aucun effet fonctionnel

### 2026-08-29 — Issue #50 : icônes embarquées en SVG, CDN supprimé

- **Cause** : `index.html` chargeait `@tabler/icons-webfont` depuis jsdelivr sans
  `integrity` ni `crossorigin`. Une compromission du CDN aurait injecté du CSS
  arbitraire sur tout le site, sans CSP pour rattraper (cf. #49)
- **`utils/iconPaths.js` + `components/Icon.jsx`** : les 15 glyphes utilisés sont
  embarqués en SVG, tracés repris
  du dépôt Tabler 3.19.0 (MIT). Rendu en `1em` et `currentColor`, donc les
  `style={{ fontSize, color }}` des composants et la règle `.hour-icon`
  continuent de s'appliquer sans modification. Seul ajout CSS :
  `.icon { vertical-align: -0.1em }`, valeur du descent de la police remplacée
- **SRI écarté** : `integrity` n'aurait couvert que la feuille, pas les polices
  qu'elle tire en relatif. Et la disproportion demeurait : 238 kB de CSS + 865 kB
  de woff2 — ~900 kB de transfert réel, la feuille étant servie en gzip — pour
  quinze glyphes, quand le bundle applicatif
  entier en fait 228
- **Bilan** : bundle 228,6 → 231,6 kB (+3,0 kB), contre ~900 kB qui ne transitent
  plus et une résolution DNS + poignée de main TLS vers un tiers en moins
- **Bug corrigé au passage** : `ti-cloud-sun` et `ti-cloud-drizzle` **n'existent
  pas** dans Tabler 3.19.0. « Partiellement nuageux » (WMO 2) et « Bruine »
  (51/53/55) n'affichaient donc aucune icône en production — silencieusement, un
  glyphe absent ne produisant ni erreur console ni trace serveur. Le défaut n'est
  apparu qu'en cherchant les SVG correspondants. Remplacés par `haze` et
  `droplets`, choisis pour rester distincts de `sun` (« Ciel dégagé ») et
  `cloud-rain` (« Pluie »)
- **`utils/iconNames.test.js`** : 5 tests fermant cette classe de bug — tout nom référencé
  par `WMO_ICONS`, par le repli des codes inconnus ou littéralement dans un
  composant doit exister, et aucune icône ne doit être embarquée sans usage.
  Un tracé vide ou tronqué étant aussi silencieux qu'un nom fantôme, la forme des
  tracés est vérifiée aussi. Sept mutations appliquées isolément, toutes tuées
  (tests en échec entre parenthèses) : réintroduire `cloud-sun` (2) · retirer une
  icône utilisée (1) · en embarquer une inutilisée (1) · nom fautif dans un
  composant (2) · tracé vide (1) · tracé tronqué, `M` initial perdu (1) · appel
  `<Icon>` écrit d'une façon que la regex ne voit plus (1)
- 22 tests au total. `npm run lint` passe sans avertissement, `npm run build` aussi
- **Non vérifié en navigateur** : l'alignement vertical des icônes
  (`vertical-align: -0.1em` reprend le descent de la police remplacée) et
  les deux nouveaux glyphes météo demandent un coup d'œil après déploiement
- **Corrections après review adversariale** (PR #51) : `Icon.test.js` ne testait
  pas `Icon.jsx` — un `return null` inconditionnel laissait la suite verte —, ne
  parcourait que `src/components/`, et ne vérifiait que l'existence des noms, pas
  celle des tracés : un tracé vide est aussi silencieux qu'un nom fantôme.
  Renommé `utils/iconNames.test.js`, pour que son nom ne promette plus le rendu
  qu'il ne teste pas ; parcours élargi à `src/` ; vérification de forme des
  tracés ajoutée ; borne du nombre d'usages rendue auto-entretenue (littéraux +
  calculés = total des `<Icon`), l'ancienne pouvant devenir verte et vide.
  Notice de copyright Tabler ajoutée, la licence MIT l'exigeant. `aria-hidden`
  n'est plus figé dans le composant : une prop `label` permet de nommer une icône
  qui porte seule une information, appliquée au badge hors ligne de la variante
  grille de `SondeCard` — la variante pleine largeur a le texte « Hors ligne », la
  grille ne l'avait pas. Défaut préexistant : la police remplacée n'était pas
  annonçable non plus
- Chiffre réseau corrigé de ~1,1 Mo à ~900 kB : les 238 kB de CSS sont
  la taille non compressée, jsdelivr la sert en gzip (38 kB). Le woff2 de 865 kB,
  lui, est déjà compressé — c'est la police qui pèse, la conclusion ne change pas
- PLAN.md v1.7 → v1.8 (décision 15). SPEC.md v1.6 → v1.7 : §4.6 nommait l'icône
  `ti-chart-dots-3`, classe qui n'existe plus nulle part depuis cette PR

### 2026-08-29 — Déploiement : le script de mise à jour se relance après le pull

- **Cause** : `scripts/update.sh` fait son `git pull` puis continue de s'exécuter,
  donc il se met à jour lui-même en cours de route. bash lit un script par
  position d'octet au fil de l'exécution : après un pull qui décale les lignes,
  la suite est lue dans le **nouveau** fichier à l'**ancien** offset. Constaté au
  déploiement de la PR #45 — le `npm test` ajouté par cette même PR n'a pas
  tourné, le script exécuté étant la version d'avant le pull
- **Correctif** : après le pull, le script se relance explicitement une fois
  (`exec bash "$REPO/scripts/update.sh" --relance`), le drapeau évitant la
  boucle. Les étapes suivantes viennent alors de la version tirée, en entier
- **Vérifié sur copie instrumentée** (aucun déploiement réel) : sans le
  garde-fou, la reprise à l'ancien offset tombe au milieu d'un commentaire de la
  nouvelle version et bash tente d'exécuter un mot français comme commande
  (`ligne 10: où: command not found`, code 127) — la panne silencieuse du 29 août
  aurait pu être bruyante, c'est une question de chance sur l'endroit du
  décalage. Avec le garde-fou : relance unique, étapes exécutées depuis la
  version tirée (marqueurs de version à l'appui), `--relance` seul ne reboucle
  pas, code de sortie propagé
- **Transition** : la version en production n'a pas encore le garde-fou, donc le
  prochain `update.sh` reste exposé au défaut qu'il corrige. Une fois cette PR
  mergée, faire ce déploiement-là en deux temps :
  `cd /home/debian/meteo && git pull origin main && bash scripts/update.sh --relance`

### 2026-08-29 — Issue #30 : géométrie curseur→viewBox partagée + runner de test frontend

- **`chartUtils.js`** : la conversion « position du pointeur → abscisse dans le
  repère du `viewBox` » est extraite en trois fonctions —
  `viewBoxXFromClient(clientX, clientY, ctm)` (conversion par la matrice
  écran→viewBox), `viewBoxXFromRect(clientX, rect, vbW, vbH)` (son équivalent
  arithmétique pour le `preserveAspectRatio` par défaut) et
  `viewBoxXFromPointerEvent(event)` qui compose les deux pour un évènement souris
  ou tactile. La matrice d'abord, la boîte en repli quand elle est indisponible
- **`AnalyseChart.jsx` / `HistoriqueChart.jsx`** : les deux `getSvgX` locaux
  disparaissent au profit du helper partagé. `AnalyseChart` garde son écrêtage
  du curseur dans la zone traçable, `HistoriqueChart` gagne la garde `null`
  qu'imposait déjà l'autre
- **La projection est écrite à la main** (`x' = a·x + c·y + e`) au lieu de
  passer par `DOMPoint` : `DOMPoint` n'existe pas sous Node, et la ligne utile
  du produit matriciel 2D tient sur une expression. La fonction devient pure et
  testable hors navigateur — c'était le point qui rendait l'ancien code
  intestable, pas la duplication
- **Les dimensions du `viewBox` sont lues sur l'élément** (`svg.viewBox.baseVal`)
  plutôt que passées en paramètre : en mode Séparé les mêmes gestionnaires sont
  attachés à deux panneaux de hauteurs différentes, un paramètre pourrait
  diverger de la géométrie rendue
- **Vue Détail inchangée** : `viewBox` de 360 de large sous une shell capée à
  390px → pas de letterboxing, ancien et nouveau calcul coïncident. Pinné par un
  test qui compare les deux formules sur quatre largeurs de boîte, et par son
  pendant qui montre la divergence au-delà de 360px (le bug #26 qui reviendrait)
- **`vitest` introduit** (devDependency, script `npm test`) : le frontend n'avait
  aucun runner. 17 tests dans `chartUtils.test.js`, sans DOM ni jsdom.
  `scripts/update.sh` lance `npm test` avant le build : sous `set -e`, une suite
  en échec arrête le déploiement — sans quoi le runner ne protégerait que ceux
  qui pensent à le lancer (il n'y a pas de CI sur ce dépôt)
- **Mutants tués**, dix mutations appliquées isolément à `chartUtils.js`, chacune
  vérifiée comme faisant tomber au moins un test (nombre de tests en échec entre
  parenthèses) : repli ramené à la règle de trois d'origine (9) · `Math.min` →
  `Math.max` dans l'échelle (10) · `viewBoxXFromClient` neutralisée en `null` (3)
  · terme `c·y` supprimé de la projection (1) · confusion `a`↔`d` (1) · garde des
  non-finis retirée, côté matrice (1) puis côté repli (1) · `+ viewBox.x` ignoré
  (1) · hauteur du `viewBox` figée au lieu d'être lue sur l'élément (1) · point
  tactile ignoré (1)
- `npm run lint` et `npm run build` passent ; bundle 228,4 kB → 228,6 kB (+0,2 kB,
  les commentaires ne pesant pas : c'est le repli par la boîte, seul code
  réellement ajouté)
- **Vérifié en navigateur le 2026-08-29 par Alexis, après déploiement** : la
  ligne de repérage suit le curseur sur la Vue Analyse à 1920px et 1280px, et la
  vue Détail mobile est inchangée. Les deux dernières cases de la DoD de l'issue
  #30 sont closes. La vérification n'avait pas pu être faite avant le
  déploiement, aucun navigateur n'étant installé sur la machine de développement
- PLAN.md v1.6 → v1.7 (décision 14 ; arborescence et dépendances frontend
  remises à jour au passage — l'arborescence était restée sur un état ancien :
  `HourlyStrip.jsx` qui n'existe plus, `hooks/` et la moitié des composants
  absents). SPEC.md inchangée : refactor sans effet fonctionnel
- **Corrections après review adversariale** (PR #45) : un test du chemin
  matriciel était vacant — sa fixture produisait la même valeur par la matrice et
  par le repli, donc il passait quel que soit le chemin emprunté ; c'est la même
  erreur que celle déjà corrigée une fois pendant l'écriture de la PR, et elle
  n'avait été détectée ni par la suite ni par la première passe de mutation.
  Ajout de deux tests couvrant les termes `c·y` et `a`≠`d` de la projection (les
  fixtures n'avaient que des matrices de translation) et l'origine `viewBox.x`.
  Deux commentaires rectifiés : celui qui affirmait préférer `null` à une valeur
  approchée, alors que le repli fait l'inverse, et celui qui présentait la
  lecture de `viewBox.baseVal` comme motivée par le mode Séparé sans dire qu'elle
  n'intervient que dans le repli — donc jamais en navigateur

### 2026-08-24 — Issue #36 : valeurs non finies (backend + remontée d'erreur frontend)

- **Cause** : `temp: float` acceptait `NaN`/`±inf` (défaut Pydantic) et
  `_parse_shelly_value` faisait un `float()` nu. Une valeur non finie en base
  faisait échouer la sérialisation JSON de **toute** la réponse, pas seulement de
  la ligne fautive → 500 sur `/api/releves` **et** sur `/api/sondes`, donc Vue
  Analyse *et* dashboard vides, sans message
- **`models.py`** : bornes `allow_inf_nan=False` + `ge`/`le` sur `ReleverPayload`
  (température -100..100 °C, humidité 0..100 %), constantes partagées
- **`main.py`** : `_parse_shelly_value` prend ses bornes en paramètre et rejette
  non finis et hors bornes en 422 ; `_finite_or_none` neutralise une valeur non
  finie **lue** en base sur les trois chemins de lecture (`/api/sondes`,
  `/api/releves` brut et agrégé) — une ligne antérieure au correctif devient une
  mesure absente au lieu d'une panne totale. Sur `/api/releves` c'est un point
  parmi des centaines ; sur `/api/sondes` c'est la valeur courante de la sonde
  qui disparaît du dashboard, le temps qu'un relevé sain la remplace
- **`main.py`** : gestionnaire de `RequestValidationError`. Celui de FastAPI
  recopie l'entrée rejetée dans le corps du 422 ; non finie, elle n'est pas
  sérialisable et le client recevait un 500 opaque — la validation marchait,
  c'est son compte rendu qui cassait
- **`main.py`** : `/api/meteo` assaini avant mise en cache. `json.loads` accepte
  les littéraux `NaN`/`Infinity`, et le cache est renseigné avant la
  sérialisation : une réponse amont empoisonnée aurait produit 30 minutes de 500
- **Humidité écrêtée plutôt que rejetée** dans une marge de 5 points autour de
  ses bornes : un capteur en condensation peut rapporter 100,2 %, et le Shelly
  n'émet qu'une fois — un rejet perdrait le relevé définitivement. Au-delà de la
  marge, c'est une aberration et le rejet demeure. La température reste rejetée
  dès le dépassement, ses bornes étant trop larges pour qu'il s'agisse d'une
  imprécision
- **`useAnalyseReleves.js`** : le `catch {}` qui confondait « pas de données » et
  « requête en échec » est remplacé par un marqueur par sonde (`null` = échec,
  `[]` = plage vide). Une sonde en échec n'emporte plus l'affichage des autres
- **`AnalyseView.jsx` / `App.css`** : bandeau d'avertissement quand au moins une
  requête a échoué, au lieu d'un graphique vide silencieux
- **`test_main.py`** : 45 tests (15 sur `main`, 30 ajoutés). Non finis et hors
  bornes rejetés sur les deux endpoints, corps JSON bruts compris (`NaN`,
  `Infinity`, `1e400`, `-1e400` — `1e400` étant du JSON valide qui déborde, c'est
  le vecteur le plus plausible) ; résilience en lecture sur les trois chemins et
  **sur les deux grandeurs** ; écrêtage de l'humidité ; réponse météo amont
  empoisonnée ; comportement SQLite consigné. Chaque garde-fou a été neutralisé
  isolément pour vérifier qu'au moins un test tombe : garde-fou température 4
  échecs, humidité 3, gestionnaire 422 4, assainissement météo 1, écrêtage 1
- **Note SQLite** : SQLite stocke `NaN` en `NULL`, donc un `NaN` était une mesure
  perdue, pas une ligne empoisonnée. C'est `±inf` qui fait l'aller-retour intact
  et constituait le vrai vecteur — le rapport d'origine de l'issue était juste
  sur le mécanisme mais imprécis sur ce point
- Base de production vérifiée au moment du correctif : 0 ligne non finie sur 7478
- SPEC.md v1.5 → v1.6 (§4.1, bornes) ; PLAN.md v1.5 → v1.6 (décision 13)

### 2026-08-24 — Issue #28 : suppression des indices de confort (Vue Analyse)

- **`AnalyseView.jsx`** : section sidebar « Indices de confort » retirée (Heat
  Index, point de rosée, écart ΔT) — fonctionnalité jugée inutilisée à l'usage.
  État `heatIndex`/`dewPoint`/`deltaT`, blocs `comfortLines` et `deltaTLines`,
  et les variables `interiorSlugs`/`exteriorSlugs` qui n'existaient que pour
  alimenter le second, supprimés ; imports nettoyés
- **`analyseUtils.js`** : fonctions `heatIndexC`, `dewPointC`, `computeDeltaT` et
  constantes `DELTA_T_COLOR`, `HEAT_INDEX_DASH`, `DEW_POINT_DASH` supprimées
- Les préférences déjà écrites en localStorage contenant encore
  `heatIndex`/`dewPoint`/`deltaT` sont simplement ignorées à la lecture, puis
  purgées à la première sauvegarde (l'objet est réécrit en entier). Vérifié par
  rendu avec ces clés orphelines présentes et à `true`, dans les trois modes
- Bundle : 230,5 kB → 228,0 kB
- SPEC.md v1.4 → v1.5 : §4.6, ligne des indices de confort retirée
- PLAN.md v1.4 → v1.5 : note sous la décision 10, dont la partie Heat Index /
  point de rosée ne s'applique plus (le choix de calcul frontend reste valable
  pour les moyennes glissantes)

### 2026-08-24 — LOT 5 livré

Vue Analyse desktop complète. Le LOT a été ouvert par l'issue #19 puis affiné
par quatre issues successives, chacune avec sa branche et sa PR :

| Issue | PR | Apport |
|---|---|---|
| #19 | #20 | Vue expert multi-courbes : mesures brutes par sonde, Open-Meteo, moyennes glissantes, bande min/max, indices de confort, histogramme, nuage de points, sélecteur de plage, panneau de sélection latéral, légende dynamique, préférences persistées |
| #21 | #22 | Layout pleine largeur desktop (extraction du conteneur mobile 390px) |
| #24 | #25 | Bascule « Combiné / Séparé » des axes température/humidité |
| #26 | #29 | Alignement de la ligne de repérage sur le curseur (`getScreenCTM`) |
| #27 | #32 | Filtre par type de mesure + dimensions fluides du graphique |

L'issue #31 (dette du letterboxing SVG) est close sans travail dédié : sa cause
a été supprimée par #32, cf. PLAN.md décision 12.

Le LOT est déclaré livré au sens où tout son périmètre initial est en
production et validé. Une réduction de périmètre a suivi la livraison :
**#28 — suppression des indices de confort** (Heat Index, point de rosée, ΔT),
livrés et fonctionnels mais inutilisés à l'usage, retirés par la PR #41 (cf.
l'entrée de changelog du même jour).

Restent aussi ouvertes, hors LOT et sans urgence : les six issues de l'audit
transversal #33 → #38. L'issue #30 (refactor de la géométrie curseur→viewBox) a
été traitée le 2026-08-29, cf. l'entrée de changelog du même jour.

### 2026-08-24 — Issue #27 : filtre par type de mesure + hauteur fluide (Vue Analyse)

- **`AnalyseChart.jsx`** : les constantes module `W = 900` / `H = 480`
  disparaissent au profit de props `width`/`height` que le `viewBox` reprend
  telles quelles ; `X1`, `Y0`/`Y1` et les libellés d'axes en dérivent, dans les
  quatre modes (Combiné, Séparé, Histogramme, Nuage de points). L'échelle de
  rendu du SVG vaut désormais exactement 1 : plus de bandes blanches latérales
  sur grand écran, et plus de letterboxing vertical (qui aurait annulé une partie
  de la hauteur gagnée) sur fenêtre étroite. En mode Séparé,
  les deux panneaux à hauteur fixe (`SPLIT_TOP_H`/`SPLIT_BOTTOM_H = 220`) sont
  remplacés par une liste de panneaux construite à partir de `showTemp`/`showHum` :
  `(height - 17) / 2` chacun à deux panneaux, `height` entier avec un seul.
  Les marges internes deviennent des constantes nommées
  (`SPLIT_PAD_TOP`/`SPLIT_PAD_INNER`/`SPLIT_PAD_XLABELS`) au lieu d'être écrites
  en dur dans quatre expressions. Couleurs d'axe déplacées dans `analyseUtils.js`
  (`TEMP_AXIS_COLOR`/`HUM_AXIS_COLOR`), partagées avec les puces du nouveau filtre
- **`AnalyseView.jsx`** : nouvelle section « Type de mesure » dans la barre
  latérale (cases Température / Humidité, cochées par défaut, persistées sous
  `showTemp`/`showHum`) ; `lines` et `bandEntries` sont filtrés selon ces cases
  avant d'être passés au graphique et à la légende. Nouvel `useLayoutEffect` qui
  mesure l'espace vertical disponible sous le haut de `.chart-card` et le passe
  en prop `height` (plancher 480px, recalcul sur `resize`). Le panneau de survol
  est vidé au changement de filtre pour ne pas afficher de série masquée. La
  section « Type de mesure » est placée en dernier dans la barre latérale :
  n'existant qu'en mode ligne, la voir disparaître ne doit pas décaler les cases
  situées au-dessus
- **`analyseUtils.js`** : `TEMP_AXIS_COLOR` / `HUM_AXIS_COLOR` exportés
- Aucun changement CSS nécessaire : `.chart-card` et `.analyse-main` n'imposaient
  déjà aucune hauteur, la carte suit la hauteur des `<svg>` qu'elle contient
- SPEC.md v1.3 → v1.4 : §4.6 complétée (filtre par type, hauteur fluide) et
  mention obsolète d'une hauteur de 400px corrigée
- PLAN.md v1.3 → v1.4 : décision 12 ajoutée

### 2026-08-23 — Fix #26 : ligne de repérage désalignée en mode Séparé (Vue Analyse)

- **`AnalyseChart.jsx`** : correction du calcul de position du curseur (`getSvgX`).
  Les `<svg>` du graphique ont une largeur fluide (`width: 100%`) mais une hauteur
  fixe en pixels ; dès que la carte dépasse la largeur du `viewBox` (900), le
  `preserveAspectRatio` par défaut (`xMidYMid meet`) rend le contenu à l'échelle 1
  et le centre horizontalement. La règle de trois sur `getBoundingClientRect()`
  ignorait ce letterboxing, d'où un décalage entre le curseur réel et la ligne de
  repérage. Le calcul passe désormais par `getScreenCTM()`, exact quels que soient
  le scaling et le `preserveAspectRatio`.
- Le mode Combiné était affecté par le même défaut (même géométrie, décalage
  proportionnel à la largeur de fenêtre) : le correctif couvre les deux modes.

### 2026-07-04 — LOT 5 : bouton "Combiné / Séparé" pour les axes température/humidité (issue #24)

- `AnalyseChart.jsx` : `LineChart` rend soit le graphique combiné à double axe
  existant (`splitAxes=false`, comportement inchangé), soit deux graphiques
  empilés à axe unique (`splitAxes=true`) — température en haut (axe gauche
  ambre), humidité en bas (axe gauche teal) ; axe X et curseur de survol
  partagés entre les deux panneaux
- `AnalyseView.jsx` : nouvel état `splitAxes` (persisté en localStorage),
  bouton bascule affiché au-dessus de la carte graphique, visible uniquement
  en mode ligne ; l'humidité brute passe de pointillée à trait plein quand
  `splitAxes` est actif
- `App.css` : nouvelles classes `.axis-toggle` / `.axis-toggle-btn`
- SPEC.md v1.2 → v1.3 : §4.6 complétée
- PLAN.md v1.2 → v1.3 : décision 11 ajoutée

### 2026-06-20 — Fix uniformisation des cartes sondes (dashboard mobile/desktop)

- `Dashboard.jsx` : `fullWidth` sur `SondeCard` n'est plus codé en dur pour la section "Extérieur" seule, mais dérivé du nombre de sondes de chaque section (`fullWidth = sondes.length === 1`)
- Avant : avec une seule sonde intérieure (`Salon`), la carte restait à moitié largeur dans la grille 2 colonnes (`175×129px`, contenu empilé verticalement) alors que la carte `Extérieur` (toujours `fullWidth`) occupait `358×66px` — rendu visuellement non uniforme
- Après : les deux cartes ont la même taille et le même style compact tant que chaque section ne contient qu'une seule sonde ; le rendu en grille 2 colonnes (cartes carrées) reste inchangé si une section contient plusieurs sondes (ex: réactivation future de `chambre-parents`/`chambre-jade`)

### 2026-06-20 — LOT 5 fix layout : Vue Analyse pleine largeur desktop (issue #21)

- `AnalyseView` extraite du conteneur `max-width: 390px` mobile : `#root` n'impose plus cette limite globalement, c'est désormais `.app-shell` (Dashboard/Detail) qui la porte — `AnalyseView` utilise son propre `.analyse-container` (`calc(100vw - 4rem)`, max `1800px`)
- Layout deux colonnes inchangé en pratique (`.analyse-layout` : panneau 240px + graphique `1fr`), mais peut désormais s'étendre sur toute la largeur disponible au lieu d'être écrasé à 390px
- Hauteur du graphique SVG portée à 480px (au lieu de 400px)
- Dashboard et vue détail sonde : apparence mobile centrée inchangée (vérifié à 390px et 1920px de largeur viewport)

### 2026-06-20 — LOT 5 ouvert : vue Analyse desktop (issue #19)

- Nouveau LOT 5 créé : vue expert desktop multi-courbes
- Accès via bouton icône header (desktop uniquement, ≥ 768px)
- Données : mesures brutes par sonde, Open-Meteo, moyennes glissantes,
  bande min/max, indices de confort (Heat Index, point de rosée, écart Δ),
  histogramme de distribution, scatter temp/humidité
- Sélecteur de plage : boutons rapides (12h→1an) + date pickers libres
- Panneau de sélection latéral avec checkboxes par groupe
- Légende explicative dynamique (affichée selon cases cochées)
- Préférences persistées en localStorage
- SPEC.md v1.1 → v1.2 : §4.6 ajouté
- PLAN.md v1.1 → v1.2 : arborescence + nouveaux composants + backend route

### 2026-06-20 — Masquage des sondes pas encore achetées (`chambre-parents`, `chambre-jade`)

- `chambre-parents` et `chambre-jade` n'existent pas physiquement (jamais achetées) — elles n'auraient jamais dû apparaître sur le dashboard avec "Aucune donnée" / "Hors ligne" permanent
- **`backend/main.py`** : `GET /api/sondes` filtre désormais `WHERE s.actif = 1` (champ stocké depuis le LOT 1 mais jamais exploité jusqu'ici, cf. PLAN.md décision 9)
- Base de production : `UPDATE sondes SET actif = 0 WHERE slug IN ('chambre-parents', 'chambre-jade')`
- **`SPEC.md`** §3, §4.2 et §4.4 mis à jour (rôle de `actif`, statut d'achat réel des 4 sondes)
- Seules `salon` et `exterieur` sont des sondes physiquement installées à ce jour. Réactivation future = `UPDATE sondes SET actif = 1` une fois la sonde achetée, aucun changement de code (cf. PLAN.md décision 4)
- Nécessite un déploiement (`scripts/update.sh`) car c'est un changement de code, contrairement aux activations précédentes qui étaient de simples UPDATE en base

### 2026-06-20 — Fix variable Shelly humidité : `${ev.h}` → `${ev.rh}` (récupération d'un fix orphelin)

- Variable correcte pour l'humidité sur firmware HTG3/1.7.5 : `${ev.rh}` (relative humidity) — `${ev.h}` est toujours null, confirmé en production sur la sonde `salon`
- Ce fix avait déjà été identifié et commité le 2026-06-18 sur la branche `fix/shelly-null-params` (commit `81ce138`), mais n'avait jamais été intégré à la PR #11 ni mergé sur `main` — repéré en repartant des logs de la sonde `exterieur` qui recevait `hum=null` en boucle (422) malgré une config d'action a priori correcte
- **`SPEC.md`** §4.1, **`PLAN.md`** décision 6, **`backend/main.py`** (docstrings `_parse_shelly_value` et `get_releve`) mis à jour
- Aucun changement de comportement backend : le paramètre reçu reste `hum=`, seule la variable Shelly côté boîtier change. Action à reconfigurer sur chaque boîtier physique existant si l'action "Changement d'humidité" utilise encore `${ev.h}`

### 2026-06-20 — Activation de la sonde extérieure (boîtier physique installé)

- Boîtier Shelly H&T Gen3 extérieur installé physiquement (boîtier abrité, cf. PLAN.md décision 1)
- Base de production (`data/maison.db`) : `UPDATE sondes SET actif = 1 WHERE slug = 'exterieur'` — la ligne existait depuis le LOT 1 (PLAN.md décision 4 : ajouter une sonde = donnée en base, pas de code), seul le flag d'activation manquait
- Aucun changement de code : le dashboard affiche déjà la sonde (section "Extérieur" déjà câblée dans `Dashboard.jsx` sur le préfixe de slug `ext*`), en attente du premier relevé webhook
- Config Shelly à saisir côté boîtier (2 actions "URL action" — cf. SPEC.md §4.1) :
  - Changement de température → `https://meteo.paradigme.me/api/releve/exterieur?temp=${ev.tC}&key=<API_KEY>`
  - Changement d'humidité → `https://meteo.paradigme.me/api/releve/exterieur?hum=${ev.rh}&key=<API_KEY>`
  - `<API_KEY>` : valeur stockée dans `backend/.env`

### 2026-06-20 — Issue #14 : panneau de survol fixe remplaçant le tooltip flottant

- **`HistoriqueChart.jsx`** : suppression du tooltip flottant SVG (bulle + texte) — conservation
  d'une simple ligne verticale de repérage (`#1A1714`, opacité 0.15). La recherche du point
  survolé se fait désormais indépendamment sur les relevés température et humidité (au lieu
  d'un seul relevé combiné), ce qui corrige le bug où une seule des deux valeurs s'affichait
  selon la courbe la plus proche du point de contact
- **`HistoriqueChart.jsx`** : nouvelle prop `onHover(releve|null)` — notifie le parent du point
  survolé/touché ; `null` à la sortie du curseur en desktop, valeur conservée après `touchend`
  sur mobile (pas de handler dédié)
- **`SurvolPanel.jsx`** (nouveau composant) : panneau fixe inséré entre le sélecteur de période
  et la carte graphique — heure (format adapté à la période), température (ambre) et humidité
  (teal) ; état "repos" grisé (dernier relevé de la période) quand rien n'est survolé
- **`chartUtils.js`** : nouvelle fonction `formatHoverLabel(date, period)` — `HH:mm` pour
  12h/24h, `lun. 12 juin` pour 7j, `12 juin` pour 30j
- **`Detail.jsx`** : état `hovered` câblé sur `HistoriqueChart`, remis à `null` au changement de
  période (le graphique est remonté via `key={period}`)
- **`App.css`** : styles `.hover-panel` — fond `#EDE6DB` (comme les metric cards), hauteur fixe
  pour éviter tout layout shift
- **`SPEC.md`** §4.3 amendée : description du panneau de survol fixe + mention de la période
  `12h` (omise depuis #12)

### 2026-06-18 — Issue #12 : ajout de la période 12h dans la vue détail sonde

- **`GET /api/releves/{slug}?period=12h`** : nouvelle valeur acceptée — fenêtre `NOW() - 12 heures`, données brutes (même logique que `24h`, pas d'agrégation par bucket)
- **`frontend/src/components/Detail.jsx`** : bouton `12h` ajouté en première position dans `PERIODS`; `24h` reste le défaut à l'ouverture
- **`frontend/src/utils/chartUtils.js`** : cas `'12h'` ajouté dans `getXTicks` — ticks toutes les 2h

### 2026-06-15 — Fix webhook Shelly : tolérance aux valeurs `null` littérales

- **`GET /api/releve/{slug}`** : `temp` et `hum` acceptés en `str` puis convertis via `_parse_shelly_value` — la chaîne littérale `"null"` (envoyée par le firmware HTG3 quand `${ev.tC}`/`${ev.h}` est absent du rapport déclencheur) est traitée comme valeur absente au lieu de provoquer un 422
- Cause : un rapport déclenché par un changement de température ne contient pas `ev.h`, donc l'action "Changement d'humidité" envoyait `hum=null`, rejeté par l'API → perte des relevés d'humidité depuis le 14/06
- **`backend/test_main.py`** (nouveau) : tests sur `_parse_shelly_value` et sur l'endpoint (`null` ignoré, clé invalide, valeur invalide → 422)
- **`backend/requirements-dev.txt`** (nouveau) : ajout `pytest==9.1.0` pour exécuter la suite de tests

### 2026-06-04 — Issue #9 : graphique historique enrichi (axes, tooltip, min/max, densité adaptative)

- **`HistoriqueChart.jsx`** (nouveau composant) : axes Y gradués temperature (ambre, 4 ticks) et humidité (teal, 3 ticks), grille horizontale sur les ticks température, grille verticale pointillée sur les ticks X
- **Axe X** : labels temporels contextuels — 24h toutes les 3h (`14h`), 7d par jour (`Lun`…), 30d tous les 5 jours (`12/5`…)
- **Tooltip interactif** : curseur + bulle `#1A1714` au hover/touch, heure + temp + humidité, ancrage inversé si proche du bord droit
- **Indicateurs min/max** : labels `▲`/`▼` flottants au-dessus/en-dessous des extrema température et humidité, clampés dans le viewBox
- **Densité adaptative backend** : `GET /api/releves/{slug}?period=7d` → agrégation 3h (≤56 pts), `period=30d` → agrégation 12h (≤60 pts), `period=24h` → données brutes
- **`chartUtils.js`** (nouveau) : `niceTicks`, `linearScale`, `smooth`, `getXTicks` encapsulés séparément du rendu
- `Detail.jsx` mis à jour : import `HistoriqueChart`, passage du prop `period`, height viewBox 200px

### 2026-06-01 — Hotfixes intégration Shelly H&T Gen3 (commits directs sur main, rattrapage §4.1 workflow)

- **Endpoint GET webhook** : ajout de `GET /api/releve/{slug}?temp=X&hum=Y&key=TOKEN` — le firmware Shelly HTG3/1.7.5 ne supporte que les URL actions GET (SPEC §4.1 mise à jour)
- **Events séparés** : le Shelly envoie temp et hum sur deux events distincts → `temp` et `hum` tous les deux optionnels, deux actions Shelly à configurer
- **Migration DB** : `temperature` rendue nullable (était `NOT NULL`) pour accepter les inserts hum-only
- **Fix `/api/sondes`** : le `dernier_releve` agrège maintenant le dernier temp ET la dernière hum via deux LEFT JOIN séparés
- **Fix `Detail.jsx`** : `lastTemp` et `lastHum` cherchés séparément dans les relevés (évite l'affichage `—` quand la dernière ligne est hum-only)
- **Fix Open-Meteo** : suppression du paramètre `&models=` qui préfixait les noms de champs et cassait l'affichage météo (PLAN.md décision 8)
- SPEC.md et PLAN.md mis à jour (décisions 6, 7, 8)

### 2026-05-30 — LOT 4 livré + déployé

- Déploiement OVH opérationnel (PR #7, mergée)
- `https://meteo.paradigme.me` accessible, certificat Let's Encrypt valide (expire 2026-08-28)
- Nginx : reverse proxy `/api/` → FastAPI :8042, build React statique, HSTS, redirection HTTP→HTTPS
- systemd `maison-temp.service` actif, démarrage auto au boot, hardening (`NoNewPrivileges`, `ProtectSystem`, `PrivateTmp`)
- CORS restreint à `https://meteo.paradigme.me`
- `scripts/install.sh` et `scripts/update.sh` opérationnels
- Token API généré et stocké dans `backend/.env` (chmod 600)
- Smoke tests post-déploiement : webhook, API sondes, HTTPS → tous verts

### 2026-05-30 — LOT 2 livré

- Frontend React opérationnel (PR #6, mergée)
- `MeteoCard` : conditions actuelles Open-Meteo, bandeau horaire 24h scrollable, prévision J+1
- `SondeCard` : température, humidité (null-safe), timestamp, badge Hors ligne si inactivité > 3h
- `Detail` : graphique SVG dual-axis température + humidité, sélecteur 24h / 7j / 30d
- Polling 30s sur les 3 hooks (`useSondes`, `useMeteo`, `useReleves`), StrictMode-safe
- Layout mobile-first 390px, charte crème/ambre/teal fidèle au mockup validé
- **LOT 3 clôturé** : la vue Détail avec graphique SVG dual-axis et sélecteur 24h/7j/30d couvre l'intégralité du scope LOT 3 — absorbé par ce LOT.
- Prochaine étape : LOT 3 (périmètre à revalider) puis LOT 4 — déploiement OVH

### 2026-05-29 — LOT 1 livré

- Backend FastAPI opérationnel (PR #5, mergée)
- 4 endpoints : `POST /api/releve/{slug}`, `GET /api/sondes`, `GET /api/releves/{slug}`, `GET /api/meteo`
- SQLite + 4 sondes pré-remplies, auth X-API-Key, proxy Open-Meteo avec cache 30min
- Prochaine étape : LOT 2 — dashboard React

### 2026-05-23 — Session UI template + prévisionnel horaire (spec amendée)

- Maquette interactive dashboard validée (`maison-temp-mockup.html`)
- Charte graphique actée : tons chauds crème/sable, ambre température, teal humidité (cf. SPEC.md §5)
- Navigation actée : tap card → vue détail avec historique, bouton retour
- Structure dashboard actée : météo en tête, sections Intérieur / Extérieur séparées
- État hors ligne : badge "Hors ligne" + card pleine largeur, timestamp en rouge
- Prévisionnel horaire ajouté au bloc météo : bandeau scrollable 24h (heure, icône, temp, précip)
- SPEC.md v1.0 → v1.1 : §4.5 restructuré (météo), §5 ajouté (charte graphique et UI template)
- Prochaine étape : LOT 2 — dashboard React

### 2026-05-23 — Initialisation du projet

- Définition du besoin : suivi températures + humidité, 4 sondes (3 intérieur + 1 extérieur)
- Hardware acté : Shelly H&T Gen3 (WiFi, webhook HTTP natif, ~20€/unité)
- Stratégie démarrage : 1 sonde achetée pour validation, 3 autres à suivre
- Stack actée : FastAPI + SQLite + React + Chart.js + Nginx + OVH
- Sous-domaine acté : `meteo.domaine.fr` (domaine principal à confirmer)
- Météo Ascain : Open-Meteo double modèle AROME + ECMWF, cache 30min
- Rédaction SPEC.md v1.0, PLAN.md v1.0, PROJECT.md v1.0
