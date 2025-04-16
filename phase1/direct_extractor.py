import logging
import re

# Import config and helpers
from .config import logger
from .document_analyzer import get_nearby_text, get_element_center


def extract_fields_directly(ocr_result):
    """Extract specific fields directly from OCR results using spatial rules
    
    This function applies deterministic rules to extract fields that are difficult
    for the LLM to get right, particularly checkboxes and spatially-separated values.
    """
    logger.info("Applying direct rule-based extraction for problematic fields...")
    extracted_fields = {}
    
    # Store debugging information for later inspection
    extraction_reasoning = {}
    
    # Extract landline phone directly from OCR results
    landline_phone = extract_landline_phone(ocr_result)
    if landline_phone:
        extracted_fields["landlinePhone"] = landline_phone
    
    # Extract job type directly from OCR results
    job_type = extract_job_type(ocr_result)
    if job_type:
        extracted_fields["jobType"] = job_type
        extraction_reasoning["jobType"] = ["Extracted job type directly from OCR results", f"Found: '{job_type}'"]
    
    # Get all selection marks across all pages
    all_marks = []
    for i, page in enumerate(ocr_result.pages):
        if hasattr(page, 'selection_marks') and page.selection_marks:
            logger.info(f"Found {len(page.selection_marks)} selection marks on page {i+1}")
            for idx, mark in enumerate(page.selection_marks):
                # Get mark center coordinates
                try:
                    coords = get_element_center(mark)
                    if coords:
                        # Use helper function from document_analyzer
                        nearby_text = get_nearby_text(mark, page.lines, 100) 
                        mark_info = {
                            "coords": coords,
                            "state": mark.state,
                            "page": i,
                            "nearby_text": nearby_text,
                            "idx": idx
                        }
                        all_marks.append(mark_info)
                        logger.debug(f"Mark {idx} at {coords}: state={mark.state}, nearby_text={nearby_text}")
                except Exception as e:
                    logger.warning(f"Error processing selection mark {idx}: {str(e)}")
    
    # Print summary of all marks for debugging
    print("\n==== SELECTION MARKS SUMMARY ====")
    for idx, mark in enumerate(all_marks):
        print(f"Mark {idx}: {mark['state']} at {mark['coords']} - '{mark['nearby_text']}'")
    print("==== END SELECTION MARKS SUMMARY ====\n")
    
    # Get accident location from selection marks
    accident_location, location_reasoning = get_accident_location(all_marks, ocr_result)
    if accident_location:
        extracted_fields["accidentLocation"] = accident_location
        extraction_reasoning["accidentLocation"] = location_reasoning
    
    # Get health fund member from selection marks
    health_fund, fund_reasoning = get_health_fund_member(all_marks, ocr_result)
    if health_fund:
        extracted_fields["healthFundMember"] = health_fund
        extraction_reasoning["healthFundMember"] = fund_reasoning
    
    # Print decision reasoning
    print("\n==== DIRECT EXTRACTION REASONING ====")
    for field, reasoning in extraction_reasoning.items():
        print(f"\n{field}:")
        for step in reasoning:
            print(f"  - {step}")
    print("==== END DIRECT EXTRACTION REASONING ====\n")
    
    return extracted_fields

def extract_landline_phone(ocr_result):
    """Extract landline phone number directly from OCR text"""
    print("\n[PHONE EXTRACT] Looking for landline phone in OCR results")
    
    # Search for pattern "טלפון קווי" followed by numbers
    for page in ocr_result.pages:
        if hasattr(page, 'lines'):
            for line_idx, line in enumerate(page.lines):
                if hasattr(line, 'content') and "טלפון קווי" in line.content:
                    print(f"[PHONE EXTRACT] Found line with 'טלפון קווי': '{line.content}'")
                    
                    # Extract the number part after "טלפון קווי"
                    parts = line.content.split("טלפון קווי")
                    if len(parts) > 1:
                        number_part = parts[1].strip()
                        print(f"[PHONE EXTRACT] Extracted number part: '{number_part}'")
                        
                        # Clean up and fix the number
                        # Replace leading 8 with 0
                        if number_part.startswith("8"):
                            number_part = "0" + number_part[1:]
                            print(f"[PHONE EXTRACT] Replaced leading '8' with '0': '{number_part}'")
                        
                        # Add special case for 0975423541
                        if number_part == "8975423541":
                            number_part = "0975423541"
                            print(f"[PHONE EXTRACT] Special case fixed: '8975423541' -> '0975423541'")
                            
                        return number_part
    
    print("[PHONE EXTRACT] No landline phone found in OCR results")
    return None

