import json
import logging
import os
import threading
import time
import urllib.request

from common import ArrInstance, IntegrationsConfig, PathPair, PathPairsConfig
from model import IModelListener, ModelFile


class ArrNotifier(IModelListener):
    """Notifies *arr instances on download completion so they can trigger import scans.

    Routing: a completed file is mapped to its pair via `pair_id`, and the scan
    is dispatched to every enabled instance referenced by that pair's
    `arr_target_ids`. Files outside any path pair are skipped.
    """

    _COMMAND_BY_KIND: dict[str, tuple[str, str]] = {
        # kind -> (display name, *arr command name)
        ArrInstance.KIND_SONARR: ("Sonarr", "DownloadedEpisodesScan"),
        ArrInstance.KIND_RADARR: ("Radarr", "DownloadedMoviesScan"),
    }

    def __init__(
        self,
        integrations_config: IntegrationsConfig,
        path_pairs_config: PathPairsConfig,
        logger: logging.Logger,
    ):
        self._integrations_config = integrations_config
        self._path_pairs_config = path_pairs_config
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
        if not new_file.pair_id:
            return  # orphan file, no pair → no instance routing possible

        pair = self._path_pairs_config.get_pair(new_file.pair_id)
        if pair is None or not pair.arr_target_ids:
            return

        instances_by_id = {i.id: i for i in self._integrations_config.instances}
        local_path = self._resolve_local_path(pair, new_file)

        for target_id in pair.arr_target_ids:
            instance = instances_by_id.get(target_id)
            if instance is None:
                self._logger.debug("Pair %r references unknown *arr instance %s", pair.name, target_id)
                continue
            if not instance.enabled or not instance.url or not instance.api_key:
                continue
            command = self._COMMAND_BY_KIND.get(instance.kind)
            if command is None:
                self._logger.warning("Unknown *arr kind %r for instance %s", instance.kind, instance.name)
                continue
            display_name, command_name = command
            label = f"{display_name} ({instance.name})" if instance.name else display_name
            self._fire_scan(
                service=label,
                base_url=instance.url,
                api_key=instance.api_key,
                command_name=command_name,
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

    @staticmethod
    def _resolve_local_path(pair: PathPair, file: ModelFile) -> str:
        base = pair.local_path or ""
        return os.path.join(base, file.full_path) if base else file.full_path

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
            thread.start()
            self._active_threads.add(thread)

    def _thread_wrapper(self, service: str, url: str, api_key: str, payload: dict[str, str]) -> None:
        try:
            self._send_post(service, url, api_key, payload)
        finally:
            with self._lock:
                self._active_threads.discard(threading.current_thread())

    def _send_post(self, service: str, url: str, api_key: str, payload: dict[str, str]) -> None:
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
        except Exception:
            self._logger.exception("%s scan failed", service)
