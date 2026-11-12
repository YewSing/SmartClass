---
description: Check the work branch is safe for main, then give Yew Sing the merge link and a note for Shino. Never merges by itself.
---

Prepare the current work branch for merging into `main`. Yew Sing clicks Merge on GitHub; never push to `main`. Fix problems on the work branch, commit and push them, then re-run the checks they affect.

1. Run `git fetch origin`. Confirm the tree has no uncommitted work except files that are meant to stay out of git, and no task loop is running. If `main` has commits this branch lacks, merge `origin/main` into the branch and resolve any conflicts there. Keep Shino's changes unless they truly can't work with ours, and if so, ask Yew Sing.
2. Backend, from `backend/`:
   - `bash ../scripts/check.sh` passes.
   - `python -c "import app.main"` works, including with `LLM_API_KEY=` and `MOODLE_TOKEN=` set empty.
   - All migrations apply to a fresh temporary database: create `smartclass_mergecheck` on the docker postgres, enable `vector`, run `alembic upgrade head` with `DATABASE_URL` pointed at it, then drop that database. Never touch the `smartclass` database or Docker volumes.
   - `python -m pip install --dry-run -q -r requirements.txt` shows no conflict.
3. Every package imported by new code is in `requirements.txt` or the matching `package.json`.
4. Build each frontend changed since `main` (`git diff --name-only origin/main...HEAD`), running `npm ci` first if `node_modules` is missing, with `--legacy-peer-deps` for the mobile apps:
   - `frontend/admin`, if it still exists: `npm run build`
   - `mobile/<app>`: `npx expo export --platform android --output-dir "$TEMP/merge-<app>"`, plus `--platform web` for the lecturer app once it has web support. Remove the temporary output afterwards.
5. Scan `git diff origin/main...HEAD` for secrets and files that must stay out of git:
   - API keys and tokens, comparing against real values without printing them;
   - course materials (`.pdf`, `.pptx`, `.docx`) and face or card images;
   - any tracked `.env` file other than `.env.example`.
6. Everything merged is finished. Unfinished features stay on a work branch or stay off by default, so `main` never shows half-built behaviour. A backend without optional setup (Moodle, LLM key) must still start.
7. If anything fails and you can't fix it, stop and tell Yew Sing plainly what is wrong. Don't offer a pull request or a merge.

When all checks pass, open the pull request from inside the Claude desktop app, so Yew Sing never has to visit GitHub (he chose this on 2026-11-13):
- Write the pull request title, and a note for Shino as the PR description. The note says what changed, what to do after pulling (packages, `alembic upgrade head`, new `.env` lines) and which changes she can ignore. End it with the PR attribution line.
- Offer the app's **Create PR** button (the `create_pr` action in the closing next-step box). Once the PR exists, bind it with the `ccd_pr` tools and check its CI. Then offer the app's **Merge** button (the `merge` action) as the next step. Yew Sing's click on that button is the merge; never merge it yourself, and never turn on auto-merge.
- If the app buttons aren't available (e.g. a terminal session), fall back to the link `https://github.com/YewSing/SmartClass/compare/main...<branch>?expand=1` with the steps: open it, paste the title and note, click **Create pull request**, then **Merge pull request** and **Confirm merge**.

Reply in plain language, for someone new to git, with a table of each check and its result, and what was not tested.
