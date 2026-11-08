# AI Animation Studio agent instructions

**ACTIVE PROJECT:** `projects/ai-animation-studio/`. Root `AGENTS.md` takes precedence.

- Keep app source, Godot files, tools, tests, dependencies, generated files and docs only in this project. Root README registration is allowed; do not edit other projects.
- Use `ai-animation-studio/<milestone>` branches and unmerged review PRs. Do not force-push or auto-merge.
- Read `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/TEST_PLAN.md` before implementation.
- **Priority:** first demonstrate deterministic two-character Godot rendering and event execution. Then persistent recipes and asset validation. Add local LLM, TTS, lip sync and generated motion one at a time.
- Keep LLM prompts and outputs separate from trusted engine commands. Validate IDs, types, positions, duration bounds and asset status before scheduling.
- Never execute arbitrary code from LLM output or download unapproved external assets. Keep runtime offline by default.
- Never commit model weights, binaries, copyrighted asset packs, audio recordings, run-time databases, generated releases, tokens or user files.
- Do not make another project an implicit dependency. Use optional, versioned adapters only with future owner approval.
- Record tests actually run and GPU observations with commands; do not claim real-time performance until measured on owner hardware.
- Keep docs/MUSE_HANDOFF.md and docs/IMPLEMENTATION_STATUS.md current. Scope changes to this folder and root index only.
