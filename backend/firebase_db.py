"""
DataGhost – Firebase Firestore Sync Service.
Mirrors incidents, devices, and scan events to Firestore cloud collections.
"""
import logging
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import firestore
from firebase_auth import initialize_firebase_admin

logger = logging.getLogger(__name__)

_firestore_client: Optional[firestore.Client] = None


def get_firestore_db() -> Optional[firestore.Client]:
    """Get or initialize Firestore database client."""
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client

    app = initialize_firebase_admin()
    if not app and firebase_admin._apps:
        try:
            app = firebase_admin.get_app()
        except Exception:
            app = None

    if app:
        try:
            _firestore_client = firestore.client(app=app)
            return _firestore_client
        except Exception as exc:
            logger.debug("Firestore client initialization deferred: %s", exc)
            return None
    return None


def sync_incident_to_firestore(incident_data: Dict[str, Any]) -> bool:
    """Store/update an incident in Firestore 'incidents' collection."""
    try:
        db = get_firestore_db()
        if db is None:
            return False

        incident_id = incident_data.get("incident_id")
        if not incident_id:
            return False

        db.collection("incidents").document(incident_id).set(incident_data, merge=True)
        logger.info("Incident %s synced to Firebase Firestore.", incident_id)
        return True
    except Exception as exc:
        logger.warning("Firestore sync failed for incident %s: %s", incident_data.get("incident_id"), exc)
        return False


def sync_device_to_firestore(device_data: Dict[str, Any]) -> bool:
    """Store/update a device in Firestore 'devices' collection."""
    try:
        db = get_firestore_db()
        if db is None:
            return False

        device_id = device_data.get("device_id")
        if not device_id:
            return False

        db.collection("devices").document(device_id).set(device_data, merge=True)
        logger.info("Device %s synced to Firebase Firestore.", device_id)
        return True
    except Exception as exc:
        logger.warning("Firestore sync failed for device %s: %s", device_data.get("device_id"), exc)
        return False


def sync_scan_log_to_firestore(scan_data: Dict[str, Any]) -> bool:
    """Store a scan event in Firestore 'scan_logs' collection."""
    try:
        db = get_firestore_db()
        if db is None:
            return False

        scan_id = scan_data.get("scan_id") or scan_data.get("file_hash")
        if not scan_id:
            return False

        db.collection("scan_logs").document(str(scan_id)).set(scan_data, merge=True)
        return True
    except Exception as exc:
        logger.warning("Firestore scan sync error: %s", exc)
        return False
