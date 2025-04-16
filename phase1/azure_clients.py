from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from openai import AzureOpenAI

# Import configuration variables
from .config import (
    DOC_INTEL_ENDPOINT,
    DOC_INTEL_KEY,
    OPENAI_ENDPOINT,
    OPENAI_KEY,
    OPENAI_API_VERSION,
    OPENAI_DEPLOYMENT # Although not used here, good practice to know it's available
)

# Initialize the Document Intelligence Client
# Ensure credentials are valid before initializing
if not DOC_INTEL_ENDPOINT or not DOC_INTEL_KEY:
    raise ValueError("Document Intelligence credentials not found in config.")

document_intelligence_client = DocumentIntelligenceClient(
    endpoint=DOC_INTEL_ENDPOINT,
    credential=AzureKeyCredential(DOC_INTEL_KEY)
)

# Initialize the Azure OpenAI client
# Ensure credentials are valid before initializing
if not OPENAI_ENDPOINT or not OPENAI_KEY:
    raise ValueError("OpenAI credentials not found in config.")

openai_client = AzureOpenAI(
    api_key=OPENAI_KEY,
    api_version=OPENAI_API_VERSION,
    azure_endpoint=OPENAI_ENDPOINT
)

# Optional: Add functions to get clients if needed elsewhere, 
# but for now, just initializing them is sufficient as they 
# will be imported directly by other modules.

def get_doc_intel_client():
    """Returns the initialized Document Intelligence client."""
    return document_intelligence_client

def get_openai_client():
    """Returns the initialized Azure OpenAI client."""
    return openai_client 