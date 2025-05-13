from db import get_conn

def delete_failed_activities():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM activities WHERE enriched_failed = TRUE;")
    count = cur.fetchone()[0]
    print(f"🧼 Deleting {count} failed activities...")

    cur.execute("DELETE FROM activities WHERE enriched_failed = TRUE;")
    conn.commit()
    conn.close()
    print("✅ Deleted.")

if __name__ == "__main__":
    delete_failed_activities()
