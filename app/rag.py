import logging
import json
import numpy as np
import faiss
from openai import AzureOpenAI

from .config import logger, INDEX_PATH, METADATA_PATH, AZURE_OPENAI_EMBEDDING_DEPLOYMENT, aoaiclient

# Global variables to hold loaded RAG components
faiss_index: faiss.Index | None = None
metadata: list[dict] = []

def load_rag_components():
    """Loads the FAISS index and metadata from disk."""
    global faiss_index, metadata
    try:
        logger.info(f"Loading FAISS index from: {INDEX_PATH}")
        faiss_index = faiss.read_index(INDEX_PATH)
        logger.info(f"FAISS index loaded successfully. Index size: {faiss_index.ntotal} vectors.")
        
        logger.info(f"Loading metadata from: {METADATA_PATH}")
        with open(METADATA_PATH, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        logger.info(f"Metadata loaded successfully. {len(metadata)} entries.")

        if faiss_index.ntotal != len(metadata):
            logger.warning(f"Mismatch between FAISS index size ({faiss_index.ntotal}) and metadata entries ({len(metadata)}). Ensure they correspond.")

    except FileNotFoundError as e:
        logger.error(f"Error loading RAG components: {e}. Make sure to run the data_ingest script first.")
        # Decide if the app should exit or continue without RAG functionality
        faiss_index = None
        metadata = []
        # raise e # Option to prevent startup if RAG files are missing
    except Exception as e:
        logger.error(f"An unexpected error occurred loading RAG components: {e}")
        faiss_index = None
        metadata = []
        # raise e

def get_query_embedding(text: str) -> np.ndarray | None:
    """Generates embedding for the user query."""
    if not aoaiclient:
        logger.error("Azure OpenAI client not initialized.")
        return None
    try:
        response = aoaiclient.embeddings.create(input=[text], model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
        embedding = response.data[0].embedding
        return np.array(embedding).astype('float32').reshape(1, -1) # Reshape for FAISS
    except Exception as e:
        logger.error(f"Error generating query embedding: {e}")
        return None

def search_index(query_text: str, k: int = 4) -> list[dict]:
    """Searches the FAISS index for relevant chunks."""
    if faiss_index is None or not metadata:
        logger.warning("RAG components not loaded. Search cannot be performed.")
        return []
    if k <= 0:
        return []

    query_embedding = get_query_embedding(query_text)
    if query_embedding is None:
        return []

    try:
        logger.info(f"Searching index for top {k} results...")
        distances, indices = faiss_index.search(query_embedding, k)
        
        results = []
        # indices is a 2D array, get the first row
        for i, idx in enumerate(indices[0]): 
            if idx != -1: # FAISS returns -1 for invalid indices
                score = distances[0][i]
                chunk_data = metadata[idx]
                results.append({
                    "score": float(score), 
                    "text": chunk_data.get('text', ''), 
                    "source": chunk_data.get('source', 'unknown')
                })
            else:
                logger.debug(f"Found invalid index -1 at position {i}")
        
        logger.info(f"Found {len(results)} relevant chunks.")
        # Optional: Add filtering based on score threshold
        # results = [r for r in results if r["score"] > SOME_THRESHOLD]
        return results
        
    except Exception as e:
        logger.error(f"Error searching FAISS index: {e}")
        return []

# Example usage (for testing)
# if __name__ == '__main__':
#     load_rag_components()
#     if faiss_index:
#         test_query = "What dental services are covered by Maccabi Gold?"
#         results = search_index(test_query, k=3)
#         print(f"Query: {test_query}")
#         print("Results:")
#         for res in results:
#             print(f"  Score: {res['score']:.4f}, Source: {res['source']}")
#             print(f"  Text: {res['text'][:150]}...") 