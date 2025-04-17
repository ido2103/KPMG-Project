import os
import glob
import logging
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import numpy as np
import faiss
from openai import AzureOpenAI

# --- Configuration ---
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    # Reduce verbosity for libraries
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logging.getLogger(__name__)

logger = setup_logging()

# Load environment variables from .env file in the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
dotenv_path = os.path.join(project_root, '.env')
if not os.path.exists(dotenv_path):
    logger.error(f".env file not found at {dotenv_path}")
    exit(1)
load_dotenv(dotenv_path=dotenv_path)

# Get Azure credentials and config
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

# Chunking parameters
try:
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 700))
    CHUNK_STRIDE = int(os.getenv("CHUNK_STRIDE", 100))
except ValueError:
    logger.error("CHUNK_SIZE or CHUNK_STRIDE in .env is not a valid integer.")
    exit(1)

# Paths (relative to project root)
DATA_DIR = os.path.join(project_root, "assignment/phase2_data")
# Allow overriding output paths via environment variables for Docker build flexibility
INDEX_PATH = os.getenv("OUTPUT_INDEX_PATH", os.path.join(project_root, "vector_store.faiss"))
METADATA_PATH = os.getenv("OUTPUT_METADATA_PATH", os.path.join(project_root, "vector_store_metadata.json"))

# Ensure output directory exists if specified via env var
output_dir = os.path.dirname(INDEX_PATH)
if output_dir and not os.path.exists(output_dir):
    logger.info(f"Creating output directory: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)

# Check essential config
if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_EMBEDDING_DEPLOYMENT]):
    logger.error("Missing Azure OpenAI credentials or embedding deployment name in .env")
    exit(1)
if not os.path.isdir(DATA_DIR):
    logger.error(f"Data directory not found: {DATA_DIR}")
    exit(1)

# Initialize Azure OpenAI client
try:
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
except Exception as e:
    logger.error(f"Failed to initialize AzureOpenAI client: {e}")
    exit(1)

# --- Helper Functions ---

def parse_html(file_path: str) -> tuple[str, str]:
    """Parses HTML file, extracts text including table cells, returns (text, source_url)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        # Find all relevant text-containing elements, including table cells (td, th)
        text_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'li', 'td', 'th'])
        
        # Extract text, stripping extra whitespace from each element's content
        paragraphs = [elem.get_text(strip=True) for elem in text_elements]
        
        # Join non-empty paragraphs/cells with newline for readability and context
        full_text = "\n".join(filter(None, paragraphs)) 
        
        source_url = os.path.basename(file_path) # Use filename as source id
        logger.debug(f"Extracted {len(full_text)} characters from {source_url}")
        return full_text, source_url
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")
        return "", ""

def chunk_text(text: str, source_url: str, chunk_size: int, chunk_stride: int) -> list[dict]:
    """Chunks text using a sliding window approach."""
    chunks = []
    text_len = len(text)
    start = 0
    while start < text_len:
        end = start + chunk_size
        chunk_text = text[start:end]
        # Basic cleanup within chunk: replace multiple newlines/spaces
        cleaned_chunk_text = ' '.join(chunk_text.split())
        if cleaned_chunk_text: # Avoid adding empty chunks after cleaning
             chunks.append({'text': cleaned_chunk_text, 'source': source_url})
        
        # Move the window
        next_start = start + chunk_stride
        if next_start >= text_len: # Stop if next window starts beyond text
             break
        if next_start <= start: # Stop if stride is non-positive or causes no progress
            logger.warning(f"Chunking stopped due to non-positive stride or lack of progress. Stride: {chunk_stride}")
            break 
        start = next_start
                 
    return chunks

def get_embeddings(texts: list[str], client: AzureOpenAI, model: str) -> np.ndarray | None:
    """Generates embeddings for a list of texts."""
    if not texts:
        logger.warning("No texts provided to get_embeddings.")
        return None
    try:
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        # Handle potential API limits by batching if necessary (though ada-002 handles 2048 items)
        # For simplicity, sending all at once assuming it's within limits.
        response = client.embeddings.create(input=texts, model=model)
        embeddings = [item.embedding for item in response.data]
        logger.info("Embeddings generated successfully.")
        return np.array(embeddings).astype('float32')
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}", exc_info=True)
        return None

# --- Main Script Logic ---
if __name__ == "__main__":
    logger.info("Starting data ingestion process...")

    html_files = glob.glob(os.path.join(DATA_DIR, "*.html"))
    if not html_files:
        logger.error(f"No HTML files found in {DATA_DIR}")
        exit(1)
    
    logger.info(f"Found {len(html_files)} HTML files to process.")

    all_chunks_data = []
    for html_file in html_files:
        logger.info(f"Processing: {html_file}")
        text, source = parse_html(html_file)
        if not text:
            logger.warning(f"Skipping {html_file} due to parsing error or empty content.")
            continue
        
        file_chunks = chunk_text(text, source, CHUNK_SIZE, CHUNK_STRIDE)
        if not file_chunks:
             logger.warning(f"No chunks generated from {source} after parsing and cleaning.")
             continue
             
        logger.info(f"Created {len(file_chunks)} chunks from {source}.")
        all_chunks_data.extend(file_chunks)

    if not all_chunks_data:
        logger.error("No text chunks were generated from the HTML files.")
        exit(1)

    logger.info(f"Total chunks generated: {len(all_chunks_data)}")

    # Prepare texts for embedding
    chunk_texts = [chunk['text'] for chunk in all_chunks_data]

    # Get embeddings
    embeddings = get_embeddings(chunk_texts, client, AZURE_OPENAI_EMBEDDING_DEPLOYMENT)

    if embeddings is None:
        logger.error("Failed to generate embeddings. Exiting.")
        exit(1)
    
    if len(embeddings) != len(all_chunks_data):
         logger.error(f"Mismatch between number of embeddings ({len(embeddings)}) and chunks ({len(all_chunks_data)}).")
         exit(1)

    # Create and build FAISS index
    try:
        dimension = embeddings.shape[1]
        logger.info(f"Creating FAISS index with dimension {dimension}...")
        index = faiss.IndexFlatIP(dimension) # Using Inner Product as suggested
        index.add(embeddings)
        logger.info(f"FAISS index built successfully. Index size: {index.ntotal} vectors.")
    except Exception as e:
        logger.error(f"Error creating or building FAISS index: {e}")
        exit(1)

    # Save FAISS index
    try:
        logger.info(f"Saving FAISS index to: {INDEX_PATH}")
        faiss.write_index(index, INDEX_PATH)
        logger.info("FAISS index saved successfully.")
    except Exception as e:
        logger.error(f"Error saving FAISS index: {e}")
        exit(1)

    # Save metadata (mapping index ID to chunk text and source)
    try:
        logger.info(f"Saving metadata to: {METADATA_PATH}")
        with open(METADATA_PATH, 'w', encoding='utf-8') as f:
            # Storing as a list where the index corresponds to the FAISS index ID
            json.dump(all_chunks_data, f, ensure_ascii=False, indent=4)
        logger.info("Metadata saved successfully.")
    except Exception as e:
        logger.error(f"Error saving metadata: {e}")
        exit(1)

    logger.info("Data ingestion process completed successfully!") 