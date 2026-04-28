import json
import logging
import threading
import time
import urllib.request
from datetime import UTC, datetime

from common import Config
from controller.notification_formatters import format_discord, format_telegram
from model import IModelListener, ModelFile


class WebhookNotifier(IModelListener):
    """Sends webhook POST notifications on file state changes."""

    def __init__(self, config: Config, logger: logging.Logger):
        self._config = config
        self._logger = logger.getChild("WebhookNotifier")
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

        event_type = self._resolve_event_type(new_file.state)
        if not event_type:
            return

        if self._config.notifications.webhook_url:
            self._fire_webhook(event_type, new_file.name, pair_id=new_file.pair_id, full_path=new_file.full_path)
        if self._config.notifications.discord_webhook_url:
            self._fire_discord(event_type, new_file.name)
        if self._config.notifications.telegram_bot_token and self._config.notifications.telegram_chat_id:
            self._fire_telegram(event_type, new_file.name)

    def _resolve_event_type(self, state: ModelFile.State) -> str | None:
        """Map a file state to an event type string, gated by config flags."""
        notif = self._config.notifications
        if state == ModelFile.State.DOWNLOADED and notif.notify_on_download_complete:
            return "download_complete"
        if state == ModelFile.State.EXTRACTED and notif.notify_on_extraction_complete:
            return "extraction_complete"
        if state == ModelFile.State.EXTRACT_FAILED and notif.notify_on_extraction_failed:
            return "extraction_failed"
        if state == ModelFile.State.DELETED and notif.notify_on_delete_complete:
            return "delete_complete"
        return None

    def shutdown(self, timeout: float = 5):
        """Drain in-flight webhook threads and prevent new ones from being queued."""
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
        """Fire-and-forget POST of raw webhook payload."""
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
        headers = {"Content-Type": "application/json"}
        body = json.dumps(payload).encode("utf-8")
        self._fire_raw("webhook", url, headers, body)

    def _fire_discord(self, event_type: str, filename: str):
        """Fire-and-forget POST of Discord embed."""
        url = self._config.notifications.discord_webhook_url
        headers, body = format_discord(event_type, filename)
        self._fire_raw("Discord", url, headers, body)

    def _fire_telegram(self, event_type: str, filename: str):
        """Fire-and-forget POST of Telegram message."""
        token = self._config.notifications.telegram_bot_token
        chat_id = self._config.notifications.telegram_chat_id
        url, headers, body = format_telegram(token, chat_id, event_type, filename)
        self._fire_raw("Telegram", url, headers, body)

    def _fire_raw(self, label: str, url: str, headers: dict[str, str], body: bytes):
        """Fire-and-forget POST in a daemon thread."""
        thread = threading.Thread(target=self._thread_wrapper, args=(label, url, headers, body), daemon=True)
        with self._lock:
            if self._shutdown_flag:
                self._logger.debug("%s notification suppressed during shutdown", label)
                return
            self._active_threads.add(thread)
        thread.start()

    def _thread_wrapper(self, label: str, url: str, headers: dict[str, str], body: bytes) -> None:
        try:
            self._send_post(label, url, headers, body)
        finally:
            with self._lock:
                self._active_threads.discard(threading.current_thread())

    def _send_post(self, label: str, url: str, headers: dict[str, str], body: bytes) -> None:
        if not url.startswith(("http://", "https://")):
            self._logger.warning("%s URL rejected: scheme is not http/https", label)
            return
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5):
                pass
            self._logger.debug("%s notification sent", label)
        except Exception as e:
            self._logger.warning("%s notification failed: %s", label, str(e))
