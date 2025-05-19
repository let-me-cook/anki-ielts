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


def save_deck_to_file(deck: Dict[str, Any], output_path: str) -> None:
	"""Save the deck to a JSON file in CrowdAnki format."""
	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(deck, f, ensure_ascii=False, indent=2)
