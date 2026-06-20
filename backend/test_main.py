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

from main import _parse_shelly_value, app


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
    assert _parse_shelly_value(None) is None


def test_parse_shelly_value_literal_null():
    assert _parse_shelly_value("null") is None
    assert _parse_shelly_value("Null") is None
    assert _parse_shelly_value("NULL") is None
    assert _parse_shelly_value("") is None
    assert _parse_shelly_value("  ") is None


def test_parse_shelly_value_float():
    assert _parse_shelly_value("26.1") == 26.1


def test_parse_shelly_value_invalid():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _parse_shelly_value("abc")
    assert exc.value.status_code == 422


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
