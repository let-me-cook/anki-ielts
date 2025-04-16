from src.datatypes import JSONFile
from pprint import pprint

jsonfile = JSONFile.from_json_file("raw/day_2.json")

pprint(jsonfile.model_dump())
