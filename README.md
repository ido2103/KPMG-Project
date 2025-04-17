# KPMG GenAI Developer Assessment Assignment

This repository contains the solutions for the GenAI Developer Assessment Assignment, encompassing two phases: Field Extraction from documents and a RAG Chatbot microservice, deployed as containerized microservices.

## Project Structure

```
KPMG Project/
├── phase1/               # Phase 1: Field Extraction Service
│   ├── Dockerfile          # Dockerfile for extractor service
│   ├── azure_clients.py  # Azure client initializations
│   ├── config.py         # Configuration, prompts, schemas
│   ├── gpt_extractor.py  # Logic for GPT-based extraction
│   └── processor.py      # Main document processing logic
├── phase1_ui.py          # Phase 1: Gradio UI entrypoint
├── app/                  # Phase 2: Backend RAG API Service
│   ├── Dockerfile          # Dockerfile for RAG API service (includes ingestion)
│   ├── main.py           # FastAPI app entry point
│   ├── models.py         # Pydantic models
│   ├── rag.py            # RAG logic (vector store interaction)
│   ├── prompts.py        # Prompt templates
│   ├── chatbot_logic.py  # Core chatbot orchestration
│   ├── config.py         # Configuration loading (runtime)
│   └── log_config.py     # Logging setup
├── frontend/             # Phase 2: Frontend Gradio UI Service
│   ├── Dockerfile          # Dockerfile for RAG UI service
│   └── ui.py             # Gradio UI code and logic
├── data_ingest/          # Phase 2: Script to build vector store
│   └── build_vector_store.py # Executed during `rag_api` Docker build / local setup
├── assignment/           # Contains original assignment spec and data (excluded via .dockerignore)
│   ├── phase1_data/      # Sample PDFs/images for Phase 1
│   └── phase2_data/      # HTML files for Phase 2 knowledge base
├── .env                  # Local environment variables (gitignored) - **CREATE THIS FILE**
├── .gitignore            # Git ignore patterns
├── .dockerignore         # Files/dirs excluded from Docker build contexts
├── requirements.txt      # Centralized Python dependencies
├── docker-compose.yml    # Docker Compose file for orchestration
└── README.md             # This file

# Note: Vector store files (vector_store.faiss, vector_store_metadata.json)
# are built automatically inside the rag_api image when using Docker Compose,
# or generated locally when running with a virtual environment.
# They are not tracked by Git.
```

## Running the Application

There are two primary methods for running this application:

1.  **Docker Compose (Recommended):** Builds and runs all services as containers.
2.  **Local Python Virtual Environment:** Runs components directly using your local Python installation.

### Method 1: Docker Compose (Recommended)

This method orchestrates the three microservices (Phase 1 UI, Phase 2 Backend API, Phase 2 Frontend UI) using Docker Compose, ensuring a consistent environment.

**Prerequisites:**

*   Docker Desktop installed and running (with Docker Compose v2+).
*   Git installed locally.

**Steps:**

1.  **Clone Repository:**
    ```bash
    git clone https://github.com/ido2103/KPMG-Project
    cd KPMG-Project
    ```

2.  **Create Environment File (`.env`):**
    *   In the project root (`KPMG-Project/`), create a file named `.env`.
    *   Populate it with your Azure credentials and configuration based on the following structure:
        ```dotenv
        # Azure Document Intelligence (Phase 1)
        AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=YOUR_DOC_INTEL_ENDPOINT
        AZURE_DOCUMENT_INTELLIGENCE_KEY=YOUR_DOC_INTEL_KEY

        # Azure OpenAI (Both Phases)
        AZURE_OPENAI_ENDPOINT=YOUR_AZURE_OPENAI_ENDPOINT
        AZURE_OPENAI_KEY=YOUR_AZURE_OPENAI_KEY
        AZURE_OPENAI_API_VERSION=2024-02-15-preview # Specify desired API version

        # Azure OpenAI Deployments
        AZURE_OPENAI_DEPLOYMENT=gpt-4o # Deployment name for Chat model (Phase 1 & 2)
        AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002 # Deployment name for Embedding model (Phase 2)

        # Phase 2 - Data Ingestion Configuration (Used during rag_api image build)
        CHUNK_SIZE=1000
        CHUNK_STRIDE=200
        INDEX_PATH=./vector_store.faiss
        METADATA_PATH=./vector_store_metadata.json
        ```
    *   **Note on Quoting:** While some tools might parse `.env` files with quotes around values, the standard convention is to omit quotes unless the value contains spaces or special characters. For simplicity and compatibility, it's recommended to enter values directly (e.g., `AZURE_OPENAI_KEY=YOUR_KEY_HERE`).
    *   **Importance:** This file provides credentials needed during the build of the `rag_api` image (for data ingestion) and at runtime for both the `extractor` and `rag_api` services to connect to Azure.

3.  **Build and Run Services:**
    *   Open a terminal in the project root directory.
    *   Execute the command:
        ```bash
        docker compose up --build
        ```
    *   This command performs the following:
        *   Builds the Docker images for `extractor`, `rag_api`, and `rag_ui` services.
        *   Automatically runs the data ingestion script during the `rag_api` image build, creating the vector store **inside the image** for the `rag_api` service.
        *   Starts containers for all three services.
        *   The services will start concurrently. The `rag_ui` might become accessible slightly before the `rag_api` is fully initialized.

