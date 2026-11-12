# Security

## Supported versions

Before the first release, `main` receives best-effort fixes. After the first release, only the latest release receives best-effort security support; upgrade before reporting a problem. There is no response-time guarantee.

## Reporting

Use [GitHub private vulnerability reporting](https://github.com/Muatasim-Aswad/english-er/security/advisories/new). Do not send vulnerability details, transcript text, audio, or credentials in public issues or Discussions.

## Trust boundary

English-er trusts the local OS user, their browser profile, installed dependencies, Codex CLI, and model files. It is an unauthenticated, loopback-only, single-user application. Local host/origin checks, request limits, and service sandboxing reduce exposure; they do not protect against a compromised local account. Do not expose it through a public interface, reverse proxy, shared machine account, or tunnel. Remote or multi-user operation is unsupported and would require an authentication/authorization design and a separate security review.

Captured text is untrusted input. Corrections are AI-generated suggestions, may be wrong, and require review. The Codex subprocess receives transcript text and can contact its provider using your account. Provider-side retention follows that provider's policies; local deletion cannot retract submissions. English-er does not manage Codex authentication or independently erase its runtime state.

[Operations](docs/OPERATIONS.md) documents permissions, network access, retention, deletion, and recovery. Reports and diagnostics must omit transcripts, audio, credentials, and private paths. The Voxtype and Codex integrations are unofficial; upstream behavior and terms can change.
