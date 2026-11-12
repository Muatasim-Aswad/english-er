# Operations

English-er is a loopback-only personal service. Installation and deployment never enable capture or edit Voxtype configuration.

## Offline inspection

Build and verify everything without touching live user state or systemd:

```bash
scripts/verify-task check
mise run local:install -- --dry-run
```

The gate uses temporary data and state roots, a fake correction provider for Playwright, a recording `systemctl` replacement for deployment-order tests, and port `127.0.0.1:8765` for isolated serving checks. The installer dry run prints the exact units it would write.

## Local installation

After dependency setup, prepare the GPU voice and build the UI. Installing or starting services modifies user state; inspect `local:install --dry-run` and explicitly approve those changes when an agent operates for you. Capture remains off unless you enable it separately.

```bash
mise run speech:prepare
pnpm run build:all
mise run local:install
systemctl --user daemon-reload
systemctl --user enable --now english-er-api.service english-er-worker.service
mise run local:deploy
```

`local:deploy` runs `alembic upgrade head`, restarts `english-er-api.service`, then restarts `english-er-worker.service`. A migration failure stops before either restart. Service startup itself never migrates.

Both services keep the home directory read-only except for declared paths. The worker alone can write `~/.codex` because each fresh `codex exec` subprocess needs writable Codex runtime state. The API can write only application data, state, and `~/.cache/english-er`, where generated WAV files persist. Provider calls remain isolated with `--ephemeral --ignore-user-config --ignore-rules`.

The worker unit preserves the Codex launcher path returned by the shell, including Mise's stable `latest` symlink. Updating Codex can therefore replace the selected installation without leaving the worker pointed at a removed version. Run `local:install`, `systemctl --user daemon-reload`, and `local:deploy` once after changing the unit templates or installer.

Run `mise run speech:prepare` before installed speech use because the API service has no external network access. The API permits device access for its isolated Kokoro child process; the worker retains a private device namespace.

The default database is `~/.local/share/english-er/english-er.sqlite3`; state is under `~/.local/state/english-er`. Capture remains off until the marker `~/.local/state/english-er/capture-enabled` is explicitly created through the UI or API.

## Voxtype integration

After inspecting the current Voxtype configuration and receiving explicit approval, set its post-process command to the absolute current-checkout path shown below:

```toml
[output.post_process]
command = "/absolute/path/to/english-er/integrations/voxtype/english_er_capture.py"
timeout_ms = 1000
```

Do not change this configuration during offline verification. To roll it back, restore the previous post-process block or remove this block.

## Status and logs

```bash
systemctl --user status english-er-api.service english-er-worker.service
journalctl --user -u english-er-api.service -u english-er-worker.service --since today
```

Operational logs must not contain transcript text. The API listens only on `127.0.0.1:8001`. Host and origin validation, request/admission limits, and deadlines are enforced by the application; loopback binding alone is not the trust boundary. `/api/v1/health/live` checks the HTTP process; `/api/v1/health/ready` also requires a usable database schema. Settings parse `ENGLISH_ER_*` overrides at startup; `config.py` owns validated defaults and allowlists.

## Reversible uninstall

```bash
systemctl --user disable --now english-er-api.service english-er-worker.service
mise run local:install -- --uninstall
systemctl --user daemon-reload
```

Uninstalling units does not delete the database, spool, failed captures, capture marker, or generated audio. Back up or remove `~/.local/share/english-er`, `~/.local/state/english-er`, and `~/.cache/english-er` separately only after an explicit data-deletion decision.

## Live checks excluded from the offline gate

Live Codex consumes account capacity, live Voxtype requires the desktop session, and real installation changes user state. The operator must inspect the dry-run diff and current marker/service/config state, request approval, then separately validate a dictated transcript, restart recovery, absence of transcript text in logs, correction quality, hook latency, and the requested final capture state.

## Backup, restoration, and retention

For a consistent full backup, explicitly disable capture and stop both services, then copy the complete application data, state, and audio-cache roots to a private backup location. Include SQLite sidecar files if present. Restart the services afterward and restore capture only to the intended state. Backups contain transcript text and audio and need the same permissions and explicit deletion policy as the originals.

Before restoring live data, work on a separate copy: run SQLite `PRAGMA integrity_check` (expect `ok`) and `PRAGMA foreign_key_check` (expect no rows), migrate the copy to the current Alembic head, and inspect it with an isolated API/state root. Confirm transcript revisions, corrections, and referenced audio files. Only then, with capture disabled and both services stopped, replace the live roots. Keep the previous roots until the restored application has been verified.

Transcripts remain until explicit deletion. Deletion removes their correction/audio metadata and attempts associated WAV cleanup after commit; a filesystem failure may leave an orphan WAV. Spool failures retain malformed or conflicting captures for explicit inspection/removal. There is no automatic cache, failed-spool, or backup expiry. Uninstalling services does not erase any of these locations; include all of them in any permanent-data-removal decision.

## Network access and sensitive data

The Voxtype hook only reads stdin and writes the local spool. The worker sends complete transcript revisions to the provider selected by the installed Codex CLI; English-er does not select or override that provider's network destination or retention policy. Review Codex authentication/provider settings and terms before enabling capture. Codex runtime files live under `~/.codex`; English-er does not clear account credentials or unrelated CLI state.

Dependency setup contacts the configured package registries, including npm, PyPI, `download.pytorch.org`, and GitHub for the pinned spaCy model. `speech:prepare` downloads Kokoro model/voice files from Hugging Face (`huggingface.co` and its download/CDN endpoints) and performs local GPU synthesis. Hugging Face caches may live outside the English-er roots, normally under `~/.cache/huggingface`; they are shared with other applications and require a separate deletion decision. Installed API speech uses these cached files without external network access.

The app does not record source microphone audio. It retains transcript text, corrections, generated speech, spool envelopes, and recovery metadata locally as described above. Operational logs exclude transcript/model content; use synthetic input and redact account details, local paths, and audio when reporting a problem. Capture applies to completed dictations while enabled; turn it off before dictating sensitive text. Backup copies and provider submissions require separate retention decisions.
