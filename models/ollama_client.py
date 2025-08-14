from functools import lru_cache
from typing import Optional

from langchain_ollama import OllamaLLM

# Known good slugs in the Ollama library:
#   - smollm2:1.7b
#   - phi4-mini:3.8b   (aka phi4-mini reasoning 3.8B)
#   - deepseek-coder:1.3b  (closest to "2b"; official tags are 1.3b, 6.7b, 33b)
# If you really need a 2B-class code model, consider codegemma:2b separately.

# Optional: alias map so we can accept friendly names like "deepseekcoder:2b".
ALIASES = {
    "deepseekcoder:2b": "deepseek-coder:1.3b",
    "deepseek-coder:2b": "deepseek-coder:1.3b",
    "phi4-mini:3.8b": "phi4-mini:3.8b",
    "smollm2:1.7b": "smollm2:1.7b",
}

@lru_cache(maxsize=16)
def load_model(slug: str = "smollm2:1.7b", stream: bool = False) -> OllamaLLM:
    canonical = ALIASES.get(slug.lower(), slug)
    return OllamaLLM(model=canonical, streaming=stream)

def invoke(slug: str, prompt: str, stream: bool = False) -> str:
    llm = load_model(slug, stream=stream)
    return llm.invoke(prompt)