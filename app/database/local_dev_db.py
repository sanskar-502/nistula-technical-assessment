from sqlalchemy import create_engine, Column, String, Float, DateTime, MetaData, Table

# ==============================================================================
# MOCK DATABASE FOR LOCAL TESTING ONLY
# ==============================================================================
# As requested in Part 2, the actual schema is designed for PostgreSQL (see schema.sql).
# This minimal SQLite mock strictly exists to allow end-to-end execution of the 
# webhook prototype locally without requiring the reviewer to spin up a Docker 
# PostgreSQL instance. 

DATABASE_URL = "sqlite:///./nistula_dev_mock.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata = MetaData()

# Mimicking Part 2's structure (Messages table only for webhook POC validation)
messages_table = Table(
    "messages", metadata,
    Column("message_id", String, primary_key=True, index=True),
    Column("source_channel", String, nullable=False),
    Column("guest_name", String, nullable=False),
    Column("message_text", String, nullable=False),
    Column("booking_ref", String, nullable=True),
    Column("property_id", String, nullable=True),
    Column("query_type", String, nullable=True),
    Column("confidence_score", Float, nullable=True),
    Column("action_taken", String, nullable=True),
    Column("channel_timestamp", DateTime, nullable=False) # Properly using DateTime
)

def init_db():
    metadata.create_all(bind=engine)
