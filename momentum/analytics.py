"""Shared Amplitude client (official amplitude-analytics SDK).

One instance per process, reused by integrations.track(). The SDK batches and
uploads on its own interval, and flushes on interpreter exit.
"""
from __future__ import annotations

import logging

from amplitude import Amplitude

from . import config

log = logging.getLogger("momentum")

if not config.AMPLITUDE_API_KEY:
    log.warning("[amplitude] AMPLITUDE_API_KEY is not set — no events will be sent")
    client = None
else:
    client = Amplitude(config.AMPLITUDE_API_KEY)
    # server_zone defaults to "US"; set "EU" only for EU-residency projects.
    client.configuration.server_zone = "US"
