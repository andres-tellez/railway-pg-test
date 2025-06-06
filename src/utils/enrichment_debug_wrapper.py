# src/utils/enrichment_debug_wrapper.py

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class EnrichmentDebugWrapper:
    def __init__(self, enrichor, session: Session):
        self.enrichor = enrichor
        self.session = session

    def enrich(self, athlete_id, activities=None, batch_size=None):
        logger.info("🟡 Starting enrichment with debug wrapper")

        # Dynamically handle enrichment method signature
        if activities is not None:
            enriched_count = self.enrichor.enrich(athlete_id=athlete_id, activities=activities, session=self.session)
        else:
            enriched_count = self.enrichor.enrich(athlete_id=athlete_id, batch_size=batch_size, session=self.session)

        # ORM state introspection after enrichment but before commit
        new_objects = list(self.session.new)
        dirty_objects = list(self.session.dirty)
        deleted_objects = list(self.session.deleted)

        logger.info("🟡 ORM session state after enrichment:")
        logger.info(f"    New objects pending commit: {len(new_objects)}")
        logger.info(f"    Dirty objects pending commit: {len(dirty_objects)}")
        logger.info(f"    Deleted objects pending commit: {len(deleted_objects)}")

        for obj in new_objects:
            logger.info(f"    New: {obj}")

        # Specifically track Split objects
        splits = [obj for obj in new_objects if obj.__class__.__name__.lower() == 'split']
        logger.info(f"    Detected {len(splits)} Split objects staged for commit")

        # Commit changes
        logger.info("🟡 Performing commit...")
        self.session.commit()
        logger.info("🟢 Commit successful")

        return enriched_count
