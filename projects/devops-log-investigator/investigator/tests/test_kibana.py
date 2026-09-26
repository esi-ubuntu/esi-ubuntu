from __future__ import annotations

import importlib
import json

import httpx
import pytest


def load_api():
    try:
        catalog = importlib.import_module("app.catalog")
        kibana = importlib.import_module("app.kibana")
    except ModuleNotFoundError as exc:
        pytest.fail(f"kibana catalog implementation missing: {exc}")
    return catalog, kibana


def client_for(kibana_module, handler):
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://kibana:5601")
    return kibana_module.KibanaClient("http://kibana:5601", http_client=http)


def test_fetch_catalog_discovers_titles_index_patterns_fields_and_queries():
    _, kibana = load_api()

    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/api/saved_objects/_find"
        body = {
            "saved_objects": [
                {
                    "id": "dv-1",
                    "type": "index-pattern",
                    "attributes": {
                        "title": "payments-*",
                        "fields": json.dumps([{"name": "customer.national_id"}, {"name": "transaction.id"}]),
                    },
                    "references": [],
                },
                {
                    "id": "search-1",
                    "type": "search",
                    "attributes": {
                        "title": "Duplicate Debit",
                        "kibanaSavedObjectMeta": {
                            "searchSourceJSON": json.dumps({"query": {"query": "operation:DB", "language": "kuery"}})
                        },
                    },
                    "references": [{"type": "index-pattern", "id": "dv-1", "name": "kibanaSavedObjectMeta.searchSourceJSON.index"}],
                },
            ]
        }
        return httpx.Response(200, json=body)

    result = client_for(kibana, handler).fetch_catalog()

    assert result.health == "ok"
    assert len(result.entries) == 2
    assert result.entries[0].index_patterns == ["payments-*"]
    assert "customer.national_id" in result.entries[0].fields
    assert "operation:DB" in (result.entries[1].query or "")


def test_fetch_catalog_returns_unauthorized_health_on_401_or_403():
    _, kibana = load_api()

    for status in (401, 403):
        result = client_for(kibana, lambda request, s=status: httpx.Response(s)).fetch_catalog()
        assert result.health == "unauthorized"
        assert result.entries == []


def test_fetch_catalog_degrades_when_kibana_is_unavailable():
    _, kibana = load_api()

    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    result = client_for(kibana, handler).fetch_catalog()

    assert result.health == "unavailable"
    assert result.entries == []
    assert "offline" in (result.error or "")


def test_fetch_catalog_skips_malformed_objects_instead_of_crashing():
    _, kibana = load_api()

    def handler(request):
        return httpx.Response(200, json={"saved_objects": [{"type": "search", "attributes": None}]})

    result = client_for(kibana, handler).fetch_catalog()

    assert result.health == "ok"
    assert result.entries == []


def test_catalog_find_candidates_returns_empty_when_no_semantic_token_matches():
    catalog_module, _ = load_api()
    catalog = catalog_module.Catalog(
        entries=[catalog_module.CatalogEntry(kind="dashboard", source_id="1", title="Payment Errors")],
        health="ok",
    )

    assert catalog.find_candidates(["cpu", "memory"]) == []
