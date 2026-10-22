# Architecture, security and implementation boundaries

## 1. Recommended implementation baseline

Windows-first **Electron + React + TypeScript + Vite**, using a maintained Electron/Vite scaffolding approach. Use a **single project-scoped package** with a pinned package-manager lockfile; Node LTS. Use modern CSS or a light component library if it improves accessibility; avoid bundling a full unrelated design system. Packaging: `electron-builder` or a current equivalent, producing a Windows x64 installer.

Choose this stack unless a serious measured constraint justifies replacing it. If changed, document why and preserve all acceptance requirements. Never install packages or create app manifests at repository root.

### Main process (trusted)
- Window lifecycle and secure navigation policy.
- GitHub API client, auth, token access and scoped GitHub URL opening.
- Local SQLite storage for nonsecret state/cache, with schema migrations.
- IPC contract validation and refresh orchestration/rate limiting.

### Preload (narrow trusted bridge)
- Expose a typed, small surface: `auth.connect`, `auth.status`, `auth.disconnect`, `repos.listAvailable`, `repos.getTracked`, `repos.setTracked`, `dashboard.get`, `repo.getDetails`, `sync.refresh`, `settings.get/update`, `links.openGitHub`.
- Use validated parameters and typed response models. No arbitrary shell, filesystem or raw HTTP/network API.
- Avoid exposing tokens or broad `ipcRenderer` access to renderer.

### Renderer (untrusted UI)
- React pages/components, state and local in-memory query cache.
- Never hold or directly fetch GitHub credentials.
- Data and errors delivered through validated preload methods.
- Make all offline, loading, stale, partial and permission states visible.

### Persistence
- Store selected repository IDs/full names and display order, preferences, last successful sync, bounded API-derived cache and migrations in a user-data SQLite DB.
- Store token **only** in OS-backed credential storage (Windows Credential Manager, through a maintained compatible library/adapter).
- Do not use renderer localStorage to store secrets, and do not embed a dev token in tests or GitHub Actions.
- Include expiry/eviction strategy for cached metadata; the cache should not indefinitely balloon.

## 2. API strategy

Use GitHub REST API via a maintained `@octokit/rest` / `@octokit/core` (or equivalent) in the Electron main process, no required hosted proxy. Centralize calls and response mapping. Anticipated calls:
- Auth/account: `GET /user`.
- Repo discovery: `GET /user/repos` or appropriate GitHub repo listing route with pagination.
- Repository: `GET /repos/{owner}/{repo}`.
- Branches: `GET /repos/{owner}/{repo}/branches`.
- Commits: `GET /repos/{owner}/{repo}/commits?sha=...`.
- Pull requests: `GET /repos/{owner}/{repo}/pulls` (state filters).
- Issues: `GET /repos/{owner}/{repo}/issues` with explicit PR-item filtering; optionally search for totals if accurate.
- Workflows: `GET /repos/{owner}/{repo}/actions/runs` where accessible.
- Check runs: `GET /repos/{owner}/{repo}/commits/{ref}/check-runs` when permitted, plus commit status endpoints if meaningful.

Do not assume all endpoints are available for every repo/token. GitHub endpoints, token permissions and API versions can evolve; check maintained official API documentation at implementation time.

Use per-page limits, lazy loading, request concurrency caps, backoff with jitter for transient failures, proper `Retry-After` / rate-limit reset handling, `ETag` or conditional requests where useful, and cancellation when users switch repos. Prefer bounded query limits (e.g. latest 20–50 records per tab by default), and a "load more" affordance.

Normalize upstream fields into typed domain models; distinguish `null`, unknown, empty, unavailable, unauthorized and stale values.

## 3. Authentication model

MVP: user-generated **fine-grained personal access token** through masked input. Explain that the user should restrict the token to intended repositories and **read-only** operations. Depending on requested endpoints, relevant read permissions include Metadata, Contents, Pull requests, Issues, Actions, Checks and Commit statuses. Show a feature-specific message when a token lacks permissions; do not ask for write scopes. Do not rely on having private repository access.

Validate token with authenticated identity; avoid logging request headers. Allow credential replacement and explicit disconnection with OS vault deletion. No hardcoded OAuth client secrets. Optional OAuth/device flow is a later enhancement **only if implemented securely with GitHub's documented process**.

**Important:** In MVP, API adapter exposes GET and safe metadata reads only. Audit to ensure no `POST`, `PUT`, `PATCH` or `DELETE` requests to GitHub can occur, even if a user supplies an overprivileged token.

## 4. Electron security baseline

- `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true` wherever compatible.
- Keep strict navigation/window-open policy. Open only validated `https://github.com/` or `https://docs.github.com/` destinations in the system browser; do not invoke shell with user-built commands.
- Enforce a useful Content Security Policy without `unsafe-eval` in production and no remote script execution.
- Validate all IPC input and output shape; renderer cannot request arbitrary URLs, file paths, local commands or repository writes.
- Disable remote module and uncontrolled `webview`; minimize privileged dependency surface.
- Do not display untrusted GitHub markdown as raw HTML. Escape external strings to prevent injection.
- Ensure devtools are off for release builds or otherwise not publicly exposed by a control surface.
- Avoid auto-update / downloaded executable replacement without a trustworthy signing and release process.

## 5. Suggested directory layout

```text
projects/github-development-command-center/
  app/
    package.json
    package-lock.json (or equivalent single lockfile)
    electron/
      main/
        index.ts
        github/
        persistence/
        ipc/
      preload/
        index.ts
    src/
      pages/
      components/
      features/
      state/
      types/
      styles/
    tests/
      unit/
      integration/
      e2e/
    assets/
    README.md
    .gitignore
  docs/
  README.md
  AGENTS.md
```

Project-local `app` may be flattened into project root if tooling significantly benefits, **never into repository root**.

## 6. Data, performance and resilience

- Initial dashboard should render promptly using saved metadata and incremental network updates, rather than blocking until every repo completes.
- Refresh only visible or tracked repos, with app-level concurrency guard and burst limits.
- No periodic refresh when offline or signed out; use debounced backoff.
- Use DB transactions for tracked list order/updates and idempotent migrations.
- If one repo fails (404, 403, network), isolate and explain that failure.
- Log only sanitized technical errors; no token, authorization header or private content dumps.
- No analytics or telemetry by default. Require explicit opt-in if ever added.

## 7. Packaging and reproducibility

Provide project-local `npm run dev`, `npm run build`, `npm run test`, `npm run lint`, `npm run typecheck`, and `npm run package:win` or explicit equivalents. Pin versions, commit a lockfile, and document Node/tooling prerequisites and clean installation. Build must not require a preexisting global package or root-level scripts. Explain whether code signing is configured; do not claim signed Windows binaries if none exist. Do not commit installers or binaries to Git.

Do not create active GitHub Actions workflow outside project folder without owner's permission; workflows under nested folders are documentation only and will not execute automatically.
