"""
Central, bounded queues that decouple MQTT ingestion from the three
domain-specific managers.  One producer (Paho thread) – many consumers.
"""

from queue import Queue
import os

ACTIONS_Q = Queue(maxsize=int(os.getenv("ACTIONS_Q_SIZE",  1_000)))
CAMERA_Q  = Queue(maxsize=int(os.getenv("CAMERA_Q_SIZE",     500)))
STORAGE_Q = Queue(maxsize=int(os.getenv("STORAGE_Q_SIZE",  1_000)))

# handy tuple for mqtt.py fan-out
ALL_QUEUES = (
    ("⚙️  actions",  ACTIONS_Q),
    ("📸 camera",   CAMERA_Q),
    ("💾 storage",  STORAGE_Q),
)
