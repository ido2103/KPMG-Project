import json
import logging

# Import config and component functions
from .config import logger
from .document_analyzer import analyze_document
from .gpt_extractor import extract_fields_with_gpt
from .direct_extractor import extract_fields_directly
from .validator import validate_extracted_data

def process_document(file_path):
    """Process a document file and extract structured information"""
    try:
        logger.info(f"Processing document: {file_path}")

        # Step 1: Analyze the document with Document Intelligence
        ocr_result = analyze_document(file_path)
        if not ocr_result:
             raise ValueError("Document analysis failed or returned empty result.")

        # Step 2: Extract fields using GPT-4o
        extracted_data = extract_fields_with_gpt(ocr_result)
        if not extracted_data:
            raise ValueError("LLM extraction failed or returned empty result.")
        logger.debug(f"Initial LLM extraction results: {extracted_data}")

        # Step 2.5: Apply direct rule-based extraction for potentially overriding fields
        direct_extractions = extract_fields_directly(ocr_result)
        logger.debug(f"Direct extraction results: {direct_extractions}")

        # Override specific fields where direct extraction is deemed more reliable
        # (Only override if direct extraction produced a non-empty value)
        fields_to_override = ["accidentLocation", "healthFundMember", "landlinePhone", "jobType"]
        for field in fields_to_override:
            if field in direct_extractions and direct_extractions[field]:
                current_value = None
                # Handle nested field for healthFundMember
                if field == "healthFundMember":
                    current_value = extracted_data.get("medicalInstitutionFields", {}).get(field)
                    if current_value != direct_extractions[field]:
                         logger.info(f"Overriding '{field}' from '{current_value}' to '{direct_extractions[field]}' based on direct extraction.")
                         if "medicalInstitutionFields" not in extracted_data:
                             extracted_data["medicalInstitutionFields"] = {}
                         extracted_data["medicalInstitutionFields"][field] = direct_extractions[field]
                else:
                    current_value = extracted_data.get(field)
                    if current_value != direct_extractions[field]:
                        logger.info(f"Overriding '{field}' from '{current_value}' to '{direct_extractions[field]}' based on direct extraction.")
                        extracted_data[field] = direct_extractions[field]

        # Step 3: Validate and potentially fix extraction issues
        validated_data, validation_issues = validate_extracted_data(extracted_data)
        logger.debug(f"Validation issues found: {validation_issues}")

        # Log any validation issues
        if validation_issues:
            logger.info(f"Validation found {len(validation_issues)} issues that were addressed or noted.")
            # Optionally log details of issues if needed for production monitoring
            # for issue in validation_issues:
            #     logger.debug(f"  - {issue}")

        final_json = json.dumps(validated_data, indent=2, ensure_ascii=False)
        logger.info("Document processing complete")
        return final_json

    except Exception as e:
        logger.error(f"Error processing document '{file_path}': {str(e)}", exc_info=True) # Log traceback
        # Return a structured error JSON
        error_json = json.dumps({"error": f"Error processing document: {str(e)}"}, indent=2, ensure_ascii=False)
        return error_json
