"""
executor package
=================
Phase 4 — Universal API Execution Engine for API Test Studio.

Public API (the only import the rest of the framework needs):

    from executor import ExecutionManager

    with ExecutionManager(env_config) as manager:
        results = manager.run(test_cases, spec_title="My API")

Internal modules (not for direct use outside this package):

    url_builder             — URLBuilder: base_url + path + params → final URL
    payload_builder         — PayloadBuilder: TestCase.request_body → PreparedPayload
    authentication_manager  — AuthConfig + AuthenticationManager: auth header injection
    retry_handler           — RetryPolicy + RetryHandler: exponential back-off retry
    request_manager         — RequestManager: sends HTTP via requests.Session
    response_wrapper        — ResponseWrapper: requests.Response → ExecutionResult
    execution_manager       — ExecutionManager: full pipeline orchestrator (public facade)

Extension points for future phases:
    - OAuth2 token exchange: AuthenticationManager.register_provider("oauth2", fn)
    - Client certificates:   manager._request_mgr.set_client_cert((cert, key))
    - Proxy support:         manager._request_mgr.set_proxy({"https": "…"})
    - Async execution:       Replace RequestManager with httpx.AsyncClient subclass
    - Parallel workers:      Wrap run() in ThreadPoolExecutor / asyncio.gather
"""

from executor.execution_manager import ExecutionManager
from executor.retry_handler import RetryPolicy

__all__ = ["ExecutionManager", "RetryPolicy"]
