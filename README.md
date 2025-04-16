# KPMG GenAI Developer Assessment Assignment

This repository contains the solutions for the GenAI Developer Assessment Assignment, encompassing two phases: Field Extraction from documents and a RAG Chatbot microservice.

## Project Structure

```
KPMG Project/
├── phase1/               # Phase 1: Field Extraction code
│   ├── azure_clients.py
│   ├── gpt_extractor.py
│   └── ... (other helper modules if any)
├── phase1_ui.py          # Phase 1: Gradio UI
├── app/                  # Phase 2: Backend FastAPI microservice
│   ├── main.py           # FastAPI app entry point
│   ├── models.py         # Pydantic models for API requests/responses
│   ├── rag.py            # RAG logic (vector store interaction)
│   ├── prompts.py        # Prompt templates for the LLM
│   ├── chatbot_logic.py  # Core chatbot orchestration logic
│   ├── config.py         # Configuration loading (from .env)
│   ├── log_config.py     # Logging setup
│   └── requirements.txt  # Backend dependencies
├── frontend/             # Phase 2: Frontend Gradio UI
│   └── ui.py             # Gradio UI code
├── data_ingest/          # Phase 2: Script to build vector store
│   └── build_vector_store.py # HTML parsing and vector store creation
├── assignment/           # Contains original assignment spec and data
│   ├── phase1_data/      # Sample PDFs/images for Phase 1
│   └── phase2_data/      # HTML files for Phase 2 knowledge base
├── vector_store.faiss      # Generated vector store (gitignored)
├── vector_store_metadata.json # Generated metadata (gitignored)
├── .env                  # Local environment variables (gitignored) - **CREATE THIS FILE**
├── .gitignore            # Git ignore file
├── supervisord.conf      # Supervisor config for managing processes in Docker
├── Dockerfile            # Dockerfile for containerization
└── README.md             # This file
```

## Running the Application (Recommended: Docker)

This method runs the Phase 1 UI, Phase 2 Backend, and Phase 2 Frontend simultaneously in a container managed by `supervisord`.

**Prerequisites:**

*   Docker Desktop installed and running.
*   Git installed locally.
*   Python 3.11+ installed locally (only needed for the one-time data ingestion step).

**Steps:**

1.  **Clone Repository:**
    ```bash
    git clone https://github.com/ido2103/KPMG-Project
    cd KPMG-Project
    ```

2.  **Create Environment File:**
    *   Create a file named `.env` in the project root directory.
    *   Copy the following structure into `.env` and fill in your actual Azure credentials and desired configurations:
        ```dotenv
        # Azure Document Intelligence (Phase 1)
        AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="YOUR_DOC_INTEL_ENDPOINT"
        AZURE_DOCUMENT_INTELLIGENCE_KEY="YOUR_DOC_INTEL_KEY"

        # Azure OpenAI (Both Phases)
        AZURE_OPENAI_ENDPOINT="YOUR_AZURE_OPENAI_ENDPOINT"
        AZURE_OPENAI_KEY="YOUR_AZURE_OPENAI_KEY"
        AZURE_OPENAI_API_VERSION="2024-02-15-preview" # Or your desired API version

        # Azure OpenAI Deployments
        AZURE_OPENAI_DEPLOYMENT="gpt-4o" # Or your preferred chat model deployment name (Phase 1 & 2)
        AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-ada-002" # Or your embedding model deployment name (Phase 2)

        # Phase 2 - Data Ingestion Configuration
        CHUNK_SIZE=1000 # Size of text chunks for vector store
        CHUNK_STRIDE=200 # Overlap between text chunks

        # Phase 2 - Optional: Data Paths (Defaults should work if structure is maintained)
        # HTML_DATA_DIR=assignment/phase2_data
        # VECTOR_STORE_PATH=vector_store.faiss
        # METADATA_PATH=vector_store_metadata.json
        ```
    *   **Important:** Ensure this `.env` file is present in the root directory. It's used by both the local ingestion script and copied into the Docker container.

