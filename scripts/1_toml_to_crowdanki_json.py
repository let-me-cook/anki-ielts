from pathlib import Path
from src.crowdanki import create_deck_structure, save_deck_to_file
from pprint import pprint

import tomllib

for filepath in Path("./data/bronze/").glob("introduction_*.toml"):
	with open(filepath, "rb") as f:
		toml_data = tomllib.load(f)

	for card in toml_data["Card"]:
		front: str = card["Front"]
		back: str = card["Back"]
