import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[4]
CHECKER = REPOSITORY / "scripts/check_boundaries.py"


def check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def put(root: Path, path: str, content: str) -> None:
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content)


def test_current_application_obeys_import_boundaries() -> None:
    result = check(REPOSITORY)
    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_rejects_transport_leaks_and_private_feature_imports(tmp_path: Path) -> None:
    put(
        tmp_path,
        "apps/backend/src/english_er/modules/first/service.py",
        "from english_er.entrypoints.http import app\nfrom english_er.modules.second.service import work\nfrom fastapi import Request\n",
    )
    put(tmp_path, "apps/web/src/infra/client.ts", 'import { Page } from "../features/review/Page";')
    result = check(tmp_path)
    assert result.returncode == 1
    assert "modules cannot import entrypoints" in result.stdout
    assert "transport import outside HTTP boundary" in result.stdout
    assert "use second's public API" in result.stdout
    assert "infra cannot import features" in result.stdout
    assert "use review's public index" in result.stdout


def test_checker_rejects_cycles_through_public_feature_apis(tmp_path: Path) -> None:
    for owner, target in [("first", "second"), ("second", "first")]:
        put(
            tmp_path,
            f"apps/backend/src/english_er/modules/{owner}/service.py",
            f"from english_er.modules.{target} import work\n",
        )
        put(
            tmp_path,
            f"apps/web/src/features/{owner}/api.ts",
            f'import {{ work }} from "../{target}";',
        )
    result = check(tmp_path)
    assert result.returncode == 1
    assert "backend features: dependency cycle:" in result.stdout
    assert "web features: dependency cycle:" in result.stdout
