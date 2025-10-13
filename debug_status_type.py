#!/usr/bin/env python3
"""Debug what type the status field is"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.db.db_session import get_session
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus

def debug_status():
    """Check what type the status field actually is"""
    
    session = get_session()
    
    try:
        # Get a pending event
        event = session.query(WebhookEvent).filter(
            WebhookEvent.status == WebhookEventStatus.PENDING.value
        ).first()
        
        if event:
            print(f"Event ID: {event.id}")
            print(f"Status value: {event.status}")
            print(f"Status type: {type(event.status)}")
            print(f"Status repr: {repr(event.status)}")
            print()
            print(f"WebhookEventStatus.PENDING = {WebhookEventStatus.PENDING}")
            print(f"WebhookEventStatus.PENDING.value = {WebhookEventStatus.PENDING.value}")
            print()
            print(f"event.status == WebhookEventStatus.PENDING: {event.status == WebhookEventStatus.PENDING}")
            print(f"event.status == WebhookEventStatus.PENDING.value: {event.status == WebhookEventStatus.PENDING.value}")
            print(f"event.status == 'PENDING': {event.status == 'PENDING'}")
        else:
            print("No pending events found")
        
    finally:
        session.close()

if __name__ == "__main__":
    debug_status()