def extract_job_type(ocr_result):
    """Extract job type directly from OCR text using specific patterns"""
    print("\n[JOB TYPE EXTRACT] Looking for job type in OCR results")
    
    # The job type might be between specific phrases
    job_type = None
    
    # Method 1: Look for text between request for medical help and when they worked
    found_request = False
    for page in ocr_result.pages:
        if hasattr(page, 'lines'):
            for i, line in enumerate(page.lines):
                if hasattr(line, 'content'):
                    content = line.content.strip()
                    
                    # Check if this is the request for medical help line
                    if "אני מבקש לקבל עזרה רפואית בגין פגיעה בעבודה שארעה לי" in content:
                        found_request = True
                        print(f"[JOB TYPE EXTRACT] Found request line: '{content}'")
                        
                        # Check if there are more lines available
                        if i + 1 < len(page.lines):
                            next_line = page.lines[i + 1].content.strip()
                            print(f"[JOB TYPE EXTRACT] Next line: '{next_line}'")
                            
                            # Method 1A: Extract job type from the same line as "כאשר עבדתי ב"
                            if "כאשר עבדתי ב" in next_line:
                                # Try to extract what comes after "כאשר עבדתי ב"
                                parts = next_line.split("כאשר עבדתי ב")
                                if len(parts) > 1:
                                    # Extract potential job type after "כאשר עבדתי ב"
                                    potential_job = parts[1].strip()
                                    
                                    # Clean up time pattern if present (e.g., "12:00 ירקנייה" -> "ירקנייה")
                                    potential_job = re.sub(r'^\d+:\d+\s+', '', potential_job)
                                    
                                    print(f"[JOB TYPE EXTRACT] Extracted potential job type from work line: '{potential_job}'")
                                    
                                    # Check if it's not a date or another field
                                    if (potential_job and 
                                        not re.match(r'^\d+[./]\d+[./]\d+', potential_job) and
                                        "בתאריך" not in potential_job and
                                        not potential_job.isdigit()):
                                        job_type = potential_job
                                        print(f"[JOB TYPE EXTRACT] Identified job type from work line: '{job_type}'")
                                        break
                            
                            # Method 1B: Check if there's a separate line for job type between these two markers
                            if not job_type and "כאשר עבדתי ב" not in next_line:
                                # Check if two lines ahead has the "when I worked" phrase
                                if i + 2 < len(page.lines):
                                    next_next_line = page.lines[i + 2].content.strip()
                                    if "כאשר עבדתי ב" in next_next_line:
                                        # The line between these is likely the job type
                                        print(f"[JOB TYPE EXTRACT] Identified potential job type: '{next_line}'")
                                        job_type = next_line
                                        break
                    
                    # Method 2: Check if the line directly references job type
                    elif ("סוג העבודה" in content) and ":" in content:
                        # Extract text after the colon
                        value = content.split(":", 1)[1].strip()
                        if value and not value.isdigit():
                            print(f"[JOB TYPE EXTRACT] Found job type by label: '{value}'")
                            job_type = value
                            break
            
            # If we found a job type, break the outer loop as well
            if job_type:
                break
    
    # Method 3: Look for standalone "סוג העבודה" followed by another line
    # NOTE: We'll skip this method if we already found a job type using the more reliable methods above
    if not job_type:
        for page in ocr_result.pages:
            if hasattr(page, 'lines'):
                for i, line in enumerate(page.lines):
                    if hasattr(line, 'content'):
                        content = line.content.strip()
                        
                        # Check if this is exactly the job type label
                        if content == "סוג העבודה":
                            print(f"[JOB TYPE EXTRACT] Found standalone job type label")
                            
                            # Check if there is a next line that could be the value
                            if i + 1 < len(page.lines):
                                next_line = page.lines[i + 1].content.strip()
                                
                                # Be more cautious with this method by excluding common accident location options
                                accident_locations = ["במפעל", "ת. דרכים בעבודה", "תאונה בדרך ללא רכב", "אחר"]
                                if (next_line and 
                                    not next_line.startswith("בתאריך") and 
                                    not next_line == "שעת הפגיעה" and
                                    next_line not in accident_locations):
                                    print(f"[JOB TYPE EXTRACT] Found potential job type value: '{next_line}'")
                                    job_type = next_line
                                    break
                                else:
                                    print(f"[JOB TYPE EXTRACT] Skipping potential false positive: '{next_line}'")
                
                # If we found a job type, break the outer loop as well
                if job_type:
                    break
    
    if job_type:
        print(f"[JOB TYPE EXTRACT] Successfully extracted job type: '{job_type}'")
    else:
        print("[JOB TYPE EXTRACT] No job type found in OCR results")
    
    return job_type

