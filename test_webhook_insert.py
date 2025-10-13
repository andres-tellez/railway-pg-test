#!/usr/bin/env python3
"""Test webhook event insertion to verify enum values work"""

import os
import sys
from sqlalchemy.orm import Session

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.db.db_session import get_session
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus

def test_webhook_insert():
    """Test inserting a webhook event with the new enum values"""
    
    session = get_session()
    
    try:
        # Create a test webhook event (similar to what Strava sends)
        test_event = WebhookEvent(
            object_type="activity",
            object_id=12345678901,  # Large ID to test BigInteger
            aspect_type="create",
            owner_id=347085,  # Your athlete ID
            subscription_id=309430,
            event_time=1760374604,
            updates={},
            status=WebhookEventStatus.PENDING.value,  # Using .value like in production
        )
        
        print("📝 Creating test webhook event...")
        print(f"   Status value: {WebhookEventStatus.PENDING.value}")
        print(f"   Object ID: {test_event.object_id} (BigInteger test)")
        
        session.add(test_event)
        session.commit()
        
        event_id = test_event.id
        print(f"✅ SUCCESS! Event inserted with ID: {event_id}")
        
        # Verify we can read it back
        retrieved = session.query(WebhookEvent).filter_by(id=event_id).first()
        if retrieved:
            print(f"✅ Event retrieved successfully!")
            print(f"   Status: {retrieved.status}")
            print(f"   Object ID: {retrieved.object_id}")
            print(f"   Received at: {retrieved.received_at}")
            
            # Clean up test data
            session.delete(retrieved)
            session.commit()
            print(f"🧹 Test event cleaned up")
            
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        session.rollback()
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    success = test_webhook_insert()
    sys.exit(0 if success else 1)

