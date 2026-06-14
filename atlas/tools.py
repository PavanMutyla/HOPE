import json
import shutil
from pathlib import Path

import aiofiles
import aiofiles.os


def _safe_path(workspace: Path, user_path: str) -> Path:
    resolved = (workspace / user_path).resolve()
    if not str(resolved).startswith(str(workspace.resolve())):
        raise PermissionError(f"Path '{user_path}' is outside the Atlas workspace.")
    return resolved


async def read_file(workspace: Path, path: str) -> str:
    target = _safe_path(workspace, path)
    if not await aiofiles.os.path.exists(target):
        raise FileNotFoundError(f"File not found: {path}")
    async with aiofiles.open(target, "r", encoding="utf-8") as f:
        return await f.read()


async def write_file(workspace: Path, path: str, content: str) -> str:
    target = _safe_path(workspace, path)
    await aiofiles.os.makedirs(target.parent, exist_ok=True)
    async with aiofiles.open(target, "w", encoding="utf-8") as f:
        await f.write(content)
    return f"Written {len(content)} characters to {path}."


async def edit_file(workspace: Path, path: str, old_text: str, new_text: str) -> str:
    target = _safe_path(workspace, path)
    if not await aiofiles.os.path.exists(target):
        raise FileNotFoundError(f"File not found: {path}")
    async with aiofiles.open(target, "r", encoding="utf-8") as f:
        contents = await f.read()
    if old_text not in contents:
        raise ValueError(f"Text to replace not found in {path}.")
    updated = contents.replace(old_text, new_text, 1)
    async with aiofiles.open(target, "w", encoding="utf-8") as f:
        await f.write(updated)
    return f"Edited {path} — replaced the specified text."


async def delete_file(workspace: Path, path: str) -> str:
    target = _safe_path(workspace, path)
    if not await aiofiles.os.path.exists(target):
        raise FileNotFoundError(f"File not found: {path}")
    await aiofiles.os.remove(target)
    return f"Deleted file {path}."


async def list_directory(workspace: Path, path: str = ".") -> str:
    target = _safe_path(workspace, path)
    if not await aiofiles.os.path.isdir(target):
        raise NotADirectoryError(f"Not a directory: {path}")
    entries = await aiofiles.os.listdir(target)
    return json.dumps(sorted(entries))


async def create_directory(workspace: Path, path: str) -> str:
    target = _safe_path(workspace, path)
    await aiofiles.os.makedirs(target, exist_ok=True)
    return f"Created directory {path}."


async def delete_directory(workspace: Path, path: str) -> str:
    target = _safe_path(workspace, path)
    if not await aiofiles.os.path.isdir(target):
        raise NotADirectoryError(f"Not a directory: {path}")
    await aiofiles.os.wrap(shutil.rmtree)(target)
    return f"Deleted directory {path} and all its contents."


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to workspace."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to workspace."},
                    "content": {"type": "string", "description": "Full content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace an exact string within an existing file (first occurrence only).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to workspace."},
                    "old_text": {"type": "string", "description": "Exact text to find and replace."},
                    "new_text": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Permanently delete a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to workspace."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the contents of a directory. Defaults to workspace root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to workspace. Defaults to '.'."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory (and any missing parent directories).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to workspace."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_directory",
            "description": "Permanently delete a directory and all its contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to workspace."}
                },
                "required": ["path"],
            },
        },
    },
]
