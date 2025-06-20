from sqlalchemy import create_engine, MetaData, Table, select, update
import os

# Load DATABASE_URL from env or hardcode for this run
DATABASE_URL = os.getenv("DATABASE_URL", "your_database_url_here")

engine = create_engine(DATABASE_URL)
metadata = MetaData()
metadata.reflect(bind=engine)
splits = metadata.tables['splits']

with engine.connect() as conn:
    # Fetch rows where split is not null and not integer
    sel = select(splits).where(splits.c.split != None)
    results = conn.execute(sel).fetchall()

    print(f"Found {len(results)} rows. Attempting cast correction.")

    for row in results:
        split_val = row.split
        try:
            cast_val = int(split_val)
            upd = update(splits).where(splits.c.id == row.id).values(split=cast_val)
            conn.execute(upd)
        except (ValueError, TypeError):
            print(f"⚠️ Skipping row ID {row.id}: cannot cast split={split_val} to int.")

    conn.commit()
    print("✅ Split values casted to INTEGER where possible.")
