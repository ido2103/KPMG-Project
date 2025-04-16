# Placeholder for core chatbot logic (handling phases, LLM calls)

from .config import logger, aoaiclient, AZURE_OPENAI_DEPLOYMENT, MAX_HISTORY_TURNS
from .models import UserInfo, ChatMessage, ChatRequest, ChatResponse
from .prompts import INTAKE_SYSTEM_PROMPT, QA_SYSTEM_PROMPT
from .rag import search_index
import json
import re
from langdetect import detect

def format_chat_history(history: list[ChatMessage]) -> str:
    """Formats chat history for the prompt."""
    return "\n".join([f"{msg.role.capitalize()}: {msg.content}" for msg in history])

def run_chat_logic(request: ChatRequest) -> ChatResponse:
    """Handles the main chat logic based on phase."""
    logger.info(f"Received request for phase: {request.phase}")

    # 1. Detect Language (simple heuristic)
    try:
        detected_lang = detect(request.message)
        # Update language in user_info if not already set or different
        if request.user_info.language != detected_lang:
             logger.info(f"Detected language: {detected_lang}, updating user_info.")
             request.user_info.language = detected_lang 
    except Exception as e:
        logger.warning(f"Language detection failed: {e}. Defaulting to {request.user_info.language}.")
        detected_lang = request.user_info.language

    # Trim history
    trimmed_history = request.chat_history[-MAX_HISTORY_TURNS*2:] # Keep last N turns (user+assistant)

    # Initialize response object
    response = ChatResponse(assistant_response="", user_info=request.user_info, phase=request.phase)

    if request.phase == "intake":
        try:
            user_info_str = request.user_info.model_dump_json(indent=2)
            history_str = format_chat_history(trimmed_history)
            
            # Construct messages for OpenAI API
            messages = [
                {"role": "system", "content": INTAKE_SYSTEM_PROMPT.format(
                    user_info_json=user_info_str,
                    chat_history=history_str,
                    user_message=request.message
                    )
                },
                # Add previous turns if needed, or rely on system prompt context
                 *[{ "role": msg.role, "content": msg.content } for msg in trimmed_history],
                 {"role": "user", "content": request.message} 
            ]

            logger.info("Calling OpenAI for intake phase...")
            completion = aoaiclient.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                temperature=0.2, # Slightly creative for conversation flow
                max_tokens=500 
            )
            assistant_msg_content = completion.choices[0].message.content
            logger.info("OpenAI intake response received.")
            
            # Check for the <INFO_COLLECTED> signal
            if "<INFO_COLLECTED>" in assistant_msg_content:
                logger.info("Info collection signal detected.")
                response.phase = "qa" # Transition phase
                
                # Extract the JSON part
                json_match = re.search(r"<JSON>(.*?)</JSON>", assistant_msg_content, re.DOTALL | re.IGNORECASE)
                final_message_match = re.search(r"</JSON>\s*(.*)", assistant_msg_content, re.DOTALL | re.IGNORECASE)
                
                if json_match:
                    try:
                        extracted_json_str = json_match.group(1).strip()
                        extracted_user_info = json.loads(extracted_json_str)
                        # Validate and update user_info Pydantic model
                        response.user_info = UserInfo(**extracted_user_info)
                        logger.info("Successfully extracted and updated user info from JSON block.")
                    except Exception as json_e:
                        logger.error(f"Failed to parse JSON from intake response: {json_e}")
                        # Keep existing user info, maybe return error message?
                        response.assistant_response = "I seem to have trouble confirming your details. Could you please summarize them for me?"
                else:
                     logger.warning("Could not find <JSON> block after <INFO_COLLECTED> signal.")
                     # Fallback or ask user to confirm manually?
                     response.assistant_response = "I think I have all your details, but couldn't fully confirm. Can we proceed to your questions?"

                # Extract the final confirmation sentence
                if final_message_match:
                    response.assistant_response = final_message_match.group(1).strip()
                else:
                    # Fallback if final message not found after JSON
                     response.assistant_response = "Great, I have all your details. How can I help you today?" 
                
            else:
                # Just a normal intake question/response
                response.assistant_response = assistant_msg_content
                # Keep phase as "intake", user_info likely not updated by LLM in this turn

        except Exception as e:
            logger.error(f"Error during intake phase processing: {e}", exc_info=True)
            response.error = "An error occurred while processing your request during intake."
            response.assistant_response = "Sorry, I encountered a problem. Let's try that again." 

    elif request.phase == "qa":
        try:
            # 1. Retrieve relevant chunks
            logger.info(f"Searching index for query: {request.message}")
            retrieved_chunks_data = search_index(request.message, k=4)
            
            # *** ADD METADATA TO RESPONSE ***
            response.retrieved_context_metadata = retrieved_chunks_data 
            # ********************************
            
            retrieved_context = "\n\n".join([
                f"Source: {chunk['source']}\nContent: {chunk['text']}"
                for chunk in retrieved_chunks_data
            ])
            if not retrieved_context:
                 retrieved_context = "No relevant information found in the knowledge base."
            logger.info(f"Retrieved {len(retrieved_chunks_data)} chunks.")

            # 2. Construct prompt
            history_str = format_chat_history(trimmed_history)
            prompt = QA_SYSTEM_PROMPT.format(
                hmo_name=request.user_info.hmo_name or "Not Specified",
                membership_tier=request.user_info.membership_tier or "Not Specified",
                language=detected_lang,
                retrieved_chunks=retrieved_context,
                chat_history=history_str,
                user_question=request.message
            )

            # 3. Call LLM
            logger.info("Calling OpenAI for QA phase...")
            messages = [
                 {"role": "system", "content": prompt},
                 # Optionally add history messages here too if needed for better context
                 # *[{ "role": msg.role, "content": msg.content } for msg in trimmed_history], # Check token limits
                 {"role": "user", "content": request.message} 
            ]
            completion = aoaiclient.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                temperature=0.1, # More factual for Q&A
                max_tokens=1000 # Allow longer answers
            )
            response.assistant_response = completion.choices[0].message.content
            logger.info("OpenAI QA response received.")

        except Exception as e:
            logger.error(f"Error during QA phase processing: {e}", exc_info=True)
            response.error = "An error occurred while processing your question."
            response.assistant_response = "Sorry, I encountered a problem answering your question. Please try again." 
    
    else:
        logger.error(f"Unknown phase received: {request.phase}")
        response.error = "Invalid chat phase."
        response.assistant_response = "Sorry, something went wrong with our chat state. Please refresh and start again."

    return response 