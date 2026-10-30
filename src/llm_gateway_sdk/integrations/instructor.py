"""Optional ``instructor`` structured-output integration (`llm-gateway-sdk[structured]`)."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI, OpenAI

from llm_gateway_sdk.exceptions import InvalidGatewaySettingsError
from llm_gateway_sdk.settings import GatewaySettings

__all__ = [
    "create_async_instructor_client",
    "create_instructor_client",
]


def _import_instructor() -> Any:
    try:
        import instructor
    except ImportError as exc:
        raise ImportError(
            "instructor is required for llm_gateway_sdk.integrations.instructor. "
            "Install it with: pip install 'llm-gateway-sdk[structured]'"
        ) from exc
    return instructor


def create_instructor_client(
    client_or_settings: OpenAI | GatewaySettings,
    *,
    mode: Any | None = None,
    **kwargs: Any,
) -> Any:
    """Wrap a synchronous :class:`openai.OpenAI` client (or ``GatewaySettings``) with Instructor.

    Args:
        client_or_settings: Either an initialized :class:`openai.OpenAI` client or a
            :class:`GatewaySettings` instance.
        mode: Optional ``instructor.Mode`` (defaults to ``instructor.Mode.TOOLS``).
        **kwargs: Additional keyword arguments forwarded to ``instructor.from_openai``.

    Returns:
        An ``instructor.Instructor`` client bound to the gateway.
    """
    instructor = _import_instructor()

    if isinstance(client_or_settings, GatewaySettings):
        openai_client = client_or_settings.create_client()
    elif isinstance(client_or_settings, OpenAI):
        openai_client = client_or_settings
    else:
        raise InvalidGatewaySettingsError(
            "create_instructor_client expects an openai.OpenAI or GatewaySettings instance"
        )

    effective_mode = instructor.Mode.TOOLS if mode is None else mode
    return instructor.from_openai(openai_client, mode=effective_mode, **kwargs)


def create_async_instructor_client(
    client_or_settings: AsyncOpenAI | GatewaySettings,
    *,
    mode: Any | None = None,
    **kwargs: Any,
) -> Any:
    """Wrap an async :class:`openai.AsyncOpenAI` client (or ``GatewaySettings``) with Instructor.

    Args:
        client_or_settings: Either an initialized :class:`openai.AsyncOpenAI` client or a
            :class:`GatewaySettings` instance.
        mode: Optional ``instructor.Mode`` (defaults to ``instructor.Mode.TOOLS``).
        **kwargs: Additional keyword arguments forwarded to ``instructor.from_openai``.

    Returns:
        An ``instructor.AsyncInstructor`` client bound to the gateway.
    """
    instructor = _import_instructor()

    if isinstance(client_or_settings, GatewaySettings):
        openai_client = client_or_settings.create_async_client()
    elif isinstance(client_or_settings, AsyncOpenAI):
        openai_client = client_or_settings
    else:
        raise InvalidGatewaySettingsError(
            "create_async_instructor_client expects an AsyncOpenAI or GatewaySettings instance"
        )

    effective_mode = instructor.Mode.TOOLS if mode is None else mode
    return instructor.from_openai(openai_client, mode=effective_mode, **kwargs)
