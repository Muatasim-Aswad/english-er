# Changelog

Changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and product versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-11-13

### Security

- Updated vulnerable Python and JavaScript dependencies, including certificate roots, file locks, HTTP clients, and the Vite+ toolchain.

## [0.1.0] - 2026-11-12

### Added

- Initial public source for opt-in Voxtype capture, revision-checked transcript editing, Codex corrections, review, retry, deletion, and local Kokoro playback.
- Loopback-only API and web UI, systemd integration, migrations and recovery documentation.
- Frozen dependencies and an offline verification gate covering boundaries, contracts, tests, browser flows, and production serving.

### Known limits

- Linux/systemd, a compatible Codex CLI, and CUDA-backed Kokoro are required for the complete workflow. Live provider, desktop capture, and GPU synthesis are excluded from the normal gate.
- Single-user loopback operation only; no authentication, remote access, or automatic cache/backup expiry.
