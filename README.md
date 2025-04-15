# National Insurance Form Extraction

A system for extracting information from ביטוח לאומי (National Insurance Institute) forms using Azure Document Intelligence (OCR) and Azure OpenAI.

## Project Overview

This project extracts structured data from National Insurance forms (in both Hebrew and English) and outputs the information in a standardized JSON format. It uses:

- Azure Document Intelligence for Optical Character Recognition (OCR)
- Azure OpenAI (GPT-4o) for field extraction and data processing
- Gradio for the user interface

## Setup Instructions

1. **Clone the repository**

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   - Copy the `.env.example` file to a new file named `.env`
   - Fill in your Azure credentials:
     - `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`
     - `AZURE_DOCUMENT_INTELLIGENCE_KEY`
     - `AZURE_OPENAI_ENDPOINT`
     - `AZURE_OPENAI_KEY`
     - `AZURE_OPENAI_DEPLOYMENT` (default: "gpt-4o")
     - `AZURE_OPENAI_API_VERSION` (default: "2024-02-15-preview")

4. **Run the application**
   ```
   python main.py
   ```

## Project Structure

```
├── main.py                  # Main application file
├── requirements.txt         # Project dependencies
├── .env                     # Environment variables (not in version control)
├── .env.example             # Template for environment variables
├── README.md                # Project documentation
└── assignment/              # Assignment data folder
    ├── phase1_data/         # Sample PDF forms for testing
    └── phase2_data/         # HTML files for Phase 2
```

## Features

- OCR processing of National Insurance forms using Azure Document Intelligence
- Information extraction using Azure OpenAI
- Support for forms in Hebrew or English
- Validation of extracted data
- Simple user interface for uploading files and viewing results

## Output Format

The system extracts information into the following JSON format:

```json
{
  "lastName": "",
  "firstName": "",
  "idNumber": "",
  "gender": "",
  "dateOfBirth": {
    "day": "",
    "month": "",
    "year": ""
  },
  "address": {
    "street": "",
    "houseNumber": "",
    "entrance": "",
    "apartment": "",
    "city": "",
    "postalCode": "",
    "poBox": ""
  },
  "landlinePhone": "",
  "mobilePhone": "",
  "jobType": "",
  "dateOfInjury": {
    "day": "",
    "month": "",
    "year": ""
  },
  "timeOfInjury": "",
  "accidentLocation": "",
  "accidentAddress": "",
  "accidentDescription": "",
  "injuredBodyPart": "",
  "signature": "",
  "formFillingDate": {
    "day": "",
    "month": "",
    "year": ""
  },
  "formReceiptDateAtClinic": {
    "day": "",
    "month": "",
    "year": ""
  },
  "medicalInstitutionFields": {
    "healthFundMember": "",
    "natureOfAccident": "",
    "medicalDiagnoses": ""
  }
}
``` 