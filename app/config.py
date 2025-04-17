import os
import logging
from dotenv import load_dotenv

# --- Basic Setup ---
def setup_logging():
    # Basic logger setup - will be enhanced by log_config.py later
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Load environment variables from .env file in the project root
# Assumes the app is run from the project root or Dockerfile handles path
# Corrected path: Go up ONE level from app/config.py location
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
dotenv_path = os.path.join(project_root, '.env')

if not os.path.exists(dotenv_path):
    logger.warning(f".env file not found at {dotenv_path}. Relying on environment variables.")
    # Optionally raise error if .env is strictly required
    # raise FileNotFoundError(f".env file not found at {dotenv_path}") 
load_dotenv(dotenv_path=dotenv_path)

# --- Azure Credentials ---
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o") # Default GPT-4o for chat
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

# Check Azure credentials
if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_EMBEDDING_DEPLOYMENT]):
    logger.error("Missing one or more Azure OpenAI environment variables (ENDPOINT, KEY, DEPLOYMENT, EMBEDDING_DEPLOYMENT)")
    # Depending on deployment strategy, you might exit here or rely on managed identity etc.
    # exit(1) 

# --- Vector Store Paths ---
# Inside the container, the files are copied directly into the /app working directory.
# Use absolute paths within the container context.
INDEX_PATH = os.getenv("INDEX_PATH", "/app/vector_store.faiss")
METADATA_PATH = os.getenv("METADATA_PATH", "/app/vector_store_metadata.json")

logger.info(f"Runtime INDEX_PATH: {INDEX_PATH}")
logger.info(f"Runtime METADATA_PATH: {METADATA_PATH}")

# --- Chat Configuration ---
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", 10))


# --- Initialize Azure Client (can also be done in a dedicated module) ---
from openai import AzureOpenAI

aoaiclient = None
try:
    # Ensure credentials are loaded before initializing
    if AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT:
        aoaiclient = AzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        logger.info("Azure OpenAI client initialized successfully.")
    else:
        logger.error("Cannot initialize Azure OpenAI client due to missing KEY or ENDPOINT.")
except Exception as e:
    logger.error(f"Failed to initialize Azure OpenAI client: {e}")
    # Decide if the app can run without the client
    # exit(1)

