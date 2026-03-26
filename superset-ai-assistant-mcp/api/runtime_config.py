from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse


_PLACEHOLDER_OPENAI_KEYS = {"replace_me", "your_openai_api_key"}
_PLACEHOLDER_JWT_SECRETS = {
    "change_me_in_env",
    "change_me_please",
    "dev-only-secret-change-me",
}
_LOCAL_HOSTS = {
    "",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "host.docker.internal",
}
_MODE_ALIASES = {
    "": "development",
    "dev": "development",
    "development": "development",
    "local": "development",
    "prod": "production",
    "production": "production",
    "public": "production",
}


class RuntimeConfigError(RuntimeError):
    pass


def _normalized_env(env: Dict[str, str] | None = None) -> Dict[str, str]:
    source = os.environ if env is None else env
    return {str(key): str(value) for key, value in source.items()}


def get_deployment_mode(env: Dict[str, str] | None = None) -> str:
    value = _normalized_env(env).get("ASSISTANT_DEPLOYMENT_MODE", "").strip().lower()
    mode = _MODE_ALIASES.get(value)
    if mode is None:
        raise RuntimeConfigError(
            "ASSISTANT_DEPLOYMENT_MODE must be one of: development, production"
        )
    return mode


def _is_local_host(hostname: str) -> bool:
    host = str(hostname or "").strip().casefold()
    if host in _LOCAL_HOSTS:
        return True
    return host.endswith(".local")


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".casefold()


def _validate_public_url(
    *,
    name: str,
    value: str,
    mode: str,
    errors: List[str],
    checks: List[str],
) -> str:
    token = str(value or "").strip()
    if not token:
        errors.append(f"{name} is required")
        return ""

    parsed = urlparse(token)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{name} must be an absolute http(s) URL")
        return ""

    if mode == "production" and _is_local_host(parsed.hostname or ""):
        errors.append(f"{name} must not point to localhost/loopback in production mode")
    else:
        checks.append(f"{name} valid")

    return token


def _split_csv(value: str) -> Iterable[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def collect_runtime_config_report(
    env: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    values = _normalized_env(env)
    mode = get_deployment_mode(values)
    errors: List[str] = []
    warnings: List[str] = []
    checks: List[str] = [f"ASSISTANT_DEPLOYMENT_MODE={mode}"]

    openai_api_key = values.get("OPENAI_API_KEY", "").strip()
    openai_model = values.get("OPENAI_MODEL", "").strip()
    jwt_secret = values.get("AUTH_JWT_SECRET", "").strip()
    superset_public_url = values.get("SUPERSET_PUBLIC_URL", "").strip()
    share_base_url = values.get("US15_SHARE_BASE_URL", "").strip()
    api_cors_origins = values.get("API_CORS_ORIGINS", "").strip()

    if not openai_api_key:
        errors.append("OPENAI_API_KEY is required")
    elif openai_api_key in _PLACEHOLDER_OPENAI_KEYS:
        errors.append("OPENAI_API_KEY still uses a placeholder value")
    else:
        checks.append("OPENAI_API_KEY set")

    if not openai_model:
        errors.append("OPENAI_MODEL is required")
    else:
        checks.append("OPENAI_MODEL set")

    if not jwt_secret:
        errors.append("AUTH_JWT_SECRET is required")
    else:
        weak_secret = jwt_secret in _PLACEHOLDER_JWT_SECRETS or len(jwt_secret) < 32
        if weak_secret and mode == "production":
            errors.append(
                "AUTH_JWT_SECRET must be non-placeholder and at least 32 characters in production mode"
            )
        elif weak_secret:
            warnings.append(
                "AUTH_JWT_SECRET is weak for production; use a non-placeholder value with at least 32 characters"
            )
        else:
            checks.append("AUTH_JWT_SECRET accepted")

    public_url = _validate_public_url(
        name="SUPERSET_PUBLIC_URL",
        value=superset_public_url,
        mode=mode,
        errors=errors,
        checks=checks,
    )

    if share_base_url:
        share_url = _validate_public_url(
            name="US15_SHARE_BASE_URL",
            value=share_base_url,
            mode=mode,
            errors=errors,
            checks=checks,
        )
        if public_url and share_url and _origin(public_url) != _origin(share_url):
            message = (
                "US15_SHARE_BASE_URL must match SUPERSET_PUBLIC_URL origin so share and explore links stay aligned"
            )
            if mode == "production":
                errors.append(message)
            else:
                warnings.append(message)
    else:
        checks.append("US15_SHARE_BASE_URL not set; falling back to SUPERSET_PUBLIC_URL")

    if api_cors_origins:
        parsed_origins = list(_split_csv(api_cors_origins))
        if not parsed_origins:
            warnings.append("API_CORS_ORIGINS is empty after parsing")
        for origin in parsed_origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"API_CORS_ORIGINS entry must be an absolute http(s) origin: {origin}")
                continue
            if mode == "production" and _is_local_host(parsed.hostname or ""):
                errors.append(
                    f"API_CORS_ORIGINS must not include localhost/loopback in production mode: {origin}"
                )
        if not any("API_CORS_ORIGINS" in item for item in errors):
            checks.append("API_CORS_ORIGINS set")
    else:
        checks.append("API_CORS_ORIGINS not set; same-origin proxy deployment assumed")

    return {
        "mode": mode,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }


def validate_runtime_config(env: Dict[str, str] | None = None) -> Dict[str, Any]:
    report = collect_runtime_config_report(env)
    if report["errors"]:
        raise RuntimeConfigError("Invalid runtime configuration:\n- " + "\n- ".join(report["errors"]))
    return report
