# CI/CD setup

Two workflows:

- **`ci.yml`** — runs on every push/PR to any branch: lint, jest unit tests,
  hadolint on the HF Dockerfile, and a full `docker build` of it (no push).
- **`deploy.yml`** — runs only on push to `main`: repackages the repo into
  the file layout a Hugging Face Docker Space expects, then force-pushes it
  to your Space's own git repo.

## One-time setup

1. **Create the Space** (free tier, no card needed):
   - Go to https://huggingface.co/new-space
   - SDK: **Docker**, Visibility: your choice, Hardware: CPU basic (free)
   - Note the full name, e.g. `your-username/anything-llm-lightweight`

2. **Create a Hugging Face access token** with **write** access:
   - https://huggingface.co/settings/tokens → New token → role `Write`

3. **Add it to this GitHub repo**:
   - Settings → Secrets and variables → Actions → **Secrets** tab
     → New repository secret → name `HF_TOKEN`, value = the token
   - Same page → **Variables** tab → New repository variable
     → name `HF_SPACE`, value = `your-username/anything-llm-lightweight`

4. **(Recommended) Make CI a required check** so a broken commit on `main`
   never triggers a deploy:
   - Settings → Branches → add a branch protection rule for `main`
   - Enable "Require status checks to pass before merging" and select the
     three `ci.yml` jobs (`lint-and-test`, `hadolint`, `docker-build-smoke-test`)
   - This gates *merging* into main; `deploy.yml` itself doesn't re-run CI,
     it just trusts that main only ever contains commits that already passed.

5. Push to `main` (or merge a PR into it) → check the **Actions** tab →
   `Deploy to Hugging Face Space` → then your Space's **Logs** tab as it
   rebuilds.

## Notes specific to this fork

- Free HF Spaces have **no persistent storage** by default: the SQLite DB,
  uploaded docs, and Chroma data are wiped on every rebuild (see
  `README-huggingface.md`). Fine for demos; add the Persistent Storage
  add-on (paid) if you need data to survive deploys.
- `deploy.yml` swaps in `docker/Dockerfile.huggingface` → `Dockerfile` and
  `README-huggingface.md` → `README.md` at the root of what gets pushed to
  the Space — it does **not** touch those files in this GitHub repo.
- Free CPU Spaces sleep after inactivity and cold-start on the next request
  (can take ~30-60s), which is normal, not a deploy failure.
