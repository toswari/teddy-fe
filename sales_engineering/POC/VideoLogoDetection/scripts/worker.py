"""Legacy worker placeholder.

Background tasks now run via the in-process queue defined in app.background_queue,
so no external worker process is required. This script remains as documentation for
previous setups and intentionally does nothing.
"""

if __name__ == "__main__":
    print("Background tasks execute in-process; no worker process is necessary.")