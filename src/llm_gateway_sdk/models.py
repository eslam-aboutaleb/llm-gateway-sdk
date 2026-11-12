"""Layer 0: Provider-agnostic request/response models and SSE stream iterators.

Provides strongly-typed Pydantic v2 models for chat completions, streaming chunks,
tool calling, vector embeddings, and model discovery without depending on any
vendor-specific LLM SDK.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from llm_gateway_sdk.exceptions import GatewayConnectionError, GatewayTimeoutError

__all__ = [
    "AsyncGatewayStream",
    "ChatChoice",
    "ChatCompletion",
    "ChatCompletionChunk",
    "ChatDelta",
    "ChatDeltaFunctionCall",
    "ChatDeltaToolCall",
    "ChatDeltaToolCallFunction",
    "ChatMessage",
    "ChatResponse",
    "ChatStreamChoice",
    "ChatStreamChunk",
    "CreateEmbeddingResponse",
    "EmbeddingData",
    "EmbeddingResponse",
    "EmbeddingUsage",
    "FunctionCall",
    "GatewayStream",
    "ModelInfo",
    "ModelListResponse",
    "RawGatewayResponse",
    "TokenUsage",
    "ToolCall",
]

T = TypeVar("T")


class FunctionCall(BaseModel):
    """Function name and JSON-serialized arguments returned by a tool call."""

    model_config = ConfigDict(extra="allow", frozen=True)

    name: str
    arguments: str = ""


class ToolCall(BaseModel):
    """Tool invocation requested by the model."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    type: str = "function"
    function: FunctionCall


class ChatMessage(BaseModel):
    """Assistant or conversation message in a chat completion response."""

    model_config = ConfigDict(extra="allow", frozen=True)

    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatChoice(BaseModel):
    """Single completion choice returned by ``/v1/chat/completions``."""

    model_config = ConfigDict(extra="allow", frozen=True)

    index: int = 0
    message: ChatMessage
    finish_reason: str | None = None


class TokenUsage(BaseModel):
    """Token consumption metadata for a chat or embedding request."""

    model_config = ConfigDict(extra="allow", frozen=True)

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """Provider-agnostic response from ``POST /v1/chat/completions``."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str = ""
    object: str = "chat.completion"
    created: int = 0
    model: str = ""
    choices: list[ChatChoice] = Field(default_factory=list)
    usage: TokenUsage | None = None
    request_id: str | None = None
    _request_id: str | None = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "_request_id", self.request_id)

    @property
    def content(self) -> str | None:
        """Return the text content of the first completion choice, if present."""
        if not self.choices:
            return None
        return self.choices[0].message.content

    @property
    def tool_calls(self) -> list[ToolCall]:
        """Return the tool calls from the first completion choice, or an empty list."""
        if not self.choices or not self.choices[0].message.tool_calls:
            return []
        return list(self.choices[0].message.tool_calls)


class ChatDeltaToolCallFunction(BaseModel):
    """Incremental function call fragment in a streaming chunk."""

    model_config = ConfigDict(extra="allow", frozen=True)

    name: str | None = None
    arguments: str | None = None


class ChatDeltaToolCall(BaseModel):
    """Incremental tool call fragment in a streaming chunk."""

    model_config = ConfigDict(extra="allow", frozen=True)

    index: int = 0
    id: str | None = None
    type: str | None = None
    function: ChatDeltaToolCallFunction | None = None


class ChatDelta(BaseModel):
    """Incremental message delta in a streaming chat completion chunk."""

    model_config = ConfigDict(extra="allow", frozen=True)

    role: str | None = None
    content: str | None = None
    tool_calls: list[ChatDeltaToolCall] | None = None


class ChatStreamChoice(BaseModel):
    """Single choice delta in a streaming chat completion chunk."""

    model_config = ConfigDict(extra="allow", frozen=True)

    index: int = 0
    delta: ChatDelta = Field(default_factory=ChatDelta)
    finish_reason: str | None = None


class ChatStreamChunk(BaseModel):
    """Provider-agnostic SSE chunk from ``POST /v1/chat/completions`` (`stream=True`)."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str = ""
    object: str = "chat.completion.chunk"
    created: int = 0
    model: str = ""
    choices: list[ChatStreamChoice] = Field(default_factory=list)
    usage: TokenUsage | None = None

    @property
    def content(self) -> str:
        """Return the incremental text delta of the first choice (or ``""`` if empty)."""
        if not self.choices:
            return ""
        return self.choices[0].delta.content or ""


class EmbeddingData(BaseModel):
    """Single vector embedding item returned by ``POST /v1/embeddings``."""

    model_config = ConfigDict(extra="allow", frozen=True)

    object: str = "embedding"
    index: int = 0
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    """Token usage metadata for ``POST /v1/embeddings``."""

    model_config = ConfigDict(extra="allow", frozen=True)

    prompt_tokens: int = 0
    total_tokens: int = 0


