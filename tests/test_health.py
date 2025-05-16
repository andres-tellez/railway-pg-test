# tests/test_health.py
def test_ping(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.data == b"pong"
