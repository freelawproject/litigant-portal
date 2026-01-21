import logging

from django.conf import settings

from .base import BaseLLMProvider
from .groq import GroqProvider
from .ollama import OllamaProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# Provider registry
_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "ollama": OllamaProvider,
    "groq": GroqProvider,
    "openai": OpenAIProvider,
}

# Cached provider instance
_provider_instance: BaseLLMProvider | None = None


def get_provider() -> BaseLLMProvider:
    """
    Get the configured LLM provider.

    Returns a cached instance to avoid recreating clients on every request.

    Returns:
        The configured LLM provider instance.

    Raises:
        ValueError: If the configured provider is not supported or not configured.
    """
    global _provider_instance

    if _provider_instance is not None:
        return _provider_instance

    provider_name = settings.CHAT_PROVIDER.lower()

    if provider_name not in _PROVIDERS:
        raise ValueError(
            f"Unknown chat provider: {provider_name}. "
            f"Supported providers: {list(_PROVIDERS.keys())}"
        )

    provider_class = _PROVIDERS[provider_name]

    try:
        _provider_instance = provider_class()
        logger.info(f"Initialized {provider_name} provider")
        return _provider_instance
    except ValueError as e:
        logger.error(f"Failed to initialize {provider_name} provider: {e}")
        raise


def register_provider(
    name: str, provider_class: type[BaseLLMProvider]
) -> None:
    """
    Register a new provider.

    This allows adding custom providers (e.g., local Ollama) without modifying
    the factory module.

    Args:
        name: The provider name (used in CHAT_PROVIDER setting).
        provider_class: The provider class to register.
    """
    _PROVIDERS[name.lower()] = provider_class
    logger.info(f"Registered provider: {name}")


def reset_provider() -> None:
    """
    Reset the cached provider instance.

    Useful for testing or when provider configuration changes.
    """
    global _provider_instance
    _provider_instance = None
