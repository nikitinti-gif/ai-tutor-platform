# Persistence audit for Render

`DATABASE_URL` is the production durability gate. The local `database.json` path
is retained for development and tests, but Render's filesystem is ephemeral and
must not be treated as restart/deploy-safe.

| Data | Storage selection | With `DATABASE_URL` | Without `DATABASE_URL` | Survives Render restart/deploy |
|---|---|---|---|---|
| users | PostgreSQL or JSON fallback | `app_users` in PostgreSQL | `database.json` | **CONDITIONAL** — YES only with PostgreSQL |
| EGE session | PostgreSQL or JSON fallback | `ege_sessions` in PostgreSQL | `database.json` (`ege_sessions`) | **CONDITIONAL** — YES only with PostgreSQL |
| exam answers | Part of the EGE session attempt | JSONB `attempt` in `ege_sessions` | nested in the JSON EGE session | **CONDITIONAL** — YES only with PostgreSQL |
| Learning DNA | PostgreSQL or JSON fallback | `student_learning_dna` in PostgreSQL | `database.json` (`learning_dna`) | **CONDITIONAL** — YES only with PostgreSQL |
| `individual_plan` | Part of Learning DNA | nested in PostgreSQL DNA JSONB | nested in JSON Learning DNA | **CONDITIONAL** — YES only with PostgreSQL |
| LearningPath / remediation | Part of the EGE session attempt | nested in PostgreSQL `attempt` JSONB | nested in the JSON EGE session | **CONDITIONAL** — YES only with PostgreSQL |
| Task Bank progress | Part of the EGE session attempt | nested in PostgreSQL `attempt` JSONB | nested in the JSON EGE session | **CONDITIONAL** — YES only with PostgreSQL |

At startup and on the existing health endpoint, the service reports either a
durable PostgreSQL EGE backend or a non-durable JSON backend. For the real
Render service, configure `DATABASE_URL`; otherwise EGE persistence remains a
development-only JSON fallback and a restart or deploy may lose student state.