4.  **Access Services:**
*   Phase 1 UI (Extractor): [`http://localhost:7860`](http://localhost:7860)
*   Phase 2 UI (RAG Chatbot): [`http://localhost:7861`](http://localhost:7861)
*   Phase 2 Backend Health Check: [`http://localhost:8000/health`](http://localhost:8000/health)

5.  **Stopping Services:**
    *   Press `Ctrl+C` in the terminal running `docker compose up`.
    *   To remove the containers and associated network: `docker compose down`

### Method 2: Local Python Virtual Environment

This method runs the components directly on your machine using Python. It requires manual setup of dependencies and the vector store.

**Prerequisites:**

*   Python 3.11+ installed.
*   Git installed.

**Steps:**

1.  **Clone Repository:**
    ```bash
    git clone https://github.com/ido2103/KPMG-Project
    cd KPMG-Project
    ```

2.  **Create Environment File (`.env`):**
    *   Follow Step 2 from the Docker Compose instructions above to create and populate the `.env` file in the project root.

3.  **Setup Virtual Environment:**
    *   It is highly recommended to use a virtual environment to manage dependencies.
    *   From the project root directory, create and activate a virtual environment:
        ```bash
        # Create the virtual environment (e.g., named 'venv')
        python -m venv venv 
        # Activate it:
        # Windows (cmd.exe)
        venv\Scripts\activate.bat 
        # Windows (PowerShell or Git Bash)
        venv\Scripts\Activate.ps1 
        # macOS / Linux
        source venv/bin/activate 
        ```
    *   Your terminal prompt should now indicate the active environment (e.g., `(venv) C:\\...\\KPMG-Project>`).

4.  **Install Dependencies:**
    *   Ensure pip is up-to-date and install all project requirements into your active virtual environment:
        ```bash
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        ```

5.  **Build Vector Store Manually:**
    *   Run the data ingestion script once to create the knowledge base for Phase 2:
        ```bash
        python data_ingest/build_vector_store.py
        ```
    *   Verify that `vector_store.faiss` and `vector_store_metadata.json` are created in the project root directory.

6.  **Run Services (in separate terminals):**
    *   You will need three separate terminals, each with the virtual environment activated (`source venv/bin/activate` or `venv\Scripts\activate`).
    *   **Terminal 1: Phase 2 Backend (FastAPI):**
        ```bash
        # (venv) ... > 
        uvicorn app.main:app --host 0.0.0.0 --port 8000
        ```
    *   **Terminal 2: Phase 1 UI (Gradio):**
        ```bash
        # (venv) ... > 
        python phase1_ui.py
        ```
    *   **Terminal 3: Phase 2 UI (Gradio):**
        ```bash
        # (venv) ... > 
        python frontend/ui.py
        ```
7.  **Access Services:**
    *   Phase 1 UI (Extractor): [`http://localhost:7860`](http://localhost:7860)
    *   Phase 2 UI (RAG Chatbot): [`http://localhost:7861`](http://localhost:7861)
    *   Phase 2 Backend Health Check: [`http://localhost:8000/health`](http://localhost:8000/health)

8.  **Stopping Services:**
    *   Press `Ctrl+C` in each of the three terminals.
    *   To deactivate the virtual environment: `deactivate`

## Usage Guide

Once the application services are running (using either Docker Compose or the local Python method), you can interact with the different components:

### Phase 1: Document Field Extraction

1.  **Access the UI:** Open your web browser and navigate to [`http://localhost:7860`](http://localhost:7860).
2.  **Upload Document:** Use the file upload interface to select a National Insurance form (PDF or image format). Sample documents are available in the `assignment/phase1_data/` directory for testing.
3.  **View Results:** After processing (which involves OCR and LLM extraction), the extracted fields will be displayed in JSON format in the output text box.

### Phase 2: HMO RAG Chatbot

1.  **Access the UI:** Open your web browser and navigate to [`http://localhost:7861`](http://localhost:7861).
2.  **Interact with the Chatbot:**
    *   The chatbot will initially guide you through an "intake" phase to collect necessary user profile information (e.g., name, HMO details). Respond to the prompts in the chat interface.
    *   Once the required information is gathered, the chatbot transitions to the RAG (Retrieval-Augmented Generation) phase.
    *   You can then ask questions related to HMO services (based on the knowledge base built from `assignment/phase2_data/`). The chatbot will use the provided profile information and the retrieved context from the knowledge base to answer your queries.

### Phase 2: Backend API Health Check (Optional)

*   To verify that the backend API service (`rag_api`) for Phase 2 is running and has successfully loaded its knowledge base (RAG components), you can access its health check endpoint: [`http://localhost:8000/health`](http://localhost:8000/health).
*   A successful response indicates the service is operational and ready: `{"status":"ok","rag_loaded":true}`.

## Notes

*   **Credentials:** Never commit your `.env` file to Git. Ensure it's listed in `.gitignore`.
*   **Vector Store:** When running with Docker Compose, the vector store is built automatically inside the `rag_api` image. When running locally, ensure you run the `data_ingest/build_vector_store.py` script after installing dependencies and before starting the backend service.

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