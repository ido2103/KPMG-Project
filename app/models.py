from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# --- User Information Model ---

# Define allowed HMO names and Tiers using Enums or Literals later if needed
ALLOWED_HMOS = ["מכבי", "מאוחדת", "כללית", "Maccabi", "Meuhedet", "Clalit"]
ALLOWED_TIERS = ["זהב", "כסף", "ארד", "Gold", "Silver", "Bronze"]

class UserInfo(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    id_number: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    hmo_name: Optional[str] = None # Should match ALLOWED_HMOS
    hmo_card_number: Optional[str] = None
    membership_tier: Optional[str] = None # Should match ALLOWED_TIERS
    language: Optional[str] = "en" # Default language

    # Add validators later for id_number, age, hmo_name, hmo_card_number, membership_tier

# --- Chat History Model ---

class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

# --- API Request/Response Models ---

class ChatRequest(BaseModel):
    user_info: UserInfo = Field(default_factory=UserInfo) # Current user details
    phase: str = "intake" # "intake", "qa"
    chat_history: List[ChatMessage] = [] # Previous turns
    message: str # Current user message

class ChatResponse(BaseModel):
    assistant_response: str # The chatbot's reply
    user_info: Optional[UserInfo] = None # Updated user info (relevant during intake)
    phase: Optional[str] = None # Potentially updated phase ("qa" after intake)
    retrieved_context_metadata: Optional[List[Dict[str, Any]]] = None # Add field for context metadata
    error: Optional[str] = None # To signal errors to the frontend 