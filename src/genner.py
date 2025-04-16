from typing import Callable
from openai import OpenAI
from src.type import Chat


class Genner:
	def __init__(
		self,
		client: OpenAI,
		model: str,
		stream: bool = True,
		stream_fn: Callable = lambda x: print(x, end="", flush=True),
	):
		self.client = client
		self.model = model
		self.stream = stream
		self.stream_fn = stream_fn

	def ch_completion(self, chat: Chat, stream: bool | None = None) -> str:
		if stream is None:
			stream = self.stream

		if not stream:
			response = self.client.chat.completions.create(
				model=self.model,  # type: ignore
				messages=chat,  # type: ignore
				stream=stream,
				temperature=0.5,
			)

			return response.choices[0].message.content
		else:
			stream_response = self.client.chat.completions.create(
				model=self.model,  # type: ignore
				messages=chat,  # type: ignore
				stream=stream,
				temperature=0.5,
			)

			acc = ""

			for chunk in stream_response:
				try:
					text_chunk = chunk.choices[0].delta.content
				except Exception as e:
					continue

				acc += text_chunk
				self.stream_fn(text_chunk)

			return acc
