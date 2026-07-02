# Railway: switch the API run store to PostgreSQL

SQLite on a Railway volume is single-instance: only one replica can hold the
file, so the API cannot scale horizontally and a volume-less rebuild loses run
history. PostgreSQL lets every API replica share one database. The code path is
already behaviour-verified against a real Postgres (see `tests/test_postgres_store.py`).

## Prerequisites

- `Dockerfile.api` installs the `postgres` extra (psycopg) — already done.
- The API image entrypoint reads `WAYFINDER_RUN_STORE` / `WAYFINDER_DATABASE_URL`.

## Steps (Railway UI or CLI)

1. **Add a Postgres database** to the project.
   - UI: *New → Database → Add PostgreSQL*.
   - CLI: `railway login` then `railway add --database postgres`.

2. **Point the API service at it** with a reference variable so the URL tracks
   the database, plus the store selector. On the `wayfinder-api` service set:

   ```env
   WAYFINDER_RUN_STORE=postgres
   WAYFINDER_DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```

   `${{Postgres.DATABASE_URL}}` is a Railway reference to the Postgres plugin's
   connection string; adjust `Postgres` to the actual service name if renamed.
   Remove or ignore `WAYFINDER_RUN_STORE_PATH` — `postgres` takes precedence over
   sqlite in the factory, but dropping it avoids confusion.

3. **Redeploy** the API service (a config change triggers this automatically).
   The store creates its schema on first boot (idempotent DDL).

4. **Verify**:
   - `GET /ready` returns `{"status":"ready","run_store":"PostgresRunStore"}`.
   - Create a thread and confirm it survives an API restart (redeploy), which
     SQLite-in-container could not guarantee without a persistent volume.

## Rollback

Set `WAYFINDER_RUN_STORE=sqlite` (with a persistent `/data` volume and
`WAYFINDER_RUN_STORE_PATH=/data/wayfinder/runs.sqlite`) and redeploy. Existing
Postgres data is left untouched; note that run history does not auto-migrate
between the two backends.

## Notes

- The store uses one lock-serialized connection per process. Correctness holds
  under Railway's default replica model (each replica opens its own connection
  to the shared database); if you later need heavy intra-process concurrency,
  swap the single connection for a psycopg connection pool.
- Keep `WAYFINDER_KEY_ENCRYPTION_SECRET` set — workspace API keys are stored as
  encrypted envelopes regardless of the run-store backend.
