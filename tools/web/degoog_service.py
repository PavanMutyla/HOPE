"""DegoogService — starts a local degoog with HOPE, the way hope.py starts the dashboard.

What start() does, first match wins:

1. degoog_url isn't localhost         → nothing; it's someone else's instance.
2. something already answers the port → use it, and leave it running on shutdown.
3. Bun is installed                   → run degoog natively from degoog_dir/app,
                                        cloning and building it on the first run.
4. Docker is installed                → run the official image, bound to 127.0.0.1.
5. neither                            → warn; search tools say degoog isn't reachable.

Docker is only the fallback, never installed for you: Bun is a user-level
install (no sudo), and degoog is a Bun app, so native is the lighter path.

Either way degoog listens on 127.0.0.1 only, and its settings page is
password-gated: HOPE generates the password once and keeps it in
degoog_dir/settings-password (mode 600) — sign in with it at
http://localhost:4444/settings to change engines yourself.

A fresh degoog has no search engines at all — they're extensions from its
store. warm_up() logs in once and installs DEFAULT_ENGINES with SafeSearch
on, then never again, so engines you add or remove in degoog's settings stay that way.

stop() only stops what start() started.
"""

import asyncio
import os
import secrets
import shutil
import signal
import socket
import subprocess
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import httpx
from loguru import logger

_REPO = "https://github.com/degoog-org/degoog.git"
_IMAGE = "ghcr.io/degoog-org/degoog:latest"
_CONTAINER = "hope-degoog"
_BUILT_MARKER = ".hope-built"  # written after a successful install + build
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_STORE_REPO = "https://github.com/degoog-org/official-extensions.git"
# The engines from degoog's official store that answer with no extra setup.
# Left out, as tested: brave (needs curl-impersonate), google and startpage
# (both answer bots with a JavaScript/anti-bot interstitial).
DEFAULT_ENGINES = ("bing", "duckduckgo", "wikipedia")
# Engines default to safeSearch "off", and with it off a plain query like
# "kokoro tts voices" came back with porn sites — junk for a researcher to read.
_SAFE_SEARCH = "moderate"


def find_bun() -> str | None:
    found = shutil.which("bun")
    if found:
        return found
    # bun.sh's installer puts it here, and a fresh shell isn't needed to use it.
    # Reflex downloads its own copy for the dashboard, which works just as well.
    for candidate in (
        Path.home() / ".bun/bin/bun",
        Path.home() / ".local/share/reflex/bun/bin/bun",
    ):
        if candidate.exists():
            return str(candidate)
    return None


def find_docker() -> str | None:
    return shutil.which("docker")


def is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def local_port(url: str) -> int | None:
    """The port degoog_url points at on this machine, or None if it's remote."""
    parsed = urlparse(url)
    if parsed.hostname not in _LOCAL_HOSTS:
        return None
    return parsed.port or (443 if parsed.scheme == "https" else 80)


