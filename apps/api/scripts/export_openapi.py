"""Write the service's OpenAPI document for the TypeScript SDK (research R-12)."""

import json
import sys
from pathlib import Path

from pono_api.config import Settings
from pono_api.main import create_app


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    # An empty configuration is enough: the schema does not depend on any secret.
    schema = create_app(Settings()).openapi()
    target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OpenAPI written to {target}")


if __name__ == "__main__":
    main()
