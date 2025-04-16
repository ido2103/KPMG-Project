import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
# Ensure the .env file is in the root directory where phase1_ui.py is run
load_dotenv()

# Configure logging - reduce verbosity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__) # Use specific logger for this module if needed, or configure root logger

# Reduce Azure SDK logging verbosity
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Get credentials from environment variables
DOC_INTEL_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
DOC_INTEL_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# Check if credentials are loaded
if not DOC_INTEL_ENDPOINT or not DOC_INTEL_KEY:
    raise ValueError("Missing Azure Document Intelligence endpoint or key. Check your .env file.")
if not OPENAI_ENDPOINT or not OPENAI_KEY:
    raise ValueError("Missing Azure OpenAI endpoint or key. Check your .env file.")


# Define the JSON schema for form extraction
EXTRACTION_SCHEMA = {
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
EXTRACTION_PROMPT = """
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