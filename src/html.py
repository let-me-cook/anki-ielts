from bs4 import BeautifulSoup
from typing import Dict, List, Any
import re
import json


def clean_text(text: str) -> str:
	"""Clean text by removing extra whitespace and normalizing characters."""
	return re.sub(r"\s+", " ", text.strip())

def parse_detailed_feedback(section: BeautifulSoup) -> Dict[str, Any]:
    """Parse the detailed feedback section of the document."""
    print("\n=== STARTING DETAILED FEEDBACK PARSER ===")
    print(f"Section tag: {section.name}, id: {section.get('id')}")
    result = {}
    
    # Print the entire section HTML to see what we're working with
    print("\nSection HTML:")
    print(str(section)[:200] + "...")  # First 200 chars
    
    # Find first h4
    first_h4 = section.find_next('h4')
    print(f"\nFound first h4: {first_h4.text if first_h4 else 'None'}")
    
    # Start from the first h4
    current_element = first_h4
    while current_element:
        if current_element.name == 'h4':
            print(f"\n--- Processing h4 section: {current_element.text.strip()} ---")
            section_name = current_element.text.strip().lower()
            result[section_name] = {
                'content': '',
                'feedback': {},
                'rewrite_suggestion': ''
            }
            
            # Get blockquote content
            blockquote = current_element.find_next('blockquote')
            if blockquote and (not blockquote.find_previous('h4') or blockquote.find_previous('h4') == current_element):
                p_text = blockquote.find('p').text.strip() if blockquote.find('p') else blockquote.text.strip()
                result[section_name]['content'] = clean_text(p_text)
                print(f"Found content: {result[section_name]['content'][:50]}...")
            else:
                print("No blockquote found or belongs to different section")
            
            # Find feedback section
            feedback_h5 = current_element.find_next('h5', string=lambda x: x and 'Feedback' in x)
            print(f"Found feedback h5: {feedback_h5.text if feedback_h5 else 'None'}")
            
            if feedback_h5:
                feedback = {}
                feedback_paragraphs = []
                next_el = feedback_h5.next_sibling
                
                while next_el:
                    if isinstance(next_el, str):
                        next_el = next_el.next_sibling
                        continue
                    if next_el.name in ['h4', 'h5']:
                        break
                    if next_el.name == 'p':
                        feedback_paragraphs.append(next_el)
                    next_el = next_el.next_sibling
                
                print(f"Found {len(feedback_paragraphs)} feedback paragraphs")
                
                for p in feedback_paragraphs:
                    print(f"\nProcessing feedback paragraph: {p.text[:50]}...")
                    strong = p.find('strong')
                    if strong:
                        key = strong.text.strip().rstrip(':')
                        value = p.text.replace('-', '', 1).replace(strong.text, '', 1).strip()
                        print(f"Extracted - Key: '{key}', Value: '{value[:50]}...'")
                        feedback[key] = clean_text(value)
                
                result[section_name]['feedback'] = feedback
                print(f"Total feedback items: {len(feedback)}")
            
            # Find rewrite suggestion
            rewrite_h5 = current_element.find_next('h5', string=lambda x: x and 'Rewrite suggestion' in x)
            print(f"Found rewrite h5: {rewrite_h5.text if rewrite_h5 else 'None'}")
            
            if rewrite_h5:
                suggestion = rewrite_h5.find_next('blockquote')
                if suggestion:
                    p_text = suggestion.find('p').text.strip() if suggestion.find('p') else suggestion.text.strip()
                    result[section_name]['rewrite_suggestion'] = clean_text(p_text)
                    print(f"Found rewrite suggestion: {result[section_name]['rewrite_suggestion'][:50]}...")
        
        # Move to next h4
        current_element = current_element.find_next('h4')
        # Check if we're still in our section
        if current_element and current_element.find_previous('h3') != section:
            print("\nReached end of section")
            break
    
    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, indent=2))
    return result


def parse_expression_improvement(
	section: BeautifulSoup,
) -> Dict[str, List[Dict[str, str]]]:
	"""Parse the expression improvement section."""
	result = {"key_tips": [], "suggested_structure": []}

	# Parse key tips
	key_tips = section.find_next("h5", id="key-tips")
	if key_tips:
		tips_list = key_tips.find_next("ul")
		if tips_list:
			for li in tips_list.find_all("li"):
				strong = li.find("strong")
				if strong:
					tip = {
						"title": strong.text.strip(":"),
						"content": clean_text(li.text.replace(strong.text, "")),
					}
					result["key_tips"].append(tip)

	# Parse suggested structure
	structure = section.find_next("h4", id="suggested-structure")
	if structure:
		structure_list = structure.find_next("ul")
		if structure_list:
			for li in structure_list.find_all("li"):
				paragraphs = li.find_all("p")
				if paragraphs:
					strong = li.find("strong")
					structure_item = {
						"title": strong.text.strip(":") if strong else "",
						"content": " ".join(p.text.strip() for p in paragraphs),
					}
					result["suggested_structure"].append(structure_item)

	return result


