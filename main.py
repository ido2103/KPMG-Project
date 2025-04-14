import os
import json
import logging
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from openai import AzureOpenAI
import gradio as gr

# Load environment variables from .env file
load_dotenv()

# Configure logging - reduce verbosity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Update the extraction prompt to address specific issues
extraction_prompt = """
You are an AI assistant specialized in extracting information from ביטוח לאומי (National Insurance Institute) forms.
I'll provide you with the textual content and layout information extracted from a form using OCR.
Your task is to extract all available information according to the specified fields and return it in JSON format.
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
Do NOT use any other key names for phone numbers (like 'phoneNumber')
SELECTIONS AND CHECKBOXES:
Look for ':selected:' or ':unselected:' markers in the OCR text to determine which options are checked. The name of the selected option appears immediately before the ':selected:' or ':unselected:' marker.
For 'accidentLocation', find which option is marked as ':selected:' among: 'במפעל', 'ת. דרכים בעבודה', 'תאונה בדרך ללא רכב', or 'אחר'
Only ONE option should be selected for each multi-choice field
HEALTH FUND MEMBER:
In the section 'למילוי ע"י המוסד הרפואי', find EXACTLY which health fund name ('כללית', 'מכבי', 'מאוחדת', or 'לאומית') is marked with ':selected:'
Assign ONLY that name to 'medicalInstitutionFields.healthFundMember' - NOT to a top-level 'healthFundMember' field
Check carefully - only one fund can be selected
SIGNATURE:
For 'signature', look for either a mark ('X') or a name near the 'חתימה' label
If a name appears next to 'שם המבקש' (Applicant Name), this might be relevant for the signature
If only an 'X' mark is present, use "Signed"
If nothing is present, use an empty string
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
למילוי ע"י המוסד הרפואי = medicalInstitutionFields
OCR Content from the document:
{ocr_content}

IMPORTANT:
- The data is not always entierly accurate, and you must use the data as a hint to extract the data.
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
    # Prepare the input for GPT-4o using a simpler line-by-line approach
    formatted_text = ""

    # Include the full document content
    if ocr_result.content:
        # Reduce log verbosity - don't log content length
        logger.info("Adding full document content...")
        formatted_text += f"Full Document Text:\n{ocr_result.content}\n\n"

    # Add simple line by line extraction, similar to test.py
    formatted_text += "---- Line by Line Content ----\n"

    for i, page in enumerate(ocr_result.pages):
        formatted_text += f"\n---- Page {i+1} ----\n"
        if page.lines:
            for line_idx, line in enumerate(page.lines):
                formatted_text += f"Line {line_idx + 1}: '{line.content}'\n"

    # Add table content if available
    if ocr_result.tables:
        formatted_text += "\n---- Tables ----\n"
        for table_idx, table in enumerate(ocr_result.tables):
            formatted_text += f"\nTable {table_idx + 1}:\n"
            
            # Create a simple visual representation of the table
            # Group cells by row
            rows = {}
            for cell in table.cells:
                if cell.row_index not in rows:
                    rows[cell.row_index] = []
                rows[cell.row_index].append((cell.column_index, cell.content))
            
            # Print table in row/column format
            for row_idx in sorted(rows.keys()):
                # Sort cells by column
                sorted_cells = sorted(rows[row_idx], key=lambda x: x[0])
                row_content = " | ".join([cell[1] for cell in sorted_cells])
                formatted_text += f"Row {row_idx}: {row_content}\n"

    # Log the formatted content for debugging - REDUCE VERBOSITY
    logger.debug("Formatted OCR content ready for GPT") # Only log at debug level

    # Fill in the prompt template
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
            temperature=0.01
        )
        
        # Parse the response
        logger.info("Parsing GPT response...")
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data
    except Exception as e:
        logger.error(f"Error during GPT processing: {str(e)}", exc_info=True)
        raise

def validate_extracted_data(data):
    """Validate and potentially fix extraction issues"""
    logger.info("Validating extracted data...")
    # Initialize a list to track validation issues
    validation_issues = []

    # 1. Fix JSON structure issues - ensure medicalInstitutionFields is nested correctly
    if "healthFundMember" in data:
        # Reduce log verbosity - don't log every fix in detail
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
        if not data["mobilePhone"].startswith("05"):
            # Check if it starts with 65 (common OCR error for 05)
            if data["mobilePhone"].startswith("65"):
                logger.warning(f"Fixing likely OCR error in mobile number: {data['mobilePhone']}")
                data["mobilePhone"] = "05" + data["mobilePhone"][2:]
                validation_issues.append(f"Fixed likely OCR error in mobile number: '65...' → '05...'")

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

    # 5. Validate health fund member (must be one of the known options)
    if "medicalInstitutionFields" in data and "healthFundMember" in data["medicalInstitutionFields"]:
        valid_funds = ["כללית", "מכבי", "מאוחדת", "לאומית"]
        hfm = data["medicalInstitutionFields"]["healthFundMember"]
        if hfm and hfm not in valid_funds:
            validation_issues.append(f"Invalid health fund: '{hfm}'")

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
        
        # Step 3: Validate and potentially fix extraction issues
        validated_data, validation_issues = validate_extracted_data(extracted_data)
        
        # Log any validation issues - REDUCE VERBOSITY
        if validation_issues:
            logger.info(f"Validation found {len(validation_issues)} issues")
            # Only log the first 3 issues to reduce verbosity
            for issue in validation_issues[:3]:
                logger.info(f"  - {issue}")
            if len(validation_issues) > 3:
                logger.info(f"  - ... and {len(validation_issues) - 3} more issues")
        
        # Return the extracted and validated data as formatted JSON
        logger.info("Document processing complete")
        return json.dumps(validated_data, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        return f"Error processing document: {str(e)}"

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