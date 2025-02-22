from pathlib import Path
from src.anki import generate_anki_deck
import json
import os

from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
	json_files = Path("raw").glob("*.json")
	output_filepath = Path("./anki-ielts.json")

	for filepath in json_files:

		# Read input JSON
		input_data = json.loads(filepath.read_text(encoding="utf-8"))

		# Generate deck
		deck = generate_anki_deck(input_data, os.getenv("DECK_UUID"))
		assert deck

		# Create output directory if needed
		output_filepath.parent.mkdir(parents=True, exist_ok=True)

		# Write output JSON
		with output_filepath.open("w", encoding="utf-8") as f:
			json.dump(deck, f, ensure_ascii=False, indent=2)
