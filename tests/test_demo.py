import json

import pytest

from app.demo import ASSETS, CASES


def test_demo_page_and_assets_are_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Run your case" in response.text
    assert "no-cache" in response.headers["cache-control"]
    for path in ("/static/demo.js", "/static/demo.css"):
        assert client.get(path).status_code == 200


def test_demo_examples_match_original_fixtures(client):
    cases = client.get("/demo/cases").json()
    assert [case["name"] for case in cases] == ["Success 1", "Failure 2", "Failure 1"]
    assert [case["expected"] for case in cases] == ["approved", "rejected", "rejected"]
    for case in cases:
        path = ASSETS / CASES[case["id"]][0]
        payload = json.loads((path / "request.json").read_text())
        assert case["title"] == payload["title"]
        assert case["description"] == payload["description"]
        assert "images" not in case
        response = client.get(f"/demo/cases/{case['id']}/request")
        assert response.json() == payload
        image = client.get("/" + case["image"])
        assert image.headers["content-type"] == "image/jpeg"
        assert image.content == (path / "image.jpg").read_bytes()


def test_demo_failure_can_be_submitted_to_real_verifier(client):
    payload = client.get("/demo/cases/failure-1/request").json()
    response = client.post("/products/verify", json=payload)
    assert response.status_code == 200
    assert response.json() == {
        "status": "rejected",
        "comments": ["Description contains a swear word: shit."],
    }


@pytest.mark.parametrize("path", ["request", "image"])
@pytest.mark.parametrize("case_id", ["unknown", ".env", "..%2F..%2F.env"])
def test_demo_only_serves_allowlisted_cases(client, path, case_id):
    assert client.get(f"/demo/cases/{case_id}/{path}").status_code == 404
