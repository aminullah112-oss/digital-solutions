"""gunicorn config for the build API.

sync workers, not threads or async: each worker is a separate OS process
with its own FreeCAD C++ state, which is what keeps concurrent requests
from corrupting each other (FreeCAD is not meant to be driven from
multiple threads in one process) and what keeps a native crash on
pathological geometry contained to the one worker handling it.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', 8000)}"
workers = int(os.environ.get("WEB_CONCURRENCY", 2))
worker_class = "sync"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 60))  # a build should take low single-digit seconds
graceful_timeout = 30
max_requests = 200  # recycle workers periodically -- cheap insurance against slow memory growth in long-lived OCCT state
max_requests_jitter = 20
