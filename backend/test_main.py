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
from models import HUM_MAX, HUM_MIN, TEMP_MAX, TEMP_MIN


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


def test_parse_shelly_value_humidity_bounds():
    assert _parse_shelly_value("96.7", HUM_MIN, HUM_MAX, "Humidité") == 96.7
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _parse_shelly_value("-0.1", HUM_MIN, HUM_MAX, "Humidité")
    with pytest.raises(HTTPException):
        _parse_shelly_value("100.1", HUM_MIN, HUM_MAX, "Humidité")


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
    resp = client.post(
        "/api/releve/salon",
        json={"temp": 20.0, "hum": 150.0},
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


def test_releves_raw_survives_infinite_row(client):
    _insert_releve("salon", 21.0, 55.0, "2026-02-10T08:00:00+00:00")
    _insert_releve("salon", float("inf"), None, "2026-02-10T09:00:00+00:00")
    resp = client.get(
        "/api/releves/salon",
        params={"from": "2026-02-10T00:00:00.000Z", "to": "2026-02-10T23:00:00.000Z"},
    )
    # Sans le garde-fou : 500, et la plage entière disparaît du graphique.
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["temperature"] == 21.0 for r in data), "le relevé sain doit rester lisible"
    assert all(r["temperature"] != float("inf") for r in data)
    assert any(r["temperature"] is None for r in data), "la ligne fautive devient une mesure absente"


def test_releves_aggregated_survives_infinite_row(client):
    _insert_releve("salon", 20.0, None, "2026-02-12T08:00:00+00:00")
    _insert_releve("salon", float("inf"), None, "2026-02-12T08:30:00+00:00")
    resp = client.get(
        "/api/releves/salon",
        params={"from": "2026-02-12T00:00:00.000Z", "to": "2026-02-19T00:00:00.000Z"},
    )
    assert resp.status_code == 200
    temps = [r["temperature"] for r in resp.json() if r["temperature"] is not None]
    assert temps, "le bucket doit rester exploitable"
    # inf contaminerait la moyenne du bucket entier, pas seulement sa propre ligne.
    assert all(t == t and abs(t) < 1e30 for t in temps)
    assert 20.0 in temps


def test_sondes_survives_infinite_last_reading(client):
    # chambre-jade est active dans le seed et n'est utilisée par aucun autre test :
    # la ligne insérée est donc bien son dernier relevé.
    _insert_releve("chambre-jade", float("inf"), None, "2026-02-14T10:00:00+00:00")
    resp = client.get("/api/sondes")
    # Sans le garde-fou : 500 sur /api/sondes, donc dashboard entièrement vide —
    # portée plus large que la seule Vue Analyse.
    assert resp.status_code == 200
    jade = next(s for s in resp.json() if s["slug"] == "chambre-jade")
    assert jade["dernier_releve"] is not None
    assert jade["dernier_releve"]["temperature"] is None
    assert jade["dernier_releve"]["recu_le"] is not None
