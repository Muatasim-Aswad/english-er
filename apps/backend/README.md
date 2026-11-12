# Backend

Python uses a `src` layout. `entrypoints` composes HTTP, CLI, and worker resources; `modules` owns business workflows; `infra` owns external resource mechanics; `platform` owns HTTP mechanisms; `shared` is pure reusable code. [Architecture](../../docs/ARCHITECTURE.md) defines import directions and public APIs.

The HTTP factory and OpenAPI generator must not open a database or create local state. [Development](../../docs/DEVELOPMENT.md) owns setup, checks, and generated contracts; [Operations](../../docs/OPERATIONS.md) owns migration and installation.
