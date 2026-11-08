# Windows install — Household Inventory and Warranty Tracker

## Portable zip (available now)

1. Download `Household Inventory-0.1.0-win-x64.zip` from the PR / release artifacts.
2. Extract it anywhere (e.g. `C:\Apps\HouseholdInventory\`).
3. Run `Household Inventory.exe`.

No installer, no admin rights, no registry changes. All data stays local:

- Database: `%APPDATA%\Household Inventory\inventory.db`
- Attachments: `%APPDATA%\Household Inventory\attachments\`
- Pre-import rollback copies: `%APPDATA%\Household Inventory\rollback-<timestamp>\`

## First-run check

1. **Items** tab → Add item → fill name/category, set a warranty end date → Save.
2. Open the item → attach a receipt PDF/photo → confirm it appears with a sha256 short hash.
3. Add a maintenance event → confirm it lists newest-first.
4. **Warranties** tab → set the window to 90 days → confirm the item appears under Expiring.
5. **Backup** tab → Export → confirm the zip path + counts; then Import the same zip → confirm counts match (current data is rolled back to `rollback-<timestamp>` first).

## Known Windows-environment notes

- **No code signing** — Windows SmartScreen will warn on first launch. This is expected for an unsigned MVP build.
- **NSIS installer** was not assembled (no Wine in the build environment). The portable zip is the deliverable for now.
- Native file dialogs (attachment picker, backup export/import) are main-process dialogs — verified in code, but click-through on real Windows 11 is still pending.
