# Voxtype capture hook

The hook atomically spools a version-1 capture only when `~/.local/state/english-er/capture-enabled` exists, then returns stdin exactly. It has no third-party dependencies and never contacts the backend or a model.

This is an unofficial integration targeting Voxtype 1.1.1; upstream changes can break its post-process contract. Follow Voxtype’s terms and review [Operations](../../docs/OPERATIONS.md) before enabling capture.

After explicitly approving the configuration change, configure Voxtype manually with the absolute current-checkout hook path:

```toml
[output.post_process]
command = "/absolute/path/to/english_er_capture.py"
timeout_ms = 1000
```

Do not enable capture during installation. The application capture control owns the marker.

Offline checks and `local:install` do not modify Voxtype configuration. Restore the previous post-process block to roll back this integration.

Run the warmed local latency gate with `python3 integrations/voxtype/benchmark.py`.
