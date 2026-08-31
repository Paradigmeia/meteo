import logging
import math
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEY", "test-key")

import config

config.API_KEY = "test-key"

_tmpdir = tempfile.TemporaryDirectory()
config.DATABASE_PATH = os.path.join(_tmpdir.name, "test.db")

from main import (
    _aggregate,
    _finite_or_none,
    _parse_recu_le,
    _parse_shelly_value,
    app,
)
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


# --- Ruptures de comportement de starlette 1.x (issue #38) ---


def test_post_releve_sans_content_type_est_rejete(client):
    """starlette 1.x refuse un corps JSON dont l'en-tête `Content-Type` manque.

    Sur la pile d'avant la remontée, la même requête passait en 200. Aucun client
    actuel n'est concerné — le Shelly emprunte le GET `?key=`, `install.sh` pose
    l'en-tête, le frontend ne poste rien — mais c'est une rupture d'API
    silencieuse, et le Shelly n'émettant qu'une fois, un futur client POST sans
    en-tête perdrait ses relevés sans bruit.

    La suite y était structurellement aveugle : tous les autres tests passent par
    `json=`, qui pose le `Content-Type` lui-même.
    """
    resp = client.post(
        "/api/releve/salon",
        content=b'{"temp": 21.0}',
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 422

    # Témoin : le même corps avec l'en-tête passe toujours.
    ok = client.post(
        "/api/releve/salon", json={"temp": 21.0}, headers={"X-API-Key": "test-key"}
    )
    assert ok.status_code == 200


def test_post_releve_sans_cle_du_tout(client):
    """Clé absente : 401 depuis starlette 1.x, 403 avant.

    Chemin distinct d'une clé fausse — c'est `APIKeyHeader` qui répond, avant
    `_key_is_valid`. Le jeu de clés fausses l'exclut volontairement ; sans ce
    test, le changement serait passé inaperçu.
    """
    resp = client.post("/api/releve/salon", json={"temp": 21.0})
    assert resp.status_code == 401


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
        for k in fausses if k  # clé absente : chemin distinct, cf. test dédié
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


# --- Bornes de plage et décalage horaire (issue #59) ---
#
# SQLite compare `recu_le` comme du texte. Les lignes sont toutes écrites en
# `+00:00` ; une borne portant un autre décalage n'est pas ordonnée comme
# l'instant qu'elle désigne, et la requête lit une fenêtre décalée d'autant.
# Chaque test place au moins une ligne que la comparaison fautive incluait à
# tort ET une qu'elle excluait à tort : un seul des deux côtés se corrige par
# accident en élargissant la fenêtre.


def _temperatures(client, slug, **params):
    resp = client.get(f"/api/releves/{slug}", params=params)
    assert resp.status_code == 200, resp.text
    return [r["temperature"] for r in resp.json()]


@pytest.mark.parametrize(
    "cas,borne_basse,borne_haute,instant_hors_fenetre",
    [
        # Les deux écritures désignent 10:00 → 12:00 UTC. La comparaison fautive
        # ignorait le décalage : elle lisait la fenêtre telle qu'elle s'écrit,
        # donc 12:00 → 14:00 pour l'une et 05:00 → 07:00 pour l'autre.
        ("positif", "2026-06-01T12:00:00+02:00", "2026-06-01T14:00:00+02:00",
         "2026-06-01T13:00:00+00:00"),
        ("negatif", "2026-06-01T05:00:00-05:00", "2026-06-01T07:00:00-05:00",
         "2026-06-01T06:00:00+00:00"),
    ],
)
def test_releves_plage_avec_decalage_lit_la_meme_fenetre_qu_en_utc(
    client, cas, borne_basse, borne_haute, instant_hors_fenetre
):
    """Une plage écrite avec un décalage doit rendre exactement les mêmes points
    que la même plage écrite en `Z`.

    Mesuré en production avant le correctif : 2 points contre 6 pour les mêmes
    deux heures. Les deux décalages exercent la même propriété — aucune des
    mutations essayées ne les sépare — mais le sens de la conversion n'est
    asymétrique que si on l'écrit à la main, et c'est peu cher à tenir.
    """
    slug = _sonde_de_test(f"test-59-decalage-{cas}")
    _insert_releve(slug, 11.1, None, "2026-06-01T10:30:00+00:00")  # exclue à tort
    _insert_releve(slug, 22.2, None, instant_hors_fenetre)  # incluse à tort

    en_utc = _temperatures(
        client, slug, **{"from": "2026-06-01T10:00:00Z", "to": "2026-06-01T12:00:00Z"}
    )
    avec_decalage = _temperatures(
        client, slug, **{"from": borne_basse, "to": borne_haute}
    )
    assert en_utc == [11.1]
    assert avec_decalage == en_utc


@pytest.fixture
def fuseau_local_decale():
    """Force l'heure locale du processus à +14:00 le temps d'un test.

    La machine tourne en UTC : sans ce décalage, `astimezone` sur un datetime
    naïf y donnerait le même résultat qu'une normalisation correcte, et le test
    qui suit passerait quoi qu'on écrive.
    """
    ancien = os.environ.get("TZ")
    os.environ["TZ"] = "Pacific/Kiritimati"
    time.tzset()
    yield
    if ancien is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = ancien
    time.tzset()


def test_releves_bornes_naives_sont_lues_comme_de_l_utc(client, fuseau_local_decale):
    """Une borne sans fuseau est documentée « ISO 8601 » et acceptée telle
    quelle. `_parse_recu_le` l'étiquette UTC ; `astimezone` sur un datetime resté
    naïf supposerait, lui, l'heure locale du processus.

    Le correctif dépend donc de cet étiquetage, et ce test tient la dépendance :
    normaliser avant le passage par `_parse_recu_le`, ou cesser d'étiqueter,
    décalerait la fenêtre de 14 h et ferait tomber ce test seul.
    """
    slug = _sonde_de_test("test-59-naif")
    _insert_releve(slug, 11.1, None, "2026-06-01T10:30:00+00:00")
    _insert_releve(slug, 22.2, None, "2026-05-31T21:00:00+00:00")  # incluse à tort

    assert _temperatures(
        client, slug, **{"from": "2026-06-01T10:00:00", "to": "2026-06-01T12:00:00"}
    ) == [11.1]


def test_releves_bornes_restent_au_format_des_lignes_en_base(client):
    """Le piège du correctif : normaliser en `Z` au lieu de `+00:00` casserait
    la comparaison dans l'autre sens.

    Les deux lignes tombent sur la seconde exacte des bornes, seul endroit où le
    suffixe est atteint par la comparaison. `+00:00` s'ordonne avant le `.` des
    microsecondes, `Z` après : avec un `Z`, la ligne de la borne basse serait
    exclue et celle de la borne haute — postérieure à `to` — incluse.
    """
    slug = _sonde_de_test("test-59-format-borne")
    _insert_releve(slug, 11.1, None, "2026-06-01T10:00:00.123456+00:00")  # dedans
    _insert_releve(slug, 22.2, None, "2026-06-01T12:00:00.123456+00:00")  # dehors

    assert _temperatures(
        client, slug, **{"from": "2026-06-01T10:00:00Z", "to": "2026-06-01T12:00:00Z"}
    ) == [11.1]


def test_releves_ligne_a_la_seconde_pile_est_bien_filtree(client):
    """Une ligne dont la microseconde est nulle s'écrit sans fraction du tout —
    `isoformat()` l'omet — et porte donc un `+` là où les autres ont un `.`.

    Il n'y en a aucune dans les 8 138 lignes de production, mais rien ne
    l'interdit : c'est une propriété des données, pas du format, et le
    raisonnement sur l'ordre lexicographique doit tenir dans ce cas aussi. La
    ligne à la seconde pile de la borne basse est incluse, celle de la borne
    haute exclue — l'ordre est bien chronologique des deux côtés.
    """
    slug = _sonde_de_test("test-59-seconde-pile")
    _insert_releve(slug, 11.1, None, "2026-06-01T10:00:00+00:00")  # borne basse
    _insert_releve(slug, 33.3, None, "2026-06-01T12:00:00.000001+00:00")  # hors

    assert _temperatures(
        client, slug, **{"from": "2026-06-01T12:00:00+02:00", "to": "2026-06-01T14:00:00+02:00"}
    ) == [11.1]


@pytest.mark.parametrize(
    "borne_basse,borne_haute",
    [
        # Ramenées en UTC, ces bornes sortent de datetime.min / datetime.max.
        ("0001-01-01T00:00:00+14:00", "0001-06-01T00:00:00+14:00"),
        ("9999-12-01T00:00:00-12:00", "9999-12-31T23:59:59-12:00"),
    ],
)
def test_releves_bornes_hors_bornes_representables_rejetees(
    client, borne_basse, borne_haute
):
    """Ces deux plages passent les gardes en amont — `to` est postérieur à
    `from`, et l'écart est très en dessous du plafond — mais `astimezone` lève
    une `OverflowError` sur la normalisation. Sans ce garde, l'endpoint répond
    500 sur une lecture publique et non authentifiée, alors qu'il rendait 200 et
    une liste vide avant que la normalisation n'existe : c'est la normalisation
    elle-même qui a introduit le chemin, pas une fragilité préexistante.

    Le message doit être distinct de celui du format invalide : ces dates sont
    de l'ISO 8601 valide, l'appelant n'a rien mal écrit.
    """
    resp = client.get(
        "/api/releves/salon", params={"from": borne_basse, "to": borne_haute}
    )
    assert resp.status_code == 400
    assert "représentables" in resp.json()["detail"]


def test_releves_bornes_extremes_en_utc_restent_acceptees(client):
    """Le témoin du test précédent : les mêmes années sans décalage ne débordent
    pas — `astimezone` sur de l'UTC ne calcule rien. Sans lui, rejeter toutes les
    dates extrêmes passerait pour un correctif.
    """
    resp = client.get(
        "/api/releves/salon",
        params={"from": "0001-01-01T00:00:00Z", "to": "0001-06-01T00:00:00Z"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_les_lignes_sont_ecrites_en_utc_suffixe_00_00(client, fuseau_local_decale):
    """L'invariant dont dépendent les deux comparaisons de chaînes du projet.

    La normalisation des bornes suppose que toute ligne s'écrit `+00:00`, et le
    `ORDER BY recu_le DESC` de `/api/sondes` — que ce correctif ne touche pas —
    en dépend tout autant : c'est lui qui élit le dernier relevé par grandeur.
    Une écriture future en heure locale, ou en `Z`, casserait les deux sans
    qu'aucun autre test ne bouge. Les deux chemins d'écriture sont exercés.

    Sous heure locale décalée, sans quoi le test ne vaut que la moitié de ce
    qu'il annonce : la machine tournant en UTC, une écriture en heure locale
    *étiquetée* — `datetime.now().astimezone()` — y produit un `+00:00` correct
    et passait. Seule la variante naïve, sans fuseau du tout, était attrapée.
    """
    for appel in (
        lambda: client.get(
            "/api/releve/test-59-format-ligne", params={"temp": "21.0", "key": "test-key"}
        ),
        lambda: client.post(
            "/api/releve/test-59-format-ligne",
            json={"temp": 21.0},
            headers={"X-API-Key": "test-key"},
        ),
    ):
        _sonde_de_test("test-59-format-ligne")
        assert appel().status_code == 200

    conn = sqlite3.connect(config.DATABASE_PATH)
    ecritures = [
        r[0]
        for r in conn.execute(
            """SELECT recu_le FROM releves
               WHERE sonde_id = (SELECT id FROM sondes WHERE slug = 'test-59-format-ligne')"""
        ).fetchall()
    ]
    conn.close()
    assert len(ecritures) == 2
    for valeur in ecritures:
        assert valeur.endswith("+00:00"), valeur
        assert datetime.fromisoformat(valeur).utcoffset().total_seconds() == 0


def test_releves_le_plafond_valide_la_fenetre_reellement_lue(client):
    """La conséquence qui motive l'issue : le plafond de #37 raisonne sur des
    instants (`end - start`), la requête comparait des chaînes. Une plage
    validée comme faisant 365 jours en lisait une autre, décalée du décalage.

    365 jours pile en `-12:00` : accepté par le plafond, et la fenêtre lue doit
    être 12:00Z → 12:00Z, pas 00:00Z → 00:00Z.
    """
    slug = _sonde_de_test("test-59-plafond")
    _insert_releve(slug, 11.1, None, "2025-01-01T06:00:00+00:00")  # incluse à tort
    _insert_releve(slug, 22.2, None, "2026-01-01T06:00:00+00:00")  # exclue à tort

    assert _temperatures(
        client,
        slug,
        **{"from": "2025-01-01T00:00:00-12:00", "to": "2026-01-01T00:00:00-12:00"},
    ) == [22.2]


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




# --- Agrégation en SQL (issue #67) ------------------------------------------
#
# `_aggregate` parcourait les lignes dans le thread de la boucle d'événements,
# sur un service mono-worker : pendant ce temps la boucle ne traitait rien
# d'autre, y compris les écritures du webhook Shelly, qui n'émet qu'une fois et
# ne réessaie pas. L'agrégation est passée en SQL ; ces tests vérifient qu'elle
# rend exactement ce que rendait le Python.
#
# La base de test est partagée par le module : ces tests vivent tous sur
# `exterieur`, dont aucun autre test ne se sert, et chacun ouvre sa propre
# fenêtre — le test différentiel occupe 2027, les cas particuliers un mois de
# 2028 chacun. `_agg_fenetre_vierge` refuse de laisser une pollution passer
# pour un résultat.

_AGG_SLUG = "exterieur"


@pytest.fixture
def repli_attendu():
    """À demander par un test qui exerce **volontairement** le repli.

    Sa seule présence dans les fixtures du test renverse le garde-fou
    ci-dessous : au lieu d'exiger que le repli n'ait pas eu lieu, il exige
    qu'il ait eu lieu.
    """
    return True


@pytest.fixture(autouse=True)
def _refuse_le_repli_silencieux(request, monkeypatch):
    """Aucun test ne doit passer par le repli sans le dire.

    Le `try/except sqlite3.OperationalError` de `_aggregate_sql` est le bon
    comportement en production et le piège parfait au test : **toute** panne du
    chemin SQL retombe sur `_aggregate`, or c'est à `_aggregate` que le test
    différentiel compare l'endpoint. Il passerait alors par construction, sur
    une implémentation SQL entièrement morte.

    Ce n'est pas une hypothèse : en rendant `unixepoch` inconnu, **87 tests sur
    88 restaient verts**, et le seul rouge était celui dont la docstring dit
    « si cet écart disparaît, retirer ce test ». Le garde-fou a donc été ajouté
    après coup, et cette mutation est ce qui le justifie.

    Il espionne `main._aggregate` plutôt que le journal : la fonction n'est
    appelée, dans le code de production, que sur le chemin de repli. Les
    références des tests (`_agg_reference`) passent par le nom importé au
    chargement du module et ne sont donc pas comptées. Un garde-fou adossé au
    journal, lui, deviendrait aveugle le jour où on étranglerait ces lignes.
    """
    import main

    appels = []
    vrai = main._aggregate
    monkeypatch.setattr(
        main, "_aggregate", lambda *a, **k: (appels.append(1), vrai(*a, **k))[1]
    )
    yield
    if "repli_attendu" in request.fixturenames:
        assert appels, (
            "ce test prétend exercer le repli et ne l'a pas fait : "
            "il ne prouve donc rien"
        )
    else:
        assert not appels, (
            "l'endpoint est passé par le repli Python : le chemin SQL n'a pas "
            "été exercé, et la comparaison à `_aggregate` est vide de sens"
        )


def _agg_fenetre_vierge(debut, fin):
    """Garde-fou : la fenêtre doit n'appartenir qu'au test qui l'ouvre."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    n = conn.execute(
        """SELECT COUNT(*) FROM releves
           WHERE sonde_id = (SELECT id FROM sondes WHERE slug = ?)
             AND recu_le >= ? AND recu_le <= ?""",
        (_AGG_SLUG, debut, fin),
    ).fetchone()[0]
    conn.close()
    assert n == 0, f"fenêtre déjà peuplée ({n} lignes) : les tests se marchent dessus"


def _agg_lignes(debut, fin):
    conn = sqlite3.connect(config.DATABASE_PATH)
    rows = conn.execute(
        """SELECT temperature, humidite, recu_le FROM releves
           WHERE sonde_id = (SELECT id FROM sondes WHERE slug = ?)
             AND recu_le >= ? AND recu_le <= ?
           ORDER BY recu_le ASC""",
        (_AGG_SLUG, debut, fin),
    ).fetchall()
    conn.close()
    return rows


def _agg_reference(debut, fin, bucket_seconds):
    """Ce que l'ancienne implémentation aurait rendu, sur les mêmes lignes."""
    return [
        (r.temperature, r.humidite, r.recu_le)
        for r in _aggregate(_agg_lignes(debut, fin), bucket_seconds)
    ]


def _agg_miroir(debut, fin, bucket_seconds, somme):
    """Réimplémentation indépendante de `_aggregate`, paramétrée par la sommation.

    Un test différentiel qui réutiliserait la fonction sous revue ne vérifierait
    qu'elle-même. Ce miroir sert à produire la **même** agrégation avec une
    sommation exacte (`math.fsum`) au lieu de la sommation naïve, pour dire ce
    que vaudrait la moyenne si la précision de la somme ne décidait plus de
    l'arrondi. Sa fidélité est vérifiée par `test_agg_miroir_fidele_a_aggregate`.
    """
    seaux = {}
    for temp, hum, recu_le in _agg_lignes(debut, fin):
        cle = int(_parse_recu_le(recu_le).timestamp() // bucket_seconds) * bucket_seconds
        temp, hum = _finite_or_none(temp), _finite_or_none(hum)
        if temp is None and hum is None:
            continue
        t, h = seaux.setdefault(cle, ([], []))
        if temp is not None:
            t.append(temp)
        if hum is not None:
            h.append(hum)
    return [
        (
            round(somme(t) / len(t), 1) if t else None,
            round(somme(h) / len(h), 1) if h else None,
            datetime.fromtimestamp(cle, tz=timezone.utc),
        )
        for cle, (t, h) in sorted(seaux.items())
    ]


def _agg_endpoint(client, debut, fin):
    resp = client.get("/api/releves/" + _AGG_SLUG, params={"from": debut, "to": fin})
    assert resp.status_code == 200, resp.text
    return [(r["temperature"], r["humidite"], _dt(r["recu_le"])) for r in resp.json()]


# Six valeurs dont la moyenne exacte, 26,85, tombe pile sur un point d'arrondi :
# `sum()` de Python donne 26,849999999999998 (→ 26,8) et `math.fsum` 26,850000000000005
# (→ 26,9). SQLite 3.40.1 rend le premier, la 3.51.1 le second. Tirées de la forme
# d'une descente de température réelle, pas d'un cas de laboratoire.
_ECART_SOMMATION = [28.1, 27.6, 27.1, 26.6, 26.1, 25.6]


def test_agregation_sql_tolere_le_seul_ecart_de_sommation(client):
    """La tolérance du test différentiel doit être exercée, pas seulement écrite.

    Sur le jeu aléatoire, aucun bucket ne produit d'écart entre sommation naïve
    et sommation exacte : la branche tolérante n'y est **jamais** empruntée, et
    le test différentiel passerait donc même si cette tolérance était fausse.
    Ce test-ci fournit le cas manquant, déterministe.

    Il vaut aussi comme repère de version : sous SQLite < 3.44 l'endpoint rend
    26,8, à partir de la 3.44 il rend 26,9, et les deux sont acceptables — c'est
    exactement ce que la décision 24 de PLAN.md consigne.
    """
    # 25 jours : bucket de 12 h, donc les six valeurs (00 h à 05 h) tombent bien
    # dans le même. Sur 5 jours le bucket est de 3 h et elles se séparaient en deux.
    debut, fin = "2029-05-01T00:00:00+00:00", "2029-05-26T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    for i, v in enumerate(_ECART_SOMMATION):
        _insert_releve(_AGG_SLUG, v, None, f"2029-05-01T{i:02d}:00:00+00:00")

    naif = _agg_reference(debut, fin, 43200)
    exact = _agg_miroir(debut, fin, 43200, math.fsum)
    assert naif[0][0] == 26.8 and exact[0][0] == 26.9, (
        "le cas doit vraiment distinguer les deux sommations, sinon il ne teste rien"
    )
    assert _agg_endpoint(client, debut, fin)[0][0] in (26.8, 26.9)


def test_agg_miroir_fidele_a_aggregate(client):
    """Le miroir doit reproduire `_aggregate` à la sommation près.

    Sans ce test, `_agg_miroir` pourrait diverger de la fonction qu'il est censé
    refléter et le test différentiel comparerait deux choses différentes en
    croyant mesurer la précision de la somme.
    """
    debut, fin = "2029-01-01T00:00:00+00:00", "2029-01-26T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    _insert_releve(_AGG_SLUG, 20.0, 50.0, "2029-01-01T00:00:00+00:00")
    _insert_releve(_AGG_SLUG, float("inf"), None, "2029-01-01T03:00:00+00:00")
    _insert_releve(_AGG_SLUG, None, None, "2029-01-05T00:00:00+00:00")  # bucket muet
    # Un bucket à six valeurs dont la moyenne dépend de l'ordre de sommation :
    # sans lui, aucun bucket de cette fenêtre n'a plus d'une valeur par grandeur
    # et le paramètre `somme` n'est jamais exercé — remplacer `somme(...)` par
    # `sum(...)` dans le miroir passait inaperçu.
    for i, v in enumerate(_ECART_SOMMATION):
        _insert_releve(_AGG_SLUG, v, None, f"2029-01-09T{i:02d}:00:00+00:00")
    assert _agg_miroir(debut, fin, 43200, sum) == _agg_reference(debut, fin, 43200)

    # Et le plancher : sans horodatage antérieur à 1970, une troncature dans le
    # miroir se confondrait avec le plancher de `_aggregate`.
    avant, apres = "1968-06-01T00:00:00+00:00", "1968-06-03T00:00:00+00:00"
    _agg_fenetre_vierge(avant, apres)
    _insert_releve(_AGG_SLUG, 5.0, None, "1968-06-01T19:00:00+00:00")
    assert _agg_miroir(avant, apres, 10800, sum) == _agg_reference(avant, apres, 10800)


def test_agregation_sql_identique_au_python(client):
    """Le test central de la bascule : sur un jeu volontairement hostile, la
    requête SQL doit rendre la même agrégation que `_aggregate`.

    Le jeu mélange ce qui distingue les deux implémentations : grandeurs
    absentes, valeurs non finies (issue #36), lignes collées aux frontières de
    bucket, sous-secondes, et des trous assez larges pour laisser des buckets
    entièrement vides. Les quatre tailles de bucket sont couvertes en variant
    l'étendue de la plage.

    **Le découpage en buckets est exigé strictement.** Les valeurs, elles, sont
    acceptées si elles valent celle de la sommation naïve **ou** celle de la
    sommation exacte : `sum()` de Python accumule naïvement, SQLite fait de même
    jusqu'à la 3.43 et somme en Kahan-Babuška-Neumaier à partir de la 3.44 — un
    ULP d'écart, qui suffit à faire basculer l'arrondi au dixième. Mesuré sur la
    base de production, 17 buckets sur 575 au pas de 3 h changent d'un dixième
    entre SQLite 3.40.1 (le serveur) et 3.51.1 (Debian 13 en embarque 3.46).
    Exiger l'égalité stricte reviendrait donc à écrire un test qui rougira à la
    prochaine montée du système, pour une différence dont aucune des deux
    valeurs n'est fausse. Ce qu'on défend ici, c'est l'appartenance de chaque
    ligne à son bucket, le traitement des grandeurs absentes et non finies, et
    la politique d'arrondi — tout ce qui ne dépend pas de l'ordre de sommation.
    """
    import random

    # Aligné sur 259 200 s, la plus grande taille de bucket — donc sur les
    # quatre. Sans cet alignement, les cales « collées aux frontières »
    # ci-dessous (0, ±1, b-1, b) ne tombent sur aucune frontière réelle et la
    # strate la plus intéressante du jeu reste inexplorée.
    base = datetime.fromtimestamp(
        (int(datetime(2027, 1, 4, tzinfo=timezone.utc).timestamp()) // 259200) * 259200,
        tz=timezone.utc,
    )
    assert int(base.timestamp()) % 259200 == 0
    _agg_fenetre_vierge(base.isoformat(), (base + timedelta(days=210)).isoformat())

    random.seed(67)
    instants = set()
    for _ in range(600):
        # des grappes, des trous, et des instants collés aux frontières
        decalage = random.choice(
            [random.randrange(0, 86400 * 200), random.randrange(0, 3600)]
        )
        cale = random.choice([0, -1, 1, 10799, 10800, 86399, 86400])
        instants.add(base + timedelta(seconds=decalage + cale))
    for t in sorted(instants):
        r = random.random()
        temp = None if r < 0.30 else (float("inf") if r < 0.34 else round(random.uniform(-8, 38), 1))
        r = random.random()
        hum = None if r < 0.30 else (float("-inf") if r < 0.34 else round(random.uniform(15, 98), 1))
        _insert_releve(
            _AGG_SLUG,
            temp,
            hum,
            t.replace(microsecond=random.choice([0, 1, 123456, 500000])).isoformat(),
        )

    debut = base.isoformat()
    for jours, bucket in [(5, 10800), (25, 43200), (85, 86400), (200, 259200)]:
        fin = (base + timedelta(days=jours)).isoformat()
        naif = _agg_reference(debut, fin, bucket)
        exact = _agg_miroir(debut, fin, bucket, math.fsum)
        obtenu = _agg_endpoint(client, debut, fin)
        contexte = f"plage de {jours} jours, bucket de {bucket} s"
        assert naif, f"{contexte} : le jeu doit produire des buckets"
        assert [t for _, _, t in obtenu] == [t for _, _, t in naif], (
            f"{contexte} : le découpage en buckets doit être identique"
        )
        for (ot, oh, t), (nt, nh, _), (et, eh, _) in zip(obtenu, naif, exact):
            assert ot in (nt, et), (
                f"{contexte}, bucket {t.isoformat()} : température {ot}, "
                f"attendu {nt} (somme naïve) ou {et} (somme exacte)"
            )
            assert oh in (nh, eh), (
                f"{contexte}, bucket {t.isoformat()} : humidité {oh}, "
                f"attendu {nh} (somme naïve) ou {eh} (somme exacte)"
            )


def test_agregation_sql_ecarte_les_valeurs_non_finies(client):
    """±inf est écarté de la moyenne du bucket, pas seulement de sa propre ligne.

    C'est le pendant SQL de `_finite_or_none` (issue #36) : `ABS(x) < 9e999` est
    faux pour l'infini, donc AVG et COUNT l'ignorent. Sans ce filtre la moyenne
    du bucket entier vaudrait inf, et la sérialisation de toute la réponse
    échouerait — pas seulement celle de la ligne fautive.
    """
    debut, fin = "2028-01-01T00:00:00+00:00", "2028-01-06T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    _insert_releve(_AGG_SLUG, 20.0, 50.0, "2028-01-01T00:00:00+00:00")
    _insert_releve(_AGG_SLUG, float("inf"), float("-inf"), "2028-01-01T01:00:00+00:00")
    _insert_releve(_AGG_SLUG, 22.0, 60.0, "2028-01-01T02:00:00+00:00")
    data = _agg_endpoint(client, debut, fin)
    assert data[0][:2] == (21.0, 55.0), "moyenne des seules lignes finies"
    assert data == _agg_reference(debut, fin, 43200)


def test_sqlite_relit_un_nan_en_null(client):
    """Le filtre SQL ne teste pas NaN, et c'est délibéré : SQLite ne sait pas le
    stocker et le relit en NULL, que AVG ignore déjà.

    Ce test épingle l'hypothèse plutôt que de la laisser implicite : c'est ici
    qu'on s'apercevrait qu'une version de SQLite s'est mise à conserver NaN.
    """
    _insert_releve(_AGG_SLUG, float("nan"), None, "2028-02-01T00:00:00+00:00")
    conn = sqlite3.connect(config.DATABASE_PATH)
    row = conn.execute(
        "SELECT temperature, typeof(temperature) FROM releves WHERE recu_le = ?",
        ("2028-02-01T00:00:00+00:00",),
    ).fetchone()
    conn.close()
    assert row == (None, "null")


def test_agregation_sql_n_invente_pas_de_bucket_vide(client):
    """Un bucket dont toutes les lignes ont leurs deux grandeurs absentes
    n'apparaît pas.

    Propriété discrète de `_aggregate`, dont le `defaultdict` n'était touché que
    sous ses deux `if` : un bucket entièrement muet n'y créait aucune entrée.
    C'est le rôle de `HAVING mesures > 0`.
    """
    debut, fin = "2028-03-01T00:00:00+00:00", "2028-03-26T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    _insert_releve(_AGG_SLUG, 18.0, None, "2028-03-01T00:00:00+00:00")
    _insert_releve(_AGG_SLUG, None, None, "2028-03-02T00:00:00+00:00")  # bucket muet
    _insert_releve(_AGG_SLUG, None, None, "2028-03-02T06:00:00+00:00")
    _insert_releve(_AGG_SLUG, 19.0, None, "2028-03-03T00:00:00+00:00")
    data = _agg_endpoint(client, debut, fin)
    jours = {t.date().isoformat() for _, _, t in data}
    assert {"2028-03-01", "2028-03-03"} <= jours
    assert "2028-03-02" not in jours, "un bucket sans aucune mesure ne doit pas être émis"
    assert data == _agg_reference(debut, fin, 43200)


def test_agregation_sql_garde_l_arrondi_de_python(client):
    """`ROUND()` de SQLite arrondit à l'écart de zéro, `round()` de Python au pair.

    Les deux divergent exactement sur ce que produit une moyenne : 20,2 et 20,3
    donnent 20,25, que Python rend en 20,2 et SQLite en 20,3. L'arrondi est donc
    resté en Python — ce test tomberait si on le poussait dans la requête.
    """
    debut, fin = "2028-04-01T00:00:00+00:00", "2028-04-06T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    _insert_releve(_AGG_SLUG, 20.2, None, "2028-04-01T00:00:00+00:00")
    _insert_releve(_AGG_SLUG, 20.3, None, "2028-04-01T01:00:00+00:00")
    assert _agg_endpoint(client, debut, fin)[0][0] == 20.2


def test_agregation_sql_frontiere_de_bucket(client):
    """La seconde exacte d'une frontière ouvre le bucket suivant, celle d'avant
    ferme le précédent.

    Vérifie le plancher : la division entière de SQLite tronque vers zéro là où
    `//` de Python plancherise, et c'est `FLOOR()` qui les réconcilie.
    """
    frontiere = datetime(2028, 5, 1, tzinfo=timezone.utc)
    assert int(frontiere.timestamp()) % 43200 == 0, "la date choisie doit être une frontière"
    debut, fin = "2028-04-25T00:00:00+00:00", "2028-05-20T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    _insert_releve(_AGG_SLUG, 10.0, None, (frontiere - timedelta(seconds=1)).isoformat())
    _insert_releve(_AGG_SLUG, 30.0, None, frontiere.isoformat())
    par_bucket = {t: temp for temp, _, t in _agg_endpoint(client, debut, fin)}
    assert par_bucket[frontiere - timedelta(seconds=43200)] == 10.0
    assert par_bucket[frontiere] == 30.0


def test_agregation_se_replie_quand_sqlite_ne_sait_pas_dater(client, caplog, repli_attendu):
    """Une ligne que `datetime.fromisoformat` accepte mais que SQLite refuse ne
    doit pas amputer le résultat.

    `2028-06-02T00:00:00+0000` en est une : décalage sans deux-points, la forme
    que produit `strftime('%z')` en Python et qu'on trouve dans un import de
    données historiques. `unixepoch` rend NULL, la ligne se retrouve dans un
    groupe de clé NULL — que `ORDER BY` place en tête — et `_aggregate` reprend
    la main. Elle reste dans la plage parce que le filtre `recu_le >= ? AND <= ?`
    est textuel : c'est ce qui rend le cas atteignable, là où une forme compacte
    `20280602T000000` serait de toute façon écartée par ce filtre.

    Aucune écriture de l'application ne produit ce format — `_now_iso` écrit
    toujours le même — mais l'endpoint est public et non authentifié, et une
    écriture directe en base ne doit pas le faire répondre à côté.
    """
    debut, fin = "2028-06-01T00:00:00+00:00", "2028-06-26T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    illisible = "2028-06-02T00:00:00+0000"
    assert debut <= illisible <= fin, "la ligne doit tomber dans la plage textuelle"

    conn = sqlite3.connect(config.DATABASE_PATH)
    assert conn.execute("SELECT unixepoch(?)", (illisible,)).fetchone()[0] is None
    conn.close()
    assert datetime.fromisoformat(illisible), "Python, lui, sait la dater"

    _insert_releve(_AGG_SLUG, 15.0, None, illisible)
    _insert_releve(_AGG_SLUG, 25.0, None, "2028-06-03T00:00:00+00:00")
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        data = _agg_endpoint(client, debut, fin)
    assert 15.0 in [t for t, _, _ in data], "la ligne datée par Python seul reste lue"
    assert data == _agg_reference(debut, fin, 43200)
    # Le repli refait le parcours Python et rend à la boucle d'événements le
    # blocage que #67 supprime : une seule ligne mal datée dans la plage suffit.
    # Il ne doit donc pas être silencieux.
    assert any("repli" in m for m in caplog.messages)


def test_agregation_sql_horodatage_anterieur_a_1970(client):
    """Le plancher, dans le seul cas où il se distingue de la troncature.

    `//` de Python plancherise, la division entière de SQLite tronque vers zéro :
    les deux ne coïncident que sur des horodatages postérieurs à 1970 — les
    seuls que cette base contienne, `_now_iso` étant son unique auteur. C'est
    `FLOOR()` qui les réconcilie ailleurs, et ce test est ce qui le prouve :
    sans lui, `unixepoch(recu_le) / 10800` placerait cette ligne trois heures
    plus tard.
    """
    debut, fin = "1969-12-30T00:00:00+00:00", "1970-01-01T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    instant = datetime(1969, 12, 31, 19, tzinfo=timezone.utc)
    assert instant.timestamp() < 0 and instant.timestamp() % 10800 != 0
    _insert_releve(_AGG_SLUG, 5.0, None, instant.isoformat())
    data = _agg_endpoint(client, debut, fin)
    assert [t for _, _, t in data] == [datetime(1969, 12, 31, 18, tzinfo=timezone.utc)]
    assert data == _agg_reference(debut, fin, 10800)


def test_agregation_sql_ecart_connu_sous_la_milliseconde(client):
    """Épingle la seule différence connue entre les deux implémentations.

    SQLite date à la **milliseconde** et arrondit au plus proche : une
    sous-seconde ≥ 0,9995 s est lue comme la seconde suivante. Quand cette
    seconde-là est une frontière de bucket, la ligne change de bucket — c'est le
    seul écart qui subsiste, et il est borné aux **500 dernières microsecondes**
    de la seconde qui précède une frontière (vérifié microseconde par
    microseconde : 999 499 est encore du bon côté, 999 500 bascule).

    Assumé plutôt que corrigé : sur les 8 188 relevés de la base de production,
    **une** ligne porte une sous-seconde ≥ 0,9995 et **aucune** ne tombe sur une
    frontière. À 79 relevés/jour et pour le plus petit bucket (3 h), l'espérance
    est d'environ une ligne concernée tous les 750 000 ans, et la conséquence
    serait qu'un relevé compte dans le bucket voisin. `_aggregate` reste la
    référence : ce test dit ce que fait le code livré, pas ce qui serait idéal.
    """
    debut, fin = "2028-07-25T00:00:00+00:00", "2028-08-19T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    frontiere = datetime(2028, 8, 1, tzinfo=timezone.utc)
    assert int(frontiere.timestamp()) % 43200 == 0
    juste_avant = frontiere - timedelta(microseconds=1)
    _insert_releve(_AGG_SLUG, 7.0, None, juste_avant.isoformat())

    obtenu = _agg_endpoint(client, debut, fin)
    reference = _agg_reference(debut, fin, 43200)
    assert [t for _, _, t in reference] == [frontiere - timedelta(seconds=43200)], (
        "Python place la ligne dans le bucket qui précède, elle lui appartient"
    )
    assert [t for _, _, t in obtenu] == [frontiere], (
        "SQL l'arrondit à la frontière et la place dans le bucket suivant"
    )
    assert obtenu != reference, (
        "si cet écart disparaît, la milliseconde n'est plus une limite : "
        "retirer ce test et la réserve qui l'accompagne dans PLAN.md"
    )


def test_agregation_se_replie_si_la_requete_ne_s_execute_pas(client, monkeypatch, caplog, repli_attendu):
    """Une SQLite qui ne sait pas exécuter la requête ne doit pas rendre 500.

    Le cas concret n'est pas théorique : `FLOOR()` fait partie des fonctions
    mathématiques, **optionnelles à la compilation** de SQLite
    (`SQLITE_ENABLE_MATH_FUNCTIONS`). Une bibliothèque assez récente pour
    `unixepoch()` mais compilée sans elles ferait échouer toutes les lectures
    agrégées — et seulement celles-là, les périodes de 12 h et 24 h ne passant
    pas par ce chemin. Sans ce garde, l'endpoint, public et non authentifié,
    répondait 500.

    Le repli doit aussi se **voir** : il refait le parcours Python et rend donc
    à la boucle d'événements exactement le blocage que l'issue #67 supprime.
    """
    import main

    debut, fin = "2029-03-01T00:00:00+00:00", "2029-03-26T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    _insert_releve(_AGG_SLUG, 12.0, 40.0, "2029-03-01T00:00:00+00:00")
    _insert_releve(_AGG_SLUG, 14.0, 44.0, "2029-03-02T00:00:00+00:00")

    monkeypatch.setattr(main, "_AGGREGATE_SQL", main._AGGREGATE_SQL.replace("FLOOR(", "FLOOR_ABSENTE("))
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        data = _agg_endpoint(client, debut, fin)
    assert data == _agg_reference(debut, fin, 43200)
    assert any("repli" in m for m in caplog.messages), (
        "le repli doit être journalisé : il ramène le blocage de boucle que #67 supprime"
    )

    # Témoin : une période non agrégée (24 h) ne passe pas par cette requête et
    # n'aurait donc rien signalé — c'est ce qui rendrait la panne difficile à voir.
    assert client.get("/api/releves/" + _AGG_SLUG, params={"period": "24h"}).status_code == 200


def test_agregation_sql_ne_melange_pas_les_sondes(client):
    """Une autre sonde présente dans la même fenêtre ne doit pas entrer dans la
    moyenne.

    Les autres tests d'agrégation ouvrent des fenêtres vierges pour **toutes**
    les sondes — leurs données vivent en 2026, les miennes en 2027 et après.
    Retirer `sonde_id = ?` du `WHERE` passait donc inaperçu : il n'y avait rien
    à mélanger. Ce test fournit de quoi.
    """
    debut, fin = "2029-07-01T00:00:00+00:00", "2029-07-26T00:00:00+00:00"
    _agg_fenetre_vierge(debut, fin)
    _insert_releve(_AGG_SLUG, 10.0, 30.0, "2029-07-01T00:00:00+00:00")
    _insert_releve("salon", 90.0, 90.0, "2029-07-01T01:00:00+00:00")
    _insert_releve("chambre-jade", -90.0, 10.0, "2029-07-01T02:00:00+00:00")

    data = _agg_endpoint(client, debut, fin)
    assert data[0][:2] == (10.0, 30.0), "seules les lignes de la sonde demandée comptent"
    assert data == _agg_reference(debut, fin, 43200)

    # Et le voisin garde bien les siennes : le filtre ne doit pas non plus les perdre.
    voisin = client.get("/api/releves/salon", params={"from": debut, "to": fin})
    assert voisin.status_code == 200
    assert [r["temperature"] for r in voisin.json()] == [90.0]
