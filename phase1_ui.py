# This file will contain the Gradio UI logic.
# It will import necessary functions from the phase1 package.

import gradio as gr
import os # Needed for file handling
# import json # Might be needed later

# Import the main processing function from the phase1 package
from phase1.processor import process_document
from phase1.config import logger # Import logger for UI startup message

# Define the Gradio interface function
def gradio_interface(file):
    if file is None:
        return "Please upload a file."
    
    # Gradio provides a temporary file object. Get its path.
    file_path = file.name
    logger.info(f"Received file: {file_path}")

    # Process the document using the imported function
    result = process_document(file_path)
    
    # The result should already be a JSON string or an error string
    return result

# Create the Gradio interface
interface = gr.Interface(
    fn=gradio_interface,
    inputs=gr.File(label="Upload PDF or image file"),
    outputs=gr.Textbox(label="Extracted Information (JSON)", lines=20),
    title="National Insurance Form Field Extractor (Phase 1)",
    description="Upload a ביטוח לאומי form (PDF or image) to extract information.",
)

if __name__ == "__main__":
    logger.info("Starting the Gradio UI...")
    interface.launch(server_name="0.0.0.0", share=False) 