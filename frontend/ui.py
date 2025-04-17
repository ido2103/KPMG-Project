import gradio as gr
import requests
import json
import os
from dotenv import load_dotenv
import logging

# Configure logging for the frontend
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables to find backend URL
# Assumes .env is in the project root where this UI might be launched from
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Configuration ---
# Get backend URL from environment variable, default for local run if not set
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
CHAT_ENDPOINT = f"{BACKEND_URL}/chat"

logger.info(f"Connecting to backend at: {BACKEND_URL}")

# --- Helper Functions ---
# Remove the old format_gradio_history function as it's no longer needed
# def format_gradio_history(chat_history_state: list):
#     ...

# --- Gradio Interface Logic ---
def handle_submit(user_message: str, history_state: list, user_info_state: dict, phase_state: str):
    """Handles message submission: sends to backend, updates state using list-of-dicts format."""
    logger.info(f"Submit | Phase: {phase_state}, User Message: {user_message[:50]}...")
    
    # Append user message to history in the new format
    history_state.append({"role": "user", "content": user_message})
    
    # Prepare payload for backend
    # Assuming backend expects standard list-of-dicts format now
    payload = {
        "user_info": user_info_state,
        "phase": phase_state,
        "chat_history": history_state[:-1], # Send history *before* current user message
        "message": user_message
    }
    
    logger.debug(f"Sending payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    assistant_response_text = "Error: Could not reach backend." # Default error
    new_user_info = user_info_state
    new_phase = phase_state
    
    try:
        response = requests.post(CHAT_ENDPOINT, json=payload, timeout=120) # Increased timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        response_data = response.json()
        logger.debug(f"Received response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        assistant_response_text = response_data.get("assistant_response", "Error: Invalid response format from backend.")
        
        # *** Log Retrieved Context Metadata ***
        retrieved_metadata = response_data.get("retrieved_context_metadata")
        if retrieved_metadata:
            logger.info("--- Retrieved Context --- ")
            for i, chunk in enumerate(retrieved_metadata):
                source = chunk.get('source', 'unknown')
                score = chunk.get('score', 0.0)
                text_preview = chunk.get('text', '')[:100] # Log first 100 chars
                logger.info(f"  {i+1}. Source: {source} | Score: {score:.4f} | Text: {text_preview}...")
            logger.info("-------------------------")
        # ************************************
        
        # Update state based on response
        # Check if key exists and value is not None before updating
        if response_data.get("user_info") is not None:
            new_user_info = response_data["user_info"]
            logger.info(f"State Update | User Info updated: {new_user_info}")
            
        if response_data.get("phase") is not None:
            new_phase = response_data["phase"]
            logger.info(f"State Update | Phase changed to: {new_phase}")
            
        if response_data.get("error") is not None:
             logger.error(f"Backend reported error: {response_data['error']}")
             # Optionally prepend error to assistant message
             # assistant_response_text = f"[Backend Error: {response_data['error']}]\n{assistant_response_text}"

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request failed: {e}")
        assistant_response_text = f"Error: Could not connect to the backend at {CHAT_ENDPOINT}. Please ensure it's running." 
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON response from backend.")
        assistant_response_text = "Error: Received invalid response from backend." 
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        assistant_response_text = "An unexpected error occurred in the frontend." 

    # Append assistant's response to history in the new format
    history_state.append({"role": "assistant", "content": assistant_response_text})
    
    # Return updated values for chatbot, history state, user_info state, phase state
    # history_state is now correctly formatted for the chatbot component
    return history_state, history_state, new_user_info, new_phase

# --- Gradio UI Definition ---
with gr.Blocks(theme=gr.themes.Soft(), css="footer {display: none !important}") as demo:
    # Client-side state variables
    # Initial user_info is empty, phase starts at 'intake'
    user_info = gr.State({})
    phase = gr.State("intake")
    chat_history = gr.State([]) # Stores history in Gradio format [[user, assistant], ...]

    gr.Markdown("## HMO Chatbot (Phase 2)")
    gr.Markdown("Welcome! I can help answer questions about Maccabi, Meuhedet, and Clalit services. First, I need to collect some details.")
    
    chatbot = gr.Chatbot(
            label="HMO Assistant",
            type='messages',
            height=600
        )
    
    msg_input = gr.Textbox(label="Your Message", placeholder="Type your message here...")
    # clear_btn = gr.ClearButton([msg_input, chatbot, user_info, phase, chat_history])
    # Re-enable clear button if state reset is desired

    # Connect submission handler
    msg_input.submit(
        handle_submit, 
        [msg_input, chat_history, user_info, phase], 
        [chatbot, chat_history, user_info, phase] # Update chatbot display and all state variables
    )
    # Clear input textbox after submission
    msg_input.submit(lambda: "", outputs=[msg_input])

if __name__ == "__main__":
    logger.info("Launching Gradio UI on port 7861...")
    # Set the server port here
    demo.launch(server_name="0.0.0.0", share=False, server_port=7861) 