# Push & Deploy Runbook

This project was assembled in an ephemeral cloud sandbox that **cannot** create a new
GitHub repo, reach Vercel, or run AWS/Vercel CLIs. So the final push to *your own* `Atlas`
repo and the deployment happen on **your machine** — one-time, a few commands each.

You received two things from the sandbox (committed to `claude-skills` under `Atlas-D365fo/`):
1. The full project tree (`Atlas-D365fo/`)
2. A self-contained git bundle: `Atlas-D365fo/dist/Atlas-D365fo.bundle` (complete standalone history)

---

## 1. Create the separate `Atlas` GitHub repo and push

**Option A — from the bundle (recommended, preserves standalone history):**

```bash
# Download Atlas-D365fo.bundle from the claude-skills repo (dist/ folder), then:
git clone Atlas-D365fo.bundle Atlas
cd Atlas
# Create an empty repo named "Atlas" on github.com (no README), then:
git remote set-url origin https://github.com/<your-user>/Atlas.git
git push -u origin main
```

**Option B — from the working tree:**

```bash
# Copy the Atlas-D365fo/ folder out of claude-skills to its own location, then:
cd Atlas-D365fo
git init && git add -A && git commit -m "Initial commit: Atlas D365 F&O Studio"
git branch -M main
git remote add origin https://github.com/<your-user>/Atlas.git
git push -u origin main
```

---

## 2. Deploy the frontend to Vercel (free tier)

```bash
cd Atlas/frontend        # or Atlas-D365fo/frontend
npm i -g vercel
vercel                   # first run links/creates the project
vercel env add ATLAS_API_URL   # set to your backend's public URL (from step 3)
vercel --prod
```

`vercel.json` is already configured (Next.js framework, `ATLAS_API_URL` wired).

---

## 3. Deploy the backend

**Fastest — Docker anywhere (Fly.io, Render, a VPS, EC2):**

```bash
cd Atlas                 # repo root (Dockerfile is here)
docker build -t atlas-backend .
docker run -p 8000:8000 \
  -e D365_BASE_URL=https://yourenv.axcloud.dynamics.com \
  -e D365_TENANT_ID=... -e D365_CLIENT_ID=... -e D365_CLIENT_SECRET=... \
  atlas-backend
# health check:
curl http://localhost:8000/health
```

**Production on AWS free tier (EC2 + RDS):** the `deploy/` folder holds an OpenTofu
skeleton. Fill in your values in `deploy/terraform.tfvars`, then:

```bash
cd Atlas/deploy
tofu init
tofu plan
tofu apply
```

Point the frontend's `ATLAS_API_URL` at the resulting backend URL.

---

## 4. Wire CI (optional)

`.circleci/config.yml` runs ruff + pytest + Next.js build + docker build on every push.
Connect the repo at circleci.com and add these env vars if you deploy from CI:
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `VERCEL_TOKEN`.

---

## 5. Security — do this first

- **Rotate the D365 client secret.** The secret used during development is still live.
  In Azure Portal → App registrations → your app → Certificates & secrets → new secret,
  delete the old one, and set the new value only as an environment variable (never in
  source or a Postman collection).

---

## Environment variables reference

| Var | Purpose | Without it |
|-----|---------|-----------|
| `D365_BASE_URL` | D365 F&O AOS base URL | Live crawl disabled; inline EDMX still works |
| `D365_TENANT_ID` / `D365_CLIENT_ID` / `D365_CLIENT_SECRET` | AAD auth | Same as above |
| `JINA_API_KEY` | jina-embeddings-v3 (1024-dim) | Local hash embedder (256-dim) |
| `GROQ_API_KEY` | llama-3.3-70b codegen refinement | Deterministic template codegen |
| `DATABASE_URL` | pgvector store | In-memory cosine store |
| `ATLAS_API_URL` | Frontend → backend URL | Defaults to `http://127.0.0.1:8321` |
