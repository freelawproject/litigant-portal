from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Response

FLOW_PATHS = [
    "/t/north-dakota/adult-name-change/standard/",
    "/t/north-dakota/adult-name-change/waiver/",
    "/t/franklin-county-oh/eviction/tenant/",
    "/t/franklin-county-oh/eviction/landlord/",
    "/t/arizona/civil-traffic/options/",
]
PAGE_PATHS = ["/", "/chat/", *FLOW_PATHS, "/accounts/login/"]
HEALTH_PATH = "/api/health/"
ASSET_RESOURCE_TYPES = {"stylesheet", "script"}
UNSYNCED_COURT_HINT = (
    "The smoke suite needs every court synced. Is CORPUS_COURT set in "
    ".env? With it set, sync_corpus imports only that court."
)


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_page_loads(page: Page, path: str) -> None:
    asset_responses = record_asset_responses(page)
    response = page.goto(path)
    check_document_response(response, path)
    check_main_present(page, path)
    check_same_origin_assets(asset_responses, page.url, path)


def test_health_ok(page: Page) -> None:
    response = page.goto(HEALTH_PATH)
    assert response is not None, f"{HEALTH_PATH}: no document response"
    assert response.status == 200, (
        f"{HEALTH_PATH} returned {response.status}: {response.text()}"
    )


def record_asset_responses(page: Page) -> list[Response]:
    asset_responses: list[Response] = []

    def record(response: Response) -> None:
        if response.request.resource_type in ASSET_RESOURCE_TYPES:
            asset_responses.append(response)

    page.on("response", record)
    return asset_responses


def check_document_response(response: Response | None, path: str) -> None:
    assert response is not None, f"{path}: no document response"
    assert response.request.redirected_from is None, (
        f"{path} redirected to {response.url}"
    )
    if response.status == 404 and path in FLOW_PATHS:
        pytest.fail(f"{path} returned 404. {UNSYNCED_COURT_HINT}")
    assert response.status == 200, f"{path} returned {response.status}"


def check_main_present(page: Page, path: str) -> None:
    assert page.locator("main").count() > 0, f"{path} has no <main> element"


def check_same_origin_assets(
    asset_responses: list[Response], page_url: str, path: str
) -> None:
    page_origin = parse_origin(page_url)
    same_origin_assets = [
        response
        for response in asset_responses
        if parse_origin(response.url) == page_origin
    ]
    # An empty list would pass the status check below without testing it.
    assert same_origin_assets, f"{path} loaded no same-origin CSS or JS"
    failed_assets = [
        f"{response.status} {response.url}"
        for response in same_origin_assets
        if response.status >= 400
    ]
    assert not failed_assets, f"{path} has failed assets: {failed_assets}"


def parse_origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
