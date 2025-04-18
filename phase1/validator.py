import logging
import re

# Import config
from .config import logger

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

        # Add regex validation for 9 digits after potential truncation
        if id_number and not re.fullmatch(r"\d{9}", id_number):
             validation_issues.append(f"Invalid ID number format: '{id_number}' (should be 9 digits)")

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
