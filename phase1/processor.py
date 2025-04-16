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
