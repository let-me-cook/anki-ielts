from textwrap import dedent
from src.datatypes import DetailedFeedback
from src.genner import Genner
from pprint import pprint


def detailed_feedback_grammatical_error_correction(
	genner: Genner, detailed_feedback: DetailedFeedback
):
    writings = [
        detailed_feedback.introduction,
        detailed_feedback.overview,
        detailed_feedback.body_paragraph_1,
        detailed_feedback.body_paragraph_2,
    ]

    for writing in writings:
        genner.ch_completion([
            {
                "role": "system",
                "content": "You are a helpful assistant assistant that helps students improve their IELTS writing score using anki. ",
            },
            {
                "role": "user",
                "content": dedent(
                    f"""
                    Given these data : 
                    <Data>
                    Grammatical Range & Accuracy: {writing.feedback.grammatical_range}
                    Content: {writing.content}
                    </Data>

                    Generate an IELTS Anki card for a student with IELTS writing level 5.5.
                    Difficulty: {predicted_difficulty}
                    Usefulness: {predicted_usefulness}
                    
                    RESPOND ONLY WITH VALID JSON. Format your response as:
                    
                    {{
                        "front": "Front content of the card",
                        "back": "Back content of the card"
                    }}
                    
                    For Cloze cards, use this format instead:
                    {{
                        "text": "Text with {{{{c1::cloze deletions}}}}"
                    }}




                    """
                )
            }
        ])

	# pprint(detailed_feedback.model_dump())
