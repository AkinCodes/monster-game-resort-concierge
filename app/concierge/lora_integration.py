"""
LoRA Model Integration for Monster Resort Concierge
===================================================

Integrates LoRA fine-tuned model as a fallback when OpenAI is unavailable.

Usage in app/main.py:
    from .lora_integration import LoRABackend

    lora = LoRABackend("lora-concierge/final")

    # Try OpenAI first, fallback to LoRA
    try:
        response = openai_call(...)
    except Exception:
        response = lora.generate(query)
"""

from typing import Optional, Dict
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch
from ..cctv.logging_utils import logger


class LoRABackend:
    """
    LoRA model backend for local inference.

    Features:
    - Lazy loading (only loads when first used)
    - GPU/CPU support
    - Caching for repeated queries
    - Graceful degradation
    """

    def __init__(
        self,
        adapter_path: str,
        base_model: str = "microsoft/Phi-3-mini-4k-instruct",
        device: Optional[str] = None,
    ):
        """
        Initialize LoRA backend.

        Args:
            adapter_path: Path to LoRA adapter directory
            base_model: Base model name
            device: Device to use ('cuda', 'cpu', or None for auto)
        """
        self.adapter_path = Path(adapter_path)
        self.base_model = base_model

        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Lazy loading
        self.model = None
        self.tokenizer = None
        self._is_loaded = False

        # Simple cache
        self._cache = {}

        logger.info(
            f"LoRA backend initialized (device: {self.device}, adapter: {adapter_path})"
        )

    def _load_model(self):
        """Lazy load model on first use."""

        if self._is_loaded:
            return

        logger.info(f"Loading LoRA model from {self.adapter_path}")

        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.base_model, trust_remote_code=True
            )
            self.tokenizer.pad_token = self.tokenizer.eos_token

            # Load base model
            logger.info(f"Loading base model: {self.base_model}")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )

            if self.device == "cpu":
                self.model = self.model.to("cpu")

            # Load LoRA adapter
            logger.info(f"Loading LoRA adapter from {self.adapter_path}")
            self.model = PeftModel.from_pretrained(self.model, str(self.adapter_path))
            self.model.eval()

            self._is_loaded = True
            logger.info("✅ LoRA model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load LoRA model: {e}")
            raise

    def generate(
        self,
        query: str,
        max_new_tokens: int = 200,
        temperature: float = 0.7,
        top_p: float = 0.9,
        use_cache: bool = True,
    ) -> str:
        """
        Generate response using LoRA model.

        Args:
            query: User query
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            use_cache: Whether to use cached responses

        Returns:
            Generated response
        """

        # Check cache
        if use_cache and query in self._cache:
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return self._cache[query]

        # Ensure model is loaded
        if not self._is_loaded:
            self._load_model()

        try:
            # Format prompt
            prompt = f"<|user|>\n{query}<|end|>\n<|assistant|>\n"

            # Tokenize
            inputs = self.tokenizer(
                prompt, return_tensors="pt", truncation=True, max_length=512
            ).to(self.model.device)

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )

            # Decode
            full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Extract assistant response
            if "<|assistant|>" in full_response:
                response = full_response.split("<|assistant|>")[-1].strip()
            else:
                response = full_response.replace(prompt, "").strip()

            # Cache result
            if use_cache:
                self._cache[query] = response

            logger.debug(f"Generated response: {response[:100]}...")
            return response

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return (
                "I apologize, but I'm having trouble generating a response right now."
            )

    def is_available(self) -> bool:
        """Check if LoRA model is available."""
        return (
            self.adapter_path.exists()
            and (self.adapter_path / "adapter_config.json").exists()
        )

    def unload(self):
        """Unload model from memory."""
        if self._is_loaded:
            del self.model
            del self.tokenizer
            torch.cuda.empty_cache()
            self._is_loaded = False
            self._cache.clear()
            logger.info("LoRA model unloaded from memory")


# Convenience function for app integration
def create_lora_backend(adapter_path: str) -> Optional[LoRABackend]:
    """
    Create LoRA backend with error handling.

    Returns None if adapter not found (graceful degradation).
    """
    try:
        backend = LoRABackend(adapter_path)
        if backend.is_available():
            return backend
        else:
            logger.warning(f"LoRA adapter not found at {adapter_path}")
            return None
    except Exception as e:
        logger.warning(f"Failed to initialize LoRA backend: {e}")
        return None
