from pathlib import Path
from typing import Dict, List, Any
import json
import uuid

def create_deck_structure(deck_name: str) -> Dict[str, Any]:
    """Generate basic CrowdAnki deck structure with Cloze note type."""
    return {
        "__type__": "Deck",
        "children": [],
        "crowdanki_uuid": str(uuid.uuid4()),
        "deck_config_uuid": str(uuid.uuid4()),
        "deck_configurations": [
            {
                "__type__": "DeckConfig",
                "autoplay": True,
                "crowdanki_uuid": str(uuid.uuid4()),
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
        "name": deck_name,
        "notes": [],
        "note_models": [
            {
                "__type__": "NoteModel",
                "crowdanki_uuid": str(uuid.uuid4()),
                "css": "",
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
                        "afmt": "{{cloze:Text}}<br><br>{{Back Extra}}",
                        "bafmt": "",
                        "bqfmt": "",
                        "did": None,
                        "name": "Cloze",
                        "ord": 0,
                        "qfmt": "{{cloze:Text}}",
                    }
                ],
                "type": 1,
            }
        ],
    }

def create_note(text: str, back_extra: str, tags: List[str], model_uuid: str) -> Dict[str, Any]:
    """Create a single cloze note."""
    return {
        "__type__": "Note",
        "data": ["", text, back_extra],
        "fields": ["Text", "Back Extra"],
        "flags": 0,
        "guid": str(uuid.uuid4()),
        "note_model_uuid": model_uuid,
        "tags": tags,
    }

def generate_detailed_feedback_notes(detailed_feedback: Dict[str, Any], model_uuid: str) -> List[Dict[str, Any]]:
    """Generate notes from detailed feedback section."""
    notes = []
    
    for section, content in detailed_feedback.items():
        if isinstance(content, dict) and "content" in content and "feedback" in content:
            # Create note for original content and rewrite
            text = (
                f"Section: {section}\n"
                f"Original: {{{{c1::{content['content']}}}}}\n"
                f"Improved: {{{{c2::{content['rewrite_suggestion']}}}}}"
            )
            
            # Compile feedback into back extra
            back_extra = "\n".join(
                f"{category}: {feedback}"
                for category, feedback in content['feedback'].items()
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

def generate_grammar_vocabulary_notes(corrections: List[Dict[str, str]], model_uuid: str) -> List[Dict[str, Any]]:
    """Generate notes from grammar and vocabulary corrections."""
    return [
        create_note(
            text=(
                f"Original: {{{{c1::{item['error']}}}}}\n"
                f"Corrected: {{{{c2::{item['correction']}}}}}"
            ),
            back_extra=f"Explanation: {item['explanation']}",
            tags=["grammar_vocabulary"],
            model_uuid=model_uuid,
        )
        for item in corrections
    ]

def generate_vocabulary_notes(vocab_data: List[Dict[str, str]], model_uuid: str) -> List[Dict[str, Any]]:
    """Generate vocabulary notes."""
    return [
        create_note(
            text=f"{{{{c1::{item['New Word']}}}}} ({item['Word Type']})\nDefinition: {{{{c2::{item['Definition']}}}}}",
            back_extra=f"Word Type: {item['Word Type']}",
            tags=["vocabulary"],
            model_uuid=model_uuid,
        )
        for item in vocab_data
    ]

def generate_expression_notes(expression_data: Dict[str, List[Dict[str, str]]], model_uuid: str) -> List[Dict[str, Any]]:
    """Generate notes from expression improvement section."""
    notes = []
    
    # Generate notes for key tips
    for tip in expression_data.get('key_tips', []):
        notes.append(
            create_note(
                text=f"Writing Tip - {tip['title']}: {{{{c1::{tip['content']}}}}}",
                back_extra=f"Category: {tip['title']}",
                tags=["writing_tips"],
                model_uuid=model_uuid,
            )
        )
    
    # Generate notes for suggested structure
    for section in expression_data.get('suggested_structure', []):
        notes.append(
            create_note(
                text=f"Section: {section['title']}\nContent: {{{{c1::{section['content']}}}}}",
                back_extra=f"Writing Section: {section['title']}",
                tags=["writing_structure"],
                model_uuid=model_uuid,
            )
        )
    
    return notes

def generate_anki_deck(input_data: Dict[str, Any], deck_name: str = "English Writing Practice") -> Dict[str, Any]:
    """Generate complete Anki deck from input data."""
    # Create base deck structure
    deck = create_deck_structure(deck_name)
    
    # Get model UUID
    model_uuid = deck["note_models"][0]["crowdanki_uuid"]
    
    # Generate all notes
    notes = []
    
    # Add detailed feedback notes
    if "detailed_feedback" in input_data:
        notes.extend(generate_detailed_feedback_notes(input_data["detailed_feedback"], model_uuid))
    
    # Add grammar and vocabulary correction notes
    if "grammar_vocabulary_correction" in input_data:
        notes.extend(generate_grammar_vocabulary_notes(input_data["grammar_vocabulary_correction"], model_uuid))
    
    # Add topic-related vocabulary notes
    if "topic_related_vocabulary" in input_data:
        notes.extend(generate_vocabulary_notes(input_data["topic_related_vocabulary"], model_uuid))
    
    # Add expression improvement notes
    if "expression_improvement" in input_data:
        notes.extend(generate_expression_notes(input_data["expression_improvement"], model_uuid))
    
    # Add notes to deck
    deck["notes"] = notes
    
    return deck