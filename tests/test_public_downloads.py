def test_public_downloads(client):
    resp = client.get("/downloads/macro")
    assert resp.status_code == 200
    disp = resp.headers.get("Content-Disposition", "")
    assert "attachment" in disp.lower()

    resp = client.get("/downloads/addin")
    assert resp.status_code == 200
    disp = resp.headers.get("Content-Disposition", "")
    assert "attachment" in disp.lower()
