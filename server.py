#!/usr/bin/env python3
"""Local web app and SSH-based grader for the EX200 practice lab."""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import subprocess
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
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024:
                raise ValueError("Solicitud demasiado grande.")
            value = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as error:
            raise ValueError("El cuerpo JSON no es válido.") from error
        if not isinstance(value, dict):
            raise ValueError("El cuerpo JSON debe ser un objeto.")
        return value

    def do_GET(self) -> None:
        path = urlparse(self.path).path
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

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/attempts":
            try:
                self._read_json()
            except ValueError as error:
                self._json(400, {"error": str(error)})
                return
            self._json(201, new_attempt())
            return

        match = re.fullmatch(r"/api/attempts/([^/]+)/finish", path)
        if not match:
            self._json(404, {"error": "Recurso no encontrado."})
            return
        attempt_id = unquote(match.group(1))
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
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"EX200 Lab disponible en http://{host}:{port}")
    print("Mantén este servidor local: los resultados se validan usando SSH a las VMs de Vagrant.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
