from textwrap import dedent
from turtle import back
from src.datatypes import JSONFile
from src.genner import Genner
from typing import List, Dict, Any, Union, Optional
from pydantic import BaseModel
from result import Ok, Err, Result
import json


class NormalCard(BaseModel):
	front: str
	back: str
	predicted_difficulty: str
	predicted_usefulness: str


class ClozeCard(BaseModel):
	text: str
	predicted_difficulty: str
	predicted_usefulness: str


def generate_anki_card(
	genner: Genner,
	data: JSONFile,
	data_paths: List[str],
	instruction: str,
	type_of_anki_card: str,
) -> Result[List[NormalCard | ClozeCard], str]:
	"""
	Generate an Anki card for IELTS writing practice using an LLM.

	Parameters:
	- data: JSONFile Pydantic model containing structured IELTS writing feedback data
	- data_paths: List of paths to extract relevant content from the data model
	- instruction: The instruction for the card
	- type_of_anki_card: Type of Anki card (Basic, Cloze, etc.)
	- predicted_difficulty: Difficulty level (Easy, Medium, Hard)
	- predicted_usefulness: Usefulness rating (Low, Medium, High, Very high)
	- llm_client: Client to interact with the LLM API

	Returns:
	- dict: Generated Anki card in the appropriate format
	"""
	content_pieces = []
	# Extract relevant content from data based on data_paths
	for path in data_paths:
		try:
			# Convert the path to a series of attribute accesses on the Pydantic model
			parts = path.split(".")
			value = data
			for part in parts:
				# Check if current value is a Pydantic model
				if hasattr(value, "__pydantic_fields__"):
					# Access attribute on Pydantic model
					value = getattr(value, part)
				elif isinstance(value, dict) and part in value:
					# Access key in dictionary
					value = value[part]
				elif isinstance(value, list):
					# Try to access by index if it's a list
					try:
						index = int(part)
						if 0 <= index < len(value):
							value = value[index]
						else:
							raise ValueError(f"Invalid list index: {part}")
					except ValueError:
						value = f"[Data not found at path: {path}]"
						break
				else:
					value = f"[Data not found at path: {path}]"
					break

			# Convert Pydantic models to dict for easier handling if needed
			if hasattr(value, "model_dump"):
				assert isinstance(value, JSONFile)

				value = value.model_dump()

			content_pieces.append(value)
		except Exception as e:
			content_pieces.append(f"[Error extracting data from path {path}: {str(e)}]")

	# Create prompt for LLM based on instruction and content
	prompt = dedent(f"""
		Instruction: {instruction}
		
		Content to work with:
		{json.dumps(content_pieces, indent=2)}
		
		Generate an IELTS Anki card for a student with IELTS writing level 5.5.
		Card type: {type_of_anki_card}
		
		RESPOND ONLY WITH VALID JSON. Format your response as:
		
		```json(Basic)
		[
			{{
				"front": "Front content of the card",
				"back": "Back content of the card"
				"predicted_difficulty": "predicted_difficulty_0_easiest_to_10_hardest"
				"predicted_usefulness": "predicted_usefullness_0_easiest_to_10_hardest"
			}},
			...
		]
		```
		
		For Cloze cards, use this format instead:
		```json(Cloze)
		[
			{{
				"text": "Text with {{{{c1::cloze deletions}}}}"
				"predicted_difficulty": "predicted_difficulty_0_easiest_to_10_hardest"
				"predicted_usefulness": "predicted_usefullness_0_easiest_to_10_hardest"
			}},
			...
		]
		```
	""")

	# Get response from LLM
	llm_response = genner.ch_completion(
		[
			{
				"role": "system",
				"content": "You are an expert IELTS writing tutor and Anki card creator specializing in helping ESL students improve their writing scores. Your task is to create effective Anki flashcards based on IELTS writing samples and feedback.",
			},
			{"role": "user", "content": prompt},
		]
	)

	if "cloze" in llm_response.lower():
		json_str = llm_response.split("```json(cloze)")[1].split("```")[0]
		json_str = json_str.strip()
		json_data = json.loads(json_str)

		cards = []
		for item in json_data:
			cards.append(ClozeCard.model_validate(item))

	elif "normal" in llm_response.lower():
		json_str = llm_response.split("```json(normal)")[1].split("```")[0]
		json_str = json_str.strip()
		# Parse response as NormalCard
		json_data = json.loads(json_str)

		cards = []
		for item in json_data:
			cards.append(ClozeCard.model_validate(item))
	else:
		return Err(
			"Invalid response format from LLM. Expected 'normal' or 'cloze' in the response."
		)

	return Ok(cards)
