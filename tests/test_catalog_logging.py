"""Catalog query/cursor/referrer access records cannot reach enabled log sinks."""

import logging
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from you_story.app import create_app


@pytest.mark.parametrize("logger_name", ["uvicorn.access", "httpx"])
def test_private_catalog_access_records_are_filtered_with_positive_capture(caplog, logger_name):
    app = create_app(readiness=lambda: True)
    logger = logging.getLogger(logger_name)
    # Uvicorn may disable propagation. Capture its actual record pipeline without
    # replacing installed filters or the existing handlers/configuration.
    logger.addHandler(caplog.handler)
    query = "private-catalog-name-author-log-canary"
    cursor = "private-catalog-cursor-log-canary"
    referer = "https://metadata.invalid/catalog?" + urlencode({"author": query, "cursor": cursor})
    try:
        with caplog.at_level(logging.INFO):
            logging.getLogger("you_story.http").info("catalog-log-capture-positive-control")
            logger.info("GET /catalog?text=%s&cursor=%s Referer: %s", query, cursor, referer)
            logger.warning("GET /api/v1/catalog/entries?author=%s Referer: %s", query, referer)
            with TestClient(app) as client:
                response = client.get(
                    "/api/v1/catalog/entries",
                    params={"author": query, "cursor": cursor},
                    headers={"Referer": referer},
                )
        assert response.status_code == 503
        assert "catalog-log-capture-positive-control" in caplog.text
        assert all(value not in caplog.text for value in [query, cursor, referer])
        assert all(value not in response.text for value in [query, cursor, referer])
    finally:
        logger.removeHandler(caplog.handler)
