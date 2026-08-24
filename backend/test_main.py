import os
import sqlite3
import tempfile

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


def test_releves_from_without_to_rejected(client):
    resp = client.get("/api/releves/salon", params={"from": "2026-01-15T00:00:00.000Z"})
    assert resp.status_code == 400


def test_releves_to_before_from_rejected(client):
    resp = client.get(
        "/api/releves/salon",
        params={"from": "2026-01-16T00:00:00.000Z", "to": "2026-01-15T00:00:00.000Z"},
    )
    assert resp.status_code == 400


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
