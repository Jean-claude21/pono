"""A small validator for the OpenAPI 3.1 subset the Pono contract uses.

It checks types (including `null` in a type list), enums, required keys, properties, items,
`$ref`, `allOf`, `oneOf`/`anyOf`, and the `uuid` and `date-time` formats. It returns every
violation with its path, so a failing test says exactly where the payload leaves the contract.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import yaml

SPECS = Path(__file__).resolve().parents[4] / "specs"
# One document per phase; a later phase adds paths and replaces same-named schemas (002 R-10).
CONTRACTS = (
    SPECS / "001-project-workshop" / "contracts" / "openapi.yaml",
    SPECS / "002-guarded-release" / "contracts" / "openapi.yaml",
    SPECS / "003-mcp-server" / "contracts" / "openapi.yaml",
    SPECS / "004-dev-runtime" / "contracts" / "openapi.yaml",
)
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "patch"})
Schema = dict[str, Any]

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "null": (type(None),),
}


def load_contract() -> Schema:
    merged: Schema = {"paths": {}, "components": {"schemas": {}, "responses": {}}}
    for contract in CONTRACTS:
        document = cast(Schema, yaml.safe_load(contract.read_text(encoding="utf-8")))
        merged["paths"].update(document.get("paths", {}))
        for section, items in document.get("components", {}).items():
            merged["components"].setdefault(section, {}).update(items)
    return merged


class ContractChecker:
    def __init__(self, contract: Schema) -> None:
        self.contract = contract

    def schema(self, name: str) -> Schema:
        return cast(Schema, self.contract["components"]["schemas"][name])

    def resolve(self, schema: Schema) -> Schema:
        while "$ref" in schema:
            path = str(schema["$ref"]).removeprefix("#/").split("/")
            node: Any = self.contract
            for part in path:
                node = node[part]
            schema = cast(Schema, node)
        return schema

    def errors(self, value: object, schema: Schema, path: str = "$") -> list[str]:
        schema = self.resolve(schema)
        found: list[str] = []
        for part in schema.get("allOf", []):
            found += self.errors(value, part, path)
        for key in ("oneOf", "anyOf"):
            if key in schema:
                options = [self.errors(value, option, path) for option in schema[key]]
                if all(options):
                    found.append(f"{path}: matches no option of {key}")
        types = schema.get("type")
        if types is not None:
            allowed = types if isinstance(types, list) else [types]
            python_types = tuple(t for name in allowed for t in _TYPES[name])
            if isinstance(value, bool) and "boolean" not in allowed:
                return [*found, f"{path}: boolean where {allowed} expected"]
            if not isinstance(value, python_types):
                return [*found, f"{path}: {type(value).__name__} where {allowed} expected"]
        if "enum" in schema and value not in schema["enum"]:
            found.append(f"{path}: {value!r} not in {schema['enum']}")
        if isinstance(value, str):
            found += self._format(value, schema.get("format"), path)
        if isinstance(value, dict):
            for key in schema.get("required", []):
                if key not in value:
                    found.append(f"{path}: missing required '{key}'")
            properties = schema.get("properties", {})
            for key, item in value.items():
                if key in properties:
                    found += self.errors(item, properties[key], f"{path}.{key}")
                elif isinstance(schema.get("additionalProperties"), dict):
                    found += self.errors(item, schema["additionalProperties"], f"{path}.{key}")
        if isinstance(value, list) and "items" in schema:
            for index, item in enumerate(value):
                found += self.errors(item, schema["items"], f"{path}[{index}]")
        return found

    @staticmethod
    def _format(value: str, format_name: object, path: str) -> list[str]:
        try:
            if format_name == "uuid":
                UUID(value)
            elif format_name == "date-time":
                datetime.fromisoformat(value)
        except ValueError:
            return [f"{path}: {value!r} is not a valid {format_name}"]
        return []

    def response_schema(self, path: str, method: str, status: int) -> Schema | None:
        responses = self.contract["paths"][path][method.lower()]["responses"]
        response = self.resolve(cast(Schema, responses[str(status)]))
        content = response.get("content", {}).get("application/json")
        return cast(Schema, content["schema"]) if content else None


__all__ = ["HTTP_METHODS", "ContractChecker", "load_contract"]
