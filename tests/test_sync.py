import pytest

# ✅ This test uses normal (unpatched) client fixture
@pytest.mark.parametrize(
    "key,code",
    [
        ("wrong", 401),
        ("devkey123", 401),  # valid key but no tokens exist → causes sync_recent to fail
    ],
)
def test_sync_auth_and_error(client, key, code):
    resp = client.get(f"/sync-strava-to-db/123?key={key}")
    # ✅ If key is wrong → 401
    # ✅ If key is correct but no tokens → will raise error and return 500
    expected_code = 401 if key == "wrong" else 500
    assert resp.status_code == expected_code


# ✅ This test uses patched_client to mock sync_recent successfully
def test_sync_success(patched_client):
    resp = patched_client.get("/sync-strava-to-db/123?key=devkey123")
    assert resp.status_code == 200
    assert resp.get_json() == {"inserted": 10}
