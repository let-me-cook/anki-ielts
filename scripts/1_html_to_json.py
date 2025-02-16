from pathlib import Path
import json
from src.html import parse_html_content


def main():
	html_files = Path("./raw").glob("*.html")

	for filepath in html_files:
		filename = filepath.stem
		foldername = filepath.parent

		with open(filepath, "r", encoding="utf-8") as file:
			content = file.read()

		# Parse the content
		parsed_data = parse_html_content(content)

		# Write the result to a JSON file
		with open(f"{foldername}/{filename}.json", "w", encoding="utf-8") as file:
			json.dump(parsed_data, file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
	main()
