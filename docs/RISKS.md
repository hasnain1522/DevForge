# Operational risks and limits

| Area | Risk | Current mitigation / limit |
|---|---|---|
| Repository paths | API accepts local paths and agents/subprocesses operate on repository files. | Use only trusted local repositories. The MVP is not an untrusted multi-tenant code execution service. |
| Provider availability | LLM calls can fail because of network, quota, or provider errors. | Provider errors are generalized in API/log output; OpenRouter can be configured as fallback. Live provider availability must be validated separately. |
| Verification environment | pytest or Ruff may be absent or repository checks may fail. | Verification records command exit results; unavailable tools are not reported as passing. |
| Session configuration | A weak/missing signing secret undermines sessions. | Backend requires `AUTH_SECRET` with at least 32 characters for authentication. Keep it in ignored `.env`. |
| Legacy database records | Existing rows may have no owner. | Migration adds nullable ownership and inaccessible unowned records are not returned through authenticated APIs. Back up the SQLite file before manual migration or reset. |
| Bob evidence | Development evidence may not have been captured. | Do not fabricate it. Keep genuine Bob development records separate under `docs/evidence/bob/`. Bob is not a product runtime dependency. |

The backend and frontend tests cover current product contracts; successful tests do not replace a successful live-provider validation.
