import os
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


def test_parse_shelly_value_none():
    assert _parse_shelly_value(None) is None


def test_parse_shelly_value_literal_null():
    assert _parse_shelly_value("null") is None
    assert _parse_shelly_value("Null") is None


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
