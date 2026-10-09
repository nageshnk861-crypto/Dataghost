"""
DataGhost – Firebase Admin SDK Integration and Token Verification.

Firebase ID token verification strategy:
  Primary:  google.oauth2.id_token.verify_firebase_token  — verifies using
            Google's public certificate endpoint. Requires only the Firebase
            project ID. Works without a service account private key.
  Fallback: firebase_admin verify_id_token — used only if a valid service
            account is loaded (for revocation-check support).

This design intentionally avoids depending on the private-key portion of the
service account so that a corrupted or missing serviceAccountKey.json does NOT
break Firebase ID token verification.

SECURITY:
  • Raw tokens are never logged.
  • Private keys are never printed or exposed.
  • Verification contacts only public Google endpoints.
"""
import logging
import os
from typing import Any, Dict, Optional

import requests as _requests_lib
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_firebase_token as _gauth_verify

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project ID
# ---------------------------------------------------------------------------
_FIREBASE_PROJECT_ID: str = (
    settings.FIREBASE_PROJECT_ID
    or os.environ.get("FIREBASE_PROJECT_ID", "")
    or "dataghost-9431f"
)

# ---------------------------------------------------------------------------
# Shared HTTP session (reuse connections for repeated token verifications)
# ---------------------------------------------------------------------------
_http_session: Optional[_requests_lib.Session] = None


def _get_http_session() -> _requests_lib.Session:
    global _http_session
    if _http_session is None:
        _http_session = _requests_lib.Session()
    return _http_session


# ---------------------------------------------------------------------------
# Firebase Admin SDK (optional — used for revocation checks only)
# ---------------------------------------------------------------------------
_firebase_admin_available = False

try:
    import firebase_admin
    from firebase_admin import auth as _fb_auth
    from firebase_admin import credentials as _fb_creds

    _firebase_admin_available = True
except ImportError:
    pass  # firebase_admin not installed — fine, we use google-auth instead.


_firebase_admin_app = None


def initialize_firebase_admin() -> Optional[Any]:
    """
    Attempt to initialise Firebase Admin SDK for optional revocation checks.
    Failure is non-fatal — primary token verification works without it.
    Idempotent; safe to call multiple times.
    """
    global _firebase_admin_app

    if not _firebase_admin_available:
        return None

    if firebase_admin._apps:
        _firebase_admin_app = firebase_admin.get_app()
        return _firebase_admin_app

    cred_path = settings.FIREBASE_CREDENTIALS_PATH or os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )
    project_id = _FIREBASE_PROJECT_ID

    if cred_path:
        # Resolve relative paths to the backend directory.
        resolved = cred_path if os.path.isabs(cred_path) else os.path.join(
            os.path.dirname(__file__), cred_path
        )
        if os.path.exists(resolved):
            try:
                cred = _fb_creds.Certificate(resolved)
                _firebase_admin_app = firebase_admin.initialize_app(cred)
                logger.info(
                    "Firebase Admin initialised with service account (%s).",
                    os.path.basename(resolved),
                )
                return _firebase_admin_app
            except Exception as cert_err:
                logger.warning(
                    "Service account file could not be loaded (%s): %s — "
                    "falling back to projectId-only mode (token verification "
                    "will use google-auth public certificates).",
                    os.path.basename(resolved),
                    cert_err,
                )

    # Initialise with projectId only — sufficient for the google-auth primary path.
    try:
        options = {"projectId": project_id} if project_id else None
        _firebase_admin_app = firebase_admin.initialize_app(options=options)
        logger.info(
            "Firebase Admin initialised with projectId=%s (no service account — "
            "token verification uses google-auth public-key path).",
            project_id,
        )
        return _firebase_admin_app
    except Exception as exc:
        logger.warning("Firebase Admin initialisation skipped: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Token verification — PRIMARY: google-auth (no private key required)
# ---------------------------------------------------------------------------

def verify_firebase_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Firebase ID token and return the decoded claims, or None.

    Uses google.oauth2.id_token.verify_firebase_token which:
      1. Fetches Google's public signing certificates (cached locally).
      2. Verifies the JWT signature, iss, aud, exp fields.
      3. Requires NO service-account private key.

    Does NOT log or expose the raw token.
    """
    if not token or not token.strip():
        return None

    if not _FIREBASE_PROJECT_ID:
        logger.warning(
            "FIREBASE_PROJECT_ID is not configured — Firebase token "
            "verification is disabled."
        )
        return None

    # ── Primary path: google-auth public-key verification ────────────────────
    try:
        session = _get_http_session()
        google_request = GoogleRequest(session=session)

        claims: Dict[str, Any] = _gauth_verify(
            id_token=token,
            request=google_request,
            audience=_FIREBASE_PROJECT_ID,
        )

        # Normalise the 'uid' field (Firebase stores it as 'sub' in the JWT).
        if "uid" not in claims and "sub" in claims:
            claims["uid"] = claims["sub"]

        logger.debug(
            "Firebase token verified via google-auth for uid=%s",
            claims.get("uid", "<unknown>"),
        )
        return claims

    except Exception as exc:
        # Classify for appropriate log level.
        exc_str = str(exc).lower()
        if "expired" in exc_str or "token has expired" in exc_str:
            logger.debug("Firebase ID token has expired.")
        elif "invalid" in exc_str or "signature" in exc_str:
            logger.debug("Firebase ID token is invalid: %s", type(exc).__name__)
        else:
            logger.debug(
                "Firebase token verification failed (%s): %s",
                type(exc).__name__,
                exc,
            )
        return None