class EmbeddingResponse(BaseModel):
    """Provider-agnostic response from ``POST /v1/embeddings``."""

    model_config = ConfigDict(extra="allow", frozen=True)

    object: str = "list"
    model: str = ""
    data: list[EmbeddingData] = Field(default_factory=list)
    usage: EmbeddingUsage | None = None
    request_id: str | None = None
    _request_id: str | None = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "_request_id", self.request_id)

    @property
    def vectors(self) -> list[list[float]]:
        """Return all embedding vectors in response order."""
        return [item.embedding for item in self.data]

    @property
    def embeddings(self) -> list[list[float]]:
        """Return all embedding vectors in response order (alias for :attr:`vectors`)."""
        return [item.embedding for item in self.data]

    @property
    def embedding(self) -> list[float]:
        """Return the first embedding vector (convenience for single-input calls)."""
        if not self.data:
            return []
        return self.data[0].embedding


class ModelInfo(BaseModel):
    """Metadata for a single gateway model alias from ``GET /v1/models``."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "litellm"


class ModelListResponse(BaseModel):
    """Provider-agnostic response from ``GET /v1/models``."""

    model_config = ConfigDict(extra="allow", frozen=True)

    object: str = "list"
    data: list[ModelInfo] = Field(default_factory=list)
    request_id: str | None = None
    _request_id: str | None = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "_request_id", self.request_id)

    @property
    def model_ids(self) -> list[str]:
        """Return the list of available model alias IDs."""
        return [item.id for item in self.data]


class RawGatewayResponse(Generic[T]):
    """Wrapper exposing HTTP status, response headers, and parsed model payload."""

    def __init__(
        self,
        *,
        status_code: int,
        headers: httpx.Headers,
        request_id: str | None,
        parsed: T,
    ) -> None:
        self.status_code = status_code
        self.headers = headers
        self.request_id = request_id
        self._parsed = parsed

    def parse(self) -> T:
        """Return the parsed typed response object."""
        return self._parsed


def _parse_sse_line(raw_line: str) -> ChatStreamChunk | bool | None:
    """Parse a single SSE line.

    Returns:
        - ``ChatStreamChunk`` for a valid JSON ``data:`` frame
        - ``False`` when ``data: [DONE]`` is encountered
        - ``None`` for comments, keep-alives, or blank lines
    """
    line = raw_line.strip()
    if not line or line.startswith(":"):
        return None
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload:
        return None
    if payload == "[DONE]":
        return False
    data = json.loads(payload)
    return ChatStreamChunk.model_validate(data)


class GatewayStream(Iterator[ChatStreamChunk]):
    """Synchronous Server-Sent Events (SSE) stream of :class:`ChatStreamChunk`."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._iterator = self._iter_chunks()
        self.request_id: str | None = response.headers.get("x-request-id")

    def _iter_chunks(self) -> Iterator[ChatStreamChunk]:
        try:
            for line in self._response.iter_lines():
                parsed = _parse_sse_line(line)
                if parsed is False:
                    break
                if isinstance(parsed, ChatStreamChunk):
                    yield parsed
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError("Gateway streaming read timed out") from exc
        except httpx.HTTPError as exc:
            raise GatewayConnectionError("Gateway streaming connection interrupted") from exc
        finally:
            self.close()

    def __iter__(self) -> GatewayStream:
        return self

    def __next__(self) -> ChatStreamChunk:
        return next(self._iterator)

    def iter_text(self) -> Iterator[str]:
        """Yield non-empty text deltas from the stream."""
        for chunk in self:
            if chunk.content:
                yield chunk.content

    def close(self) -> None:
        """Close the underlying HTTP stream and release the connection back to the pool."""
        self._response.close()

    def __enter__(self) -> GatewayStream:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncGatewayStream(AsyncIterator[ChatStreamChunk]):
    """Asynchronous Server-Sent Events (SSE) stream of :class:`ChatStreamChunk`."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._iterator = self._aiter_chunks()
        self.request_id: str | None = response.headers.get("x-request-id")

    async def _aiter_chunks(self) -> AsyncIterator[ChatStreamChunk]:
        try:
            async for line in self._response.aiter_lines():
                parsed = _parse_sse_line(line)
                if parsed is False:
                    break
                if isinstance(parsed, ChatStreamChunk):
                    yield parsed
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError("Gateway async streaming read timed out") from exc
        except httpx.HTTPError as exc:
            raise GatewayConnectionError("Gateway async streaming connection interrupted") from exc
        finally:
            await self.close()

    def __aiter__(self) -> AsyncGatewayStream:
        return self

    async def __anext__(self) -> ChatStreamChunk:
        return await self._iterator.__anext__()

    async def iter_text(self) -> AsyncIterator[str]:
        """Yield non-empty text deltas from the async stream."""
        async for chunk in self:
            if chunk.content:
                yield chunk.content

    async def close(self) -> None:
        """Close the underlying async HTTP stream and release the connection."""
        await self._response.aclose()

    async def aclose(self) -> None:
        """Alias for :meth:`close`."""
        await self.close()

    async def __aenter__(self) -> AsyncGatewayStream:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


ChatCompletion = ChatResponse
ChatCompletionChunk = ChatStreamChunk
ChatDeltaFunctionCall = ChatDeltaToolCallFunction
CreateEmbeddingResponse = EmbeddingResponse
