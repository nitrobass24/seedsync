import json
import unittest

from controller.notification_formatters import (
    DISCORD_COLORS,
    EVENT_LABELS,
    format_discord,
    format_telegram,
)


class TestFormatDiscord(unittest.TestCase):
    def test_returns_json_content_type(self):
        headers, _ = format_discord("download_complete", "file.mkv")
        self.assertEqual("application/json", headers["Content-Type"])

    def test_body_is_valid_json(self):
        _, body = format_discord("download_complete", "file.mkv")
        payload = json.loads(body)
        self.assertIn("embeds", payload)
        self.assertEqual(1, len(payload["embeds"]))

    def test_embed_title_contains_event_label(self):
        for event_type, label in EVENT_LABELS.items():
            _, body = format_discord(event_type, "file.mkv")
            embed = json.loads(body)["embeds"][0]
            self.assertIn(label, embed["title"], msg=event_type)

    def test_embed_description_contains_filename(self):
        _, body = format_discord("download_complete", "Movie.2024.mkv")
        embed = json.loads(body)["embeds"][0]
        self.assertIn("Movie.2024.mkv", embed["description"])

    def test_embed_color_matches_event_type(self):
        for event_type, color in DISCORD_COLORS.items():
            _, body = format_discord(event_type, "f")
            embed = json.loads(body)["embeds"][0]
            self.assertEqual(color, embed["color"], msg=event_type)

    def test_embed_has_timestamp(self):
        _, body = format_discord("test", "f", timestamp="2026-01-01T00:00:00+00:00")
        embed = json.loads(body)["embeds"][0]
        self.assertEqual("2026-01-01T00:00:00+00:00", embed["timestamp"])

    def test_unknown_event_type_uses_raw_string(self):
        _, body = format_discord("custom_event", "f")
        embed = json.loads(body)["embeds"][0]
        self.assertIn("custom_event", embed["title"])


class TestFormatTelegram(unittest.TestCase):
    def test_url_contains_bot_token(self):
        url, _, _ = format_telegram("TOKEN123", "CHAT456", "download_complete", "file.mkv")
        self.assertEqual("https://api.telegram.org/botTOKEN123/sendMessage", url)

    def test_body_contains_chat_id(self):
        _, _, body = format_telegram("tok", "12345", "download_complete", "file.mkv")
        payload = json.loads(body)
        self.assertEqual("12345", payload["chat_id"])

    def test_body_uses_markdown_parse_mode(self):
        _, _, body = format_telegram("tok", "id", "download_complete", "file.mkv")
        payload = json.loads(body)
        self.assertEqual("Markdown", payload["parse_mode"])

    def test_text_contains_filename(self):
        _, _, body = format_telegram("tok", "id", "download_complete", "Movie.2024.mkv")
        payload = json.loads(body)
        self.assertIn("Movie.2024.mkv", payload["text"])

    def test_text_contains_event_label(self):
        for event_type, label in EVENT_LABELS.items():
            _, _, body = format_telegram("tok", "id", event_type, "f")
            payload = json.loads(body)
            self.assertIn(label, payload["text"], msg=event_type)

    def test_returns_json_content_type(self):
        _, headers, _ = format_telegram("tok", "id", "test", "f")
        self.assertEqual("application/json", headers["Content-Type"])


if __name__ == "__main__":
    unittest.main()
