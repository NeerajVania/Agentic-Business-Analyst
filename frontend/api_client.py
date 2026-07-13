"""
frontend/api_client.py
=======================
Centralised HTTP client for all backend API calls.
Handles auth token injection, error normalisation, and timeouts.
"""

from __future__ import annotations

import streamlit as st
import requests
from typing import Any, Optional
from styles import API_BASE


def _headers() -> dict:
    """Return auth headers if a token is stored in session state."""
    token = st.session_state.get("auth_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def get(path: str, params: Optional[dict] = None, timeout: int = 15) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", headers=_headers(), params=params, timeout=timeout)


def post(path: str, json: Any = None, files: Any = None, timeout: int = 300) -> requests.Response:
    return requests.post(
        f"{API_BASE}{path}",
        headers=_headers() if files is None else {k: v for k, v in _headers().items()},
        json=json,
        files=files,
        timeout=timeout,
    )


def delete(path: str, timeout: int = 10) -> requests.Response:
    return requests.delete(f"{API_BASE}{path}", headers=_headers(), timeout=timeout)


def safe_json(resp: requests.Response) -> tuple[bool, Any]:
    """Return (ok, data_or_error_str)."""
    try:
        resp.raise_for_status()
        return True, resp.json()
    except requests.HTTPError:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        return False, detail
    except Exception as exc:
        return False, str(exc)
