#!/usr/bin/env python3
"""Manually process pending webhook events"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.db.db_session import get_session
from src.services.webhook_processor import process_webhook_event
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus

def process_all_pending():
    """Process all pending webhook events"""
    
    session = get_session()
    
    try:
        # Get all pending events
        pending_events = session.query(WebhookEvent).filter(
            WebhookEvent.status == WebhookEventStatus.PENDING.value
        ).all()
        
        print(f"📋 Found {len(pending_events)} pending events\n")
        
        for event in pending_events:
            print(f"🔄 Processing event {event.id}: {event.object_type}.{event.aspect_type} (object_id={event.object_id})")
            
            try:
                # Refresh the event from DB to get latest status
                session.refresh(event)
                print(f"   Current status: {event.status}")
                
                success = process_webhook_event(session, event.id)
                
                # Refresh again to see new status
                session.refresh(event)
                print(f"   New status: {event.status}")
                
                if success:
                    print(f"   ✅ Success")
                else:
                    print(f"   ⚠️  Skipped or failed")
                    if event.error_message:
                        print(f"   Error message: {event.error_message}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
            
            print()
        
        print("✅ All pending events processed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        session.close()

if __name__ == "__main__":
    process_all_pending()

