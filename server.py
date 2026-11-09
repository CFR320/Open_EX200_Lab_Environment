#!/usr/bin/env python3
"""Local web app and SSH-based grader for the EX200 practice lab."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from checks import CHECKS

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "data/questions.json").read_text(encoding="utf-8"))
STATIC = ROOT / "static"
ATTEMPT_SECONDS = 3 * 60 * 60
QUESTION_COUNT = 24
POINTS_PER_QUESTION = 12.5
ATTEMPTS: dict[str, dict[str, Any]] = {}
ATTEMPTS_LOCK = threading.Lock()
VAGRANT = os.environ.get("VAGRANT", "vagrant")
MACHINES = {"gateway", "node1", "node2"}
PROVIDERS = {"virtualbox", "vmware_desktop", "hyperv"}
ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.environ.get(
        "EX200_ALLOWED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,"
        "http://127.0.0.1:8080,http://localhost:8080",
    ).split(",")
    if origin.strip()
}
LAB_LOCK = threading.Lock()
MACHINE_STATUS_CACHE_SECONDS = 60
MACHINE_STATUS_CACHE: tuple[float, dict[str, str], str | None] | None = None
LAB_OPERATION: dict[str, Any] = {
    "id": None,
    "action": None,
    "provider": None,
    "phase": "idle",
    "running": False,
    "success": None,
    "error": None,
    "output": [],
}
CONSOLE_PROXIES: list[subprocess.Popen[bytes]] = []


def novnc_root() -> Path:
    configured = os.environ.get("EX200_NOVNC_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise RuntimeError("LOCALAPPDATA no está definido; configura EX200_NOVNC_PATH.")
        return Path(local_app_data) / "EX200Lab" / "noVNC"
    return Path.home() / ".local" / "share" / "ex200-lab" / "noVNC"


def console_proxy_command(web_root: Path, web_port: int, vnc_port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "websockify",
        "--web",
        str(web_root),
        "--heartbeat",
        "30",
        f"127.0.0.1:{web_port}",
        f"127.0.0.1:{vnc_port}",
    ]


def start_console_proxies() -> None:
    web_root = novnc_root()
    if not (web_root / "vnc.html").is_file():
        raise RuntimeError(
            f"No se encontró noVNC en {web_root}. Ejecuta scripts/setup_novnc.ps1 "
            "o configura EX200_NOVNC_PATH."
        )
    if importlib.util.find_spec("websockify") is None:
        raise RuntimeError(
            "No está instalado websockify. Ejecuta scripts/setup_novnc.ps1 "
            "para instalar las dependencias de las consolas."
        )

    log_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "EX200Lab" / "logs"
    if os.name != "nt":
        log_dir = Path.home() / ".local" / "state" / "ex200-lab"
    log_dir.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        web_port = 6081 + index
        vnc_port = 5901 + index
        log_path = log_dir / f"websockify-{web_port}.log"
        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                console_proxy_command(web_root, web_port, vnc_port),
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        CONSOLE_PROXIES.append(process)

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stop_console_proxies()
                try:
                    details = log_path.read_text(encoding="utf-8")[-2000:]
                except OSError:
                    details = ""
                raise RuntimeError(
                    f"No se pudo iniciar el proxy noVNC en 127.0.0.1:{web_port}."
                    + (f"\n{details}" if details else "")
                )
            try:
                with socket.create_connection(("127.0.0.1", web_port), timeout=0.25):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            stop_console_proxies()
            raise RuntimeError(f"El proxy noVNC no abrió 127.0.0.1:{web_port} a tiempo.")


def stop_console_proxies() -> None:
    while CONSOLE_PROXIES:
        process = CONSOLE_PROXIES.pop()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def new_attempt() -> dict[str, Any]:
    mandatory = [question for question in QUESTIONS if question["number"] <= 20]
    optional = [question for question in QUESTIONS if question["number"] > 20]
    selected = mandatory + secrets.SystemRandom().sample(optional, QUESTION_COUNT - len(mandatory))
    secrets.SystemRandom().shuffle(selected)
    attempt_id = secrets.token_urlsafe(24)
    started_at = time.time()
    attempt = {
        "id": attempt_id,
        "started_at": started_at,
        "deadline": started_at + ATTEMPT_SECONDS,
        "question_ids": [question["id"] for question in selected],
        "result": None,
        "grading": False,
    }
    with ATTEMPTS_LOCK:
        ATTEMPTS[attempt_id] = attempt
    return {
        "id": attempt_id,
        "started_at": started_at,
        "deadline": attempt["deadline"],
        "duration_seconds": ATTEMPT_SECONDS,
        "questions": [{**question, "points": POINTS_PER_QUESTION} for question in selected],
    }


def make_check_script(question_ids: list[str]) -> str:
    lines = ["set +e"]
    for question_id in question_ids:
        check = CHECKS[question_id]
        lines.extend(
            [
                "(",
                check,
                ") >/dev/null 2>&1",
                "status=$?",
                f"printf '__EX200_RESULT__{question_id}:%s\\n' \"$status\"",
            ]
        )
    return "\n".join(lines) + "\n"


def vagrant_ssh_config(machine: str) -> dict[str, str]:
    if machine not in {"node1", "node2"}:
        raise ValueError(f"Nodo no permitido: {machine}")
    completed = subprocess.run(
        [VAGRANT, "ssh-config", machine],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    config: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        match = re.match(r"^\s*(HostName|User|Port|IdentityFile)\s+(.+?)\s*$", line)
        if match:
            config[match.group(1)] = shlex.split(match.group(2))[0]
    required = {"HostName", "User", "Port", "IdentityFile"}
    if not required.issubset(config):
        raise RuntimeError(f"Vagrant no devolvió una configuración SSH completa para {machine}.")
    return config


def run_checks(machine: str, question_ids: list[str]) -> dict[str, bool]:
    config = vagrant_ssh_config(machine)
    command = [
        "ssh",
        "-p",
        config["Port"],
        "-i",
        config["IdentityFile"],
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        f'{config["User"]}@{config["HostName"]}',
        "sudo -n bash -s",
    ]
    completed = subprocess.run(
        command,
        input=make_check_script(question_ids),
        capture_output=True,
        text=True,
        timeout=90,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or "sin detalles adicionales"
        raise RuntimeError(f"No se pudo validar {machine} por SSH: {detail}")
    results: dict[str, bool] = {}
    for line in completed.stdout.splitlines():
        match = re.fullmatch(r"__EX200_RESULT__([a-z0-9-]+):([0-9]+)", line)
        if match:
            results[match.group(1)] = match.group(2) == "0"
    if set(results) != set(question_ids):
        raise RuntimeError(f"El nodo {machine} no devolvió todos los resultados de validación.")
    return results


def grade_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    selected = [question_id for question_id in attempt["question_ids"]]
    by_node: dict[str, list[str]] = {"node1": [], "node2": []}
    question_by_id = {question["id"]: question for question in QUESTIONS}
    for question_id in selected:
        by_node[question_by_id[question_id]["node"]].append(question_id)

    checks: dict[str, bool] = {}
    for machine, question_ids in by_node.items():
        if question_ids:
            checks.update(run_checks(machine, question_ids))

    details = [
        {
            "id": question_id,
            "passed": checks[question_id],
            "points": POINTS_PER_QUESTION if checks[question_id] else 0,
        }
        for question_id in selected
    ]
    score = sum(item["points"] for item in details)
    return {
        "score": score,
        "maximum": 300,
        "passed": score >= 210,
        "correct": sum(item["passed"] for item in details),
        "total": len(details),
        "details": details,
    }


def machine_status() -> tuple[dict[str, str], str | None]:
    completed = subprocess.run(
        [VAGRANT, "status", "--machine-readable"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    states: dict[str, str] = {}
    providers: set[str] = set()
    for row in csv.reader(io.StringIO(completed.stdout)):
        if len(row) >= 4 and row[1] in MACHINES:
            if row[2] == "state":
                states[row[1]] = row[3]
            elif row[2] == "provider-name" and row[3] in PROVIDERS:
                providers.add(row[3])
    if set(states) != MACHINES:
        raise RuntimeError("Vagrant no devolvió el estado de las tres máquinas.")
    if len(providers) > 1:
        raise RuntimeError("Las máquinas del laboratorio usan proveedores distintos.")
    return states, next(iter(providers), None)


def machine_states() -> dict[str, str]:
    return machine_status()[0]


def configured_console_urls() -> dict[str, dict[str, str]]:
    raw_urls = os.environ.get("EX200_CONSOLE_URLS")
    if raw_urls is None:
        return {
            "vmware_desktop": {
                "gateway": "http://127.0.0.1:6081/vnc.html?autoconnect=1",
                "node1": "http://127.0.0.1:6082/vnc.html?autoconnect=1",
                "node2": "http://127.0.0.1:6083/vnc.html?autoconnect=1",
            }
        }
    try:
        value = json.loads(raw_urls)
    except json.JSONDecodeError as error:
        raise RuntimeError("EX200_CONSOLE_URLS debe contener un objeto JSON válido.") from error
    if not isinstance(value, dict):
        raise RuntimeError("EX200_CONSOLE_URLS debe ser un objeto JSON.")

    urls: dict[str, dict[str, str]] = {}
    for provider, machine_urls in value.items():
        if provider not in PROVIDERS or not isinstance(machine_urls, dict):
            raise RuntimeError(f"Configuración de consola no válida para {provider}.")
        urls[provider] = {}
        for machine, url in machine_urls.items():
            parsed = urlparse(url) if isinstance(url, str) else None
            if (
                machine not in MACHINES
                or parsed is None
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise RuntimeError(f"URL de consola no válida para {provider}/{machine}.")
            urls[provider][machine] = url
    return urls


def lab_status() -> dict[str, Any]:
    global MACHINE_STATUS_CACHE
    with LAB_LOCK:
        operation = {**LAB_OPERATION, "output": list(LAB_OPERATION["output"])}
        if operation["running"]:
            return {
                **operation,
                "machines": {},
                "provider": operation["provider"],
                "consoles": {},
                "ready": False,
                "status_error": None,
            }
        cached_status = MACHINE_STATUS_CACHE
        if (
            cached_status is not None
            and time.monotonic() - cached_status[0] < MACHINE_STATUS_CACHE_SECONDS
        ):
            _, states, provider = cached_status
            states = dict(states)
            status_error = None
        else:
            try:
                states, provider = machine_status()
            except (OSError, subprocess.SubprocessError, RuntimeError) as error:
                states = {}
                provider = (
                    operation["provider"]
                    if operation["provider"] in PROVIDERS
                    else cached_status[2] if cached_status else None
                )
                status_error = str(error)
            else:
                MACHINE_STATUS_CACHE = (time.monotonic(), dict(states), provider)
                status_error = None
        try:
            consoles = configured_console_urls().get(provider, {}) if provider else {}
        except RuntimeError as error:
            consoles = {}
            console_error = str(error)
        else:
            console_error = None
        return {
            **operation,
            "machines": states,
            "provider": provider,
            "consoles": consoles,
            "ready": states.keys() == MACHINES and all(state == "running" for state in states.values()),
            "status_error": status_error,
            "console_error": console_error,
        }


def append_lab_output(line: str) -> None:
    with LAB_LOCK:
        output = LAB_OPERATION["output"]
        output.append(line.rstrip())
        del output[:-100]


def run_lab_operation(operation_id: str, action: str, provider: str) -> None:
    global MACHINE_STATUS_CACHE
    if provider == "vmware_desktop":
        machines = ("gateway", "node1", "node2")
        commands = []
        if action in {"reset", "destroy"}:
            commands.extend(
                (f"Restableciendo {machine}", ["destroy", "-f", machine])
                for machine in machines
            )
        if action != "destroy":
            commands.extend(
                (f"Desplegando {machine}", ["up", machine, f"--provider={provider}"])
                for machine in machines
            )
    else:
        commands = []
        if action in {"reset", "destroy"}:
            commands.append(("Eliminando máquinas", ["destroy", "-f"]))
        if action != "destroy":
            commands.append(("Desplegando máquinas", ["up", f"--provider={provider}"]))
    try:
        def run_vagrant_command(phase: str, arguments: list[str]) -> None:
            with LAB_LOCK:
                LAB_OPERATION["phase"] = phase
            append_lab_output(f"$ {VAGRANT} {' '.join(arguments)}")
            with subprocess.Popen(
                [VAGRANT, *arguments],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            ) as process:
                if process.stdout is None:
                    raise RuntimeError("No se pudo leer la salida de Vagrant.")
                for line in process.stdout:
                    append_lab_output(line)
                return_code = process.wait()
            if return_code:
                tail = "\n".join(LAB_OPERATION["output"][-10:])
                raise RuntimeError(f"Vagrant terminó con código {return_code}.\n{tail}")

        def gateway_is_ready() -> bool:
            arguments = [
                "ssh",
                "gateway",
                "--command",
                "curl --fail --silent --show-error --max-time 3 http://127.0.0.1/health",
            ]
            append_lab_output(f"$ {VAGRANT} {' '.join(arguments)}")
            result = subprocess.run(
                [VAGRANT, *arguments],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
            for line in result.stdout.splitlines():
                append_lab_output(line)
            return result.returncode == 0

        for phase, arguments in commands:
            run_vagrant_command(phase, arguments)
            if provider == "vmware_desktop" and arguments[:2] == ["up", "gateway"]:
                with LAB_LOCK:
                    LAB_OPERATION["phase"] = "Verificando gateway"
                if not gateway_is_ready():
                    append_lab_output(
                        "El gateway no está listo; se repetirá su aprovisionamiento antes de continuar."
                    )
                    run_vagrant_command("Reaprovisionando gateway", ["provision", "gateway"])
                    if not gateway_is_ready():
                        raise RuntimeError(
                            "El gateway sigue sin responder en http://127.0.0.1/health "
                            "después de volver a aprovisionarlo."
                        )
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        with LAB_LOCK:
            if LAB_OPERATION["id"] == operation_id:
                MACHINE_STATUS_CACHE = None
                LAB_OPERATION.update(running=False, phase="failed", success=False, error=str(error))
        return
    with LAB_LOCK:
        if LAB_OPERATION["id"] == operation_id:
            MACHINE_STATUS_CACHE = (
                time.monotonic(),
                {machine: "not_created" for machine in MACHINES}
                if action == "destroy"
                else {machine: "running" for machine in MACHINES},
                provider,
            )
            LAB_OPERATION.update(running=False, phase="completed", success=True, error=None)


def start_lab_operation(action: str, provider: str) -> dict[str, Any]:
    global MACHINE_STATUS_CACHE
    if action not in {"deploy", "reset", "destroy"}:
        raise ValueError("Operación de laboratorio no válida.")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError("Proveedor no válido.")

    with LAB_LOCK:
        if LAB_OPERATION["running"]:
            raise RuntimeError("Ya hay una operación del laboratorio en curso.")
        MACHINE_STATUS_CACHE = None
        if action in {"reset", "destroy"}:
            with ATTEMPTS_LOCK:
                if any(attempt["grading"] for attempt in ATTEMPTS.values()):
                    raise RuntimeError("No se puede reiniciar el laboratorio mientras se corrige un intento.")
                ATTEMPTS.clear()

        operation_id = secrets.token_urlsafe(12)
        LAB_OPERATION.update(
            id=operation_id,
            action=action,
            provider=provider,
            phase="starting",
            running=True,
            success=None,
            error=None,
            output=[],
        )
        worker = threading.Thread(
            target=run_lab_operation,
            args=(operation_id, action, provider),
            daemon=True,
        )
        try:
            worker.start()
        except RuntimeError as error:
            LAB_OPERATION.update(
                running=False,
                phase="failed",
                success=False,
                error=f"No se pudo iniciar la operación: {error}",
            )
            raise
        return {**LAB_OPERATION, "output": list(LAB_OPERATION["output"])}


class Handler(BaseHTTPRequestHandler):
    server_version = "EX200Lab/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _json(self, status: int, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(payload)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            self._json(403, {"error": "Origen web no permitido."})
            return False
        return True

    def _read_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("El tipo de contenido debe ser application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("La longitud de la solicitud no es válida.") from error
        if length < 0 or length > 1024:
            raise ValueError("Solicitud demasiado grande o longitud no válida.")
        try:
            value = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("El cuerpo JSON no es válido.") from error
        if not isinstance(value, dict):
            raise ValueError("El cuerpo JSON debe ser un objeto.")
        return value

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/lab/status":
            self._json(200, lab_status())
            return
        if path == "/":
            target = STATIC / "index.html"
        elif path in {"/app.js", "/style.css"}:
            target = STATIC / path.lstrip("/")
        else:
            self._json(404, {"error": "Recurso no encontrado."})
            return
        content_type = "text/javascript; charset=utf-8" if target.suffix == ".js" else (
            "text/css; charset=utf-8" if target.suffix == ".css" else "text/html; charset=utf-8"
        )
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self) -> None:
        if not self._origin_allowed():
            return
        origin = self.headers.get("Origin")
        if origin is None:
            self.send_error(403, "Se requiere un origen web permitido.")
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_POST(self) -> None:
        if not self._origin_allowed():
            return
        path = urlparse(self.path).path
        if path in {"/api/lab/deploy", "/api/lab/reset", "/api/lab/destroy"}:
            try:
                body = self._read_json()
                operation = start_lab_operation(
                    urlparse(path).path.rsplit("/", 1)[-1],
                    body.get("provider", ""),
                )
            except ValueError as error:
                self._json(400, {"error": str(error)})
                return
            except RuntimeError as error:
                self._json(409, {"error": str(error)})
                return
            except OSError as error:
                self._json(503, {"error": f"No se pudo iniciar la operación: {error}"})
                return
            self._json(202, operation)
            return

        if path == "/api/attempts":
            try:
                self._read_json()
            except ValueError as error:
                self._json(400, {"error": str(error)})
                return
            with LAB_LOCK:
                if LAB_OPERATION["running"]:
                    self._json(409, {"error": "Espera a que termine la operación del laboratorio."})
                    return
                try:
                    states = machine_states()
                except (OSError, subprocess.SubprocessError, RuntimeError) as error:
                    self._json(503, {"error": f"No se pudo comprobar el estado de Vagrant: {error}"})
                    return
                if any(states[machine] != "running" for machine in MACHINES):
                    self._json(409, {"error": "Despliega las tres máquinas antes de comenzar el intento."})
                    return
                self._json(201, new_attempt())
            return

        match = re.fullmatch(r"/api/attempts/([^/]+)/finish", path)
        if not match:
            self._json(404, {"error": "Recurso no encontrado."})
            return
        attempt_id = unquote(match.group(1))
        with LAB_LOCK:
            if LAB_OPERATION["running"]:
                self._json(409, {"error": "No se puede corregir mientras se modifica el laboratorio."})
                return
            with ATTEMPTS_LOCK:
                attempt = ATTEMPTS.get(attempt_id)
                if attempt is None:
                    self._json(404, {"error": "Intento no encontrado en este servidor."})
                    return
                if attempt["result"] is not None:
                    self._json(200, attempt["result"])
                    return
                if attempt["grading"]:
                    self._json(409, {"error": "Este intento ya se está validando."})
                    return
                attempt["grading"] = True

        try:
            result = grade_attempt(attempt)
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as error:
            with ATTEMPTS_LOCK:
                attempt["grading"] = False
            self._json(503, {"error": str(error)})
            return

        with ATTEMPTS_LOCK:
            attempt["result"] = result
            attempt["grading"] = False
        self._json(200, result)


def main() -> None:
    host = os.environ.get("EX200_HOST", "127.0.0.1")
    port = int(os.environ.get("EX200_PORT", "8000"))
    try:
        start_console_proxies()
        server = ThreadingHTTPServer((host, port), Handler)
        print(f"EX200 Lab disponible en http://{host}:{port}")
        print("Consolas noVNC disponibles en http://127.0.0.1:6081-6083")
        print("Mantén este servidor local: los resultados se validan usando SSH a las VMs de Vagrant.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    finally:
        stop_console_proxies()


if __name__ == "__main__":
    main()
