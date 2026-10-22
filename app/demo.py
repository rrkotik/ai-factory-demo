"""Browser demo backed by the same product requests used in the fixtures."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

STATIC = Path(__file__).parent / "static"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
CASES = {
    "success-1": ("success/1", "Success 1", "Matching listing", "approved"),
    "failure-2": ("fail/2", "Failure 2", "Image and text mismatch", "rejected"),
    "failure-1": ("fail/1", "Failure 1", "Restricted language", "rejected"),
}
router = APIRouter(include_in_schema=False)


def case_directory(case_id: str) -> Path:
    if case_id not in CASES:
        raise HTTPException(status_code=404, detail="Example not found")
    return ASSETS / CASES[case_id][0]


@router.get("/")
def demo_page() -> FileResponse:
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@router.get("/demo/cases")
def demo_cases() -> list[dict[str, str]]:
    cases = []
    for case_id, (directory, name, subtitle, expected) in CASES.items():
        payload = json.loads((ASSETS / directory / "request.json").read_text())
        cases.append(
            {
                "id": case_id,
                "name": name,
                "subtitle": subtitle,
                "expected": expected,
                "title": payload["title"],
                "description": payload["description"],
                "image": f"demo/cases/{case_id}/image",
            }
        )
    return cases


@router.get("/demo/cases/{case_id}/request")
def demo_request(case_id: str) -> FileResponse:
    return FileResponse(case_directory(case_id) / "request.json", media_type="application/json")


@router.get("/demo/cases/{case_id}/image")
def demo_image(case_id: str) -> FileResponse:
    return FileResponse(case_directory(case_id) / "image.jpg", media_type="image/jpeg")
