#!/usr/bin/env python3
"""
Dump the current contents of the meta‑tables so you can see
 • categories
 • device‑models (+ unicode / code‑points)
 • which schema‑rows per kind exist for every model
 -------------------------------------------------------------------------
Run inside the container:

    docker‑compose exec factory-lens python dev_scripts/db_introspect.py
"""

import sys
import os

# Add the project directory to the system path to ensure app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app        # uses your existing config
from extensions import db
from models.device_category import DeviceCategory
from models.device_model    import DeviceModel
from models.device_schema   import DeviceSchema

def printable(s: str) -> str:
    """Show every code‑point → helps spotting U+00A0 non‑breaking spaces."""
    return " ".join(f"U+{ord(c):04X}" for c in s)

app = create_app()
with app.app_context():
    print("\n=== Device categories ===")
    for cat in DeviceCategory.query.order_by(DeviceCategory.id):
        print(f"[{cat.id:3}] {cat.name!r}  →  {cat.label}")

    print("\n=== Device models ===")
    for mdl in DeviceModel.query.order_by(DeviceModel.id):
        print(f"[{mdl.id:3}] {mdl.name!r}  (cat {mdl.category.name})")
        print(f"      code‑points: {printable(mdl.name)}")

    print("\n=== Schemas per model ===")
    for mdl in DeviceModel.query.order_by(DeviceModel.id):
        print(f"\n· {mdl.name} (id={mdl.id})")
        for sch in mdl.schemas:
            summary = f"{sch.kind:<8}  v{sch.version:<6}"
            # show top‑level keys of JSON blob so you don’t dump everything
            keys = ", ".join((sch.schema or {}).keys())
            print(f"  - {summary}  keys=[{keys}]")

    print("\nDone ✔︎")
