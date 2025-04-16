from os import getenv

from dotenv import load_dotenv
from openai import OpenAI

from src.datatypes import JSONFile
from src.genner import Genner
from src.sub.detailed_feedback import detailed_feedback_grammatical_error_correction

load_dotenv()

# gets API Key from environment variable OPENAI_API_KEY
client = OpenAI(
	base_url="https://openrouter.ai/api/v1",
	api_key=getenv("OPENROUTER_API_KEY"),
)

genner = Genner(client, model="google/gemini-2.0-flash-001")

jsonfile = JSONFile.from_json_file("raw/day_2.json")

detailed_feedback_grammatical_error_correction(genner, jsonfile.detailed_feedback)
