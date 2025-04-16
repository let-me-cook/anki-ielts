from multiprocessing.managers import DictProxy
from typing import TypeAlias, List, Dict, TypedDict


class Message(TypedDict):
	content: str
	role: str


Chat: TypeAlias = List[Message]
