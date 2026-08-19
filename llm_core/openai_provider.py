"""OpenAI provider implementation"""

from typing import List, Dict, Any, Optional, AsyncIterator
import logging
import openai

from llm_core.base import BaseLLMProvider, LLMMessage, LLMResponse, LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        super().__init__(model, api_key)
        self.provider_name = "openai"
        openai.api_key = api_key
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using OpenAI"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=self.model,
                provider=LLMProvider.OPENAI,
                tokens_input=response.usage.prompt_tokens,
                tokens_output=response.usage.completion_tokens,
                stop_reason=response.choices[0].finish_reason,
                raw_response=response.model_dump()
            )
        except Exception as e:
            logger.error(f"OpenAI completion error: {str(e)}")
            raise

    async def stream_complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion from OpenAI"""
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI streaming error: {str(e)}")
            raise

    async def tool_call(
        self,
        messages: List[LLMMessage],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """Call OpenAI with tools"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                **kwargs
            )
            
            return {
                "content": response.choices[0].message.content,
                "tool_calls": response.choices[0].message.tool_calls,
                "finish_reason": response.choices[0].finish_reason,
                "tokens": {
                    "input": response.usage.prompt_tokens,
                    "output": response.usage.completion_tokens
                }
            }
        except Exception as e:
            logger.error(f"OpenAI tool call error: {str(e)}")
            raise
