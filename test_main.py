import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Helper classes to mock Anthropic's response structure
class MockMessage:
    def __init__(self, text_content):
        self.text = text_content

class MockContent:
    def __init__(self, text_content):
        self.content = [MockMessage(text_content)]

@patch("app.main.anthropic_client.messages.create")
@patch("app.main.mock_db_save") # Mock DB so tests don't pollute local DB
def test_presales_availability_mocked(mock_db, mock_create):
    # 1. Force the mocked LLM to return an ideal response
    # Need to simulate the markdown wrappers Claude sometimes adds
    mock_create.return_value = MockContent(
        '```json\n{"query_type": "pre_sales_availability", "drafted_reply": "Yes, completely available.", "confidence_score": 0.95}\n```'
    )

    payload = {
        "source": "whatsapp",
        "guest_name": "Rahul Sharma",
        "message": "Is the villa available from April 20 to 24?",
        "timestamp": "2026-05-05T10:30:00Z",
        "booking_ref": "NIS-2024-0891",
        "property_id": "villa-b1"
    }
    
    response = client.post("/webhook/message", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "pre_sales_availability"
    assert data["confidence_score"] == 0.95
    assert data["action"] == "auto_send"
    
    mock_create.assert_called_once()
    mock_db.assert_called_once()

@patch("app.main.anthropic_client.messages.create")
@patch("app.main.mock_db_save")
def test_complaint_escalation_mocked(mock_db, mock_create):
    # Mocking an angry guest where the LLM correctly parses it as a complaint
    mock_create.return_value = MockContent(
        '{"query_type": "complaint", "drafted_reply": "I am so sorry about the AC.", "confidence_score": 0.70}'
    )

    payload = {
        "source": "airbnb",
        "guest_name": "Sara Smith",
        "message": "The AC is broken.",
        "timestamp": "2026-05-06T22:30:00Z",
        "booking_ref": "NIS-2024-0892",
        "property_id": "villa-b1"
    }
    
    response = client.post("/webhook/message", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Despite confidence being 0.70, it MUST be escalated due to query_type == complaint
    assert data["query_type"] == "complaint"
    assert data["action"] == "escalate"

@patch("app.main.anthropic_client.messages.create")
@patch("app.main.mock_db_save")
def test_llm_hallucination_fallback(mock_db, mock_create):
    # Simulate the LLM returning completely unparseable garbage instead of JSON
    mock_create.return_value = MockContent("I am an AI and I don't want to use JSON today.")

    payload = {
        "source": "instagram",
        "guest_name": "John Doe",
        "message": "What is the WiFi password?",
        "timestamp": "2026-05-07T14:15:00Z",
        "booking_ref": "NIS-2024-0893",
        "property_id": "villa-b1"
    }
    
    response = client.post("/webhook/message", json=payload)
    
    # API should survive, catch the JSONDecodeError, and trigger fallback
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "general_enquiry"
    assert data["confidence_score"] == 0.0
    assert data["action"] == "escalate"

def test_invalid_payload_schema():
    # Negative test: source "myspace" is not in the Literal schema
    payload = {
        "source": "myspace",
        "guest_name": "John Doe",
        "message": "Hello",
        "timestamp": "bad-date formatting",
        "property_id": "villa-b1"
    }
    
    response = client.post("/webhook/message", json=payload)
    assert response.status_code == 422 # Pydantic Unprocessable Entity constraint hit

