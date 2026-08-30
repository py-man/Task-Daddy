"""Deterministic non-production CI for the approved Task-Daddy repository."""

import os
import shutil
import subprocess
import tempfile
import time

import wmill


REPOSITORY = "git@github.com:py-man/Task-Daddy.git"
KEY_VARIABLE = "u/admin/taskdaddy_github_deploy_key"


def run(command: list[str], cwd: str, env: dict[str, str], timeout: int = 1200) -> dict:
    if command[0] in {"docker", "docker-compose", "ssh", "alembic", "nomad"}:
        raise ValueError("deployment, migration, infrastructure and SSH commands are forbidden")
    started = time.monotonic()
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True,
                            timeout=timeout, check=False)
    evidence = {"command": command, "exit_code": result.returncode,
                "duration_seconds": round(time.monotonic() - started, 3),
                "stdout": result.stdout[-12000:], "stderr": result.stderr[-12000:]}
    if result.returncode:
        raise RuntimeError(f"deterministic check failed: {evidence}")
    return evidence


def main(ref: str = "main") -> dict:
    if not ref or len(ref) > 120 or ref.startswith("-") or any(c.isspace() for c in ref):
        raise ValueError("invalid Git ref")
    private_key = wmill.get_variable(KEY_VARIABLE)
    if not private_key or "PRIVATE KEY" not in private_key:
        raise RuntimeError("Task-Daddy read-only GitHub deploy key is unavailable")
    root = tempfile.mkdtemp(prefix="taskdaddy-ci-")
    checkout = os.path.join(root, "repo")
    key_path = os.path.join(root, "deploy_key")
    try:
        with open(key_path, "w", encoding="utf-8") as handle:
            handle.write(private_key.rstrip() + "\n")
        os.chmod(key_path, 0o600)
        env = os.environ.copy()
        env.pop("DOCKER_HOST", None)
        env["GIT_SSH_COMMAND"] = f"ssh -i {key_path} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
        steps = [
            run(["git", "clone", "--filter=blob:none", "--no-checkout", REPOSITORY, checkout], root, env),
            run(["git", "fetch", "--depth=1", "origin", ref], checkout, env),
            run(["git", "checkout", "--detach", "FETCH_HEAD"], checkout, env),
        ]
        commit = run(["git", "rev-parse", "HEAD"], checkout, env)["stdout"].strip()
        steps.append(run(["python3", "-m", "compileall", "-q", "apps/api/app"], checkout, env))
        steps.append(run(["npm", "ci", "--ignore-scripts"], checkout, env))
        steps.append(run(["npm", "run", "typecheck"], checkout, env))
        return {"ok": True, "project": "taskdaddy", "resolved_commit": commit,
                "worker_hostname": subprocess.check_output(["hostname"], text=True).strip(),
                "checks": len(steps), "steps": steps}
    finally:
        shutil.rmtree(root, ignore_errors=True)
