# National Insurance Form Field Extractor

An application for extracting structured information from National Insurance Institute (ביטוח לאומי) forms using Azure Document Intelligence and Azure OpenAI GPT models.

## Features

- Extracts information from scanned forms using OCR
- Processes both Hebrew and English text
- Extracts personal details, contact information, accident details, and medical information
- Validates and fixes common extraction issues
- Provides results in structured JSON format

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with the following credentials:
   ```
   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=your_doc_intelligence_endpoint
   AZURE_DOCUMENT_INTELLIGENCE_KEY=your_doc_intelligence_key
   AZURE_OPENAI_ENDPOINT=your_openai_endpoint
   AZURE_OPENAI_KEY=your_openai_key
   AZURE_OPENAI_DEPLOYMENT=gpt-4o
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

## Usage

Run the application:
```
python main.py
```

This will start a Gradio web interface where you can:
1. Upload PDF or image files containing National Insurance forms
2. Process them to extract structured information
3. View the results in JSON format

## Extracted Information

The application extracts and structures the following information:
- Personal details (name, ID, gender, date of birth)
- Address information
- Contact information (phone numbers)
- Employment details
- Accident details (date, time, location, description)
- Medical information (injured body part, health fund)

## Technologies Used

- Azure Document Intelligence (OCR processing)
- Azure OpenAI GPT-4o (intelligent extraction)
- Python with Gradio UI 