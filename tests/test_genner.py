from openai import OpenAI
from src.genner import Genner
from os import getenv
from dotenv import load_dotenv

load_dotenv()

# gets API Key from environment variable OPENAI_API_KEY
client = OpenAI(
	base_url="https://openrouter.ai/api/v1",
	api_key=getenv("OPENROUTER_API_KEY"),
)

genner = Genner(client, model="google/gemini-2.0-flash-001")

genner.ch_completion(
	chat=[{"role": "user", "content": "What is the capital of France?"}]
)
