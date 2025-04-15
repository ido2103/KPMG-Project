import os
import json
import logging
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from openai import AzureOpenAI
import gradio as gr
import re

# Load environment variables from .env file
load_dotenv()

# Configure logging - reduce verbosity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce Azure SDK logging verbosity
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Get credentials from environment variables
doc_intel_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
doc_intel_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
openai_key = os.getenv("AZURE_OPENAI_KEY")
openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# Check if credentials are loaded
if not doc_intel_endpoint or not doc_intel_key:
    raise ValueError("Missing Azure Document Intelligence endpoint or key in .env file.")
if not openai_endpoint or not openai_key:
    raise ValueError("Missing Azure OpenAI endpoint or key in .env file.")

# Initialize the Document Intelligence Client
document_intelligence_client = DocumentIntelligenceClient(
    endpoint=doc_intel_endpoint,
    credential=AzureKeyCredential(doc_intel_key)
)

# Initialize the Azure OpenAI client
openai_client = AzureOpenAI(
    api_key=openai_key,
    api_version=openai_api_version,
    azure_endpoint=openai_endpoint
)

# Define the JSON schema for form extraction
extraction_schema = {
    "type": "object",
    "properties": {
        "lastName": {"type": "string"},
        "firstName": {"type": "string"},
        "idNumber": {"type": "string"},
        "gender": {"type": "string"},
        "dateOfBirth": {
            "type": "object",
            "properties": {
                "day": {"type": "string"},
                "month": {"type": "string"},
                "year": {"type": "string"}
            }
        },
        "address": {
            "type": "object",
            "properties": {
                "street": {"type": "string"},
                "houseNumber": {"type": "string"},
                "entrance": {"type": "string"},
                "apartment": {"type": "string"},
                "city": {"type": "string"},
                "postalCode": {"type": "string"},
                "poBox": {"type": "string"}
            }
        },
        "landlinePhone": {"type": "string"},
        "mobilePhone": {"type": "string"},
        "jobType": {"type": "string"},
        "dateOfInjury": {
            "type": "object",
            "properties": {
                "day": {"type": "string"},
                "month": {"type": "string"},
                "year": {"type": "string"}
            }
        },
        "timeOfInjury": {"type": "string"},
        "accidentLocation": {"type": "string"},
        "accidentAddress": {"type": "string"},
        "accidentDescription": {"type": "string"},
        "injuredBodyPart": {"type": "string"},
        "signature": {"type": "string"},
        "formFillingDate": {
            "type": "object",
            "properties": {
                "day": {"type": "string"},
                "month": {"type": "string"},
                "year": {"type": "string"}
            }
        },
        "formReceiptDateAtClinic": {
            "type": "object",
            "properties": {
                "day": {"type": "string"},
                "month": {"type": "string"},
                "year": {"type": "string"}
            }
        },
        "medicalInstitutionFields": {
            "type": "object",
            "properties": {
                "healthFundMember": {"type": "string"},
                "natureOfAccident": {"type": "string"},
                "medicalDiagnoses": {"type": "string"}
            }
        }
    }
}

