from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class IntroductionFeedback(BaseModel):
	task_response: str = Field(..., alias="Task Response/Task Achievement")
	coherence_cohesion: str = Field(..., alias="Coherence & Cohesion")
	grammatical_range: str = Field(..., alias="Grammatical Range & Accuracy")
	lexical_resource: str = Field(..., alias="Lexical Resource")


class SectionFeedback(BaseModel):
	content: str
	feedback: IntroductionFeedback
	rewrite_suggestion: str


class DetailedFeedback(BaseModel):
	introduction: SectionFeedback
	overview: SectionFeedback
	body_paragraph_1: SectionFeedback = Field(..., alias="body paragraph 1")
	body_paragraph_2: SectionFeedback = Field(..., alias="body paragraph 2")


class KeyTip(BaseModel):
	title: str
	content: str


class StructureSection(BaseModel):
	title: str
	content: str


class ExpressionImprovement(BaseModel):
	key_tips: List[KeyTip]
	suggested_structure: List[StructureSection]


class GrammarCorrection(BaseModel):
	error: str
	correction: str
	explanation: str


class Vocabulary(BaseModel):
	new_word: str = Field(..., alias="New Word")
	word_type: str = Field(..., alias="Word Type")
	definition: str = Field(..., alias="Definition")


class GrammarStructure(BaseModel):
	grammar_structure: str = Field(..., alias="Grammar Structure")
	original_sentence: str = Field(..., alias="Original Sentence")
	rephrased_sentence: str = Field(..., alias="Rephrased Sentence")


class CohesionEnhancement(BaseModel):
	original_text: str = Field(..., alias="Original Text")
	improved_text: str = Field(..., alias="Improved Text")
	explanation: str = Field(..., alias="Explanation")


class JSONFile(BaseModel):
	detailed_feedback: DetailedFeedback
	expression_improvement: ExpressionImprovement
	grammar_vocabulary_correction: List[GrammarCorrection]
	topic_related_vocabulary: List[Vocabulary]
	grammar_enhancement: List[GrammarStructure]
	cohesion_enhancement: List[CohesionEnhancement]

	# Alternative model configuration if the JSON root is the WritingFeedback itself
	@classmethod
	def parse_direct(cls, data: dict):
		"""
		Alternative parser if the JSON file contains WritingFeedback directly
		without a wrapper object.
		"""
		return super().model_validate(data)

	# Example usage methods
	@classmethod
	def from_json_file(cls, file_path: str):
		"""Load and parse JSON from a file path"""
		import json

		with open(file_path, "r") as f:
			data = json.load(f)

		# Try direct parsing if the JSON doesn't have a wrapper
		try:
			return cls.model_validate(data)
		except Exception as e:
			return cls.model_validate(cls.parse_direct(data))
