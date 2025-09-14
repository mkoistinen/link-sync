from abc import ABCMeta, abstractmethod
from http import HTTPStatus
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union
from urllib.parse import quote

import requests
from requests.auth import HTTPDigestAuth


logger = logging.getLogger(__name__)


class ApiException(Exception):
    """An API-specific exception."""


class ApiResponse:
    """
    Encapsulate an API Response.

    This class is "slotted" to keep these instances lightweight and performant.

    Parameters
    ----------
    status_code : int
        The HTTP status code of the response.
    payload : object or None, default None
        Optional. The deserialized JSON response as an `object` (Typically
        a dictionary or list).
    """

    __slots__ = "status_code", "payload"

    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self, status_code: int, payload: Optional[object] = None
    ):
        self.status_code = status_code
        self.payload = payload

    @property
    def success(self) -> bool:
        """Return True if the API returned a success status_code."""
        return HTTPStatus.OK <= self.status_code < HTTPStatus.MULTIPLE_CHOICES


class AbstractApi(metaclass=ABCMeta):
    """Abstractly describes the API."""

    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self,
        *,
        name: Optional[str] = None,
        host: str,
        username: str,
        password: str,
    ):
        self.name = name or f"@ {host}"
        self.host = host
        self.username = username
        self.password = password
        self._api_base = f"{self.host}/api/v1"
        self._session = None

    @abstractmethod
    def status_response(self, method="GET") -> ApiResponse:
        """Return the deserialized status payload as a dictionary."""

    @abstractmethod
    def files_response(
        self,
        method: str = "GET",
        *,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]],
        path: Union[Path, str],
    ) -> ApiResponse:
        """Return the deserialized files payload as a dictionary."""


class PrusaLinkApi(AbstractApi):
    """Implement the API for PrusaLink."""

    @property
    def auth(self):
        """Prepare and return an HTTPDigestAuth instance."""
        return HTTPDigestAuth(username=self.username, password=self.password)

    @property
    def session(self) -> requests.Session:
        """Manage a lazy-instantiated, cached session instance."""
        return requests.Session()

    def status_response(self, method: str = "GET") -> ApiResponse:
        """Return the deserialized status API and payload."""
        url = f"{self._api_base}/status"
        res = self.session.request(method=method, url=url, auth=self.auth)
        if HTTPStatus.OK <= res.status_code < HTTPStatus.MULTIPLE_CHOICES:
            try:
                payload = res.json()
            except Exception:  # Deliberately broad
                payload = None
        else:
            payload = None

        return ApiResponse(res.status_code, payload)

    def files_response(
        self,
        method: str = "GET",
        *,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        path: Union[Path, str],
    ) -> ApiResponse:
        """Return the deserialized files API status and payload."""
        if not headers:
            headers = {}
        url = f"{self._api_base}/files{quote(str(path))}"
        options = {}

        if headers:
            options["headers"] = headers
        # PrusaLink doesn't like both types of Authentication in a request.
        if not headers or "X-Api-Key" not in headers:
            options["auth"] = self.auth

        # Only add `data` if it was provided
        if data is not None:
            options["data"] = data
        res = self.session.request(method=method, url=url, **options)
        if HTTPStatus.OK <= res.status_code < HTTPStatus.MULTIPLE_CHOICES:
            try:
                payload = res.json()
            except Exception:  # Deliberately broad
                payload = None
        else:
            payload = None

        return ApiResponse(res.status_code, payload)
