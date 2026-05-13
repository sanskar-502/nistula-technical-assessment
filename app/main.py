import asyncio
import os
import uuid
import json
import logging
from datetime import datetime
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
from anthropic import Anthropic, APIConnectionError, RateLimitError, APIError

from .database.local_dev_db import init_db, messages_table, engine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize DB safely on lifespan startup, not at import time
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        # Stop app cleanly if DB crashes
        raise RuntimeError("Database unavailable. Halting startup.")
    yield
    # Cleanup code can go here

app = FastAPI(title="Nistula Guest Message Handler", lifespan=lifespan)

# Initialize and validate Anthropic client safely
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key or "your_temporary_api_key_here" in api_key:
    logger.critical("CRITICAL: ANTHROPIC_API_KEY is missing or invalid in environment. System halted.")
    # Exit cleanly if critical integration is missing
    raise RuntimeError("Missing ANTHROPIC_API_KEY")

anthropic_client = Anthropic(api_key=api_key)

# Allowed strictly typed output for classification safety net
AllowedQueryType = Literal[
    "pre_sales_availability", 
    "pre_sales_pricing", 
    "post_sales_checkin", 
    "special_request", 
    "complaint", 
    "general_enquiry"
]

class WebhookPayload(BaseModel):
    source: Literal["whatsapp", "booking_com", "airbnb", "instagram", "direct"]
    guest_name: str
    message: str
    timestamp: datetime
    booking_ref: str | None = None
    property_id: str

class UnifiedMessage(BaseModel):
    message_id: str
    source: str
    guest_name: str
    message_text: str
    timestamp: str
    booking_ref: str | None = None
    property_id: str
    query_type: str

class WebhookResponse(BaseModel):
    message_id: str
    query_type: str
    drafted_reply: str
    confidence_score: float
    action: str

class AIResponseValidation(BaseModel):
    query_type: AllowedQueryType
    drafted_reply: str
    confidence_score: float = Field(ge=0.0, le=1.0)

# Mock Context
MOCK_PROPERTY_CONTEXT = """
Property: Villa B1, Assagao, North Goa
Bedrooms: 3 | Max guests: 6 | Private pool: Yes
Check-in: 2pm | Check-out: 11am
Base rate: INR 18,000 per night (up to 4 guests)
Extra guest: INR 2,000 per night per person
WiFi password: Nistula@2024
Caretaker: Available 8am to 10pm
Chef on call: Yes, pre-booking required
Availability April 20-24: Available
Cancellation: Free up to 7 days before check-in
"""

def determine_action(score: float, query_type: str) -> str:
    if query_type == "complaint" or score < 0.60:
        return "escalate"
    elif score >= 0.85:
        return "auto_send"
    else:
        return "agent_review"
        
def mock_db_save(unified_message: UnifiedMessage, confidence_score: float, action_taken: str):
    """
    Simulates persisting the normalized schema into the database.
    Actually executing the INSERT using SQLAlchemy to local SQLite.
    """
    with engine.connect() as conn:
        ins = messages_table.insert().values(
            message_id=unified_message.message_id,
            source_channel=unified_message.source,
            guest_name=unified_message.guest_name,
            message_text=unified_message.message_text,
            booking_ref=unified_message.booking_ref,
            property_id=unified_message.property_id,
            query_type=unified_message.query_type,
            confidence_score=confidence_score,
            action_taken=action_taken,
            channel_timestamp=datetime.fromisoformat(unified_message.timestamp)
        )
        conn.execute(ins)
        conn.commit()
    logger.info(f"==> 💾 PERSISTED UNIFIED SCHEMA to DB for message_id: {unified_message.message_id}")

@app.post("/webhook/message", response_model=WebhookResponse)
async def handle_message(payload: WebhookPayload):
    try:
        message_id = str(uuid.uuid4())
        
        system_prompt = f"""
You are an expert hospitality assistant for Nistula premium properties.
Analyze the guest's message, classify the query type strictly from the allowed list, draft a polite reply based *only* on the property context, and assign a confidence score (0.0 to 1.0).

Property Context:
{MOCK_PROPERTY_CONTEXT}

Allowed Query Types:
- pre_sales_availability
- pre_sales_pricing
- post_sales_checkin
- special_request
- complaint
- general_enquiry

If the context fully answers the query, confidence_score should be high (0.85-1.0).
If the guest asks about something NOT in the context (like pets, parking, etc.), you MUST score it below 0.84.
If answering requires info not in context, score low (<0.5).

Respond ONLY with valid JSON strictly matching this structure:
{{
  "query_type": "...",
  "drafted_reply": "Your drafted text here, addressing the guest by name",
  "confidence_score": 0.95
}}
"""
        user_prompt = f"Guest Name: {payload.guest_name}\nMessage: {payload.message}"

        # Call Claude API with robust exception handling
        try:
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.0
            )
        except APIConnectionError as e:
            logger.error(f"Anthropic connection failed: {e}")
            raise HTTPException(status_code=503, detail="AI Service is currently unreachable.")
        except RateLimitError as e:
            logger.error(f"Anthropic rate limit exceeded: {e}")
            raise HTTPException(status_code=429, detail="Too many requests to AI Service.")
        except APIError as e:
            logger.error(f"Anthropic API Error: {e}")
            raise HTTPException(status_code=500, detail="Internal AI Integration Error.")
        
        # Parse output safely
        raw_text = response.content[0].text.strip()
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            raw_text = raw_text[start_idx:end_idx+1]
            
        try:
            ai_data = json.loads(raw_text)
            # Pydantic safety net validation against the LLM's hallucination
            validated_ai = AIResponseValidation(**ai_data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"LLM hallucinated invalid schema or data: {e}")
            
            error_query_type = "general_enquiry"
            fallback_reply = "Thank you for reaching out. Our team is currently reviewing your message and will assist you shortly."
            
            if "complaint" in payload.message.lower() or "not working" in payload.message.lower() or "unacceptable" in payload.message.lower():
                error_query_type = "complaint"
                fallback_reply = "I sincerely apologize for the inconvenience. I have escalated this issue immediately, and our priority support team will contact you shortly."
                
            validated_ai = AIResponseValidation(
                query_type=error_query_type,
                drafted_reply=fallback_reply,
                confidence_score=0.0
            )

        # Build unified schema mapping
        unified_message = UnifiedMessage(
            message_id=message_id,
            source=payload.source,
            guest_name=payload.guest_name,
            message_text=payload.message,
            timestamp=payload.timestamp.isoformat(),
            booking_ref=payload.booking_ref,
            property_id=payload.property_id,
            query_type=validated_ai.query_type
        )
        
        action = determine_action(validated_ai.confidence_score, validated_ai.query_type)
        
        # Real persistence, offloaded to thread to prevent async loop blocking
        await asyncio.to_thread(mock_db_save, unified_message, validated_ai.confidence_score, action)
        
        return WebhookResponse(
            message_id=message_id,
            query_type=validated_ai.query_type,
            drafted_reply=validated_ai.drafted_reply,
            confidence_score=validated_ai.confidence_score,
            action=action
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected internal error occurred.")
