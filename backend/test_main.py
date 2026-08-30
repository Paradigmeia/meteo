import os
import sqlite3
import tempfile
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEY", "test-key")

import config

config.API_KEY = "test-key"

_tmpdir = tempfile.TemporaryDirectory()
config.DATABASE_PATH = os.path.join(_tmpdir.name, "test.db")

from main import _finite_or_none, _parse_shelly_value, app
from models import (
    HUM_ACCEPT_MAX,
    HUM_ACCEPT_MIN,
    HUM_MAX,
    HUM_MIN,
    TEMP_MAX,
    TEMP_MIN,
    clamp_humidity,
)


def _parse_temp(value):
    return _parse_shelly_value(value, TEMP_MIN, TEMP_MAX, "Température")


@pytest.fixture(scope="module", autouse=True)
def client():
    with TestClient(app) as c:
        yield c


def _last_salon_row():
    conn = sqlite3.connect(config.DATABASE_PATH)
    row = conn.execute(
        """SELECT temperature, humidite FROM releves
           WHERE sonde_id = (SELECT id FROM sondes WHERE slug = 'salon')
           ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    conn.close()
    return row


def test_parse_shelly_value_none():
    assert _parse_temp(None) is None


def test_parse_shelly_value_literal_null():
    assert _parse_temp("null") is None
    assert _parse_temp("Null") is None
    assert _parse_temp("NULL") is None
    assert _parse_temp("") is None
    assert _parse_temp("  ") is None


def test_parse_shelly_value_float():
    assert _parse_temp("26.1") == 26.1


def test_parse_shelly_value_invalid():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _parse_temp("abc")
    assert exc.value.status_code == 422


# --- Valeurs non finies et hors bornes (issue #36) ---


@pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-inf", "Infinity"])
def test_parse_shelly_value_non_finite_rejected(value):
    """float() accepte ces chaînes ; sans garde, elles entraient en base."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _parse_temp(value)
    assert exc.value.status_code == 422
    assert "non finie" in exc.value.detail


@pytest.mark.parametrize("value", ["-100.1", "100.1", "1e30"])
def test_parse_shelly_value_out_of_range_rejected(value):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _parse_temp(value)
    assert exc.value.status_code == 422
    assert "hors bornes" in exc.value.detail


def test_parse_shelly_value_bounds_are_inclusive():
    assert _parse_temp(str(TEMP_MIN)) == TEMP_MIN
    assert _parse_temp(str(TEMP_MAX)) == TEMP_MAX


def _parse_hum(value):
    return _parse_shelly_value(value, HUM_ACCEPT_MIN, HUM_ACCEPT_MAX, "Humidité")


def test_parse_shelly_value_humidity_in_range():
    assert _parse_hum("96.7") == 96.7


def test_parse_shelly_value_humidity_beyond_tolerance_rejected():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _parse_hum("120")
    assert exc.value.status_code == 422


def test_clamp_humidity():
    """Dans la marge, on écrête au lieu de rejeter : un rejet perdrait le relevé,
    le Shelly n'émettant qu'une fois."""
    assert clamp_humidity(None) is None
    assert clamp_humidity(58.2) == 58.2
    assert clamp_humidity(100.2) == 100.0   # condensation
    assert clamp_humidity(-0.3) == 0.0
    assert clamp_humidity(HUM_MAX) == HUM_MAX
    assert clamp_humidity(HUM_MIN) == HUM_MIN


def test_releve_humidity_slightly_over_100_is_clamped_not_lost(client):
    resp = client.get(
        "/api/releve/salon",
        params={"hum": "100.2", "key": "test-key"},
    )
    assert resp.status_code == 200
    _, hum = _last_salon_row()
    assert hum == 100.0, "le relevé doit être conservé, écrêté"


def test_post_releve_humidity_clamped(client):
    resp = client.post(
        "/api/releve/salon",
        json={"temp": 21.0, "hum": 103.0},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 200
    _, hum = _last_salon_row()
    assert hum == 100.0


def test_releve_non_finite_rejected_by_endpoint(client):
    resp = client.get(
        "/api/releve/salon",
        params={"temp": "nan", "key": "test-key"},
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "body",
    [b'{"temp": NaN}', b'{"temp": Infinity}', b'{"temp": 1e400}', b'{"temp": -1e400}'],
)
def test_post_releve_non_finite_rejected(client, body):
    """Corps JSON bruts : `json=` ne peut pas encoder NaN, un vrai client si.

    `1e400` est du JSON parfaitement valide qui déborde en inf — c'est le
    vecteur le plus plausible. Sans le gestionnaire de RequestValidationError,
    ces requêtes repartaient en 500 : la validation rejetait bien la valeur,
    mais le corps du 422 la recopiait et n'était pas sérialisable.
    """
    resp = client.post(
        "/api/releve/salon",
        content=body,
        headers={"X-API-Key": "test-key", "Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    resp.json()  # le corps doit être du JSON lisible, pas une 500 opaque


def test_post_releve_out_of_range_rejected(client):
    """150 % dépasse la marge d'écrêtage : c'est une aberration, pas une
    imprécision de mesure."""
    resp = client.post(
        "/api/releve/salon",
        json={"temp": 20.0, "hum": 150.0},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 422


def test_post_releve_temperature_out_of_range_rejected(client):
    resp = client.post(
        "/api/releve/salon",
        json={"temp": 150.0},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 422


def test_finite_or_none():
    assert _finite_or_none(None) is None
    assert _finite_or_none(float("nan")) is None
    assert _finite_or_none(float("inf")) is None
    assert _finite_or_none(float("-inf")) is None
    assert _finite_or_none(21.5) == 21.5
    assert _finite_or_none(0.0) == 0.0


def test_releve_hum_null_is_ignored(client):
    resp = client.get(
        "/api/releve/salon",
        params={"temp": "25.4", "hum": "null", "key": "test-key"},
    )
    assert resp.status_code == 200
    temp, hum = _last_salon_row()
    assert temp == 25.4
    assert hum is None


def test_releve_empty_hum_is_ignored(client):
    resp = client.get(
        "/api/releve/salon",
        params={"temp": "22.0", "hum": "", "key": "test-key"},
    )
    assert resp.status_code == 200
    temp, hum = _last_salon_row()
    assert temp == 22.0
    assert hum is None


def test_releve_only_null_is_rejected(client):
    resp = client.get(
        "/api/releve/salon",
        params={"temp": "null", "hum": "null", "key": "test-key"},
    )
    assert resp.status_code == 422


def test_releve_wrong_key_rejected(client):
    resp = client.get(
        "/api/releve/salon",
        params={"temp": "25.4", "key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_releve_invalid_value_rejected(client):
    resp = client.get(
        "/api/releve/salon",
        params={"temp": "abc", "key": "test-key"},
    )
    assert resp.status_code == 422


def _insert_releve(slug, temp, hum, recu_le):
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.execute(
        """INSERT INTO releves (sonde_id, temperature, humidite, recu_le)
           VALUES ((SELECT id FROM sondes WHERE slug = ?), ?, ?, ?)""",
        (slug, temp, hum, recu_le),
    )
    conn.commit()
    conn.close()


def test_releves_period_90d_and_1an_accepted(client):
    assert client.get("/api/releves/salon", params={"period": "90d"}).status_code == 200
    assert client.get("/api/releves/salon", params={"period": "1an"}).status_code == 200


def test_releves_invalid_period_rejected(client):
    resp = client.get("/api/releves/salon", params={"period": "12mois"})
    assert resp.status_code == 400


def test_releves_from_to_filters_range(client):
    _insert_releve("salon", 19.5, 50.0, "2026-01-15T10:00:00+00:00")
    _insert_releve("salon", 99.9, 99.0, "2026-03-01T10:00:00+00:00")  # hors plage
    resp = client.get(
        "/api/releves/salon",
        params={"from": "2026-01-15T00:00:00.000Z", "to": "2026-01-16T00:00:00.000Z"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["temperature"] == 19.5 for r in data)
    assert all(r["temperature"] != 99.9 for r in data)


def test_get_releve_non_ascii_key_rejected_not_crashed(client):
    """Une clé accentuée levait une TypeError dans compare_digest : 500 au lieu
    de 401, sur un chemin d'authentification et sans être authentifié (#44)."""
    resp = client.get("/api/releve/salon", params={"temp": "21.0", "key": "clé-é"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Clé API invalide"


def test_post_releve_non_ascii_key_rejected_not_crashed(client):
    """Le second point de contrôle, par en-tête, avait le même défaut.

    Un en-tête HTTP ne transporte pas d'UTF-8. Le client de test ne relaie pas
    les octets tels quels — il les relit en iso-8859-1 puis les ré-encode, si
    bien que la fonction reçoit 'clÃ©-Ã©' et non 'clé-é'. Peu importe : c'est
    non-ASCII dans les deux cas, et c'est ce qui faisait lever compare_digest.
    Sur la pile réelle (octets 0xE9 bruts émis par curl), la valeur décodée en
    latin-1 par Starlette est tout aussi non-ASCII, et donne 401.
    """
    resp = client.post(
        "/api/releve/salon",
        headers={"X-API-Key": "clé-é".encode("latin-1")},
        json={"temp": 21.0, "hum": 50.0},
    )
    assert resp.status_code == 401


def test_key_check_gives_the_same_status_whatever_the_wrong_key(client):
    """Un statut qui varie selon la forme de la clé est un canal d'information.
    Toutes les clés fausses doivent se ressembler, quel qu'en soit l'alphabet."""
    fausses = [
        "mauvaise-cle",          # ASCII, simplement fausse
        "clé-é",                 # non-ASCII
        "clé" * 500,             # non-ASCII et très longue
        "日本語",                  # hors alphabet latin
        "\x00binaire",           # octet nul
        "",                      # vide
        # Famille préfixe / troncature / longueur, celle-là même que
        # compare_digest est censé traiter correctement : sans ces trois-là, une
        # comparaison tronquée aux 4 premiers octets passait tous les tests
        "test",                  # préfixe strict de la bonne clé
        "test-ke",               # préfixe plus long
        "test-keyX",             # bonne clé plus un caractère
    ]
    statuts = {
        client.get("/api/releve/salon", params={"temp": "21.0", "key": k}).status_code
        for k in fausses
    }
    assert statuts == {401}

    # Le même jeu sur le contrôle par en-tête : avant, toute l'authentification
    # de cet endpoint ne tenait qu'à une seule assertion
    statuts_entete = {
        client.post(
            "/api/releve/salon",
            headers={"X-API-Key": k.encode("utf-8", "replace")},
            json={"temp": 21.0},
        ).status_code
        for k in fausses if k  # une valeur vide donne 403 (en-tête absent), cf. APIKeyHeader
    }
    assert statuts_entete == {401}


def test_key_check_rejects_invalid_utf8_in_the_url(client):
    """Une séquence d'octets invalide est remplacée par U+FFFD au décodage : elle
    arrive donc comme une chaîne, non-ASCII, et doit être refusée proprement."""
    resp = client.get("/api/releve/salon?temp=21.0&key=%ED%A0%80")
    assert resp.status_code == 401


def test_key_check_refuses_everything_when_no_key_is_configured(client, monkeypatch):
    """Sans ce contrôle, une installation dont l'API_KEY n'a pas été renseignée
    accepterait une clé vide — compare_digest('', '') est vrai."""
    import main as main_module
    monkeypatch.setattr(main_module, "API_KEY", "")
    for k in ["", "test-key", "n'importe quoi"]:
        resp = client.get("/api/releve/salon", params={"temp": "21.0", "key": k})
        assert resp.status_code == 401, k


def test_key_check_still_accepts_the_right_key(client):
    """Point d'ancrage explicite du cas passant. (Refuser toute clé fait déjà
    tomber treize autres tests — ce n'est pas ce test qui l'attrape.)"""
    resp = client.get("/api/releve/salon", params={"temp": "21.0", "key": "test-key"})
    assert resp.status_code == 200


def test_releves_from_without_to_rejected(client):
    resp = client.get("/api/releves/salon", params={"from": "2026-01-15T00:00:00.000Z"})
    assert resp.status_code == 400


def test_releves_to_before_from_rejected(client):
    resp = client.get(
        "/api/releves/salon",
        params={"from": "2026-01-16T00:00:00.000Z", "to": "2026-01-15T00:00:00.000Z"},
    )
    assert resp.status_code == 400


def test_releves_range_of_exactly_one_year_accepted(client):
    """La borne est inclusive : un an pile passe, c'est la plus longue période
    que l'interface sait proposer (issue #37)."""
    resp = client.get(
        "/api/releves/salon",
        # 2025-01-01 → 2026-01-01 : 365 jours pile, soit exactement MAX_RANGE_HOURS
        params={"from": "2025-01-01T00:00:00.000Z", "to": "2026-01-01T00:00:00.000Z"},
    )
    assert resp.status_code == 200


def test_releves_range_over_one_year_rejected(client):
    resp = client.get(
        "/api/releves/salon",
        params={"from": "2020-01-01T00:00:00.000Z", "to": "2026-01-01T00:00:00.000Z"},
    )
    assert resp.status_code == 400
    # Le message dit ce qui a été demandé et ce qui est admis : sans les deux,
    # l'appelant ne sait pas de combien resserrer
    detail = resp.json()["detail"]
    assert "2192 jours" in detail and "365 jours" in detail


def test_releves_one_second_over_the_cap_rejected(client):
    """La borne est épinglée par le haut aussi : sans ce test, un plafond
    relâché d'une heure passerait, et le serveur accepterait une plage que le
    garde-fou client refuse — la divergence exacte qu'on cherche à éviter."""
    resp = client.get(
        "/api/releves/salon",
        params={"from": "2025-01-01T00:00:00.000Z", "to": "2026-01-01T00:00:01.000Z"},
    )
    assert resp.status_code == 400


def test_releves_message_never_contradicts_itself_just_over_the_cap(client):
    """Juste au-dessus de la borne, un arrondi affichait « 365 jours demandés,
    maximum 365 jours »."""
    resp = client.get(
        "/api/releves/salon",
        params={"from": "2025-01-01T00:00:00.000Z", "to": "2026-01-01T01:00:00.000Z"},
    )
    assert resp.status_code == 400
    assert "366 jours demandés" in resp.json()["detail"]


def test_releves_absurd_range_rejected(client):
    """La plage qui motivait l'issue : bornes extrêmes, coût nul pour l'appelant."""
    resp = client.get(
        "/api/releves/salon",
        params={"from": "1970-01-01T00:00:00.000Z", "to": "2100-01-01T00:00:00.000Z"},
    )
    assert resp.status_code == 400


def test_releves_period_1an_still_accepted_after_cap(client):
    """Le plafond ne doit pas atteindre les périodes prédéfinies, qui ne passent
    pas par le même chemin de code."""
    resp = client.get("/api/releves/salon", params={"period": "1an"})
    assert resp.status_code == 200


def test_releves_invalid_date_format_rejected(client):
    resp = client.get(
        "/api/releves/salon",
        params={"from": "pas-une-date", "to": "2026-01-16T00:00:00.000Z"},
    )
    assert resp.status_code == 400


# --- Résilience en lecture : une ligne non finie déjà en base (issue #36) ---
#
# Les bornes ajoutées à l'écriture empêchent d'en créer de nouvelles, mais une
# ligne antérieure au garde-fou reste possible. Sans _finite_or_none, une seule
# suffisait à faire échouer la sérialisation JSON de la réponse entière.


def test_sqlite_stores_nan_as_null_but_roundtrips_inf():
    """Documente l'hypothèse portante du correctif.

    SQLite n'a pas de représentation pour NaN et le stocke en NULL : un NaN se
    traduit donc par une mesure perdue, pas par une ligne empoisonnée. En
    revanche ±inf fait l'aller-retour intact — c'est lui le vrai vecteur.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (v REAL)")
    conn.execute("INSERT INTO t VALUES (?)", (float("nan"),))
    assert conn.execute("SELECT v FROM t").fetchone()[0] is None
    conn.execute("DELETE FROM t")
    conn.execute("INSERT INTO t VALUES (?)", (float("inf"),))
    assert conn.execute("SELECT v FROM t").fetchone()[0] == float("inf")
    conn.close()


# Chaque cas est joué sur les DEUX grandeurs : les garde-fous température et
# humidité sont trois appels distincts chacun, et une première version de ces
# tests n'insérait un inf qu'en température — on pouvait retirer les trois appels
# côté humidité sans qu'un seul test ne tombe.
GRANDEURS = [
    pytest.param("temperature", id="temp"),
    pytest.param("humidite", id="hum"),
]


def _poison(slug, grandeur, recu_le, sain=None, valeur_saine=None):
    """Insère une ligne non finie sur `grandeur`, et éventuellement une ligne saine."""
    if sain is not None:
        _insert_releve(
            slug,
            valeur_saine if grandeur == "temperature" else None,
            valeur_saine if grandeur == "humidite" else None,
            sain,
        )
    _insert_releve(
        slug,
        float("inf") if grandeur == "temperature" else None,
        float("inf") if grandeur == "humidite" else None,
        recu_le,
    )


@pytest.mark.parametrize("grandeur", GRANDEURS)
def test_releves_raw_survives_infinite_row(client, grandeur):
    day = {"temperature": "2026-02-10", "humidite": "2026-02-11"}[grandeur]
    _poison("salon", grandeur, f"{day}T09:00:00+00:00", sain=f"{day}T08:00:00+00:00", valeur_saine=21.0)
    resp = client.get(
        "/api/releves/salon",
        params={"from": f"{day}T00:00:00.000Z", "to": f"{day}T23:00:00.000Z"},
    )
    # Sans le garde-fou : 500, et la plage entière disparaît du graphique.
    assert resp.status_code == 200
    data = resp.json()
    valeurs = [r[grandeur] for r in data]
    assert 21.0 in valeurs, "le relevé sain doit rester lisible"
    assert all(v != float("inf") for v in valeurs)
    assert any(v is None for v in valeurs), "la ligne fautive devient une mesure absente"


@pytest.mark.parametrize("grandeur", GRANDEURS)
def test_releves_aggregated_survives_infinite_row(client, grandeur):
    day = {"temperature": "2026-02-12", "humidite": "2026-02-20"}[grandeur]
    end = {"temperature": "2026-02-19", "humidite": "2026-02-27"}[grandeur]
    _poison("salon", grandeur, f"{day}T08:30:00+00:00", sain=f"{day}T08:00:00+00:00", valeur_saine=20.0)
    resp = client.get(
        "/api/releves/salon",
        params={"from": f"{day}T00:00:00.000Z", "to": f"{end}T00:00:00.000Z"},
    )
    assert resp.status_code == 200
    valeurs = [r[grandeur] for r in resp.json() if r[grandeur] is not None]
    assert valeurs, "le bucket doit rester exploitable"
    # inf contaminerait la moyenne du bucket entier, pas seulement sa propre ligne.
    assert all(v == v and abs(v) < 1e30 for v in valeurs)
    assert 20.0 in valeurs


@pytest.mark.parametrize("grandeur", GRANDEURS)
def test_sondes_survives_infinite_last_reading(client, grandeur):
    # chambre-parents et chambre-jade sont actives dans le seed et ne servent à
    # aucun autre test : la ligne insérée est bien leur dernier relevé.
    slug = {"temperature": "chambre-jade", "humidite": "chambre-parents"}[grandeur]
    _poison(slug, grandeur, "2026-02-14T10:00:00+00:00")
    resp = client.get("/api/sondes")
    # Sans le garde-fou : 500 sur /api/sondes, donc dashboard entièrement vide —
    # portée plus large que la seule Vue Analyse.
    assert resp.status_code == 200
    sonde = next(s for s in resp.json() if s["slug"] == slug)
    assert sonde["dernier_releve"] is not None
    assert sonde["dernier_releve"][grandeur] is None
    assert sonde["dernier_releve"]["recu_le"] is not None


def _sonde_de_test(slug):
    """Crée une sonde active dédiée, pour ne pas dépendre de l'état laissé par
    les autres tests — la base est partagée par tout le module."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO sondes (slug, nom, actif) VALUES (?, ?, 1)", (slug, slug)
    )
    conn.commit()
    conn.close()
    return slug


def _dernier_releve(client, slug):
    resp = client.get("/api/sondes")
    assert resp.status_code == 200
    sonde = next(s for s in resp.json() if s["slug"] == slug)
    return sonde["dernier_releve"]


VIEUX = "2026-01-01T10:00:00+00:00"
RECENT = "2026-06-01T10:00:00+00:00"


def _dt(valeur):
    """Compare des instants, pas leur écriture : la base stocke `+00:00` et
    Pydantic sérialise en `Z`."""
    if valeur is None:
        return None
    return datetime.fromisoformat(valeur.replace("Z", "+00:00"))


def test_sondes_recu_le_suit_l_humidite_quand_elle_est_la_plus_recente(client):
    """Le cas de l'issue #43 : la température ne remonte plus, l'humidité si.

    Sans le correctif, `recu_le` renvoyait l'horodatage de la température quelle
    que soit son ancienneté — la card affichait un horodatage figé et un badge
    « Hors ligne » indu alors que des données arrivaient.
    """
    slug = _sonde_de_test("test-43-hum-recente")
    _insert_releve(slug, 19.0, None, VIEUX)
    _insert_releve(slug, None, 55.0, RECENT)
    dr = _dernier_releve(client, slug)
    assert _dt(dr["recu_le"]) == _dt(RECENT)
    # Les deux grandeurs restent lisibles, chacune avec sa date.
    assert dr["temperature"] == 19.0 and _dt(dr["recu_le_temp"]) == _dt(VIEUX)
    assert dr["humidite"] == 55.0 and _dt(dr["recu_le_hum"]) == _dt(RECENT)


def test_sondes_recu_le_suit_la_temperature_quand_elle_est_la_plus_recente(client):
    """Le cas symétrique, que l'ancien code traitait correctement : il doit le
    rester, sans quoi le correctif aurait déplacé le défaut au lieu de le
    corriger."""
    slug = _sonde_de_test("test-43-temp-recente")
    _insert_releve(slug, None, 55.0, VIEUX)
    _insert_releve(slug, 19.0, None, RECENT)
    dr = _dernier_releve(client, slug)
    assert _dt(dr["recu_le"]) == _dt(RECENT)
    assert _dt(dr["recu_le_temp"]) == _dt(RECENT) and _dt(dr["recu_le_hum"]) == _dt(VIEUX)


def test_sondes_recu_le_avec_la_seule_humidite(client):
    """Une sonde qui n'a jamais envoyé de température : `recu_le` ne peut venir
    que de l'humidité, et `recu_le_temp` doit être absent plutôt qu'inventé."""
    slug = _sonde_de_test("test-43-hum-seule")
    _insert_releve(slug, None, 55.0, RECENT)
    dr = _dernier_releve(client, slug)
    assert _dt(dr["recu_le"]) == _dt(RECENT)
    assert dr["recu_le_temp"] is None
    assert _dt(dr["recu_le_hum"]) == _dt(RECENT)
    assert dr["temperature"] is None


def test_sondes_recu_le_avec_la_seule_temperature(client):
    slug = _sonde_de_test("test-43-temp-seule")
    _insert_releve(slug, 19.0, None, RECENT)
    dr = _dernier_releve(client, slug)
    assert _dt(dr["recu_le"]) == _dt(RECENT)
    assert _dt(dr["recu_le_temp"]) == _dt(RECENT)
    assert dr["recu_le_hum"] is None
    assert dr["humidite"] is None


def test_sondes_recu_le_compare_des_instants_pas_des_chaines(client):
    """Deux décalages horaires différents, où l'ordre des chaînes ISO contredit
    l'ordre chronologique.

    `09:00+02:00` s'écrit après `08:00+00:00` mais vaut 07:00 UTC, une heure plus
    tôt. Une comparaison lexicographique — celle du code d'origine — élirait la
    température. Ce test est le seul qui distingue les deux, la base n'ayant
    aujourd'hui que des lignes au même format.
    """
    slug = _sonde_de_test("test-43-fuseaux")
    _insert_releve(slug, 19.0, None, "2026-06-01T09:00:00+02:00")
    _insert_releve(slug, None, 55.0, "2026-06-01T08:00:00+00:00")
    dr = _dernier_releve(client, slug)
    assert _dt(dr["recu_le"]) == _dt("2026-06-01T08:00:00+00:00")


def test_sondes_recu_le_tolere_un_horodatage_sans_fuseau(client):
    """Une ligne écrite sans fuseau doit être lue comme de l'UTC.

    Il n'y en a aucune aujourd'hui, mais la colonne est du TEXT libre. Sans la
    normalisation faite par `_parse_recu_le`, comparer un `datetime` naïf à un
    `datetime` tz-aware lève une `TypeError` et `/api/sondes` répond 500 — donc
    dashboard entièrement vide, pour une seule ligne mal formée.
    """
    slug = _sonde_de_test("test-43-naif")
    _insert_releve(slug, 19.0, None, "2026-06-01T09:00:00")
    _insert_releve(slug, None, 55.0, "2026-06-01T08:00:00+00:00")
    dr = _dernier_releve(client, slug)
    assert _dt(dr["recu_le"]) == _dt("2026-06-01T09:00:00+00:00")


def test_sondes_sans_aucun_releve(client):
    """Aucune ligne : `dernier_releve` reste nul plutôt que d'être un objet vide
    — la card affiche « Aucune donnée »."""
    slug = _sonde_de_test("test-43-vide")
    assert _dernier_releve(client, slug) is None


def test_sondes_recu_le_horodatages_egaux(client):
    """Les deux grandeurs arrivent dans le même relevé, cas nominal du POST :
    aucune des deux ne traîne, et `recu_le` vaut cet horodatage."""
    slug = _sonde_de_test("test-43-egaux")
    _insert_releve(slug, 19.0, 55.0, RECENT)
    dr = _dernier_releve(client, slug)
    assert _dt(dr["recu_le"]) == _dt(dr["recu_le_temp"]) == _dt(dr["recu_le_hum"]) == _dt(RECENT)


def test_meteo_non_finite_upstream_is_neutralised(client, monkeypatch):
    """json.loads accepte les littéraux NaN/Infinity : une réponse amont
    empoisonnée serait mise en cache puis renverrait 500 pendant 30 minutes."""
    import main

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"current": {"temperature_2m": float("inf")}, "hourly": {"temperature_2m": [1.0, float("nan")]}}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            return _FakeResponse()

    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **kw: _FakeClient())
    main._meteo_cache["data"] = None
    main._meteo_cache["expires_at"] = None
    try:
        resp = client.get("/api/meteo")
        assert resp.status_code == 200
        body = resp.json()
        assert body["current"]["temperature_2m"] is None
        assert body["hourly"]["temperature_2m"] == [1.0, None]
    finally:
        main._meteo_cache["data"] = None
        main._meteo_cache["expires_at"] = None
