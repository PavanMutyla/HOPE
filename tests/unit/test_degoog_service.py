import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from tools.web import degoog_service
from tools.web.degoog_service import DegoogService, local_port


class FakeRun:
    """Records every subprocess.run call; a git clone creates the checkout."""

    def __init__(self, inspect_rc: int = 1, fail_on: str | None = None):
        self.calls: list[list[str]] = []
        self.inspect_rc = inspect_rc
        self.fail_on = fail_on

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if self.fail_on and self.fail_on in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        if cmd[:2] == ["git", "clone"]:
            target = Path(cmd[-1])
            target.mkdir(parents=True)
            (target / "package.json").write_text("{}")
        if "inspect" in cmd:
            return SimpleNamespace(returncode=self.inspect_rc)
        return SimpleNamespace(returncode=0)


class FakePopen:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append({"cmd": list(cmd), **kwargs})
        return SimpleNamespace(pid=4242, wait=lambda timeout=None: 0)


def make(tmp_path, *, url="http://localhost:4444", bun="/usr/bin/bun", docker=None,
         listening=False, run=None, popen=None):
    return DegoogService(
        url,
        tmp_path / "degoog",
        tmp_path / "logs" / "degoog.log",
        find_bun=lambda: bun,
        find_docker=lambda: docker,
        is_listening=lambda port: listening,
        run=run or FakeRun(),
        popen=popen or FakePopen(),
    )


def installed(service: DegoogService) -> None:
    service.app_dir.mkdir(parents=True)
    (service.app_dir / "package.json").write_text("{}")
    (service.app_dir / ".hope-built").touch()


@pytest.mark.unit
@pytest.mark.parametrize("url, port", [
    ("http://localhost:4444", 4444),
    ("http://127.0.0.1:9000", 9000),
    ("http://localhost", 80),
    ("https://search.example.com", None),
    ("http://192.168.1.5:4444", None),
])
def test_local_port_only_for_this_machine(url, port):
    assert local_port(url) == port


@pytest.mark.unit
def test_remote_url_starts_nothing(tmp_path):
    popen, run = FakePopen(), FakeRun()
    service = make(tmp_path, url="https://search.example.com", run=run, popen=popen)
    service.start()
    assert service.mode is None
    assert popen.calls == [] and run.calls == []


@pytest.mark.unit
def test_already_running_instance_is_used_and_left_alone(tmp_path, monkeypatch):
    popen, run = FakePopen(), FakeRun()
    service = make(tmp_path, listening=True, run=run, popen=popen)
    service.start()
    assert service.mode == "external"
    assert popen.calls == [] and run.calls == []

    killed = []
    monkeypatch.setattr(degoog_service.os, "killpg", lambda *a: killed.append(a))
    service.stop()
    assert killed == [] and run.calls == []


@pytest.mark.unit
def test_installed_native_starts_bound_to_localhost(tmp_path):
    popen, run = FakePopen(), FakeRun()
    service = make(tmp_path, run=run, popen=popen)
    installed(service)
    service.start()

    assert service.mode == "native"
    assert run.calls == []  # nothing to install
    (call,) = popen.calls
    assert call["cmd"] == ["/usr/bin/bun", "run", "start"]
    assert call["cwd"] == service.app_dir
    assert call["env"]["DEGOOG_BIND_ADDRESS"] == "127.0.0.1"
    assert call["env"]["DEGOOG_PORT"] == "4444"
    assert call["start_new_session"] is True


@pytest.mark.unit
def test_first_native_run_clones_installs_and_builds(tmp_path):
    popen, run = FakePopen(), FakeRun()
    service = make(tmp_path, run=run, popen=popen)
    service.start()

    assert [c[:3] for c in run.calls] == [
        ["git", "clone", "--depth"],
        ["/usr/bin/bun", "install"],
        ["/usr/bin/bun", "run", "build"],
    ]
    assert (service.app_dir / ".hope-built").exists()
    assert not service.app_dir.with_name("app.partial").exists()
    assert service.mode == "native"


@pytest.mark.unit
def test_failed_build_leaves_search_off_and_retries_next_time(tmp_path):
    popen = FakePopen()
    service = make(tmp_path, run=FakeRun(fail_on="build"), popen=popen)
    service.start()  # must not raise
    assert service.mode is None
    assert popen.calls == []
    assert not (service.app_dir / ".hope-built").exists()

    retry_run = FakeRun()
    retry = make(tmp_path, run=retry_run, popen=FakePopen())
    retry.start()
    assert ["git", "clone"] not in [c[:2] for c in retry_run.calls]  # checkout is kept
    assert retry.mode == "native"


@pytest.mark.unit
def test_refuses_to_install_over_an_unrelated_folder(tmp_path):
    popen, run = FakePopen(), FakeRun()
    service = make(tmp_path, run=run, popen=popen)
    service.app_dir.mkdir(parents=True)
    (service.app_dir / "something.txt").write_text("not degoog")
    service.start()
    assert service.mode is None
    assert run.calls == []
    assert (service.app_dir / "something.txt").exists()


@pytest.mark.unit
def test_docker_is_only_the_fallback_without_bun(tmp_path):
    run = FakeRun()
    service = make(tmp_path, bun=None, docker="/usr/bin/docker", run=run)
    service.start()

    assert service.mode == "docker"
    docker_run = next(c for c in run.calls if c[1] == "run")
    assert "127.0.0.1:4444:4444" in docker_run
    assert f"{service.docker_data_dir}:/app/data" in docker_run

    service.stop()
    assert run.calls[-1] == ["/usr/bin/docker", "stop", "hope-degoog"]