def parse_table_section(section: BeautifulSoup) -> List[Dict[str, str]]:
	"""Parse a table section into a list of dictionaries."""
	result = []

	# Find the table
	table = section.find_next("table")
	if not table or table.find_previous("h3") != section:
		return result

	# Get headers
	headers = []
	thead = table.find("thead")
	if thead:
		headers = [th.text.strip() for th in thead.find_all("th")]

	# Get rows
	tbody = table.find("tbody")
	if tbody and headers:
		for tr in tbody.find_all("tr"):
			cells = [td.text.strip() for td in tr.find_all("td")]
			if len(cells) == len(headers):
				row = dict(zip(headers, cells))
				result.append(row)

	return result



def parse_grammar_corrections(section: BeautifulSoup) -> List[Dict[str, str]]:
    """Parse the grammar & vocabulary correction table."""
    print("\n=== STARTING GRAMMAR CORRECTIONS PARSER ===")
    print(f"Section tag: {section.name}, id: {section.get('id')}")
    result = []
    
    # Find the table - looking directly within this section
    table = None
    current = section.next_sibling
    while current:
        if isinstance(current, str):
            current = current.next_sibling
            continue
        if current.name == 'table':
            table = current
            break
        if current.name == 'h3':  # Stop if we hit another section
            break
        current = current.next_sibling
    
    print(f"Found table: {table is not None}")
    if not table:
        return result
        
    # Get headers
    headers = []
    thead = table.find('thead')
    if thead:
        headers = [th.text.strip().lower() for th in thead.find_all('th')]
        print(f"Found headers: {headers}")
    
    # Get rows
    tbody = table.find('tbody')
    if tbody and headers:
        rows = tbody.find_all('tr')
        print(f"Found {len(rows)} rows")
        
        for tr in rows:
            cells = []
            for td in tr.find_all('td'):
                # Clean the cell text by removing extra whitespace
                text = ' '.join(td.text.strip().split())
                cells.append(text)
                
            print(f"\nProcessing row with cells: {cells}")
            
            if len(cells) == len(headers):
                row_dict = dict(zip(headers, cells))
                result.append(row_dict)
                print(f"Added row: {row_dict}")
    
    print(f"\nTotal rows parsed: {len(result)}")
    print("\n=== FINAL GRAMMAR CORRECTIONS RESULT ===")
    print(json.dumps(result, indent=2))
    return result




def parse_vocabulary_table(section: BeautifulSoup) -> List[Dict[str, str]]:
	"""Parse the topic-related vocabulary table."""
	return parse_table_section(section)


def parse_grammar_enhancement(section: BeautifulSoup) -> List[Dict[str, str]]:
	"""Parse the grammar enhancement table."""
	return parse_table_section(section)


def parse_cohesion_enhancement(section: BeautifulSoup) -> List[Dict[str, str]]:
	"""Parse the cohesion enhancement table."""
	return parse_table_section(section)


def parse_html_content(html_content: str) -> Dict[str, Any]:
    """Parse the complete HTML content using individual section parsers."""
    soup = BeautifulSoup(html_content, 'html.parser')
    print("\nStarting parse_html_content")
    
    # Initialize with the correct keys
    result = {
        'detailed_feedback': {},
        'expression_improvement': {
            'key_tips': [],
            'suggested_structure': []
        },
        'grammar_vocabulary_correction': [],  # This is the key we want to use
        'topic_related_vocabulary': [],
        'grammar_enhancement': [],
        'cohesion_enhancement': []
    }
    
    # Map section IDs to result keys
    section_mapping = {
        'detailed-feedback': ('detailed_feedback', parse_detailed_feedback),
        'expression-improvement': ('expression_improvement', parse_expression_improvement),
        'grammar--vocabulary-correction': ('grammar_vocabulary_correction', parse_grammar_corrections),
        'topic-related-vocabulary': ('topic_related_vocabulary', parse_vocabulary_table),
        'grammar-enhancement': ('grammar_enhancement', parse_grammar_enhancement),
        'cohesion-enhancement': ('cohesion_enhancement', parse_cohesion_enhancement)
    }
    
    for section_id, (result_key, parser_func) in section_mapping.items():
        print(f"\nProcessing section: {section_id}")
        print(f"Will store in result key: {result_key}")
        
        # Find section
        section = soup.find('h3', id=section_id)
        if not section and '--' in section_id:
            encoded_id = section_id.replace('--', '&amp;')
            section = soup.find('h3', id=encoded_id)
            print(f"Trying encoded ID: {encoded_id}")
        
        print(f"Found section: {section is not None}")
        
        if section:
            # Parse the section
            parsed_data = parser_func(section)
            print(f"Parsed data length: {len(parsed_data) if isinstance(parsed_data, (list, dict)) else 'N/A'}")
            
            # Assign to the correct key
            result[result_key] = parsed_data
            print(f"Assigned to result[{result_key}]")
            print(f"Verification - result[{result_key}] length: {len(result[result_key]) if isinstance(result[result_key], (list, dict)) else 'N/A'}")
    
    print("\nFinal result keys and lengths:")
    for key, value in result.items():
        print(f"{key}: {len(value) if isinstance(value, (list, dict)) else 'N/A'}")
    
    return result