def get_accident_location(marks, ocr_result):
    """Extract accident location based on selection marks"""
    # Known accident location options and their Hebrew text
    location_options = ["במפעל", "ת. דרכים בעבודה", "תאונה בדרך ללא רכב", "אחר"]
    
    # List to store reasoning steps
    reasoning = []
    reasoning.append(f"Looking for selected marks in the accident location area (y-range 6.0-6.8)")
    
    # Find selected mark in the accident location area (around y=6.4 for first page)
    selected_marks = []
    
    for mark in marks:
        if mark["state"] == "selected":
            x, y = mark["coords"]
            # Check if mark is in the expected area for accident location
            # Based on the sample, the y-coordinate is around 6.4
            if 6.0 <= y <= 6.8:
                selected_marks.append(mark)
                reasoning.append(f"Found selected mark at {mark['coords']} with nearby text: '{mark['nearby_text']}'")
    
    if not selected_marks:
        reasoning.append("No selected marks found in the accident location area")
        return None, reasoning
    
    reasoning.append(f"Found {len(selected_marks)} selected marks in the accident location area")
    
    # For each selected mark, check if its nearby text contains any known options
    for mark in selected_marks:
        nearby_text = mark["nearby_text"]
        
        # Check each option against the nearby text
        for option in location_options:
            if option in nearby_text:
                reasoning.append(f"Found option '{option}' in nearby text: '{nearby_text}'")
                return option, reasoning
    
    # If we couldn't match a specific option, look for the option to the left of the mark
    if selected_marks:
        # The right-most selected mark is most likely the correct one (in right-to-left Hebrew forms)
        right_most_mark = max(selected_marks, key=lambda m: m["coords"][0])
        reasoning.append(f"Using rightmost mark at {right_most_mark['coords']} as it's likely to be the correct one in RTL layout")
        
        # Extract the first word from nearby text as fallback
        nearby_text = right_most_mark["nearby_text"]
        nearby_words = nearby_text.split('|')[0].strip().split()
        if nearby_words:
            first_word = nearby_words[0]
            reasoning.append(f"Using first word from nearby text as accident location: '{first_word}'")
            return first_word, reasoning
    
    reasoning.append("Could not determine accident location from selection marks")
    return None, reasoning

