# Anki IELTS

# Logic
- Use and get the result of https://engnovate.com/ielts-academic-writing-task-1-report-checker/
- Get the specific HTML of the result
- Convert the HTML into JSON using `./scripts/1_html_to_json.py`
- Convert the JSON into proper anki card using `./scripts/2_json_to_crowdanki_json.py`
- The output will be on `./anki-ielts.json`
- Anki installed with `git anki` plugin will be able to interpret the public github link of this and get the proper anki cards