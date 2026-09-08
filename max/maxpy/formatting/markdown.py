from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from enum import Enum


class ElementType(str, Enum):
    """Markdown element types."""

    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    CODE = "code"
    PRE = "pre"
    LINK = "link"
    MENTION = "mention"
    HASHTAG = "hashtag"
    BOT_COMMAND = "bot_command"
    EMAIL = "email"
    PHONE = "phone"
    TEXT = "text"


@dataclass
class MarkdownElement:
    """Markdown element."""

    type: ElementType
    text: str
    offset: int
    length: int
    data: dict[str, Any] | None = None


class MarkdownFormatter:
    """Parse and format markdown for MAX messages."""

    # Regex patterns
    PATTERNS = {
        ElementType.BOLD: r"\*\*(.+?)\*\*",
        ElementType.ITALIC: r"_(.+?)_",
        ElementType.UNDERLINE: r"__(.+?)__",
        ElementType.STRIKETHROUGH: r"~~(.+?)~~",
        ElementType.CODE: r"`(.+?)`",
        ElementType.PRE: r"```(\w+)?\n(.+?)```",
        ElementType.LINK: r"\[(.+?)\]\((.+?)\)",
    }

    def __init__(self):
        self.elements: list[MarkdownElement] = []

    def parse(self, text: str) -> tuple[str, list[MarkdownElement]]:
        """Parse markdown text into plain text + elements."""
        self.elements = []
        plain_text = text
        offset = 0

        # Simple approach: find and replace patterns
        for elem_type, pattern in self.PATTERNS.items():
            matches = list(re.finditer(pattern, plain_text, re.DOTALL))
            for match in matches:
                if elem_type == ElementType.PRE:
                    lang = match.group(1) or ""
                    content = match.group(2)
                    element = MarkdownElement(
                        type=elem_type,
                        text=content,
                        offset=match.start() + offset,
                        length=len(content),
                        data={"language": lang} if lang else None,
                    )
                    # Replace with plain content
                    replacement = content
                elif elem_type == ElementType.LINK:
                    label = match.group(1)
                    url = match.group(2)
                    element = MarkdownElement(
                        type=elem_type,
                        text=label,
                        offset=match.start() + offset,
                        length=len(label),
                        data={"url": url},
                    )
                    replacement = label
                else:
                    content = match.group(1)
                    element = MarkdownElement(
                        type=elem_type,
                        text=content,
                        offset=match.start() + offset,
                        length=len(content),
                    )
                    replacement = content

                self.elements.append(element)
                # Update plain text
                plain_text = plain_text[:match.start()] + replacement + plain_text[match.end():]
                offset += len(replacement) - (match.end() - match.start())

        # Sort elements by offset
        self.elements.sort(key=lambda e: e.offset)
        return plain_text, self.elements

    def format(self, text: str, parse_mode: str = "markdown") -> tuple[str, list[MarkdownElement]]:
        """Format text for sending."""
        if parse_mode == "markdown":
            return self.parse(text)
        elif parse_mode == "html":
            return self.parse_html(text)
        else:
            return text, []

    def parse_html(self, text: str) -> tuple[str, list[MarkdownElement]]:
        """Parse HTML (subset)."""
        # Simple HTML parsing
        elements = []
        plain = text

        # Bold
        plain = re.sub(r"<b>(.+?)</b>", r"\1", plain)
        # Italic
        plain = re.sub(r"<i>(.+?)</i>", r"\1", plain)
        # Code
        plain = re.sub(r"<code>(.+?)</code>", r"\1", plain)
        # Pre
        plain = re.sub(r"<pre>(.+?)</pre>", r"\1", plain, flags=re.DOTALL)
        # Links
        plain = re.sub(r'<a href="(.+?)">(.+?)</a>', r"\2", plain)

        return plain, elements

    def build_attachments(self, elements: list[MarkdownElement]) -> list[dict]:
        """Build attachment objects from elements."""
        # Convert elements to MAX attachment format
        attachments = []
        for elem in elements:
            if elem.type == ElementType.LINK:
                attachments.append({
                    "type": "inline_keyboard",
                    "buttons": [[{"text": elem.text, "url": elem.data.get("url")}]],
                })
        return attachments


def bold(text: str) -> str:
    return f"**{text}**"


def italic(text: str) -> str:
    return f"_{text}_"


def underline(text: str) -> str:
    return f"__{text}__"


def strikethrough(text: str) -> str:
    return f"~~{text}~~"


def code(text: str) -> str:
    return f"`{text}`"


def pre(text: str, language: str | None = None) -> str:
    if language:
        return f"```{language}\n{text}```"
    return f"```\n{text}```"


def link(text: str, url: str) -> str:
    return f"[{text}]({url})"


def mention(user_id: str, name: str | None = None) -> str:
    return f"[{name or user_id}](tg://user?id={user_id})"


def escape_markdown(text: str) -> str:
    """Escape markdown special characters."""
    chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(chars)}])", r"\\\1", text)