"""Print the application OpenAPI schema without starting runtime services."""

import json
import sys

from english_er.entrypoints.http import create_app


def main() -> None:
    schema = create_app().openapi()
    json.dump(schema, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