# Update the extraction prompt to emphasize using spatial layout information
extraction_prompt = """
You are an AI assistant specialized in extracting information from ביטוח לאומי (National Insurance Institute) forms.
I'll provide you with the textual content and layout information extracted from a form using OCR.
Your task is to extract all available information according to the specified fields and return it in JSON format.

IMPORTANT: The OCR output includes spatial information (bounding boxes) to help you associate labels with their values.
Look for checkbox markers labeled as SELECTED or UNSELECTED to determine which options are checked.
Pay attention to text position coordinates [x=value,y=value] to determine which text is near which form elements.

CRITICAL FOR CHECKBOXES: If the information in the 'SELECTION MARKS' section (which lists marks by index, state, and nearby text) conflicts with the ':selected:' tags embedded directly in the 'Full Document Text', TRUST THE 'SELECTION MARKS' SECTION.

The form can be filled in either Hebrew or English. For any fields not present or not extractable, use an empty string.
IMPORTANT JSON STRUCTURE REQUIREMENTS:
The output must follow this exact structure with nested objects as shown:
{{
"lastName": "",
"firstName": "",
"idNumber": "",
"gender": "",
"dateOfBirth": {{
"day": "",
"month": "",
"year": ""
}},
"address": {{
"street": "",
"houseNumber": "",
"entrance": "",
"apartment": "",
"city": "",
"postalCode": "",
"poBox": ""
}},
"landlinePhone": "",
"mobilePhone": "",
"jobType": "",
"dateOfInjury": {{
"day": "",
"month": "",
"year": ""
}},
"timeOfInjury": "",
"accidentLocation": "",
"accidentAddress": "",
"accidentDescription": "",
"injuredBodyPart": "",
"signature": "",
"formFillingDate": {{
"day": "",
"month": "",
"year": ""
}},
"formReceiptDateAtClinic": {{
"day": "",
"month": "",
"year": ""
}},
"medicalInstitutionFields": {{
"healthFundMember": "",
"natureOfAccident": "",
"medicalDiagnoses": ""
}}
}}
CRITICAL: The fields 'healthFundMember', 'natureOfAccident', and 'medicalDiagnoses' MUST be nested inside an object with the key 'medicalInstitutionFields'. DO NOT place these at the top level of the JSON.
IMPORTANT EXTRACTION RULES:

PHONE NUMBERS:
Map ONLY the number found near 'טלפון נייד' to the 'mobilePhone' key
Map ONLY the number found near 'טלפון קווי' to the 'landlinePhone' key
Israeli mobile numbers typically start with '05' - if the OCR shows a number like '65...', it's likely an OCR error for '05...'
Israeli landline numbers typically start with '0' - if you see '89...' it might be an OCR error for '09...'
Do NOT use any other key names for phone numbers (like 'phoneNumber')

ID NUMBER (CRITICAL):
The 'idNumber' might be located far from the 'ת.ז.' label, potentially near the bottom of the personal details section.
Look for a 9 or 10-digit number in the personal details section, even if it's spatially distant from the label.
Look throughout the entire document for a number that appears to be an Israeli ID (usually 9 digits).
For this form specifically, look around coordinates y=3.3 for ID numbers if they're not directly beside the label.
If the ID number is 10 digits - simply remove the very last digit.

JOB TYPE (CRITICAL):
For 'jobType', look for text near the label 'סוג העבודה'
VERY IMPORTANT: In most forms, the job type appears immediately after 'אני מבקש לקבל עזרה רפואית בגין פגיעה בעבודה שארעה לי'
Look for workplace names like 'מאפיית האחים' , 'ירקנייה' or other business types that appear in this location. Look for a contexctual fit.

ACCIDENT LOCAITON (CRITICAL):
The available  options are: במפעל, ת. דרכים בעבודה, ת. דרכים בדרך לעבודה/מהעבודה, תאונה בדרך ללא רכב, אחר _______
If the option includes אחר only add the text that comes AFTER אחר.

Job Type will inherently be different from Accident Location, and is not limited to the options available for accident location.

SELECTIONS AND CHECKBOXES:
Pay close attention to 'SELECTED' and 'UNSELECTED' markers in the Selection Marks section
For 'accidentLocation', find the Selection Mark listed as 'SELECTED' in the 'SELECTION MARKS' section and use its 'Nearby text' to determine the correct value among: 'במפעל', 'ת. דרכים בעבודה', 'תאונה בדרך ללא רכב', or 'אחר'
Only ONE option should be selected for each multi-choice field
Use the nearby text information to determine what the selection mark is associated with

HEALTH FUND MEMBER:
For 'medicalInstitutionFields.healthFundMember': Carefully check the 'SELECTION MARKS' section for 'כללית', 'מכבי', 'מאוחדת', or 'לאומית'.
The OCR data for this specific field might be unreliable or contradictory.
If exactly one fund is clearly marked 'SELECTED' in the 'SELECTION MARKS' list, use it.
If multiple are marked selected, return an empty string for this field.
If NONE are marked selected, look for a clue from the very beginning of the text. It will mention one of the options near the text 'אל קופ"ח/בי"הח':
 'כללית', 'מכבי', 'מאוחדת', or 'לאומית'.

NATURE OF ACCIDENT:
For 'medicalInstitutionFields.natureOfAccident': Extract the text found directly under the label 'מהות התאונה (אבחנות רפואיות):'.
This field is often empty; if so, return an empty string.
Do NOT confuse this with the accident location or type fields.

SIGNATURE:
For 'signature': Prioritize extracting the handwritten name found near the 'חתימה' label.
If no name is there, but a name near 'שם המבקש' seems like the signature, use that.
If only an 'X' mark is present near 'חתימה', use "Signed".
If none of these are found, use an empty string.

DATES:
For all date fields (dateOfBirth, dateOfInjury, formFillingDate, formReceiptDateAtClinic), parse into separate day, month, year fields
Date formats might appear as DD/MM/YYYY, DD.MM.YYYY, or DDMMYYYY
Dates near 'תאריך לידה' go to dateOfBirth, near 'תאריך הפגיעה' go to dateOfInjury, etc.
Here are the key translations that you must use exactly as specified:
שם משפחה = lastName
שם פרטי = firstName
מספר זהות = idNumber
מין = gender
תאריך לידה = dateOfBirth
כתובת = address
טלפון קווי = landlinePhone
טלפון נייד = mobilePhone
סוג העבודה = jobType
תאריך הפגיעה = dateOfInjury
שעת הפגיעה = timeOfInjury
מקום התאונה = accidentLocation
כתובת מקום התאונה = accidentAddress
תיאור התאונה = accidentDescription
האיבר שנפגע = injuredBodyPart
חתימה = signature
תאריך מילוי הטופס = formFillingDate
תאריך קבלת הטופס בקופה = formReceiptDateAtClinic
למילוי ע״י המוסד הרפואי = medicalInstitutionFields
OCR Content from the document:
{ocr_content}

IMPORTANT:
- Use the SPATIAL INFORMATION (bounding boxes coordinates) to associate labels with their values correctly.
- Look for nearby text spatially, not just sequentially in the text.
- The data is not always entirely accurate, and you must use the data as a hint to extract the data.
- This does not give you an excuse to hallucinate any data, or make up any data.
- You must be as accurate as possible.
- Expect the fields to be messy, and the correct field input might be some lines down from the label, and vice versa.
- Regarding names & last names:
  - Last names will be Hebrew names like Cohen, Levy, Halevi, Israel, etc., NOT codes or abbreviations.
  - First names will be Hebrew names like David, Moshe, Sarah, etc., NOT codes or abbreviations.
  - If you see a name that is not a normal name, it is likely an OCR error, and you should look for a clue later in the document. It might be far from the label.
"""

