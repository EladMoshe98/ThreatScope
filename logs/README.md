# logs/

Runtime request log for the API. Once the stack is running, the API writes here:

- `requests.db` — SQLite request history (timestamp, filename, latency, entity
  counts, status). **Metadata only — the uploaded document text is never stored.**
- `nerf.log` — the application's structured log output.

### Where these come from
In Docker, this folder is **bind-mounted** into the api container — i.e. the container's
`/app/logs` is wired directly to this folder on your machine (`docker-compose.yml`:
`../logs:/app/logs`). So the request history is **visible on disk** and survives
container restarts, instead of being hidden inside the container.

The generated files (`requests.db`, `nerf.log`) are **excluded from Git**; only this
README is committed.
