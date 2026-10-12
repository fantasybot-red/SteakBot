"""
Message catalog.

All user-facing strings live in ``src/messages.json``, organised into nested
groups, and rendered with ``string.Template`` (``${name}``) substitution. This
keeps copy out of the code and makes it easy to tweak wording or translate.

Keys are **dotted paths** into the JSON, e.g. ``"leaderboard.title"`` or
``"revive.button_label"``.

A value may be:
  * a string                    -> ``messages.get(key, **kwargs)``
  * a list of strings           -> ``get`` picks one string at random
  * an object ``{title, body}`` -> ``messages.group(key, **kwargs)``
  * a list of objects
    ``[{...}, {...}]``           -> ``group`` picks one object at random, so the
                                   title + body of a variant stay matched

Usage:
    from utils import messages

    messages.get("revive.button_label", revives=2)
    title_body = messages.group("reminder", guild="X", count=12, hours=2)
    embed_title = title_body["title"]
"""

import json
import os
import random
from string import Template


class Messages:
    """Loads ``messages.json`` and renders templates by dotted key path."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "messages.json"
        )
        with open(self.path, encoding="utf-8") as f:
            self._messages: dict = json.load(f)

    def _resolve(self, key: str):
        """Walk a dotted key path into the message tree."""
        node = self._messages
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(
                    f"Không tìm thấy mẫu tin nhắn '{key}' trong messages.json"
                )
            node = node[part]
        return node

    @staticmethod
    def _render(template_str: str, **kwargs) -> str:
        template = Template(template_str)
        if not kwargs:
            return template.template
        return template.safe_substitute(**kwargs)

    def raw(self, key: str) -> str:
        """
        Return a raw template string for a dotted key. If the value is a list of
        strings, one is picked at random. Use ``group`` for ``{title, body}``.
        """
        value = self._resolve(key)
        if isinstance(value, list):
            if not value:
                raise ValueError(f"Mẫu tin nhắn '{key}' là danh sách rỗng.")
            return random.choice(value)
        if not isinstance(value, str):
            raise ValueError(f"Mẫu tin nhắn '{key}' không phải là chuỗi.")
        return value

    def get(self, key: str, **kwargs) -> str:
        """Render a single-string (or list-of-strings) message template."""
        return self._render(self.raw(key), **kwargs)

    def group(self, key: str, **kwargs) -> dict[str, str]:
        """
        Render a group of fields (e.g. ``{"title": ..., "body": ...}``).

        * If the value is a single object, it is used directly (locked).
        * If the value is a **list of objects**, one is picked at random, so the
          title and body of a variant always stay matched.

        Every field in the chosen object is rendered with the given kwargs.
        """
        node = self._resolve(key)

        if isinstance(node, list):
            if not node or not isinstance(node[0], dict):
                raise ValueError(
                    f"Mẫu tin nhắn '{key}' phải là danh sách các object {{...}}."
                )
            node = random.choice(node)

        if not isinstance(node, dict):
            raise ValueError(
                f"Mẫu tin nhắn '{key}' phải là object hoặc danh sách object."
            )

        return {field: self._render(text, **kwargs) for field, text in node.items()}


# Module-level singleton used across the bot.
messages = Messages()