3.  **Install Local Dependencies for Data Ingestion:**
    *   (Optional but recommended) Create and activate a Python virtual environment:
        ```bash
        python -m venv venv
        source venv/bin/activate # On Linux/macOS
        # venv\Scripts\activate # On Windows
        ```
    *   Install packages needed *only* for the ingestion script:
        ```bash
        # Make sure pip is up to date
        python -m pip install --upgrade pip
        # Install ingestion requirements
        pip install python-dotenv beautifulsoup4 numpy faiss-cpu openai
        ```
        *(Note: `faiss-gpu` can be used instead of `faiss-cpu` if you have a compatible GPU and CUDA setup.)*

4.  **Run Data Ingestion:**
    *   Execute the script to process the HTML files and create the vector store:
        ```bash
        python data_ingest/build_vector_store.py
        ```
    *   Verify that `vector_store.faiss` and `vector_store_metadata.json` are created in the project root. These files are crucial and will be copied into the Docker image.

5.  **Build Docker Image:**
    *   From the project root directory (where the `Dockerfile` is located):
        ```bash
        docker build -t kpmg-genai-app .
        ```

6.  **Run Docker Container:**
    *   The `--env-file .env` flag passes your Azure credentials securely into the container.
    ```bash
    docker run --rm -p 8000:8000 -p 7860:7860 -p 7861:7861 --env-file .env --name kpmg-genai-container kpmg-genai-app
    ```
    *(Note: `--rm` automatically removes the container when it exits. Remove it if you want to inspect a stopped container.)*

7.  **Access Services:**
    *   Phase 1 UI: `http://localhost:7860`
    *   Phase 2 UI: `http://localhost:7861`
    *   Phase 2 Backend Health Check: `http://localhost:8000/health`

## Running Locally (Using Virtual Environment)

This method allows running the different components individually without Docker.

**Prerequisites:**

*   Python 3.11+ installed.
*   Git installed.

**Steps:**

1.  **Clone Repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Create Environment File:**
    *   Follow Step 2 from the Docker instructions above to create and populate the `.env` file in the project root.

3.  **Setup Virtual Environment and Install All Dependencies:**
    *   Create and activate a Python virtual environment (see Step 3 in Docker instructions).
    *   Install all necessary dependencies for both phases and data ingestion:
        ```bash
        python -m pip install --upgrade pip
        # Install backend dependencies (FastAPI, Uvicorn, etc.)
        pip install -r app/requirements.txt
        # Install Phase 1 dependencies
        pip install azure-ai-documentintelligence==1.0.0b2 # Pin version if necessary
        # Install Phase 2 frontend dependencies
        pip install gradio requests
        # Install data ingestion dependencies
        pip install python-dotenv beautifulsoup4 numpy faiss-cpu openai==1.30.1 # Pin openai version if needed
        ```

4.  **Run Data Ingestion (if not already done):**
    *   If you haven't run it yet (e.g., you skipped the Docker setup), run the ingestion script:
        ```bash
        python data_ingest/build_vector_store.py
        ```
    *   Ensure `vector_store.faiss` and `vector_store_metadata.json` exist in the root.

5.  **Run Components (in separate terminals):**

    *   **Terminal 1: Phase 2 Backend (FastAPI)**
        ```bash
        # Ensure your virtual environment is active
        uvicorn app.main:app --reload --port 8000
        ```

    *   **Terminal 2: Phase 1 UI (Gradio)**
        ```bash
        # Ensure your virtual environment is active
        python phase1_ui.py
        ```
        *(Access at `http://localhost:7860`)*

    *   **Terminal 3: Phase 2 UI (Gradio)**
        ```bash
        # Ensure your virtual environment is active
        python frontend/ui.py
        ```
        *(Access at `http://localhost:7861`)*

## Notes

*   **Vector Store:** The application relies on the `vector_store.faiss` and `vector_store_metadata.json` files. You **must** run the `data_ingest/build_vector_store.py` script successfully at least once before running the Phase 2 backend (either locally or via Docker build). These files are intentionally gitignored.
*   **Credentials:** Never commit your `.env` file to Git. Ensure it's listed in your `.gitignore` file.
*   **Paths:** The default paths assume the standard project structure. If you modify the structure, update the relevant path configurations in `app/config.py` and `data_ingest/build_vector_store.py`.
*   **Dependencies:** Pay attention to potential version conflicts. Using a virtual environment is highly recommended. Check the `requirements.txt` and individual `pip install` commands for specific versions if needed.

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