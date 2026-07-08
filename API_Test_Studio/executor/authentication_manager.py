"""
executor/authentication_manager.py
====================================
Prepares authentication headers and credentials for HTTP requests.

Supported strategies (Phase 4):
    - none       — no authentication headers added
    - bearer     — ``Authorization: Bearer <token>``
    - api_key    — ``X-API-Key: <key>``  or custom header name
    - basic      — ``Authorization: Basic <base64(user:password)>``

Extension hooks (Phase 5+):
    - oauth2     — register an OAuth2TokenProvider subclass and call
                   AuthenticationManager.register_provider()
    - client_cert — pass cert tuple to requests directly

The manager only PREPARES headers. It never makes login/token-exchange
HTTP calls. That responsibility belongs to a future TokenProvider layer.

Usage:
    headers = AuthenticationManager.prepare(
        auth_config={"type": "bearer", "token": "abc123"},
    )
    # → {"Authorization": "Bearer abc123"}
"""

import base64
from typing import Any, Dict, Optional

from constants.app_constants import AuthTypes
from utilities.logger import get_logger

logger = get_logger(__name__)


class AuthConfig:
    """
    Value object encapsulating authentication configuration for one request.

    Attributes:
        auth_type:    Strategy identifier (``"none"``, ``"bearer"``, etc.).
        token:        Bearer token string.
        api_key:      API key value.
        api_key_header: Header name to carry the API key (default ``"X-API-Key"``).
        username:     Basic-auth username.
        password:     Basic-auth password.
        custom_headers: Arbitrary extra headers injected by auth logic.
    """

    def __init__(
        self,
        auth_type: str = AuthTypes.NONE,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        username: Optional[str] = None,
        password: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.auth_type = auth_type.lower()
        self.token = token
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.username = username
        self.password = password
        self.custom_headers: Dict[str, str] = custom_headers or {}

    @classmethod
    def from_environment(cls, env_config: Any) -> "AuthConfig":
        """
        Build an ``AuthConfig`` from an ``EnvironmentConfig`` instance.

        Reads ``auth_type`` and credential variables from the environment.
        Credentials are looked up from environment variables defined in
        ``environments.yaml`` under the ``variables`` block:

            variables:
                bearer_token: "my_token"
                api_key: "my_key"
                username: "user"
                password: "pass"

        Args:
            env_config: An ``EnvironmentConfig`` instance.

        Returns:
            Populated ``AuthConfig``.
        """
        auth_type = getattr(env_config, "auth_type", AuthTypes.NONE)
        variables = getattr(env_config, "variables", {}) or {}

        return cls(
            auth_type=auth_type,
            token=variables.get("bearer_token") or variables.get("token"),
            api_key=variables.get("api_key"),
            api_key_header=variables.get("api_key_header", "X-API-Key"),
            username=variables.get("username"),
            password=variables.get("password"),
        )

    @classmethod
    def from_test_case_headers(cls, headers: Dict[str, str]) -> "AuthConfig":
        """
        Derive auth configuration by inspecting the test case's header dict.

        This allows the executor to honour auth headers that were explicitly
        set by the test case generators (e.g. NegativeGenerator setting an
        invalid token).

        Args:
            headers: The TestCase.headers dict.

        Returns:
            An ``AuthConfig`` in ``"none"`` mode with all headers passed
            through as ``custom_headers``.  The caller is responsible for
            deciding whether to supplement or override these.
        """
        return cls(
            auth_type=AuthTypes.NONE,
            custom_headers=dict(headers),
        )


class AuthenticationManager:
    """
    Prepares authentication headers for an outgoing HTTP request.

    All methods are static — no instantiation required.

    Extension point for OAuth2 / client-cert:
        Subclass ``AuthenticationManager`` and override ``prepare()``, or
        register a callable via ``register_provider()`` (see below).
    """

    # Registry for future token-provider plugins
    # { auth_type_string: callable(auth_config) -> Dict[str, str] }
    _providers: Dict[str, Any] = {}

    @classmethod
    def register_provider(cls, auth_type: str, provider: Any) -> None:
        """
        Register a custom authentication provider for *auth_type*.

        The *provider* must be a callable that accepts an ``AuthConfig``
        and returns a ``Dict[str, str]`` of headers.

        Example (OAuth2 future implementation)::

            def oauth2_provider(auth_config):
                token = OAuth2Client.get_token(auth_config.token_url, ...)
                return {"Authorization": f"Bearer {token}"}

            AuthenticationManager.register_provider("oauth2", oauth2_provider)

        Args:
            auth_type: Strategy identifier string (e.g. ``"oauth2"``).
            provider:  Callable accepting ``AuthConfig``, returning header dict.
        """
        cls._providers[auth_type.lower()] = provider
        logger.info("AuthenticationManager: provider registered for '%s'.", auth_type)

    @classmethod
    def prepare(
        cls,
        auth_config: AuthConfig,
        existing_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Build and return the complete authentication header dict.

        The result is merged with *existing_headers* — the auth headers
        take precedence on key conflicts.

        Args:
            auth_config:      Configured ``AuthConfig`` instance.
            existing_headers: Headers already present on the request.

        Returns:
            Dict of headers with authentication entries added.
        """
        base = dict(existing_headers or {})

        # Apply any custom headers from the auth config first (lowest priority)
        base.update(auth_config.custom_headers)

        auth_type = auth_config.auth_type

        # ── Check registered providers first (OAuth2, custom, etc.) ───
        if auth_type in cls._providers:
            try:
                provider_headers = cls._providers[auth_type](auth_config)
                base.update(provider_headers)
                logger.debug(
                    "AuthenticationManager: custom provider applied for '%s'.", auth_type
                )
                return base
            except Exception as exc:
                logger.error(
                    "AuthenticationManager: provider '%s' failed: %s", auth_type, exc
                )
                return base

        # ── Built-in strategies ────────────────────────────────────────
        if auth_type == AuthTypes.NONE or not auth_type:
            logger.debug("AuthenticationManager: no auth applied.")

        elif auth_type == AuthTypes.BEARER:
            token = auth_config.token or ""
            if token:
                base["Authorization"] = f"Bearer {token}"
                logger.debug("AuthenticationManager: Bearer token applied.")
            else:
                logger.warning(
                    "AuthenticationManager: auth_type='bearer' but no token provided."
                )

        elif auth_type == AuthTypes.API_KEY:
            key = auth_config.api_key or ""
            if key:
                base[auth_config.api_key_header] = key
                logger.debug(
                    "AuthenticationManager: API key applied to header '%s'.",
                    auth_config.api_key_header,
                )
            else:
                logger.warning(
                    "AuthenticationManager: auth_type='api_key' but no key provided."
                )

        elif auth_type == AuthTypes.BASIC:
            username = auth_config.username or ""
            password = auth_config.password or ""
            if username:
                credentials = base64.b64encode(
                    f"{username}:{password}".encode()
                ).decode()
                base["Authorization"] = f"Basic {credentials}"
                logger.debug("AuthenticationManager: Basic auth applied.")
            else:
                logger.warning(
                    "AuthenticationManager: auth_type='basic' but no username provided."
                )

        else:
            logger.warning(
                "AuthenticationManager: unknown auth_type '%s'. No auth applied.",
                auth_type,
            )

        return base
