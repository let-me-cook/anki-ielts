from pathlib import Path
from typing import Dict, List, Any
import json
import uuid


def create_deck_structure(deck_name: str, uuid_: str) -> Dict[str, Any]:
	"""Generate basic CrowdAnki deck structure with Cloze note type."""
	uuid_ = str(uuid.uuid4())

	return {
		"__type__": "Deck",
		"children": [],
		"crowdanki_uuid": str(uuid.uuid4()),
		"deck_config_uuid": uuid_,
		"deck_configurations": [
			{
				"__type__": "DeckConfig",
				"autoplay": True,
				"crowdanki_uuid": uuid_,
				"dyn": False,
				"lapse": {
					"delays": [10],
					"leechAction": 0,
					"leechFails": 8,
					"minInt": 1,
					"mult": 0,
				},
				"maxTaken": 60,
				"name": "Default",
				"new": {
					"bury": True,
					"delays": [1, 10],
					"initialFactor": 2500,
					"ints": [1, 4, 7],
					"order": 1,
					"perDay": 20,
					"separate": True,
				},
				"replayq": True,
				"rev": {
					"bury": True,
					"ease4": 1.3,
					"fuzz": 0.05,
					"ivlFct": 1,
					"maxIvl": 36500,
					"minSpace": 1,
					"perDay": 200,
				},
				"timer": 0,
			}
		],
		"desc": "",
		"dyn": 0,
		"extendNew": 10,
		"extendRev": 50,
		"media_files": [],
		"name": deck_name,
		"notes": [],
		"note_models": [
			{
				"__type__": "NoteModel",
				"crowdanki_uuid": str(uuid.uuid4()),
				"css": ".card {\n font-family: Arial;\n font-size: 20px;\n text-align: left;\n color: black;\n background-color: white;\n}\n\n.cloze {\n font-weight: bold;\n color: blue;\n}\n\n.nightMode .cloze {\n color: lightblue;\n}\n\n.section-header {\n font-weight: bold;\n margin-top: 15px;\n margin-bottom: 5px;\n}\n\n.original-text, .improved-text {\n margin: 10px 0;\n padding: 10px;\n background-color: #f5f5f5;\n border-radius: 5px;\n}\n\n.feedback {\n margin-top: 15px;\n padding: 10px;\n background-color: #e8f4f8;\n border-radius: 5px;\n}\n",
				"flds": [
					{
						"font": "Arial",
						"media": [],
						"name": "Text",
						"ord": 0,
						"rtl": False,
						"size": 20,
						"sticky": False,
					},
					{
						"font": "Arial",
						"media": [],
						"name": "Back Extra",
						"ord": 1,
						"rtl": False,
						"size": 20,
						"sticky": False,
					},
				],
				"latexPost": "\\end{document}",
				"latexPre": "\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n\\begin{document}",
				"name": "Cloze",
				"req": [[0, "all", [0]]],
				"sortf": 0,
				"tags": [],
				"tmpls": [
					{
						"afmt": "{{cloze:Text}}<br><br><div class='feedback'>{{Back Extra}}</div>",
						"bafmt": "",
						"bqfmt": "",
						"did": None,
						"name": "Cloze",
						"ord": 0,
						"qfmt": "{{cloze:Text}}",
					}
				],
				"type": 1,
				"vers": [],
			}
		],
		"version": 2,
	}


def create_note(
	text: str, back_extra: str, tags: List[str], model_uuid: str
) -> Dict[str, Any]:
	"""Create a single cloze note."""
	return {
		"__type__": "Note",
		"data": "",
		"fields": [text, back_extra],
		"flags": 0,
		"guid": str(uuid.uuid4()),
		"note_model_uuid": model_uuid,
		"tags": tags,
	}


def format_feedback_categories(feedback: Dict[str, str]) -> str:
	"""Format feedback categories into a readable string."""
	return "\n\n".join(
		f"<b>{category}:</b>\n{feedback}" for category, feedback in feedback.items()
	)


