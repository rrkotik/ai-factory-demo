import pytest


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": " ", "description": "A shirt", "images": ["abc"]},
        {"title": "x" * 201, "description": "A shirt", "images": ["abc"]},
        {"title": "Shirt", "description": "x" * 4001, "images": ["abc"]},
        {"title": "Shirt", "description": "A shirt", "images": []},
        {"title": "Shirt", "description": "A shirt", "images": ["abc"] * 21},
    ],
)
def test_product_request_limits(client, payload):
    assert client.post("/products/verify", json=payload).status_code == 422


def test_product_deterministic_rejection_has_comments(client):
    response = client.post(
        "/products/verify",
        json={"title": "COCAINE", "description": "Shit!", "images": ["%%%"]},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "rejected"
    comments = " ".join(result["comments"]).lower()
    assert "title" in comments and "cocaine" in comments
    assert "description" in comments and "shit" in comments
    assert "image 1" in comments and "base64" in comments


@pytest.mark.parametrize("field,value", [("title", "!!!"), ("description", "bad\x00text")])
def test_product_sanity_rejects_without_openai(client, field, value):
    from tests.product_helpers import product_payload

    result = client.post("/products/verify", json=product_payload(**{field: value})).json()
    assert result["status"] == "rejected"
    assert any(field in comment.lower() for comment in result["comments"])


@pytest.mark.parametrize(
    "image_options,reason",
    [
        ({"size": (255, 256)}, "dimensions"),
        ({"size": (4097, 256)}, "dimensions"),
        ({"format": "GIF"}, "format"),
        ({"color": "black"}, "dark"),
        ({"color": "white"}, "bright"),
        ({"color": "gray"}, "detail"),
    ],
)
def test_product_image_checks(client, image_options, reason):
    from tests.product_helpers import image_base64, product_payload

    response = client.post(
        "/products/verify", json=product_payload(images=[image_base64(**image_options)])
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "rejected"
    assert any("Image 1" in c and reason in c.lower() for c in result["comments"])


def test_valid_product_without_reviewer_returns_503(client):
    from tests.product_helpers import product_payload

    response = client.post("/products/verify", json=product_payload())
    assert response.status_code == 503
    assert response.json() == {"detail": "A required service is unavailable. Retry the request."}


@pytest.mark.parametrize(
    "format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_supported_images_reach_required_ai_review(client, format, mime):
    from tests.product_helpers import image_base64, product_payload

    image = image_base64(format=format)
    for value in (image, f"data:{mime};base64,{image}"):
        response = client.post("/products/verify", json=product_payload(images=[value]))
        assert response.status_code == 503  # Local checks passed, but no reviewer is configured.


@pytest.mark.parametrize("title", ["Shitake mushroom", "Classical shirt", "東京のシャツ"])
def test_text_checks_do_not_reject_substrings_or_non_english_letters(client, title):
    from tests.product_helpers import product_payload

    assert client.post("/products/verify", json=product_payload(title=title)).status_code == 503


def test_unicode_normalization_catches_fullwidth_restricted_word(client):
    from tests.product_helpers import product_payload

    result = client.post("/products/verify", json=product_payload(title="ＣＯＣＡＩＮＥ")).json()
    assert result["status"] == "rejected"
    assert any("cocaine" in comment for comment in result["comments"])


@pytest.mark.parametrize(
    "kind", ["mime_mismatch", "corrupt", "not_an_image", "animated", "too_large"]
)
def test_invalid_image_content_is_rejected(client, kind):
    import base64
    from io import BytesIO

    from PIL import Image

    from tests.product_helpers import image_base64, product_payload

    value = image_base64()
    if kind == "mime_mismatch":
        value = f"data:image/jpeg;base64,{value}"
    elif kind == "corrupt":
        value = base64.b64encode(base64.b64decode(value)[:60]).decode()
    elif kind == "not_an_image":
        value = base64.b64encode(b"not an image").decode()
    elif kind == "animated":
        output = BytesIO()
        Image.new("RGB", (256, 256), "red").save(
            output,
            format="PNG",
            save_all=True,
            append_images=[Image.new("RGB", (256, 256), "blue")],
            duration=100,
        )
        value = base64.b64encode(output.getvalue()).decode()
    else:
        value = base64.b64encode(b"x" * (5 * 1024 * 1024 + 1)).decode()
    response = client.post("/products/verify", json=product_payload(images=[value]))
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert any("Image 1" in comment for comment in response.json()["comments"])


def test_total_decoded_image_limit(client):
    import base64

    from tests.product_helpers import image_base64, product_payload

    # A valid PNG padded to exactly 5 MiB exercises byte limits without huge pixels.
    data = base64.b64decode(image_base64())
    padded = base64.b64encode(data + b"\0" * (5 * 1024 * 1024 - len(data))).decode()
    assert (
        client.post("/products/verify", json=product_payload(images=[padded] * 4)).status_code
        == 503
    )
    # Use the verifier directly: the HTTP envelope has a separate, tighter bound.
    from app.product_verification import ProductVerifier
    from app.schemas import ProductInput

    result = ProductVerifier().verify(ProductInput(**product_payload(images=[padded] * 5)))
    assert result.status == "rejected"
    assert any("20 MiB" in comment for comment in result.comments)


def test_oversized_product_body_is_rejected_before_json_parsing(client):
    response = client.post(
        "/products/verify",
        content=b" " * (32 * 1024 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Product request body must be at most 32 MiB."}


def test_product_validation_errors_do_not_echo_image_data(client):
    payload = {"title": "Shirt", "description": "A shirt", "images": ["private-image-data"] * 21}
    response = client.post("/products/verify", json=payload)
    assert response.status_code == 422
    assert "private-image-data" not in response.text
