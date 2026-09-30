"""Print the service's OpenAPI schema, the source the TypeScript client is generated from."""

import json

from emva_api.main import app


def main() -> None:
    print(json.dumps(app.openapi(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
