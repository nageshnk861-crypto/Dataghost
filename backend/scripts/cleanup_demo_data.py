#!/usr/bin/env python3
"""
DataGhost — Admin-only Demo Data Cleanup Script
================================================

Deletes data that was inserted by _seed_demo_data() and _seed_admin() in main.py.
This script is NEVER run automatically; it must be invoked by an administrator.

Demo data markers
-----------------
  Devices   : device_id LIKE 'DGD-%'
  ScanLogs  : device_id LIKE 'DGD-%'
  Incidents : device_id LIKE 'DGD-%'
  Users     : username IN ('analyst01', 'analyst02', 'viewer01')

Usage
-----
  # Dry run (print what would be deleted, touch nothing):
  python scripts/cleanup_demo_data.py --dry-run

  # Actually delete:
  python scripts/cleanup_demo_data.py --confirm

  # Delete and also wipe demo users:
  python scripts/cleanup_demo_data.py --confirm --include-users
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from database import SessionLocal
from models import Device, Incident, ScanLog, User

DEMO_DEVICE_ID_PREFIX = "DGD-"
DEMO_USER_USERNAMES = ("analyst01", "analyst02", "viewer01")


def _find_demo_rows(db):
    devices   = db.query(Device).filter(Device.device_id.like(f"{DEMO_DEVICE_ID_PREFIX}%")).all()
    scan_logs = db.query(ScanLog).filter(ScanLog.device_id.like(f"{DEMO_DEVICE_ID_PREFIX}%")).all()
    incidents = db.query(Incident).filter(Incident.device_id.like(f"{DEMO_DEVICE_ID_PREFIX}%")).all()
    demo_users= db.query(User).filter(User.username.in_(DEMO_USER_USERNAMES)).all()
    return devices, scan_logs, incidents, demo_users


def run(dry_run: bool, include_users: bool):
    db = SessionLocal()
    try:
        devices, scan_logs, incidents, demo_users = _find_demo_rows(db)
        tag = "[DRY RUN] " if dry_run else ""
        print(f"\n{tag}DataGhost demo data cleanup")
        print("=" * 60)
        print(f"  Devices   : {len(devices)}")
        print(f"  ScanLogs  : {len(scan_logs)}")
        print(f"  Incidents : {len(incidents)}")
        print(f"  Demo users: {len(demo_users)} ({', '.join(u.username for u in demo_users) or 'none'})")

        if dry_run:
            print("\n[DRY RUN] No rows deleted. Pass --confirm to actually delete.")
            if devices:
                print("\nDevices that WOULD be deleted:")
                for d in devices:
                    print(f"  {d.device_id}  {d.device_name}  ({d.platform or d.os_type})")
            if include_users and demo_users:
                print("\nDemo users that WOULD be deleted:")
                for u in demo_users:
                    print(f"  {u.username}  <{u.email}>  role={u.role}")
            return

        del_inc  = db.query(Incident).filter(Incident.device_id.like(f"{DEMO_DEVICE_ID_PREFIX}%")).delete(synchronize_session=False)
        del_sl   = db.query(ScanLog).filter(ScanLog.device_id.like(f"{DEMO_DEVICE_ID_PREFIX}%")).delete(synchronize_session=False)
        del_dev  = db.query(Device).filter(Device.device_id.like(f"{DEMO_DEVICE_ID_PREFIX}%")).delete(synchronize_session=False)
        del_usr  = 0
        if include_users:
            del_usr = db.query(User).filter(User.username.in_(DEMO_USER_USERNAMES)).delete(synchronize_session=False)

        db.commit()
        print(f"\nDeleted: {del_inc} incidents, {del_sl} scan logs, {del_dev} devices, {del_usr} demo users")
        print("Cleanup complete.")
    except Exception as exc:
        db.rollback()
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Delete demo-seeded DataGhost data.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Print what would be deleted, touch nothing.")
    mode.add_argument("--confirm", action="store_true", help="Actually delete demo rows. Irreversible.")
    parser.add_argument("--include-users", action="store_true", default=False,
                        help="Also delete demo user accounts (analyst01, analyst02, viewer01).")
    args = parser.parse_args()
    run(dry_run=args.dry_run, include_users=args.include_users)


if __name__ == "__main__":
    main()
