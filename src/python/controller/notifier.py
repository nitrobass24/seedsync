import json
import logging
import threading
import urllib.request
from datetime import datetime, timezone

from model import IModelListener, ModelFile


class WebhookNotifier(IModelListener):
    """Sends webhook POST notifications on file state changes."""

    def __init__(self, config, logger: logging.Logger):
        self._config = config
        self._logger = logger.getChild("WebhookNotifier")

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
            self._fire_webhook(event_type, new_file.name,
                               pair_id=new_file.pair_id,
                               full_path=new_file.full_path)

    def _fire_webhook(self, event_type: str, filename: str,
                       pair_id: str = None, full_path: str = None):
        """Fire-and-forget POST in a daemon thread."""
        url = self._config.notifications.webhook_url
        payload = {
            "event_type": event_type,
            "filename": filename,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if pair_id:
            payload["pair_id"] = pair_id
        if full_path:
            payload["path"] = full_path
        thread = threading.Thread(
            target=self._send_post,
            args=(url, payload),
            daemon=True
        )
        thread.start()

    def _send_post(self, url: str, payload: dict):
        if not url.startswith(("http://", "https://")):
            self._logger.warning("Webhook URL rejected: scheme is not http/https")
            return
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
            self._logger.debug("Webhook sent: %s %s", payload["event_type"], payload["filename"])
        except Exception as e:
            self._logger.warning("Webhook failed: %s", str(e))
