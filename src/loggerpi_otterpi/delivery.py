import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from model.batch import Batch

LOGGER = logging.getLogger(__name__)


class DeliveryResult:
    """Ergebnis eines Zustellversuchs."""

    SUCCESS = "success"  # HTTP 202
    PERMANENT = "permanent"  # 4xx (Batch-Fehler), 5xx permanent, SSL, Config
    TRANSIENT = "transient"  # 5xx transient, Netzwerk, Timeout, unerwartete Exception


# 4xx-Codes, die einen Batch-Fehler signalisieren (nicht retry-fähig)
_PERMANENT_4XX = {400, 409, 413, 422}

# 5xx-Codes, die einen permanenten Fehler signalisieren (nicht retry-fähig)
_PERMANENT_5XX = {505, 508, 510}


class _NoRedirectHandler(HTTPRedirectHandler):
    """Verhindert, dass urlopen Redirects folgt.

    Ein Redirect würde den POST in einen GET umwandeln (301/302/303)
    und den Authorization-Header an ein fremdes Ziel weiterleiten.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(
            req.full_url,
            code,
            f"Redirect not allowed: {newurl}",
            headers,
            fp,
        )


_opener = build_opener(_NoRedirectHandler)


def _urlopen(request, timeout):
    return _opener.open(request, timeout=timeout)


class BatchDelivery:
    def __init__(self, endpoint: str, token: str, timeout: float = 10.0) -> None:
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def send(self, batch: Batch) -> str:
        try:
            request = Request(
                self.endpoint,
                data=_encode_batch(batch),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.token}",
                },
                method="POST",
            )
        except ValueError as exc:
            LOGGER.error(
                "Delivery: invalid endpoint %r for batch %s: %s",
                self.endpoint,
                batch.batch_id,
                exc,
            )
            return DeliveryResult.PERMANENT

        try:
            with _urlopen(request, timeout=self.timeout) as response:
                if response.status == 202:
                    return DeliveryResult.SUCCESS
                LOGGER.warning(
                    "Delivery: unexpected HTTP %s for batch %s",
                    response.status,
                    batch.batch_id,
                )
                return DeliveryResult.TRANSIENT
        except HTTPError as exc:
            if exc.code in _PERMANENT_4XX or exc.code in _PERMANENT_5XX:
                LOGGER.error(
                    "Delivery: permanent HTTP %s for batch %s",
                    exc.code,
                    batch.batch_id,
                )
                return DeliveryResult.PERMANENT
            LOGGER.warning(
                "Delivery: transient HTTP %s for batch %s",
                exc.code,
                batch.batch_id,
            )
            return DeliveryResult.TRANSIENT
        except URLError as exc:
            LOGGER.warning(
                "Delivery: network error for batch %s: %s",
                batch.batch_id,
                exc,
            )
            return DeliveryResult.TRANSIENT
        except Exception as exc:
            LOGGER.exception(
                "Delivery: unexpected error for batch %s: %s",
                batch.batch_id,
                exc,
            )
            return DeliveryResult.TRANSIENT


def _encode_batch(batch: Batch) -> bytes:
    return json.dumps(batch.to_dict(), ensure_ascii=False).encode("utf-8")
