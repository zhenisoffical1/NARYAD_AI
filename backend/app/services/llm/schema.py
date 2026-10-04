"""JSON-схема для structured outputs из Pydantic-модели.

API принимает подмножество JSON Schema: у объектов обязательны `additionalProperties: false`
и полный `required`, а числовые и строковые ограничения (minimum, maxLength…) не поддерживаются.
Поэтому схема для API — «строгая и простая», а границы проверяет сама Pydantic-модель после ответа.
"""

from typing import Any

from pydantic import BaseModel

_DROP = frozenset(
    {
        "title",
        "default",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    }
)


def _strict(node: Any) -> Any:
    if isinstance(node, dict):
        out = {k: _strict(v) for k, v in node.items() if k not in _DROP}
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"])
        return out
    if isinstance(node, list):
        return [_strict(item) for item in node]
    return node


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    result: dict[str, Any] = _strict(model.model_json_schema())
    return result
