# Contributing

English-er supports local, single-user transcript review on Linux. Discuss larger changes and new integrations before implementing them. Ask questions in [Discussions](https://github.com/Muatasim-Aswad/english-er/discussions); report vulnerabilities through [Security](SECURITY.md).

Follow [Development](docs/DEVELOPMENT.md) for setup, [Architecture](docs/ARCHITECTURE.md) for ownership, and [Operations](docs/OPERATIONS.md) for live-state boundaries. Install the documented hooks. Run the complete gate before opening a pull request:

```bash
scripts/verify-task check
```

Fork the repository and submit focused pull requests with meaningful tests for changed behavior. Use synthetic examples; remove transcripts, account information, local paths, and secrets from reports and screenshots. Never run live capture or provider checks as routine verification.

Describe the resulting behavior, privacy implications, migrations and compatibility, and checks run; mark non-applicable items. Update authoritative documentation and regenerate both HTTP artifacts when contracts change. Generated files must not be edited by hand.

Maintainer pull requests require passing checks and another eligible CODEOWNER's approval, or a deliberate solo-maintainer admin bypass documented in the pull request. Auto-merge requires deliberate maintainer review and must wait for required checks and approvals.
