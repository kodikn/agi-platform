"""Level 0: LLM Core - LLM provider abstraction layer"""

from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    VLLM = "vllm"
    OPENROUTER = "openrouter"


class LLMMessage(Dict[str, Any]):
    """LLM message format"""
    role: str  # system, user, assistant
    content: str


class LLMResponse:
    """LLM response wrapper"""
    
    def __init__(
        self,
        content: str,
        model: str,
        provider: LLMProvider,
        tokens_input: int = 0,
        tokens_output: int = 0,
        stop_reason: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.model = model
        self.provider = provider
        self.tokens_input = tokens_input
        self.tokens_output = tokens_output
        self.stop_reason = stop_reason
        self.raw_response = raw_response or {}

    def __str__(self) -> str:
        return self.content


class BaseLLMProvider(ABC):
    """Base class for LLM providers"""
    
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.provider_name = "base"

    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Generate completion"""
        pass

    @abstractmethod
    async def stream_complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ):
        """Stream completion"""
        pass

    @abstractmethod
    async def tool_call(
        self,
        messages: List[LLMMessage],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """Call LLM with tools"""
        pass


class LLMCoreConfig:
    """LLM Core configuration"""
    
    def __init__(
        self,
        default_provider: LLMProvider = LLMProvider.OPENAI,
        default_model: str = "gpt-4",
        fallback_provider: LLMProvider = LLMProvider.ANTHROPIC,
        fallback_model: str = "claude-3-opus",
        enable_cost_tracking: bool = True,
        enable_token_tracking: bool = True,
        cache_responses: bool = True
    ):
        self.default_provider = default_provider
        self.default_model = default_model
        self.fallback_provider = fallback_provider
        self.fallback_model = fallback_model
        self.enable_cost_tracking = enable_cost_tracking
        self.enable_token_tracking = enable_token_tracking
        self.cache_responses = cache_responses


class LLMCore:
    """Level 0: LLM Core - Main LLM abstraction"""
    
    def __init__(self, config: LLMCoreConfig):
        self.config = config
        self.providers: Dict[str, BaseLLMProvider] = {}
        self.token_usage: Dict[str, Dict[str, int]] = {}
        self.cost_tracking: Dict[str, float] = {}
        
        logger.info(f"Initializing LLM Core with default provider: {config.default_provider}")

    def register_provider(self, name: str, provider: BaseLLMProvider):
        """Register an LLM provider"""
        self.providers[name] = provider
        self.token_usage[name] = {"input": 0, "output": 0}
        self.cost_tracking[name] = 0.0
        logger.info(f"Registered LLM provider: {name}")

    async def complete(
        self,
        messages: List[LLMMessage],
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Generate completion with fallback support"""
        
        provider = provider or self.config.default_provider
        model = model or self.config.default_model
        
        try:
            llm_provider = self.providers.get(provider.value)
            if not llm_provider:
                raise ValueError(f"Provider {provider} not registered")
            
            response = await llm_provider.complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Track usage
            if self.config.enable_token_tracking:
                self.token_usage[provider.value]["input"] += response.tokens_input
                self.token_usage[provider.value]["output"] += response.tokens_output
            
            logger.info(f"Completed with {provider.value}: {response.tokens_input + response.tokens_output} tokens")
            return response
            
        except Exception as e:
            logger.warning(f"Provider {provider} failed: {str(e)}. Falling back...")
            
            # Try fallback provider
            fallback_provider = self.providers.get(self.config.fallback_provider.value)
            if fallback_provider:
                response = await fallback_provider.complete(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                logger.info(f"Fallback completed with {self.config.fallback_provider.value}")
                return response
            
            raise

    async def stream_complete(
        self,
        messages: List[LLMMessage],
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ):
        """Stream completion"""
        
        provider = provider or self.config.default_provider
        llm_provider = self.providers.get(provider.value)
        
        if not llm_provider:
            raise ValueError(f"Provider {provider} not registered")
        
        async for chunk in llm_provider.stream_complete(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            yield chunk

    async def tool_call(
        self,
        messages: List[LLMMessage],
        tools: List[Dict[str, Any]],
        provider: Optional[LLMProvider] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Call LLM with tools"""
        
        provider = provider or self.config.default_provider
        llm_provider = self.providers.get(provider.value)
        
        if not llm_provider:
            raise ValueError(f"Provider {provider} not registered")
        
        return await llm_provider.tool_call(
            messages=messages,
            tools=tools,
            **kwargs
        )

    def get_token_usage(self, provider: Optional[str] = None) -> Dict[str, int]:
        """Get token usage statistics"""
        if provider:
            return self.token_usage.get(provider, {"input": 0, "output": 0})
        return self.token_usage

    def get_cost_estimate(self, provider: Optional[str] = None) -> float:
        """Get cost estimate"""
        if provider:
            return self.cost_tracking.get(provider, 0.0)
        return sum(self.cost_tracking.values())
