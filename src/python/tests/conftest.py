"""
Global test configuration.

Sets the multiprocessing start method to 'spawn' to match production
behavior (see seedsync.py). This ensures tests catch any pickling or
cross-process issues that would occur in the real application.
"""

import multiprocessing


def pytest_configure(config):
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        current = multiprocessing.get_start_method()
        if current != "spawn":
            raise RuntimeError(
                f"Cannot set multiprocessing start method to 'spawn'; "
                f"current method is '{current}'. Tests require spawn."
            )
