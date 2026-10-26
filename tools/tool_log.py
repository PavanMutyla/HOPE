"""Shared by HOPE's tool wrapper (tools/registry.py) and Atlas's own tool
loop, so both write "[tool]" lines the same way."""


def brief_args(arguments: dict, limit: int = 60) -> str:
    """One-line, log-safe view of tool arguments — a write_file's whole
    content would otherwise land in the log."""
    parts = []
    for key, value in (arguments or {}).items():
        text = str(value).replace("\n", " ")
        if len(text) > limit:
            text = text[:limit] + "…"
        parts.append(f"{key}={text!r}" if isinstance(value, str) else f"{key}={text}")
    return ", ".join(parts)
