# Underreach Spectator Viewer

This is the Slice 28C.1 local spectator client. It is a React/TypeScript single-page app served by the existing FastAPI Feed process; it does not contain or mutate authoritative simulation state.

The validation runner builds the app, binds the server to `127.0.0.1`, starts one continuous Unreal consumer, and leaves the browser controls limited to presentation focus:

- Follow a camera-available Descender
- Switch between camera-available Descenders
- Return the session to automatic focus

There is intentionally no authentication, public deployment, embedded video transport, or public network binding in this slice. Keep the default localhost bind until authentication and permissions are designed.

Local checks:

```powershell
npm test
npm run build
```

The full integrated proof is run from the repository root with `scripts/run-underreach-spectator-viewer-validation.ps1`.