@pytest.mark.unit
def test_existing_container_is_restarted_not_recreated(tmp_path):
    run = FakeRun(inspect_rc=0)
    service = make(tmp_path, bun=None, docker="/usr/bin/docker", run=run)
    service.start()
    assert ["/usr/bin/docker", "start", "hope-degoog"] in run.calls
    assert not any(c[1] == "run" for c in run.calls)


@pytest.mark.unit
def test_bun_wins_over_docker(tmp_path):
    run = FakeRun()
    service = make(tmp_path, docker="/usr/bin/docker", run=run)
    installed(service)
    service.start()
    assert service.mode == "native"
    assert not any("docker" in c[0] for c in run.calls)


@pytest.mark.unit
def test_neither_bun_nor_docker_turns_search_off(tmp_path):
    popen, run = FakePopen(), FakeRun()
    service = make(tmp_path, bun=None, docker=None, run=run, popen=popen)
    service.start()
    assert service.mode is None
    assert popen.calls == [] and run.calls == []


@pytest.mark.unit
def test_stop_kills_the_whole_native_process_group(tmp_path, monkeypatch):
    service = make(tmp_path)
    installed(service)
    service.start()

    killed = []
    monkeypatch.setattr(degoog_service.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(degoog_service.os, "killpg", lambda pgid, sig: killed.append((pgid, sig)))
    service.stop()
    assert killed == [(4242, degoog_service.signal.SIGTERM)]


@pytest.mark.unit
async def test_wait_ready_reports_when_degoog_answers(tmp_path):
    answers = iter([False, False, True])
    service = make(tmp_path)
    installed(service)
    service.start()
    service._is_listening = lambda port: next(answers)
    assert await service.wait_ready(timeout=5, interval=0.01) is True


@pytest.mark.unit
async def test_wait_ready_gives_up(tmp_path):
    service = make(tmp_path)
    installed(service)
    service.start()
    assert await service.wait_ready(timeout=0.05, interval=0.01) is False


@pytest.mark.unit
def test_settings_password_is_generated_once_and_private(tmp_path):
    service = make(tmp_path)
    first = service.settings_password()
    assert len(first) >= 24
    assert service.settings_password() == first
    assert (tmp_path / "degoog" / "settings-password").stat().st_mode & 0o777 == 0o600


@pytest.mark.unit
def test_native_and_docker_both_get_the_settings_password(tmp_path):
    popen = FakePopen()
    native = make(tmp_path, popen=popen)
    installed(native)
    native.start()
    password = native.settings_password()
    assert popen.calls[0]["env"]["DEGOOG_SETTINGS_PASSWORDS"] == password

    run = FakeRun()
    make(tmp_path, bun=None, docker="/usr/bin/docker", run=run).start()
    docker_run = next(c for c in run.calls if c[1] == "run")
    assert f"DEGOOG_SETTINGS_PASSWORDS={password}" in docker_run


def degoog_api(requests: list, install_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/settings/auth":
            return httpx.Response(200, json={"ok": True, "token": "tok"})
        return httpx.Response(install_status, json={"ok": install_status == 200})
    return httpx.MockTransport(handler)


def running_native(tmp_path, transport):
    service = make(tmp_path)
    service._transport = transport
    installed(service)
    service.start()
    return service


@pytest.mark.unit
async def test_default_engines_installed_once_with_the_password(tmp_path):
    requests: list[httpx.Request] = []
    service = running_native(tmp_path, degoog_api(requests))
    await service.install_default_engines()

    auth, *rest = requests
    assert json.loads(auth.content) == {"password": service.settings_password()}
    installs = [r for r in rest if r.url.path == "/api/store/install"]
    assert [json.loads(r.content)["itemPath"] for r in installs] == [
        f"engines/{e}" for e in degoog_service.DEFAULT_ENGINES
    ]
    assert all(r.headers["x-settings-token"] == "tok" for r in rest)

    requests.clear()
    await service.install_default_engines()
    assert requests == []  # engines changed later in degoog's settings stay changed


@pytest.mark.unit
async def test_unreachable_api_leaves_engines_to_retry_next_start(tmp_path):
    def down(request):
        raise httpx.ConnectError("refused")

    service = running_native(tmp_path, httpx.MockTransport(down))
    await service.install_default_engines()  # must not raise
    assert not (service.app_dir / "data" / ".hope-engines-installed").exists()


@pytest.mark.unit
async def test_warm_up_never_touches_an_instance_it_didnt_start(tmp_path):
    requests: list[httpx.Request] = []
    service = make(tmp_path, listening=True)
    service._transport = degoog_api(requests)
    service.start()
    await service.warm_up()
    assert requests == []


@pytest.mark.unit
async def test_safe_search_is_turned_on_for_every_installed_engine(tmp_path):
    requests: list[httpx.Request] = []
    service = running_native(tmp_path, degoog_api(requests))
    await service.install_default_engines()

    settings = [r for r in requests if r.url.path.endswith("/settings")]
    assert [r.url.path for r in settings] == [
        f"/api/extensions/degoog-org-official-extensions-{e}-engine/settings"
        for e in degoog_service.DEFAULT_ENGINES
    ]
    assert all(json.loads(r.content) == {"safeSearch": "moderate"} for r in settings)


@pytest.mark.unit
async def test_failed_engine_install_skips_its_settings(tmp_path):
    requests: list[httpx.Request] = []
    service = running_native(tmp_path, degoog_api(requests, install_status=400))
    await service.install_default_engines()
    assert not any(r.url.path.endswith("/settings") for r in requests)
