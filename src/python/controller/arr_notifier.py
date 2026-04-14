import json
import logging
import threading
import time
import urllib.request

from common import Config
from model import IModelListener, ModelFile


class ArrNotifier(IModelListener):
    """Notifies Sonarr/Radarr on download completion so they can trigger import scans."""

    def __init__(self, config: Config, logger: logging.Logger):
        self._config = config
        self._logger = logger.getChild("ArrNotifier")
        self._shutdown_flag = False
        self._active_threads: set[threading.Thread] = set()
        self._lock = threading.Lock()

    def file_added(self, file: ModelFile):
        pass

    def file_removed(self, file: ModelFile):
        pass

    def file_updated(self, old_file: ModelFile, new_file: ModelFile):
        if old_file.state == new_file.state:
            return

        if new_file.state != ModelFile.State.DOWNLOADED:
            return

        local_path = new_file.full_path
        cfg = self._config.integrations

        if cfg.sonarr_enabled and cfg.sonarr_url and cfg.sonarr_api_key:
            self._fire_scan(
                service="Sonarr",
                base_url=cfg.sonarr_url,
                api_key=cfg.sonarr_api_key,
                command_name="DownloadedEpisodesScan",
                path=local_path,
            )

        if cfg.radarr_enabled and cfg.radarr_url and cfg.radarr_api_key:
            self._fire_scan(
                service="Radarr",
                base_url=cfg.radarr_url,
                api_key=cfg.radarr_api_key,
                command_name="DownloadedMoviesScan",
                path=local_path,
            )

    def shutdown(self, timeout: float = 5):
        """Drain in-flight threads and prevent new ones."""
        with self._lock:
            self._shutdown_flag = True
            threads = list(self._active_threads)

        if not threads:
            self._logger.debug("Arr notifier shutdown: no in-flight threads")
            return

        self._logger.info("Arr notifier shutting down, waiting for %d in-flight thread(s)", len(threads))
        deadline = time.monotonic() + timeout
        for thread in threads:
            remaining = max(0, deadline - time.monotonic())
            thread.join(timeout=remaining)

        with self._lock:
            still_alive = [t for t in self._active_threads if t.is_alive()]

        if still_alive:
            self._logger.warning(
                "Arr notifier shutdown: %d thread(s) did not complete within %.1fs timeout",
                len(still_alive),
                timeout,
            )
        else:
            self._logger.info("Arr notifier shutdown: all threads completed")

    def _fire_scan(self, service: str, base_url: str, api_key: str, command_name: str, path: str):
        """Fire-and-forget POST in a daemon thread."""
        url = base_url.rstrip("/") + "/api/v3/command"
        payload = {"name": command_name, "path": path}
        thread = threading.Thread(
            target=self._thread_wrapper,
            args=(service, url, api_key, payload),
            daemon=True,
        )
        with self._lock:
            if self._shutdown_flag:
                self._logger.debug("%s scan suppressed during shutdown: %s", service, path)
                return
            self._active_threads.add(thread)
        thread.start()

    def _thread_wrapper(self, service: str, url: str, api_key: str, payload: dict) -> None:
        try:
            self._send_post(service, url, api_key, payload)
        finally:
            with self._lock:
                self._active_threads.discard(threading.current_thread())

    def _send_post(self, service: str, url: str, api_key: str, payload: dict) -> None:
        if not url.startswith(("http://", "https://")):
            self._logger.warning("%s URL rejected: scheme is not http/https", service)
            return
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": api_key,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10):
                pass
            self._logger.debug("%s scan triggered: %s", service, payload.get("path", ""))
        except Exception as e:
            self._logger.warning("%s scan failed: %s", service, str(e))