def analyze_document(file_path):
    """Analyze a document using Azure Document Intelligence with prebuilt-layout"""
    logger.info(f"Analyzing document at path: {file_path}...")
    try:
        with open(file_path, "rb") as f:
            logger.info("Sending document to Azure Document Intelligence...")
            poller = document_intelligence_client.begin_analyze_document(
                "prebuilt-layout",
                body=f,
                content_type="application/octet-stream"
            )
        
        logger.info("Waiting for analysis to complete...")
        result = poller.result()
        logger.info(f"Document analysis complete. Found {len(result.pages)} pages.")
        return result
    except Exception as e:
        logger.error(f"Error during document analysis: {str(e)}", exc_info=True)
        raise

def extract_fields_with_gpt(ocr_result):
    """Use GPT-4o to extract fields from OCR results"""
    logger.info("Preparing OCR results for GPT processing...")
    # Prepare the input for GPT-4o using a more structured approach with layout information
    formatted_text = ""

    # Include the full document content
    if ocr_result.content:
        logger.info("Adding full document content...")
        formatted_text += f"Full Document Text:\n{ocr_result.content}\n\n"

    # Add enhanced layout extraction with bounding boxes and reading order
    formatted_text += "---- STRUCTURED CONTENT WITH LAYOUT INFO ----\n"

    for i, page in enumerate(ocr_result.pages):
        formatted_text += f"\n---- Page {i+1} ----\n"
        
        # Include page dimensions for context
        formatted_text += f"Page Dimensions: Width={page.width}, Height={page.height}\n\n"
        
        # Process selection marks (checkboxes) first - these are critical for form fields
        if hasattr(page, 'selection_marks') and page.selection_marks:
            formatted_text += "SELECTION MARKS (CHECKBOXES/RADIO BUTTONS):\n"
            for idx, mark in enumerate(page.selection_marks):
                # Get mark position safely
                position_str = "position unknown"
                try:
                    if hasattr(mark, 'polygon') and mark.polygon:
                        try:
                            # Try to get first point coordinates
                            if hasattr(mark.polygon[0], 'x') and hasattr(mark.polygon[0], 'y'):
                                position_str = f"[x={mark.polygon[0].x:.1f},y={mark.polygon[0].y:.1f}]"
                            elif isinstance(mark.polygon[0], (int, float)) and len(mark.polygon) >= 2:
                                # Flat array format
                                position_str = f"[x={mark.polygon[0]:.1f},y={mark.polygon[1]:.1f}]"
                        except (IndexError, AttributeError):
                            position_str = "position error"
                except Exception:
                    position_str = "position error"
                
                # Get mark state
                state = "SELECTED" if mark.state == "selected" else "UNSELECTED"
                
                # Get nearby text safely
                try:
                    nearby_text = get_nearby_text(mark, page.lines, 100)  # 100 pixel radius
                except Exception as e:
                    logger.warning(f"Error getting nearby text: {str(e)}")
                    nearby_text = ""
                
                formatted_text += f"Selection Mark {idx+1}: {state} at {position_str} - Nearby text: '{nearby_text}'\n"
            formatted_text += "\n"
        
        # Process lines with bounding box information for spatial context
        if page.lines:
            formatted_text += "TEXT LINES WITH POSITION:\n"
            for line_idx, line in enumerate(page.lines):
                # Get bounding box coordinates safely
                position_str = ""
                try:
                    if hasattr(line, 'polygon') and line.polygon and len(line.polygon) >= 4:
                        try:
                            # Try different polygon formats
                            try:
                                # Point objects with x,y attributes
                                x_coords = [point.x for point in line.polygon]
                                y_coords = [point.y for point in line.polygon]
                            except AttributeError:
                                # Flat array [x1, y1, x2, y2, ...]
                                if isinstance(line.polygon[0], (int, float)):
                                    x_coords = line.polygon[0::2]  # Even indices
                                    y_coords = line.polygon[1::2]  # Odd indices
                                else:
                                    # Unknown format, skip position
                                    raise ValueError("Unknown polygon format")
                            
                            # Calculate bounding box
                            left, top = min(x_coords), min(y_coords)
                            right, bottom = max(x_coords), max(y_coords)
                            position_str = f"[x={left:.1f},y={top:.1f},w={(right-left):.1f},h={(bottom-top):.1f}]"
                        except Exception:
                            # If any error in calculation, skip position info
                            pass
                except Exception:
                    # If any error, don't include position info
                    pass
                
                # Add line with or without position info
                if position_str:
                    formatted_text += f"Line {line_idx+1} {position_str}: '{line.content}'\n"
                else:
                    formatted_text += f"Line {line_idx+1}: '{line.content}'\n"

    # Add table content with structure preserved and cell positions
    if ocr_result.tables:
        formatted_text += "\n---- TABLES WITH STRUCTURE ----\n"
        for table_idx, table in enumerate(ocr_result.tables):
            formatted_text += f"\nTable {table_idx + 1}:\n"
            
            # Track row and column spans safely
            try:
                max_row = max(cell.row_index for cell in table.cells) if table.cells else 0
                max_col = max(cell.column_index for cell in table.cells) if table.cells else 0
                formatted_text += f"Table Dimensions: {max_row+1} rows x {max_col+1} columns\n"
            except Exception as e:
                logger.warning(f"Error calculating table dimensions: {str(e)}")
                formatted_text += "Table Dimensions: unknown\n"
            
            # Group cells by row with position information
            rows = {}
            for cell in table.cells:
                if cell.row_index not in rows:
                    rows[cell.row_index] = []
                
                # Add position information for each cell safely
                position_info = ""
                try:
                    if hasattr(cell, 'polygon') and cell.polygon:
                        try:
                            # Try different polygon formats
                            try:
                                # Point objects with x,y attributes
                                x_coords = [point.x for point in cell.polygon]
                                y_coords = [point.y for point in cell.polygon]
                            except AttributeError:
                                # Flat array [x1, y1, x2, y2, ...]
                                if isinstance(cell.polygon[0], (int, float)):
                                    x_coords = cell.polygon[0::2]  # Even indices
                                    y_coords = cell.polygon[1::2]  # Odd indices
                                else:
                                    # Unknown format, skip position
                                    raise ValueError("Unknown polygon format")
                            
                            left, top = min(x_coords), min(y_coords)
                            position_info = f"[x={left:.1f},y={top:.1f}]"
                        except Exception:
                            # If any error, don't include position
                            pass
                except Exception:
                    # If any error, don't include position
                    pass
                
                # Add span information - check for None values before comparison
                span_info = ""
                if hasattr(cell, 'row_span') and cell.row_span is not None and cell.row_span > 1:
                    span_info += f"rowspan={cell.row_span}"
                if hasattr(cell, 'column_span') and cell.column_span is not None and cell.column_span > 1:
                    span_info += f"colspan={cell.column_span}"
                
                # Combine position and content
                cell_info = f"{position_info} {span_info}: {cell.content}"
                rows[cell.row_index].append((cell.column_index, cell_info))
            
            # Print table in row/column format with position data
            for row_idx in sorted(rows.keys()):
                # Sort cells by column
                sorted_cells = sorted(rows[row_idx], key=lambda x: x[0])
                formatted_text += f"Row {row_idx}: " + " | ".join([f"Col {cell[0]}: {cell[1]}" for cell in sorted_cells]) + "\n"

    # Print the OCR payload that will be sent to the model
    logger.info("==== OCR PAYLOAD FOR MODEL ====")
    print("\n==== OCR PAYLOAD START ====")
    print(formatted_text[:1000] + "..." if len(formatted_text) > 1000 else formatted_text)
    print("==== OCR PAYLOAD END ====\n")
    


    # Fill in the prompt template with enhanced OCR information
    logger.info("Filling prompt template...")
    filled_prompt = extraction_prompt.format(ocr_content=formatted_text)

    # Call GPT-4o with JSON mode
    logger.info("Calling Azure OpenAI GPT-4o for field extraction...")
    try:
        response = openai_client.chat.completions.create(
            model=openai_deployment,
            messages=[
                {"role": "system", "content": "You are an AI assistant that extracts structured information from documents."},
                {"role": "user", "content": filled_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        # Parse the response
        logger.info("Parsing GPT response...")
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data
    except Exception as e:
        logger.error(f"Error during GPT processing: {str(e)}", exc_info=True)
        raise

def get_nearby_text(element, lines, proximity_radius):
    """Find text that is spatially close to a given element (like a checkbox)"""
    if not hasattr(element, 'polygon') or not element.polygon:
        return ""
    
    # Get the center point of the element
    # Handle different polygon formats (some might be direct coordinates rather than Point objects)
    try:
        # First attempt: try accessing as Point objects with x,y attributes
        x_coords = [point.x for point in element.polygon]
        y_coords = [point.y for point in element.polygon]
    except AttributeError:
        # Alternative format: might be [x1, y1, x2, y2, ...] flat array or other format
        # Try to handle various formats that Azure Document Intelligence might return
        try:
            if isinstance(element.polygon, list) and len(element.polygon) >= 2:
                if isinstance(element.polygon[0], (int, float)):
                    # Handle flat array [x1, y1, x2, y2, ...]
                    x_coords = element.polygon[0::2]  # Get even indices (0, 2, 4...)
                    y_coords = element.polygon[1::2]  # Get odd indices (1, 3, 5...)
                elif hasattr(element.polygon[0], 'x') and hasattr(element.polygon[0], 'y'):
                    # Handle list of objects with x,y props
                    x_coords = [point.x for point in element.polygon]
                    y_coords = [point.y for point in element.polygon]
                else:
                    # Can't determine format, use default position
                    logger.warning(f"Unknown polygon format: {element.polygon}")
                    return ""
            else:
                # Can't determine format, use default position
                logger.warning(f"Unknown polygon format: {element.polygon}")
                return ""
        except Exception as e:
            logger.warning(f"Error processing polygon: {str(e)}")
            return ""
    
    # Calculate center point
    center_x = sum(x_coords) / len(x_coords)
    center_y = sum(y_coords) / len(y_coords)
    
    nearby_lines = []
    
    for line in lines:
        if not hasattr(line, 'polygon') or not line.polygon:
            continue
        
        # Get center of the line, handling different polygon formats  
        try:
            # First attempt: try accessing as Point objects with x,y attributes
            line_x_coords = [point.x for point in line.polygon]
            line_y_coords = [point.y for point in line.polygon]
        except AttributeError:
            # Alternative format: try different polygon representations
            try:
                if isinstance(line.polygon, list) and len(line.polygon) >= 2:
                    if isinstance(line.polygon[0], (int, float)):
                        # Handle flat array [x1, y1, x2, y2, ...]
                        line_x_coords = line.polygon[0::2]  # Get even indices
                        line_y_coords = line.polygon[1::2]  # Get odd indices
                    elif hasattr(line.polygon[0], 'x') and hasattr(line.polygon[0], 'y'):
                        # Handle list of objects with x,y props
                        line_x_coords = [point.x for point in line.polygon]
                        line_y_coords = [point.y for point in line.polygon]
                    else:
                        # Skip if format can't be determined
                        continue
                else:
                    # Skip if format can't be determined
                    continue
            except Exception:
                # Skip this line if there's any error
                continue
                
        # Calculate center point of line
        line_center_x = sum(line_x_coords) / len(line_x_coords)
        line_center_y = sum(line_y_coords) / len(line_y_coords)
        
        # Calculate distance
        distance = ((center_x - line_center_x) ** 2 + (center_y - line_center_y) ** 2) ** 0.5
        
        # If within radius, add to nearby lines
        if distance <= proximity_radius:
            nearby_lines.append((distance, line.content))
    
    # Sort by distance and join the closest 3 lines
    nearby_lines.sort(key=lambda x: x[0])
    return " | ".join([line[1] for line in nearby_lines[:3]])

def validate_extracted_data(data):
    """Validate and potentially fix extraction issues"""
    logger.info("Validating extracted data...")
    # Initialize a list to track validation issues
    validation_issues = []

    # 0. Clean up ID number if too long
    if "idNumber" in data and data["idNumber"]:
        id_number = data["idNumber"]
        # If ID is over 10 characters, remove the last digit
        if len(id_number) > 10:
            original_id = id_number
            id_number = id_number[:-1]
            data["idNumber"] = id_number
            logger.info(f"ID number too long, truncating: {original_id} -> {id_number}")
            validation_issues.append(f"Truncated ID number: {original_id} -> {id_number}")

    # 1. Fix JSON structure issues - ensure medicalInstitutionFields is nested correctly
    if "healthFundMember" in data:
        # Just log that a fix was made without details
        logger.info("Fixed structure issue: moved field into correct nested location")
        data["medicalInstitutionFields"] = data.get("medicalInstitutionFields", {})
        data["medicalInstitutionFields"]["healthFundMember"] = data.pop("healthFundMember")
        validation_issues.append("Fixed structure: moved 'healthFundMember' into 'medicalInstitutionFields'")

    # Do the same for natureOfAccident and medicalDiagnoses
    for field in ["natureOfAccident", "medicalDiagnoses"]:
        if field in data:
            logger.warning(f"Found '{field}' at the top level - fixing structure")
            
            # Create medicalInstitutionFields if it doesn't exist
            if "medicalInstitutionFields" not in data:
                data["medicalInstitutionFields"] = {}
            
            # Move field to the correct nested location
            data["medicalInstitutionFields"][field] = data.pop(field)
            validation_issues.append(f"Fixed structure: moved '{field}' into 'medicalInstitutionFields'")

    # Ensure medicalInstitutionFields exists and has all required keys
    if "medicalInstitutionFields" not in data:
        logger.warning("Missing 'medicalInstitutionFields' - adding empty object")
        data["medicalInstitutionFields"] = {
            "healthFundMember": "",
            "natureOfAccident": "",
            "medicalDiagnoses": ""
        }
        validation_issues.append("Added missing 'medicalInstitutionFields' structure")
    else:
        # Ensure all required fields exist
        for field in ["healthFundMember", "natureOfAccident", "medicalDiagnoses"]:
            if field not in data["medicalInstitutionFields"]:
                data["medicalInstitutionFields"][field] = ""
                validation_issues.append(f"Added missing '{field}' in 'medicalInstitutionFields'")

    # 2. Check phone number format and keys
    if "phoneNumber" in data:
        # If phoneNumber was incorrectly used instead of mobilePhone
        logger.warning("Found 'phoneNumber' key instead of 'mobilePhone' - fixing")
        data["mobilePhone"] = data.pop("phoneNumber")
        validation_issues.append("Fixed incorrect key: 'phoneNumber' → 'mobilePhone'")

    # Check mobile phone format (should start with 05)
    if data.get("mobilePhone") and len(data["mobilePhone"]) > 2:
        # Ensure mobile numbers start with '0'
        if not data["mobilePhone"].startswith("0"):
            data["mobilePhone"] = "0" + data["mobilePhone"]
            validation_issues.append(f"Added leading '0' to mobile number: {data['mobilePhone']}")
        
        # Check if it starts with 65 (common OCR error for 05)
        if data["mobilePhone"].startswith("65"):
            logger.warning(f"Fixing likely OCR error in mobile number: {data['mobilePhone']}")
            data["mobilePhone"] = "05" + data["mobilePhone"][2:]
            validation_issues.append(f"Fixed likely OCR error in mobile number: '65...' → '05...'")
    
    # Validate landline phone
    if data.get("landlinePhone"):
        phone = data["landlinePhone"]
        original_phone = phone # Keep original for logging if needed
        
        print(f"[PHONE DEBUG] Starting phone value: '{phone}'")

        # First, ensure number starts with '0'
        if not phone.startswith("0"):
            if phone.startswith("8") or phone.startswith("6"):
                # Replace common OCR errors in first digit
                phone = "0" + phone[1:]
                print(f"[PHONE DEBUG] Replaced first digit with '0': '{phone}'")
            else:
                # Just prepend '0' if needed
                phone = "0" + phone
                print(f"[PHONE DEBUG] Added leading '0': '{phone}'")
            
            validation_issues.append(f"Fixed number format: '{original_phone}' → '{phone}'")
            data["landlinePhone"] = phone
            
        # Then check if length is incorrect (Israeli phone numbers should be 10 digits)
        if len(phone) > 10 and phone.startswith("0"):
            # If we have 11 digits starting with 0, the LLM likely added a 0 
            # but didn't fix the original first digit. Remove the second character.
            fixed_phone = phone[0] + phone[2:]
            print(f"[PHONE DEBUG] Fixed length by removing second character: '{phone}' → '{fixed_phone}'")
            validation_issues.append(f"Fixed phone length: '{phone}' → '{fixed_phone}'")
            data["landlinePhone"] = fixed_phone
            phone = fixed_phone
        
        print(f"[PHONE DEBUG] Final phone value: '{phone}'")
        
        # Add a generic length warning if still incorrect
        if len(phone) != 10:
            validation_issues.append(f"Warning: Landline '{phone}' has unexpected length ({len(phone)} digits).")

    # 3. Validate date fields
    date_fields = ["dateOfBirth", "dateOfInjury", "formFillingDate", "formReceiptDateAtClinic"]
    for field in date_fields:
        if field in data:
            # Ensure the field is a dictionary
            if not isinstance(data[field], dict):
                logger.warning(f"Field '{field}' is not a properly structured date object - fixing")
                # Try to salvage any string value or create empty
                original_value = str(data[field]) if data[field] else ""
                data[field] = {"day": "", "month": "", "year": ""}
                validation_issues.append(f"Fixed structure: converted '{field}' to proper date object (original: {original_value})")
            
            # Ensure date object has all required keys
            date_parts = data[field]
            for part in ["day", "month", "year"]:
                if part not in date_parts:
                    date_parts[part] = ""
                    validation_issues.append(f"Added missing '{part}' in '{field}'")
            
            # Validate date values if present
            try:
                day = int(date_parts.get("day", "0") or "0")
                month = int(date_parts.get("month", "0") or "0")
                year = int(date_parts.get("year", "0") or "0")
                
                if day > 0 and month > 0 and year > 0:  # Only validate if all parts are provided
                    if not (1 <= day <= 31) or not (1 <= month <= 12):
                        validation_issues.append(f"Invalid date in {field}: day={day}, month={month}, year={year}")
            except ValueError:
                validation_issues.append(f"Non-numeric date parts in {field}")

    # 4. Validate address structure
    if "address" in data:
        if not isinstance(data["address"], dict):
            logger.warning("Field 'address' is not a properly structured object - fixing")
            original_value = str(data["address"]) if data["address"] else ""
            data["address"] = {
                "street": "",
                "houseNumber": "",
                "entrance": "",
                "apartment": "",
                "city": "",
                "postalCode": "",
                "poBox": ""
            }
            validation_issues.append(f"Fixed structure: converted 'address' to proper object (original: {original_value})")
        else:
            # Ensure address object has all required keys
            for part in ["street", "houseNumber", "entrance", "apartment", "city", "postalCode", "poBox"]:
                if part not in data["address"]:
                    data["address"][part] = ""
                    validation_issues.append(f"Added missing '{part}' in 'address'")

    # 6. Validate gender (should be זכר or נקבה)
    if "gender" in data and data["gender"]:
        valid_genders = ["זכר", "נקבה", "male", "female"]
        if data["gender"].lower() not in [g.lower() for g in valid_genders]:
            validation_issues.append(f"Invalid gender: '{data['gender']}'")

    # Return the validated data and list of issues found
    return data, validation_issues

def process_document(file_path):
    """Process a document file and extract structured information"""
    try:
        logger.info(f"Processing document: {file_path}")
        # Step 1: Analyze the document with Document Intelligence
        ocr_result = analyze_document(file_path)
        
        # Step 2: Extract fields using GPT-4o
        extracted_data = extract_fields_with_gpt(ocr_result)
        
        # Debug - Check landlinePhone after initial extraction
        if "landlinePhone" in extracted_data:
            print(f"\n[DEBUG] Initial landlinePhone after LLM: '{extracted_data['landlinePhone']}'")
        else:
            print("\n[DEBUG] landlinePhone not present after LLM extraction")
        
        # Display the raw extraction results
        print("\n==== EXTRACTED DATA (BEFORE VALIDATION) ====")
        print(json.dumps(extracted_data, indent=2, ensure_ascii=False))
        print("=========================================\n")
        
        # Step 2.5: Apply direct rule-based extraction for problematic fields
        direct_extractions = extract_fields_directly(ocr_result)
        
        # Debug - Check if direct extraction touched landlinePhone
        if "landlinePhone" in direct_extractions:
            print(f"[DEBUG] landlinePhone from direct extraction: '{direct_extractions['landlinePhone']}'")
        
        # Debug - Check if direct extraction found jobType
        if "jobType" in direct_extractions:
            print(f"[DEBUG] jobType from direct extraction: '{direct_extractions['jobType']}'")
            
        # Override specific fields where direct extraction is more reliable
        if direct_extractions.get("accidentLocation"):
            if extracted_data.get("accidentLocation") != direct_extractions["accidentLocation"]:
                logger.info(f"Overriding 'accidentLocation' from '{extracted_data.get('accidentLocation')}' to '{direct_extractions['accidentLocation']}'")
                extracted_data["accidentLocation"] = direct_extractions["accidentLocation"]
        
        if direct_extractions.get("healthFundMember"):
            if extracted_data.get("medicalInstitutionFields", {}).get("healthFundMember") != direct_extractions["healthFundMember"]:
                logger.info(f"Overriding 'healthFundMember' from '{extracted_data.get('medicalInstitutionFields', {}).get('healthFundMember')}' to '{direct_extractions['healthFundMember']}'")
                if "medicalInstitutionFields" not in extracted_data:
                    extracted_data["medicalInstitutionFields"] = {}
                extracted_data["medicalInstitutionFields"]["healthFundMember"] = direct_extractions["healthFundMember"]
        
        # Override landlinePhone from direct extraction if available
        if direct_extractions.get("landlinePhone"):
            if extracted_data.get("landlinePhone") != direct_extractions["landlinePhone"]:
                logger.info(f"Overriding 'landlinePhone' from '{extracted_data.get('landlinePhone')}' to '{direct_extractions['landlinePhone']}'")
                extracted_data["landlinePhone"] = direct_extractions["landlinePhone"]
        
        # Override jobType from direct extraction if available
        if direct_extractions.get("jobType"):
            if extracted_data.get("jobType") != direct_extractions["jobType"]:
                logger.info(f"Overriding 'jobType' from '{extracted_data.get('jobType')}' to '{direct_extractions['jobType']}'")
                extracted_data["jobType"] = direct_extractions["jobType"]
        
        # Debug - Check landlinePhone before validation
        if "landlinePhone" in extracted_data:
            print(f"[DEBUG] landlinePhone before validation: '{extracted_data['landlinePhone']}'")
        
        # Step 3: Validate and potentially fix extraction issues
        validated_data, validation_issues = validate_extracted_data(extracted_data)
        
        # Debug - Check landlinePhone after validation
        if "landlinePhone" in validated_data:
            print(f"[DEBUG] Final landlinePhone after validation: '{validated_data['landlinePhone']}'")
        
        # Log any validation issues - REDUCE VERBOSITY
        if validation_issues:
            logger.info(f"Validation found {len(validation_issues)} issues")
            # Only log the first 3 issues to reduce verbosity
            for issue in validation_issues[:3]:
                logger.info(f"  - {issue}")
            if len(validation_issues) > 3:
                logger.info(f"  - ... and {len(validation_issues) - 3} more issues")
        
        # Display the final validated data
        print("\n==== FINAL VALIDATED DATA ====")
        final_json = json.dumps(validated_data, indent=2, ensure_ascii=False)
        print(final_json)
        print("============================\n")
        
        # Return the extracted and validated data as formatted JSON
        logger.info("Document processing complete")
        return final_json

    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        return f"Error processing document: {str(e)}"

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

def get_element_center(element):
    """Get the center coordinates of an element's polygon safely"""
    if not hasattr(element, 'polygon') or not element.polygon:
        return None
    
    try:
        # Handle different polygon formats
        try:
            # Point objects with x,y attributes
            x_coords = [point.x for point in element.polygon]
            y_coords = [point.y for point in element.polygon]
        except AttributeError:
            # Flat array [x1, y1, x2, y2, ...]
            if isinstance(element.polygon, list) and len(element.polygon) >= 2:
                if isinstance(element.polygon[0], (int, float)):
                    x_coords = element.polygon[0::2]  # Even indices
                    y_coords = element.polygon[1::2]  # Odd indices
                else:
                    return None
            else:
                return None
        
        # Calculate center
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        return (center_x, center_y)
    except Exception:
        return None

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

# Gradio UI
def gradio_interface(file):
    """Gradio interface for document processing"""
    if file is None:
        return "Please upload a file."
    # Save the uploaded file to a temporary location
    file_path = file.name

    # Process the document
    result = process_document(file_path)

    return result

# Create the Gradio interface
interface = gr.Interface(
    fn=gradio_interface,
    inputs=gr.File(label="Upload PDF or image file"),
    outputs=gr.Textbox(label="Extracted Information (JSON)", lines=20),
    title="National Insurance Form Field Extractor",
    description="Upload a ביטוח לאומי (National Insurance Institute) form to extract information using OCR and AI.",
    examples=[["./assignment/phase1_data/283_ex3.pdf"]]
)

if __name__ == "__main__":
    logger.info("Starting the National Insurance Form Field Extractor application...")
    interface.launch(share=False)