# Public Go-Live Checklist

Use this document as the final public-exposure checklist for the only supported stack: `Next.js + FastAPI`.

## Public Model

Recommended go-live contract:

- `https://assistant.example.com/` -> `Next.js`
- `https://assistant.example.com/api/*` -> `FastAPI`
- `https://superset.example.com/` -> `Superset`

Recommended rule:
- do not publish `:8100` directly to the public internet
- keep FastAPI behind the assistant host and same-origin `/api/*` proxy
- leave `API_CORS_ORIGINS` unset unless you intentionally expose FastAPI
  cross-origin

## Required Before Public Exposure

Must be set:
- `ASSISTANT_DEPLOYMENT_MODE=production`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `AUTH_JWT_SECRET`
  - non-placeholder
  - at least 32 characters
- `SUPERSET_PUBLIC_URL=https://superset.example.com`

Optional but recommended:
- `US15_SHARE_BASE_URL=https://superset.example.com`
  - if set, it must match `SUPERSET_PUBLIC_URL` origin
- `ASSISTANT_RELEASE_VERSION`
- `ASSISTANT_BUILD_SHA`
- `ASSISTANT_BUILD_TIMESTAMP`

Set `API_CORS_ORIGINS` only when you intentionally need cross-origin API access:
- example: `API_CORS_ORIGINS=https://assistant.example.com`
- preferred same-origin public rollout: leave it unset

## Proxy/Ingress Checks

Before opening traffic:

1. `assistant.example.com` serves the Next.js UI
2. `assistant.example.com/api/*` proxies to FastAPI
3. `superset.example.com` serves Superset
4. `assistant-api` is not directly exposed on a public port
5. `SUPERSET_PUBLIC_URL` points to the public Superset host, not to `localhost`
6. share/explore links open the public Superset host

Reference config:
- `docs/examples/nginx-primary-ui.conf.example`

## Release-Candidate Signoff

1. validate env:
   ```bash
   ./docker/dev/validate-primary-env.sh
   ```
2. deploy:
   ```bash
   ./docker/dev/deploy-primary-stack.sh
   ```
3. internal health:
   ```bash
   ./docker/dev/check-primary-stack.sh
   ```
4. external health:
   ```bash
   curl -I https://assistant.example.com/login
   curl -I https://assistant.example.com/api/health
   curl -I https://superset.example.com/health
   ```
5. confirm release/build metadata:
   ```bash
   curl https://assistant.example.com/api/health
   ```
6. browser smoke:
   - login/register
   - `chat -> preview -> recommend -> share -> scan`
7. run:
   - `docs/manual-smoke-checklist.md`
   - `docs/demo-query-pack.md`
8. verify one share/explore link opens `https://superset.example.com/...`
9. confirm logs and trace correlation:
   ```bash
   ./docker/dev/tail-primary-logs.sh
   ./docker/dev/tail-primary-logs.sh structured
   ```

## Ready Now vs Environment-Specific

Repo-backed and ready now:
- single supported runtime stack
- deploy/update/health helpers
- production-mode env validation
- release/build metadata in `/api/health`
- public same-origin model documented

Still environment-specific:
- real DNS records
- TLS certificates
- installed reverse proxy / ingress
- final public hostnames
- real production secrets

## Rollback

Rollback is same-stack deployment rollback:

1. stop exposing the faulty release
2. restore the previous known-good revision or deployment artifact
3. rerun `./docker/dev/deploy-primary-stack.sh`
4. rerun `./docker/dev/check-primary-stack.sh`
5. rerun `docs/manual-smoke-checklist.md`
