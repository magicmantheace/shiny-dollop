# Product specification — GitHub Development Command Center

Version: 1.0 requirements baseline (2026-10-22)  
Platform: Windows 11 x64 first; macOS/Linux may follow.  
Audience: a single hobbyist or professional developer managing several GitHub repositories.  
GitHub target: GitHub.com (enterprise instances are out of initial scope).

## 1. Product outcome

Build a **real installable desktop application** that acts as a single pane of glass for a GitHub account's development work. A user must be able to authenticate, choose repositories, review accurate live GitHub data, act on actionable information by opening its official GitHub page, and keep their local choices across sessions. This is not a demo dashboard.

### Non-goals in MVP
- No AI chatbot, AI coding, autonomous agents, code editing, git cloning, terminals or IDE.
- No GitHub write/mutation operations (merges, branch creation, comments, issue updates, dispatch, reruns, approvals, secrets).
- No dependency on Synveil, AthenZ, Developmental AI or any other project.
- No mandatory hosted server, cloud database, telemetry, account on a vendor service, or subscription.
- No mobile version, GitHub Enterprise support, multi-user accounts or OAuth backend in the first release.

## 2. Core user journey

1. Install and start the application on Windows 11.
2. See a polished onboarding screen explaining GitHub connection and least-privilege token requirements.
3. Add a fine-grained GitHub personal access token through a masked input, validate it using GitHub API, show the signed-in username, and securely store it in the operating-system credential vault.
4. Browse/search repositories the token can access; choose which ones to track, untrack or reorder. Do not hardcode account/repo names.
5. View an overview populated with real data: tracked repository count, open PRs, open issues, actionable failing or pending CI/checks, and recent updates.
6. Click a repository to see branches, latest commits, open PRs, issues, workflows/checks, and direct links to GitHub.
7. Filter/sort lists and inspect meaningful details; opening a GitHub item uses the default browser.
8. Manually refresh; background refresh at user-selected cadence, with last-sync timestamp and API errors displayed.
9. Quit and reopen: selected repos, ordering, view settings and a reasonable nonsecret cache remain; credential stays in OS vault.
10. Disconnect: erase local saved credential and stop GitHub requests; allow optional deletion of cached metadata and tracked repository choices.

## 3. Required screens

### A. First run / settings
- Connection status; connected GitHub username and avatar.
- Masked credential input; clearly describe token creation outside the app and direct to official GitHub token settings.
- Validate credential before saving; never render it back after connection.
- Explain permissions needed for repository metadata, pull requests, issues, commit/branch details and optional Actions/checks. Show missing-permission indicators per feature.
- Test connection, change token, disconnect, clear cache.
- Refresh choices: manual, off or intervals such as 5/15/30 minutes; use safe throttling.
- Appearance: light/dark/system, and readable text size where practical.

### B. Overview
- Cards with tracked repositories, open PRs, open issues and CI attention count (with explicitly defined aggregation).
- Recently active tracked projects; meaningful activity timestamps and link to each repo.
- "Needs attention" section: failing latest default-branch checks, review requests (if accessible) and stale/errored syncs — every item backed by actual data.
- A visible "Updated at" indicator, manual refresh button, loading skeletons and clear error state.
- Empty state when no repositories are selected; offline cached snapshot clearly labeled as cached.

### C. Repositories
- Search available repositories (owned and accessible), track/untrack and reorder a shortlist.
- Table/cards with name, visibility (when authorized), description, default branch, primary language if supplied, last activity, open PRs/issues and CI status when available.
- Filter tracked/all; sort by recent update or name.
- Pagination and lazy loading: handle an account with 100+ repositories without freezing UI.

### D. Repository details
- Header with name, description, default branch, last sync and GitHub "Open" link.
- **Branches:** default indicator; branch name; latest commit SHA, message and date where accessible; branch loading/pagination.
- **Commits:** recent history of selected/default branch; author, abbreviated SHA, date, message; link to commit.
- **Pull requests:** number, title, draft marker, author, source/target branch, updated time, review state if supportable, link; open/closed/merged filters if feasible. Never conflate `closed` with `merged`.
- **Issues:** number, title, labels, assignee, age, status and link; distinguish PRs from issues where GitHub endpoint overlap exists.
- **CI/Actions/checks:** recent workflow runs where authorized and/or checks for latest default-branch commit; correct success/failure/pending/cancelled/skipped/unknown status and time; direct GitHub link.
- **Activity:** latest commits/PRs/issues/workflow runs with source and timestamps (avoid falsely claiming GitHub's events API is exhaustive).

### E. Local notes (stretch after core MVP)
- Optional markdown/plain-text per-repo notes and priority labels, stored locally; never posted to GitHub.
- User-editable and preserved across restarts; backup/export may follow.

## 4. Data correctness and permission behavior

- Show real API data only after successful authorization; clearly label fixture/demo data if a demo mode exists.
- No fabricated commits, dates, PR counts or build statuses.
- A workflow run conclusion is not the same thing as check-run status; show both accurately when available.
- "No workflows" is different from "not authorized", "API error" and "not yet loaded".
- Where CI runs are absent or unauthorized, show `Unavailable` or `No data` with reason; do not show a green check.
- Partial failure of one repo should not prevent the others from updating.
- For private repos, never leak titles/names/content outside authenticated local UI and local storage; never send to analytics.
- Support pagination, GitHub rate limits, timeouts, transient network errors, cancelled requests and token expiry/revocation.
- Treat local timezones properly; store timestamps as UTC, format in UI with user's locale.
- Don't sort non-chronological identifiers as dates; don't imply metric coverage beyond what's fetched.

## 5. UX and accessibility

Modern but original design, left navigation (Overview, Repositories, Settings), compact dense lists, readable status chips, search, filters, responsive resize, keyboard tab navigation, focus indicators, accessible labels, sufficient contrast, tooltips only for auxiliary information. No inert controls. Avoid heavy animation and unnecessary GPU overhead. Empty/loading/error/permission denied/offline states must have useful copy and safe retry paths.

## 6. Acceptance targets

- First-run onboarding works using a real token on Windows 11.
- At least three repos can be tracked simultaneously; list and status views remain usable.
- Overview values correspond to fetched API responses, and links open correct URLs.
- User can inspect commits, branches, PRs, issues and CI where permissions/data permit.
- No GitHub mutations occur from the app, even when token has broader permissions.
- Persistent settings and selected repos survive restart; missing token triggers clear reconnect.
- Works offline from clearly labeled cache and does not loop/flood requests.
- Manual refresh, permission errors and invalid token are comprehensible.
- A packaged Windows installer and a development run command are documented and exercised (or platform limitation explicitly recorded).
- Unit, integration and smoke tests exist and can be run on a clean checkout.

See `TEST_PLAN.md` for exact evidence and test cases.
