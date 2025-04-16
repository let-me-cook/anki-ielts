from openai import OpenAI
from src.datatypes import JSONFile
from src.datatypes_instruction import InstructionData
from src.general import generate_anki_card
from src.genner import Genner
from os import getenv
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# gets API Key from environment variable OPENAI_API_KEY
client = OpenAI(
	base_url="https://openrouter.ai/api/v1",
	api_key=getenv("OPENROUTER_API_KEY"),
)

genner = Genner(client, model="google/gemini-2.0-flash-001")
jsonfile = JSONFile.from_json_file("raw/day_2.json")
instructions = InstructionData.from_json_file("data/instruction_detailed_feedback.json")

for instruction in instructions:
    try:
        anki_cards = generate_anki_card(
            genner,
            data=jsonfile,
            data_paths=instruction.data_paths,
            instruction=instruction.instruction,
            type_of_anki_card=instruction.type_of_anki_card,
        ).unwrap()
    except Exception as e:
        logger.error(f"Error generating Anki card: {e}")

logger.info("Anki cards generated successfully.")
for anki_card in anki_cards:
    logger.info(f"Generated Anki card: {anki_card}")