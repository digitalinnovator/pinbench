"""The one place pinbench makes small HTTPS requests (alerts, release checks)."""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping

_TIMEOUT = 20

# (method, url, headers, body) -> (status, body). Tests inject a fake; nothing else opens a socket.
Http = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, bytes]]


class HttpError(RuntimeError):
    pass


def https_request(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None
) -> tuple[int, bytes]:
    if urllib.parse.urlsplit(url).scheme != "https":
        raise HttpError("endpoints must use https")
    request = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        # The reason never includes the URL, which for a Slack webhook is itself the secret.
        raise HttpError(f"request failed: {getattr(exc, 'reason', exc)}") from None
