"""Command parsing. Knows nothing about rendering or the sim."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatCommand:
    """A parsed chat command. The single message type on the command queue,
    produced by both the Twitch thread and the dev injector."""

    cmd: str
    args: list[str] = field(default_factory=list)
    author: str = ""


# Speak-feature seam: the `!say <message>` command flows through this same
# parser (cmd="say", the message is `" ".join(parsed.args)`) and is dispatched
# by World._cmd_say. A future Twitch Channel-Points redemption source would
# build the SAME ChatCommand(cmd="say", args=[...], author=...) and enqueue it on
# the command queue -- no change to the parser or the world handler is needed,
# only a new producer (EventSub channel-point redemption -> ChatCommand) feeding
# the existing queue.
def parse_command(content: str, author: str = "") -> ChatCommand | None:
    """Return a ChatCommand for a `!`-prefixed message, else None."""
    content = content.strip()
    if not content.startswith("!"):
        return None
    parts = content[1:].split()
    if not parts:
        return None
    return ChatCommand(cmd=parts[0].lower(), args=parts[1:], author=author.lower())


def normalize_target(raw: str) -> str:
    """Resolve a command target like '@SomeUser' to a bare lowercase username."""
    return raw.lstrip("@").lower()
