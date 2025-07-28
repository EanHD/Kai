import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def run_openai(prompt: str, stream: bool = False):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        stream=stream
    )

    if stream:
        buffer = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                buffer += chunk.choices[0].delta.content
                if " " in buffer:
                    parts = buffer.split(" ")
                    for part in parts[:-1]:
                        yield part + " "
                    buffer = parts[-1]
        if buffer:
            yield buffer
    else:
        return response.choices[0].message.content.strip()