class DegoogService:
    def __init__(
        self,
        url: str,
        directory: str | Path,
        log_path: str | Path,
        find_bun: Callable[[], str | None] = find_bun,
        find_docker: Callable[[], str | None] = find_docker,
        is_listening: Callable[[int], bool] = is_listening,
        run=subprocess.run,
        popen=subprocess.Popen,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = url
        self._dir = Path(directory)
        self._log_path = Path(log_path)
        self._find_bun = find_bun
        self._find_docker = find_docker
        self._is_listening = is_listening
        self._run = run
        self._popen = popen
        self._transport = transport
        self._port: int | None = None
        self._proc: subprocess.Popen | None = None
        self._docker: str | None = None  # set only when start() ran the container
        self.mode: str | None = None  # "external" | "native" | "docker" | None

    @property
    def app_dir(self) -> Path:
        return self._dir / "app"

    @property
    def docker_data_dir(self) -> Path:
        return self._dir / "docker-data"

    def settings_password(self) -> str:
        path = self._dir / "settings-password"
        if path.exists():
            return path.read_text().strip()
        self._dir.mkdir(parents=True, exist_ok=True)
        password = secrets.token_urlsafe(24)
        path.touch(mode=0o600)
        path.write_text(password)
        return password

    def start(self) -> None:
        """Blocking. Fast once installed; the first native run clones and
        builds degoog, which takes a minute or so."""
        self._port = local_port(self._url)
        if self._port is None:
            logger.info(f"[degoog] {self._url} isn't local, not starting one")
            return
        if self._is_listening(self._port):
            self.mode = "external"
            logger.info(f"[degoog] Already running on :{self._port}, using it")
            return

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if bun := self._find_bun():
                self._start_native(bun)
            elif docker := self._find_docker():
                self._start_docker(docker)
            else:
                logger.warning("[degoog] Neither Bun nor Docker found, web search is off")
                print(
                    "Web search is off: install Bun (curl -fsSL https://bun.sh/install | bash) "
                    "and restart HOPE."
                )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning(f"[degoog] Couldn't start: {exc}. Web search is off (see {self._log_path})")
            print(f"Web search is off: degoog didn't start. Details in {self._log_path}")

    def _start_native(self, bun: str) -> None:
        if not (self.app_dir / _BUILT_MARKER).exists():
            self._install(bun)
        env = {
            **os.environ,
            "DEGOOG_BIND_ADDRESS": "127.0.0.1",
            "DEGOOG_PORT": str(self._port),
            "DEGOOG_SETTINGS_PASSWORDS": self.settings_password(),
        }
        with open(self._log_path, "ab") as log:
            self._proc = self._popen(
                [bun, "run", "start"],
                cwd=self.app_dir,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # so stop() can kill bun's children too
            )
        self.mode = "native"
        logger.info(f"[degoog] Started natively (pid {self._proc.pid}) on 127.0.0.1:{self._port}")

    def _install(self, bun: str) -> None:
        print("Setting up degoog for web search (first run only, about a minute)…")
        logger.info(f"[degoog] Installing into {self.app_dir}")
        if not (self.app_dir / "package.json").exists():
            if self.app_dir.exists() and any(self.app_dir.iterdir()):
                raise OSError(f"{self.app_dir} exists but isn't a degoog checkout")
            # Clone beside it and rename, so an interrupted clone never looks installed.
            partial = self.app_dir.with_name(self.app_dir.name + ".partial")
            shutil.rmtree(partial, ignore_errors=True)
            self._logged(["git", "clone", "--depth", "1", _REPO, str(partial)])
            partial.rename(self.app_dir)
        self._logged([bun, "install"], cwd=self.app_dir)
        self._logged([bun, "run", "build"], cwd=self.app_dir)
        (self.app_dir / _BUILT_MARKER).touch()
        logger.info("[degoog] Installed")

    def _start_docker(self, docker: str) -> None:
        exists = self._run(
            [docker, "container", "inspect", _CONTAINER], capture_output=True
        ).returncode == 0
        if exists:
            self._logged([docker, "start", _CONTAINER])
        else:
            print("Starting degoog in Docker (first run pulls the image)…")
            self.docker_data_dir.mkdir(parents=True, exist_ok=True)
            self._logged([
                docker, "run", "-d", "--name", _CONTAINER,
                "-p", f"127.0.0.1:{self._port}:4444",
                "-v", f"{self.docker_data_dir}:/app/data",
                "-e", f"DEGOOG_SETTINGS_PASSWORDS={self.settings_password()}",
                _IMAGE,
            ])
        self._docker = docker
        self.mode = "docker"
        logger.info(f"[degoog] Started in Docker ({_CONTAINER}) on 127.0.0.1:{self._port}")

    def _logged(self, cmd: list[str], cwd: Path | None = None) -> None:
        """Runs a setup command with its output going to degoog's log, not
        this terminal (which belongs to the dashboard). Raises on failure."""
        with open(self._log_path, "ab") as log:
            self._run(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)

    async def warm_up(self) -> None:
        """Runs in the background from hope.py: wait for degoog, then make
        sure it has engines to search with."""
        if await self.wait_ready() and self.mode in ("native", "docker"):
            await self.install_default_engines()

    async def install_default_engines(self) -> None:
        """Once per data dir. Best-effort: a failure leaves search returning
        no results, which the log says how to fix, and is retried next start."""
        data_dir = self.app_dir / "data" if self.mode == "native" else self.docker_data_dir
        marker = data_dir / ".hope-engines-installed"
        if marker.exists():
            return
        try:
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{self._port}", timeout=30, transport=self._transport
            ) as client:
                auth = await client.post(
                    "/api/settings/auth", json={"password": self.settings_password()}
                )
                auth.raise_for_status()
                headers = {"x-settings-token": auth.json()["token"]}
                for engine in DEFAULT_ENGINES:
                    response = await client.post("/api/store/install", headers=headers, json={
                        "repoUrl": _STORE_REPO, "itemPath": f"engines/{engine}", "type": "engine",
                    })
                    if not response.is_success:
                        logger.warning(f"[degoog] Engine {engine} didn't install: {response.text[:200]}")
                        continue
                    # Engines without a safeSearch setting (wikipedia) just ignore the key.
                    await client.post(
                        f"/api/extensions/degoog-org-official-extensions-{engine}-engine/settings",
                        headers=headers, json={"safeSearch": _SAFE_SEARCH},
                    )
                    logger.info(f"[degoog] Installed engine: {engine} (SafeSearch {_SAFE_SEARCH})")
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning(
                f"[degoog] Couldn't install search engines ({exc}). Searches will come back "
                f"empty until engines are added at http://localhost:{self._port}/settings"
            )
            return
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()

    async def wait_ready(self, timeout: float = 60.0, interval: float = 0.5) -> bool:
        """Logs when degoog starts answering. HOPE doesn't wait on this —
        a search before then just reports degoog isn't reachable yet."""
        if self._port is None or self.mode in (None, "external"):
            return self.mode == "external"
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            if await asyncio.to_thread(self._is_listening, self._port):
                logger.info(f"[degoog] Ready on 127.0.0.1:{self._port}")
                return True
            await asyncio.sleep(interval)
        logger.warning(f"[degoog] Not answering after {timeout:.0f}s, see {self._log_path}")
        return False

    def stop(self) -> None:
        if self._proc is not None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                self._proc.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self._proc = None
        if self._docker is not None:
            try:
                self._run([self._docker, "stop", _CONTAINER], capture_output=True, timeout=20)
            except (OSError, subprocess.SubprocessError):
                logger.exception("[degoog] Couldn't stop the container")
            self._docker = None
