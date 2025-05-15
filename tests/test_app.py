def test_ping(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.data == b"pong"

def test_init_db(client, monkeypatch):
    # Monkey-patch init_db so it doesn’t run real SQL
    called = {}
    def fake_init_db(url):
        called['url'] = url

    monkeypatch.setattr("src.app.init_db", fake_init_db)
    resp = client.get("/init-db")
    assert resp.status_code == 200
    assert b"Database initialized" in resp.data
    assert called['url'] == client.application.config["DATABASE_URL"]
