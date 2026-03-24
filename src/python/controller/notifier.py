import json
import logging
import threading
import time
import urllib.request
from datetime import UTC, datetime

from model import IModelListener, ModelFile


class WebhookNotifier(IModelListener):
    """Sends webhook POST notifications on file state changes."""

    def __init__(self, config, logger: logging.Logger):
        self._config = config
        self._logger = logger.getChild("WebhookNotifier")
        self._shutdown_flag = False
        self._active_threads = set()
        self._lock = threading.Lock()

    def file_added(self, file: ModelFile):
        pass

    def file_removed(self, file: ModelFile):
        pass

    def file_updated(self, old_file: ModelFile, new_file: ModelFile):
        if old_file.state == new_file.state:
            return

        event_type = None
        if new_file.state == ModelFile.State.DOWNLOADED:
            if self._config.notifications.notify_on_download_complete:
                event_type = "download_complete"
        elif new_file.state == ModelFile.State.EXTRACTED:
            if self._config.notifications.notify_on_extraction_complete:
                event_type = "extraction_complete"
        elif new_file.state == ModelFile.State.EXTRACT_FAILED:
            if self._config.notifications.notify_on_extraction_failed:
                event_type = "extraction_failed"
        elif new_file.state == ModelFile.State.DELETED:
            if self._config.notifications.notify_on_delete_complete:
                event_type = "delete_complete"

        if event_type and self._config.notifications.webhook_url:
            self._fire_webhook(event_type, new_file.name, pair_id=new_file.pair_id, full_path=new_file.full_path)

    def shutdown(self, timeout: float = 5):
        """Drain in-flight webhook threads and prevent new ones from being queued.

        Args:
            timeout: Maximum total seconds to wait for all in-flight threads to complete.
        """
        with self._lock:
            self._shutdown_flag = True
            threads = list(self._active_threads)

        if not threads:
            self._logger.debug("Webhook notifier shutdown: no in-flight threads")
            return

        self._logger.info("Webhook notifier shutting down, waiting for %d in-flight thread(s)", len(threads))
        deadline = time.monotonic() + timeout
        for thread in threads:
            remaining = max(0, deadline - time.monotonic())
            thread.join(timeout=remaining)

        with self._lock:
            still_alive = [t for t in self._active_threads if t.is_alive()]

        if still_alive:
            self._logger.warning(
                "Webhook notifier shutdown: %d thread(s) did not complete within %.1fs timeout",
                len(still_alive),
                timeout,
            )
        else:
            self._logger.info("Webhook notifier shutdown: all threads completed")

    def _fire_webhook(self, event_type: str, filename: str, pair_id: str | None = None, full_path: str | None = None):
        """Fire-and-forget POST in a daemon thread."""
        url = self._config.notifications.webhook_url
        payload = {
            "event_type": event_type,
            "filename": filename,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if pair_id:
            payload["pair_id"] = pair_id
        if full_path:
            payload["path"] = full_path
        thread = threading.Thread(target=self._thread_wrapper, args=(url, payload), daemon=True)
        with self._lock:
            if self._shutdown_flag:
                self._logger.debug("Webhook suppressed during shutdown: %s %s", event_type, filename)
                return
            self._active_threads.add(thread)
        thread.start()

    def _thread_wrapper(self, url: str, payload: dict):
        """Wraps _send_post to track thread lifecycle."""
        try:
            self._send_post(url, payload)
        finally:
            with self._lock:
                self._active_threads.discard(threading.current_thread())

    def _send_post(self, url: str, payload: dict):
        if not url.startswith(("http://", "https://")):
            self._logger.warning("Webhook URL rejected: scheme is not http/https")
            return
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5):
                pass
            self._logger.debug("Webhook sent: %s %s", payload["event_type"], payload["filename"])
        except Exception as e:
            self._logger.warning("Webhook failed: %s", str(e))
