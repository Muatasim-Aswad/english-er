# Source-only releases

English-er is installed from Git. Releases publish a versioned tag and release notes; GitHub provides its standard source archives. There are no custom bundles, binaries, container images, or downloadable build outputs.

`apps/backend/pyproject.toml` owns the product version. The CLI, API schema, browser build, and build-information endpoint derive from it. Update it once per release, refresh the lockfile, move the Unreleased changelog entries into a dated version section, and regenerate HTTP artifacts:

```bash
uv lock --directory apps/backend
mise run api:generate
scripts/verify-task check
```

Review and merge the release commit through the normal pull-request process. Tag that exact commit `vX.Y.Z`; the tag must match the product version. Push only the reviewed tag after branch publication is approved. The Release workflow validates the tag and changelog, runs the full gate and redacted source scan, then creates a release with that changelog section. Write permission is limited to the publishing job. Release tags must never move.

Rehearse the same release checks without publishing:

```bash
mise run release:check -- vX.Y.Z
scripts/verify-task check
scripts/scan-secrets
```

For a publication failure, rerun the workflow for the existing tag. It verifies an already published release rather than overwriting it. Immutable releases must be enabled before publication.

## Build identity

The build reads version from installed package metadata generated from `pyproject.toml`, and clean revision/commit time from Git. Missing Git or modified/untracked source reports revision `dev`. Build time is `SOURCE_DATE_EPOCH` when set, otherwise the clean commit time; development builds use the current time. This keeps clean rebuild identity deterministic. Actual attempt times remain in CI logs.

The web build embeds this identity and writes ignored `dist/version.json`. The API captures that file at startup, serves the running identity uncached, and logs it. Replacing frontend files alone cannot claim that the backend restarted. About English-er compares the loaded UI with the served build when opened or rechecked and offers Reload for a different build. A revision-only local browser marker suppresses repeated update notices; clearing browser site data clears it. No transcript or account data is stored there.

`english-er --version` works from installed metadata without Git or network access. `english-er build-info` prints source identity as JSON. `mise run local:deploy` refuses a stale or dirty frontend build and compares the running endpoint with the intended revision after restarting the API.
