from pathlib import Path

import aiofiles
import aiofiles.os
import send2trash


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
    await aiofiles.os.wrap(send2trash.send2trash)(str(target))
    return f"Moved {path} to trash."


async def list_directory(workspace: Path, path: str = ".") -> str:
    target = _safe_path(workspace, path)
    if not await aiofiles.os.path.isdir(target):
        raise NotADirectoryError(f"Not a directory: {path}")
    entries = sorted(await aiofiles.os.listdir(target))
    if not entries:
        return f"Directory '{path}' is empty."
    lines = []
    for entry in entries:
        kind = "folder" if (target / entry).is_dir() else "file"
        lines.append(f"  {kind}: {entry}")
    return f"Contents of '{path}' ({len(entries)} items):\n" + "\n".join(lines)


async def delete_all_in_directory(workspace: Path, path: str = ".") -> str:
    target = _safe_path(workspace, path)
    if not await aiofiles.os.path.isdir(target):
        raise NotADirectoryError(f"Not a directory: {path}")
    entries = await aiofiles.os.listdir(target)
    if not entries:
        return f"Directory '{path}' is already empty — nothing to delete."
    trashed = []
    for entry in entries:
        entry_path = target / entry
        await aiofiles.os.wrap(send2trash.send2trash)(str(entry_path))
        trashed.append(entry)
    return f"Moved {len(trashed)} items to trash from '{path}': {', '.join(trashed)}."


async def create_directory(workspace: Path, path: str) -> str:
    target = _safe_path(workspace, path)
    await aiofiles.os.makedirs(target, exist_ok=True)
    return f"Created directory {path}."


async def delete_directory(workspace: Path, path: str) -> str:
    target = _safe_path(workspace, path)
    if not await aiofiles.os.path.isdir(target):
        raise NotADirectoryError(f"Not a directory: {path}")
    await aiofiles.os.wrap(send2trash.send2trash)(str(target))
    return f"Moved directory {path} to trash."


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
            "description": "Create or overwrite a FILE (not a folder) with the given content. Always use this when asked to create a file.",
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
            "description": "Create a FOLDER/DIRECTORY only — never use this to create files. Use write_file for files.",
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
            "description": "Permanently delete a single FOLDER and all its contents.",
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
            "name": "delete_all_in_directory",
            "description": "Delete ALL files and folders inside a directory in one call. Use this whenever asked to 'clear', 'empty', or 'delete everything in' a directory. Defaults to workspace root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to workspace. Defaults to '.'."}
                },
                "required": [],
            },
        },
    },
]
