"""
Tool registry — the 'Agentic Tools' box.

A tool is three things: a name + description the model reads, a JSON schema for its
arguments, and a Python function that runs. That's it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from google import genai
from google.genai import types

@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., str]

    def to_api(self) -> dict[str, Any]:
        """Anthropic format — kept for compatibility."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def to_gemini(self) -> genai.protos.Tool:
        """
        Gemini wants a Tool proto wrapping a FunctionDeclaration.
        The parameter schema is the same JSON Schema shape we already have,
        but Gemini needs it as a protos.Schema object.
        """
        properties = {}
        for prop_name, prop_def in self.input_schema.get("properties", {}).items():
            properties[prop_name] = genai.protos.Schema(
                type=_json_type_to_gemini(prop_def.get("type", "string")),
                description=prop_def.get("description", ""),
            )

        parameters = genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties=properties,
            required=self.input_schema.get("required", []),
        )

        return genai.protos.Tool(
            function_declarations=[
                genai.protos.FunctionDeclaration(
                    name=self.name,
                    description=self.description,
                    parameters=parameters,
                )
            ]
        )


def _json_type_to_gemini(json_type: str) -> genai.protos.Type:
    """Map JSON Schema primitive types to Gemini proto Type enum."""
    return {
        "string":  genai.protos.Type.STRING,
        "number":  genai.protos.Type.NUMBER,
        "integer": genai.protos.Type.INTEGER,
        "boolean": genai.protos.Type.BOOLEAN,
        "array":   genai.protos.Type.ARRAY,
        "object":  genai.protos.Type.OBJECT,
    }.get(json_type, genai.protos.Type.STRING)   # default to STRING if unknown


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        """Anthropic format."""
        return [t.to_api() for t in self._tools.values()]

    def gemini_schemas(self) -> list[genai.protos.Tool]:
        """
        Gemini format. Pass this to GenerativeModel(tools=...).
        One Tool proto per registered tool.
        """
        return [t.to_gemini() for t in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            return tool.fn(**args)
        except Exception as exc:
            return f"Error running {name}: {exc}"