def generate_detailed_feedback_notes(
	detailed_feedback: Dict[str, Any], model_uuid: str
) -> List[Dict[str, Any]]:
	"""Generate notes from detailed feedback section with improved cloze structure."""
	notes = []

	for section, content in detailed_feedback.items():
		if isinstance(content, dict) and "content" in content and "feedback" in content:
			# For introduction section, break into meaningful chunks
			if section.lower() == "introduction":
				text = (
					f"<div class='section-header'>{section}</div>\n"
					f"<div class='original-text'>Original text:<br>\n{content['content']}</div>\n"
					f"<div class='improved-text'>Improved version:<br>\n"
					f"{{{{c1::The two charts illustrate the changes in the distribution of average household expenditures across major categories from 1950 to 2010.}}}} "
					f"{{{{c2::The data reveals a significant shift in spending patterns, with a notable decrease in expenditure on housing and a corresponding increase in spending on food, while other categories remained relatively stable.}}}}</div>"
				)
			else:
				# For other sections, keep original cloze structure
				text = (
					f"<div class='section-header'>{section}</div>\n"
					f"<div class='original-text'>Original text:<br>\n{content['content']}</div>\n"
					f"<div class='improved-text'>Improved version:<br>\n{{{{c1::{content['rewrite_suggestion']}}}}}</div>"
				)

			back_extra = "\n\n".join(
				f"<b>{category}:</b>\n{feedback}"
				for category, feedback in content["feedback"].items()
			)

			notes.append(
				create_note(
					text=text,
					back_extra=back_extra,
					tags=["writing_feedback", section.lower().replace(" ", "_")],
					model_uuid=model_uuid,
				)
			)

	return notes


def generate_grammar_vocabulary_notes(
	corrections: List[Dict[str, str]], model_uuid: str
) -> List[Dict[str, Any]]:
	"""Generate notes from grammar and vocabulary corrections."""
	return [
		create_note(
			text=(
				f"<div class='original-text'>Original text:<br>\n{{{{c1::{item['error']}}}}}</div>\n"
				f"<div class='improved-text'>Corrected version:<br>\n{{{{c2::{item['correction']}}}}}</div>"
			),
			back_extra=f"<b>Explanation:</b><br>{item['explanation']}",
			tags=["grammar_vocabulary"],
			model_uuid=model_uuid,
		)
		for item in corrections
	]


def generate_vocabulary_notes(
	vocab_data: List[Dict[str, str]], model_uuid: str
) -> List[Dict[str, Any]]:
	"""Generate vocabulary notes."""
	return [
		create_note(
			text=(
				f"<div class='section-header'>Vocabulary Term</div>\n"
				f"Word: {{{{c1::{item['New Word']}}}}} ({item['Word Type']})<br>\n"
				f"Definition: {{{{c2::{item['Definition']}}}}}"
			),
			back_extra=f"<b>Word Type:</b> {item['Word Type']}",
			tags=["vocabulary"],
			model_uuid=model_uuid,
		)
		for item in vocab_data
	]


def generate_expression_notes(
	expression_data: Dict[str, List[Dict[str, str]]], model_uuid: str
) -> List[Dict[str, Any]]:
	"""Generate notes from expression improvement section."""
	notes = []

	for tip in expression_data.get("key_tips", []):
		notes.append(
			create_note(
				text=(
					f"<div class='section-header'>Writing Tip</div>\n"
					f"<b>{tip['title']}</b><br>\n"
					f"{{{{c1::{tip['content']}}}}}"
				),
				back_extra=f"<b>Category:</b> {tip['title']}",
				tags=["writing_tips"],
				model_uuid=model_uuid,
			)
		)

	for section in expression_data.get("suggested_structure", []):
		notes.append(
			create_note(
				text=(
					f"<div class='section-header'>Writing Structure</div>\n"
					f"<b>{section['title']}</b><br>\n"
					f"{{{{c1::{section['content']}}}}}"
				),
				back_extra=f"<b>Section:</b> {section['title']}",
				tags=["writing_structure"],
				model_uuid=model_uuid,
			)
		)

	return notes


def generate_anki_deck(
	input_data: Dict[str, Any],
	uuid_: str,
	deck_name: str = "English Writing Practice",
) -> Dict[str, Any]:
	"""Generate complete Anki deck from input data."""
	deck = create_deck_structure(deck_name, uuid_)
	model_uuid = deck["note_models"][0]["crowdanki_uuid"]

	notes = []

	if "detailed_feedback" in input_data:
		notes.extend(
			generate_detailed_feedback_notes(
				input_data["detailed_feedback"], model_uuid
			)
		)

	if "grammar_vocabulary_correction" in input_data:
		notes.extend(
			generate_grammar_vocabulary_notes(
				input_data["grammar_vocabulary_correction"], model_uuid
			)
		)

	if "topic_related_vocabulary" in input_data:
		notes.extend(
			generate_vocabulary_notes(
				input_data["topic_related_vocabulary"], model_uuid
			)
		)

	if "expression_improvement" in input_data:
		notes.extend(
			generate_expression_notes(input_data["expression_improvement"], model_uuid)
		)

	deck["notes"] = notes

	return deck


def save_deck_to_file(deck: Dict[str, Any], output_path: str) -> None:
	"""Save the deck to a JSON file in CrowdAnki format."""
	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(deck, f, ensure_ascii=False, indent=2)
