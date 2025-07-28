from langchain_ollama import OllamaLLM

def load_model(model_name="smollm2:1.7b", stream=True):
    return OllamaLLM(model=model_name, streaming=stream)