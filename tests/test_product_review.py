import json
from threading import Barrier, Lock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from app.main import create_app
from app.product_review import OpenAIProductReviewer
from app.product_verification import ProductVerifier
from tests.product_helpers import image_base64, product_payload

CHECKS = ("image_safety", "text_safety", "title_description_alignment", "image_text_relevance")


def request_kind(body):
    content = body["input"][0]["content"]
    types = {part["type"] for part in content}
    if types == {"input_image"}:
        return "image_safety"
    if types == {"input_text"}:
        return "text"
    assert types == {"input_text", "input_image"}
    return "image_text_relevance"


def review_response(kind, failed=None, image_count=2):
    def check(name):
        return {"passed": name != failed, "comment": f"{name} failed." if name == failed else ""}

    if kind == "text":
        return {name: check(name) for name in ("text_safety", "title_description_alignment")}
    return {
        "images": [
            {"image_index": index, **check(kind if index == image_count else "passed")}
            for index in range(1, image_count + 1)
        ]
    }


def sdk_response(review):
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "model": "gpt-6-sol",
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps(review), "annotations": []}],
            }
        ],
    }


@pytest.mark.parametrize("failed", [None, *CHECKS])
def test_three_parallel_isolated_reviews_drive_final_verdict(service, failed):
    barrier = Barrier(3, timeout=10)
    lock = Lock()
    seen = []
    images = [image_base64(), image_base64(format="JPEG")]

    def handle(request):
        assert request.url.path == "/v1/responses"
        body = json.loads(request.content)
        kind = request_kind(body)
        with lock:
            seen.append(kind)
        assert body["store"] is False
        assert body["model"] == "gpt-6-sol"
        assert body["reasoning"] == {"effort": "low"}
        assert body["text"]["format"]["strict"] is True
        content = body["input"][0]["content"]
        if kind != "image_safety":
            assert json.loads(content[0]["text"]) == {
                "title": "Shirt",
                "description": "A cotton shirt",
            }
        if kind != "text":
            assert [part["image_url"] for part in content if part["type"] == "input_image"] == [
                f"data:image/png;base64,{images[0]}",
                f"data:image/jpeg;base64,{images[1]}",
            ]
        # All three HTTP calls must be in flight before ANY can return: catches
        # sequential calls without fragile wall-clock timing assertions.
        barrier.wait()
        return httpx.Response(200, json=sdk_response(review_response(kind, failed)))

    with OpenAI(
        api_key="test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    ) as sdk:
        verifier = ProductVerifier(OpenAIProductReviewer(sdk, "gpt-6-sol", "low"))
        with TestClient(create_app(service=service, verifier=verifier)) as client:
            response = client.post(
                "/products/verify", json=product_payload(title="  Shirt  ", images=images)
            )
    assert sorted(seen) == ["image_safety", "image_text_relevance", "text"]
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == ("rejected" if failed else "approved")
    assert len(result["comments"]) == (1 if failed else 0)
    if failed:
        assert f"{failed} failed." in result["comments"][0]
        if failed in ("image_safety", "image_text_relevance"):
            assert "Image 2" in result["comments"][0]


@pytest.mark.parametrize("failed_kind", ["image_safety", "text", "image_text_relevance"])
@pytest.mark.parametrize(
    "mode",
    [
        "error",
        "invalid_json",
        "missing_check",
        "no_reason",
        "refusal",
        "incomplete",
        "null_output",
        "missing_output",
        "null_content",
        "wrong_envelope_type",
    ],
)
def test_failure_of_any_parallel_review_returns_generic_503(service, failed_kind, mode):
    def handle(request):
        kind = request_kind(json.loads(request.content))
        review = review_response(kind, image_count=1)
        body = sdk_response(review)
        if kind != failed_kind:
            return httpx.Response(200, json=body)
        if mode == "error":
            return httpx.Response(429, json={"error": {"message": "secret-vendor-error"}})
        if mode == "missing_check":
            review.clear()
            body = sdk_response(review)
        if mode == "no_reason":
            check = review["text_safety"] if kind == "text" else review["images"][0]
            check.update(passed=False, comment=" ")
            body = sdk_response(review)
        if mode == "invalid_json":
            body["output"][0]["content"][0]["text"] = "not JSON"
        if mode == "refusal":
            body["output"][0]["content"] = [{"type": "refusal", "refusal": "Cannot review"}]
        if mode == "incomplete":
            body["status"] = "incomplete"
        if mode == "null_output":
            body["output"] = None
        if mode == "missing_output":
            del body["output"]
        if mode == "null_content":
            body["output"][0]["content"] = None
        if mode == "wrong_envelope_type":
            body = "unexpected response"
        return httpx.Response(200, json=body)

    with OpenAI(
        api_key="test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    ) as sdk:
        verifier = ProductVerifier(OpenAIProductReviewer(sdk, "gpt-6-sol", "low"))
        with TestClient(create_app(service=service, verifier=verifier)) as client:
            response = client.post("/products/verify", json=product_payload())
    assert response.status_code == 503
    assert response.json() == {"detail": "A required service is unavailable. Retry the request."}


@pytest.mark.parametrize("kind", ["image_safety", "image_text_relevance"])
@pytest.mark.parametrize("indices", [[1], [1, 1], [1, 3], [2, 1], [1, 2, 3]])
def test_every_image_must_be_reviewed_exactly_once(service, kind, indices):
    def handle(request):
        current = request_kind(json.loads(request.content))
        review = review_response(current)
        if current == kind:
            review["images"] = [{"image_index": i, "passed": True, "comment": ""} for i in indices]
        return httpx.Response(200, json=sdk_response(review))

    with OpenAI(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handle))
    ) as sdk:
        verifier = ProductVerifier(OpenAIProductReviewer(sdk, "gpt-6-sol", "low"))
        with TestClient(create_app(service=service, verifier=verifier)) as client:
            response = client.post(
                "/products/verify", json=product_payload(images=[image_base64()] * 2)
            )
    assert response.status_code == (200 if indices == [2, 1] else 503)
    if indices == [2, 1]:
        assert response.json() == {"status": "approved", "comments": []}


def test_rejections_are_aggregated_in_stable_order(service):
    def handle(request):
        kind = request_kind(json.loads(request.content))
        review = review_response(kind, image_count=1)
        checks = list(review.values()) if kind == "text" else review["images"]
        for check in checks:
            check.update(passed=False, comment=f"{kind} rejected.")
        return httpx.Response(200, json=sdk_response(review))

    with OpenAI(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handle))
    ) as sdk:
        verifier = ProductVerifier(OpenAIProductReviewer(sdk, "gpt-6-sol", "low"))
        with TestClient(create_app(service=service, verifier=verifier)) as client:
            response = client.post("/products/verify", json=product_payload())
    result = response.json()
    assert response.status_code == 200 and result["status"] == "rejected"
    assert len(result["comments"]) == 4
    assert "image_safety rejected." in result["comments"][0]
    assert "text rejected." in result["comments"][1]
    assert "text rejected." in result["comments"][2]
    assert "image_text_relevance rejected." in result["comments"][3]


def test_deterministic_failure_never_calls_openai(service):
    def unexpected_call(request):
        pytest.fail("OpenAI must not be called after a deterministic rejection")

    with OpenAI(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(unexpected_call))
    ) as sdk:
        verifier = ProductVerifier(OpenAIProductReviewer(sdk, "gpt-6-sol", "low"))
        with TestClient(create_app(service=service, verifier=verifier)) as client:
            response = client.post("/products/verify", json=product_payload(title="Fuck!"))
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
