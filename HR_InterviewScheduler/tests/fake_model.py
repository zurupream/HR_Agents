"""Deterministic scripted BaseLlm implementation for end-to-end ADK agent tests."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, AsyncGenerator

from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field, PrivateAttr


def tool_call(
    name: str,
    args: dict[str, Any] | None = None,
    **kwargs: Any,
) -> LlmResponse:
    """Build an LlmResponse that invokes a single named tool with arguments."""
    call_args = dict(args or {})
    call_args.update(kwargs)
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_function_call(name=name, args=call_args)],
        ),
        partial=False,
        turn_complete=True,
    )


def final_text(text: str = "Done.") -> LlmResponse:
    """Build an LlmResponse with final model text and no function calls."""
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=text)],
        ),
        partial=False,
        turn_complete=True,
    )


def _coerce_step(step: Any) -> LlmResponse:
    if isinstance(step, LlmResponse):
        return step
    if isinstance(step, types.Content):
        return LlmResponse(content=step, partial=False, turn_complete=True)
    if isinstance(step, types.Part):
        return LlmResponse(
            content=types.Content(role="model", parts=[step]),
            partial=False,
            turn_complete=True,
        )
    if isinstance(step, str):
        return final_text(step)
    if isinstance(step, tuple):
        if len(step) == 1:
            return tool_call(step[0], {})
        if len(step) == 2:
            return tool_call(step[0], step[1] or {})
        raise ValueError(f"Unsupported tuple step format: {step!r}")
    if isinstance(step, dict):
        if "text" in step and len(step) == 1:
            return final_text(str(step["text"]))
        if "tool" in step:
            return tool_call(step["tool"], step.get("args") or {})
        if "name" in step:
            return tool_call(step["name"], step.get("args") or {})
        if "function_call" in step:
            fc = step["function_call"]
            if isinstance(fc, dict):
                return tool_call(fc["name"], fc.get("args") or {})
            if isinstance(fc, types.FunctionCall):
                return tool_call(fc.name or "", dict(fc.args or {}))
        if "text" in step:
            return final_text(str(step["text"]))
    raise TypeError(f"Unsupported scripted step: {step!r}")


class ScriptedLlm(BaseLlm):
    """A deterministic BaseLlm that yields a scripted sequence of LlmResponses."""

    model: str = "scripted-llm"
    responses: list[LlmResponse] = Field(default_factory=list)
    requests: list[LlmRequest] = Field(default_factory=list)
    _index: int = PrivateAttr(default=0)

    def __init__(
        self,
        steps: Iterable[Any] | None = None,
        *,
        responses: Iterable[Any] | None = None,
        script: Iterable[Any] | None = None,
        model: str = "scripted-llm",
        **data: Any,
    ) -> None:
        raw_steps = steps if steps is not None else (responses if responses is not None else script)
        coerced = [_coerce_step(s) for s in (raw_steps or [])]
        super().__init__(model=model, responses=coerced, **data)

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    tool_call = staticmethod(tool_call)
    final_text = staticmethod(final_text)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Yield the next scripted LlmResponse for a single model turn."""
        self.requests.append(llm_request)
        if self._index < len(self.responses):
            response = self.responses[self._index]
            self._index += 1
            yield response
        else:
            yield final_text("Done.")
