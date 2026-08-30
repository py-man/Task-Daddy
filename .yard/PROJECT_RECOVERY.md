# Task-Daddy recovery and cluster execution contract

This is the canonical secret-free operational document for Task-Daddy. Read it with `AGENTS.md`, `.yard/project-state.json`, `docs/DEPLOYMENT.md`, security reviews and current Git history.

## Product and boundaries

Task-Daddy is the public open-source task manager distribution: Next.js/TypeScript web, FastAPI API, PostgreSQL, Redis, file uploads, encrypted integration data, backup artifacts, MFA and external integrations. Canonical source is `https://github.com/py-man/Task-Daddy.git`, branch `main`.

This public repository must never contain private environment identifiers, credentials, private keys, production dumps or internal-only tools. Yard owns inventory, policy, targets and audit. Windmill owns deterministic clean-checkout CI. Nomad is not authorized to adopt the current runtime.

## Mandatory safety

- Never expose `.env`, APP_SECRET, FERNET_KEY, passwords, seed credentials, MFA recovery data, PEM files, tokens, integration payloads, uploads or database dumps.
- Never build/test in the running AWS checkout or against its PostgreSQL volume.
- Never run `down -v`, volume prune, global prune, reset scripts or broad Docker deletion on production-like environments.
- API startup applies Alembic migrations and seeds; production releases must review those effects before restart.
- A commit, merge, Windmill run or image build is not deployment. Exact operator approval is required.
- Preserve unrelated AWS containers and Portainer. Never change firewall, DNS, routes, Caddy or Tailscale for an application-only change.

## Architecture and data

The base Compose contract uses `redis`, `db`, `api` and `web`. Local defaults expose loopback ports 6379, 5432, 8000 and 3010. Persistent state is `taskdaddy_db`, `taskdaddy_uploads` and `taskdaddy_backups`; Redis is configured without persistence and is rebuildable cache/queue state.

Source control does not back up any of those volumes. A future central PostgreSQL platform may host a dedicated Task-Daddy database and owner, but Task-Daddy must not share another application's database credential or schema.

## Development and CI

Use a clean task branch/worktree. Run `npm ci --ignore-scripts`, `npm run typecheck`, Python compile checks and safe unit tests against isolated test data. Validate Compose configuration without starting it. UI changes require browser QA. Report branch, commit, files, tests, screenshots, migration/integration impact, risks and deployment class.

Windmill script `u/admin/taskdaddy_ci` clones only `py-man/Task-Daddy` at an explicit ref using a repository-specific read-only key from Windmill secret storage. It cannot run Docker, Compose, migrations, deployment scripts, SSH, AWS commands or arbitrary repositories. The last verified run passed at `25c2ec56000488cc445ea19f5646cbd7b5557857`; rerun against the new contract commit before marking this copy current.

## Backup, release and recovery

Before any production restart or release, create a custom-format database dump, read-only archives of uploads and application backup volume, and a Git backup tag for the exact running commit. Verify `pg_restore --list`, archive checksums and restore metadata. Store artifacts encrypted outside Git.

Deployment classes are no-deploy, web-only, API-only and reviewed migration. Prebuild first and replace only the approved service with `--no-build`. Do not recreate PostgreSQL, uploads, backups or Redis for a web-only release. Prove API health, web render, login/MFA paths where affected, container image identity, migrations, integrations and persistent counts.

If Compose recreation fails, preserve the old container and volumes, inspect the exact conflict and stop broad retries. Recovery stops writers, preserves failed evidence, restores into isolation, validates schema/counts/uploads, then performs an approved cutover. Reboot recovery verifies Docker, Compose, DB, API, web and Portainer without restarting unrelated infrastructure.

## Known risks and lessons

- The verified CI reported 9 high and 1 critical dependency findings; these require reviewed remediation, not automated `npm audit fix --force`.
- A dependency requires Node 22 while the current Windmill worker was Node 20. Pin and prove the supported worker runtime.
- The AWS checkout previously used ephemeral high ports and must not be treated as the canonical release layout.
- Runtime-generated APP_SECRET/FERNET_KEY is suitable only for local bootstrap; stable production secrets must be externally managed or sessions/integration encryption can break across restarts.
- Automatic migrations and seed on API start couple deployment to data change. Separate them before production-grade scheduler adoption.
- Bootstrap credentials are sensitive runtime artifacts in `taskdaddy_backups`; never print them into Foundry/Windmill logs.

Append verified incidents and decisions to `docs/PROJECT_MEMORY.md`; preserve all earlier evidence.
