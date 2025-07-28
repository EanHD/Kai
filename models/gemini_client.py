import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def run_gemini(prompt: str, model_name: str = "gemini-1.5-flash", stream: bool = False):
    model = genai.GenerativeModel(model_name)
    if stream:
        response = model.generate_content(prompt, stream=True)
        async def generator():
            buffer = ""
            for chunk in response:
                if chunk.text:
                    buffer += chunk.text
                    if " " in buffer:
                        parts = buffer.split(" ")
                        for part in parts[:-1]:
                            yield part + " "
                        buffer = parts[-1]
            if buffer:
                yield buffer
        return generator()
    else:
        response = model.generate_content(prompt)
        return response.text.strip()