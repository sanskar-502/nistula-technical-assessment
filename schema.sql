-- Nistula Backend PostgreSQL Schema

-- 1. Guest Profiles: one record per guest across all channels
CREATE TABLE guests (
    guest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    -- Store unified contact info extracted or deduced
    phone_number VARCHAR(50),
    email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Guest Channel Identities (To handle mapping channels like WhatsApp, AirBnb to a unified guest)
CREATE TABLE guest_channel_identities (
    identity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id UUID REFERENCES guests(guest_id) ON DELETE CASCADE,
    channel_name VARCHAR(50) NOT NULL, -- e.g., 'whatsapp', 'airbnb'
    channel_user_id VARCHAR(255) NOT NULL, -- The ID the channel uses
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_name, channel_user_id)
);

-- 2. Reservations/Bookings
CREATE TABLE reservations (
    reservation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id UUID REFERENCES guests(guest_id) ON DELETE CASCADE,
    booking_ref VARCHAR(100) UNIQUE NOT NULL, -- e.g. NIS-2024-0891
    property_id VARCHAR(100) NOT NULL,
    check_in_date DATE,
    check_out_date DATE,
    status VARCHAR(50) DEFAULT 'confirmed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Conversations (Linked to guest and reservation)
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id UUID REFERENCES guests(guest_id) ON DELETE CASCADE,
    reservation_id UUID REFERENCES reservations(reservation_id) ON DELETE SET NULL, -- Optional if not regarding a specific reservation
    property_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'open', -- 'open', 'resolved', 'escalated'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4 & 5. Messages (Unified schema, tracking AI drafting & scoring)
CREATE TABLE messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    source_channel VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    message_text TEXT NOT NULL,
    
    -- AI metadata
    query_type VARCHAR(100),            -- pre_sales_availability, etc.
    confidence_score NUMERIC(3, 2),     -- 0.00 to 1.00
    
    -- Processing metadata
    processing_status VARCHAR(50) CHECK (processing_status IN ('pending', 'ai_drafted', 'agent_edited', 'auto_sent', 'sent')),
    drafted_reply TEXT,
    action_taken VARCHAR(50) CHECK (action_taken IN ('auto_send', 'agent_review', 'escalate')),
    
    -- Timestamps
    channel_timestamp TIMESTAMP WITH TIME ZONE NOT NULL, -- When the message occurred on the channel
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Indexes for Performance (Scaling the inbox)
CREATE INDEX idx_guest_identities_guest ON guest_channel_identities(guest_id);
CREATE INDEX idx_reservations_guest ON reservations(guest_id);
CREATE INDEX idx_conversations_guest ON conversations(guest_id);
CREATE INDEX idx_conversations_res ON conversations(reservation_id);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);

/*
DESIGN DECISIONS:
- Separate Guest Channel Identities: We might have guests booking via Airbnb today and returning via WhatsApp tomorrow. 
  Having a `guest_channel_identities` table allows us to link multiple external identity descriptors to our single robust generic `guests` row.
- Normalised Conversations: Linking messages back to conversations allows chunking interactions for agents rather than disparate message streams.

HARDEST DESIGN DECISION:
The hardest structural decision was figuring out how to neatly associate messages with reservations. A guest could message us without a reservation, or about a past, pre-existing, or future reservation. I solved this by treating the conversation table as an intermediary that optionally links to a reservation (`reservation_id` can be NULL). The inbound message contains the booking_ref, so when normalising the message payload, the backend resolves the conversational context dynamically before inserting the message into the `messages` table. This keeps `messages` cleanly focused on payload metadata and AI processing variables.
*/