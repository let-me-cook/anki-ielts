import json
from typing import List
from pydantic import BaseModel


class InstructionData(BaseModel):
	data_paths: List[str]
	instruction: str
	type_of_anki_card: str

	@classmethod
	def from_json_file(cls, file_path: str) -> List["InstructionData"]:
		"""
		Reads data from a JSON file and creates a list of AnkiCardData objects.
		"""
		try:
			with open(file_path, "r") as f:
				data = json.load(f)
				return [cls(**item) for item in data]
		except FileNotFoundError:
			raise FileNotFoundError(f"File not found at {file_path}")
		except json.JSONDecodeError:
			raise json.JSONDecodeError(f"Could not decode JSON from {file_path}", "", 0)
		except Exception as e:
			raise Exception(f"An unexpected error occurred: {e}")
