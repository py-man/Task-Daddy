lint:
	ruff check .

format:
	ruff check . --fix
	black .

test:
	DATABASE_URL=postgresql+asyncpg://taskdaddy:taskdaddy@db:5432/taskdaddy_test alembic upgrade head
	DATABASE_URL=postgresql+asyncpg://taskdaddy:taskdaddy@db:5432/taskdaddy_test SEED_ADMIN_PASSWORD=admin1234 SEED_MEMBER_PASSWORD=member1234 python -m app.seed
	DATABASE_URL=postgresql+asyncpg://taskdaddy:taskdaddy@db:5432/taskdaddy_test pytest -q
