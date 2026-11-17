import json
import ssl
from urllib.error import HTTPError, URLError

import pytest
from batch_factory import SequenceStore, create_batch
from delivery import BatchDelivery, DeliveryResult

TEST_TOKEN = "lp-test-token-1234567890abcdef"


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _batch(tmp_path):
    store = SequenceStore(tmp_path / "sequence")
    return create_batch("logger-001", store)


def _delivery():
    return BatchDelivery("http://otterpi/api/v1/batches", token=TEST_TOKEN)


def test_delivery_sends_batch_as_json(monkeypatch, tmp_path):
    batch = _batch(tmp_path)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(202)

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    delivery = _delivery()

    assert delivery.send(batch) == DeliveryResult.SUCCESS

    request = captured["request"]

    assert request.method == "POST"
    assert request.full_url == "http://otterpi/api/v1/batches"
    assert request.headers["Content-type"] == "application/json"
    assert request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
    assert json.loads(request.data.decode("utf-8")) == batch.to_dict()
    assert captured["timeout"] == 10.0


def test_delivery_accepts_only_http_202(monkeypatch, tmp_path):
    batch = _batch(tmp_path)

    monkeypatch.setattr(
        "delivery._urlopen",
        lambda request, timeout: FakeResponse(200),
    )

    assert _delivery().send(batch) == DeliveryResult.TRANSIENT


@pytest.mark.parametrize("code", [400, 409, 413, 422])
def test_delivery_permanent_4xx(monkeypatch, tmp_path, code):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise HTTPError("url", code, "error", None, None)

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.PERMANENT


@pytest.mark.parametrize("code", [408, 429])
def test_delivery_transient_4xx(monkeypatch, tmp_path, code):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise HTTPError("url", code, "error", None, None)

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.TRANSIENT


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_delivery_transient_5xx(monkeypatch, tmp_path, code):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise HTTPError("url", code, "error", None, None)

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.TRANSIENT


def test_delivery_transient_network_error(monkeypatch, tmp_path):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise URLError("network down")

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.TRANSIENT


def test_delivery_transient_unexpected_exception(monkeypatch, tmp_path):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.TRANSIENT


@pytest.mark.parametrize(
    "code",
    [
        401,
        403,
        404,
        405,
        406,
        407,
        410,
        411,
        412,
        414,
        415,
        416,
        417,
        421,
        424,
        425,
        426,
        428,
        431,
        451,
    ],
)
def test_delivery_transient_config_4xx(monkeypatch, tmp_path, code):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise HTTPError("url", code, "error", None, None)

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.TRANSIENT


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_delivery_rejects_redirects(monkeypatch, tmp_path, code):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise HTTPError("url", code, "redirect", None, None)

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.TRANSIENT


@pytest.mark.parametrize("code", [505, 508, 510])
def test_delivery_permanent_5xx(monkeypatch, tmp_path, code):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise HTTPError("url", code, "error", None, None)

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.PERMANENT


def test_delivery_transient_ssl_error(monkeypatch, tmp_path):
    batch = _batch(tmp_path)

    def fake_urlopen(request, timeout):
        raise URLError(ssl.SSLError("certificate verify failed"))

    monkeypatch.setattr("delivery._urlopen", fake_urlopen)

    assert _delivery().send(batch) == DeliveryResult.TRANSIENT


def test_delivery_permanent_invalid_endpoint(tmp_path):
    batch = _batch(tmp_path)
    delivery = BatchDelivery("", token=TEST_TOKEN)

    assert delivery.send(batch) == DeliveryResult.PERMANENT