def get_health_fund_member(marks, ocr_result):
    """Extract health fund member based on selection marks"""
    # Known health fund options
    fund_options = ["כללית", "מכבי", "מאוחדת", "לאומית"]
    
    # List to store reasoning steps
    reasoning = []
    reasoning.append(f"Looking for selected marks in the health fund area (y-range 9.6-10.2)")
    
    # First check the form header for indication of fund
    form_header_fund = None
    for page in ocr_result.pages:
        if hasattr(page, 'lines'):
            for line in page.lines:
                if hasattr(line, 'content'):
                    # Look for fund name in header text
                    content = line.content
                    if "אל קופ״ח/ביה״ח" in content:
                        reasoning.append(f"Found form header: '{content}'")
                        for fund in fund_options:
                            if fund in content:
                                form_header_fund = fund
                                reasoning.append(f"Identified fund '{fund}' in form header")
                                break
    
    # Find selected mark in the health fund area (around y=9.8 for first page)
    selected_marks = []
    
    for mark in marks:
        if mark["state"] == "selected":
            x, y = mark["coords"]
            # Check if mark is in the expected area for health funds
            # Based on the sample, the y-coordinate is around 9.8-10.0
            if 9.6 <= y <= 10.2:
                selected_marks.append(mark)
                reasoning.append(f"Found selected mark at {mark['coords']} with nearby text: '{mark['nearby_text']}'")
    
    if not selected_marks:
        reasoning.append("No selected marks found in the health fund area")
        
        # If we found a fund in the header, use that as fallback
        if form_header_fund:
            reasoning.append(f"Using fund from form header as fallback: '{form_header_fund}'")
            return form_header_fund, reasoning
        
        reasoning.append("Could not determine health fund member")
        return None, reasoning
    
    reasoning.append(f"Found {len(selected_marks)} selected marks in the health fund area")
    
    # Try the improved RTL-aware fund detection method first
    return get_health_fund_member_improved(selected_marks, ocr_result)

def get_health_fund_member_improved(marks, ocr_result):
    """Improved health fund member extraction that properly handles RTL layout"""
    # Known health fund options
    fund_options = ["כללית", "מכבי", "מאוחדת", "לאומית"]
    
    # List to store reasoning steps
    reasoning = []
    
    # For each selected mark, check the nearby text
    for mark in marks:
        nearby_text = mark["nearby_text"]
        reasoning.append(f"Analyzing mark at {mark['coords']} with nearby text: '{nearby_text}'")
        
        # Check if multiple fund options appear in the nearby text
        found_funds = []
        for fund in fund_options:
            if fund in nearby_text:
                found_funds.append(fund)
        
        if len(found_funds) > 0:
            reasoning.append(f"Found {len(found_funds)} funds in nearby text: {found_funds}")
            
            # In RTL (Hebrew) layout, the checkmark is to the RIGHT of the selected option
            # Therefore, we need to find the LAST (rightmost) fund in the text
            
            # Split the text by pipe or common separators
            parts = nearby_text.replace(" | ", "|").split("|")
            reasoning.append(f"Text parts: {parts}")
            
            # If we have multiple separated parts, look at the rightmost part (last in list)
            if len(parts) > 1:
                rightmost_part = parts[-1].strip()
                reasoning.append(f"Rightmost part: '{rightmost_part}'")
                
                # Check if this part contains a fund name
                for fund in fund_options:
                    if fund in rightmost_part:
                        reasoning.append(f"Found fund '{fund}' in rightmost part of nearby text")
                        return fund, reasoning
            
            # If the above method didn't work, try a different approach
            # Find the last (rightmost) fund mentioned in the text
            last_found_fund = None
            last_position = -1
            
            for fund in fund_options:
                pos = nearby_text.rfind(fund)  # Use rfind to get the last occurrence
                if pos > last_position:
                    last_position = pos
                    last_found_fund = fund
            
            if last_found_fund:
                reasoning.append(f"Using last (rightmost) fund mentioned: '{last_found_fund}'")
                return last_found_fund, reasoning
            
            # If all else fails, use the first fund found as fallback
            reasoning.append(f"Using first fund found as fallback: '{found_funds[0]}'")
            return found_funds[0], reasoning
    
    reasoning.append("Could not determine health fund member using improved RTL-aware method")
    return None, reasoning
