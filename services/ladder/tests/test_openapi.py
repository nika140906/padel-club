"""openapi.yaml must describe exactly the routes the app really has.

If someone adds, removes or renames a route and forgets the document,
this test fails. This file is the same in both services.
"""
import os
import re

import yaml

SERVICE_DIR = os.path.dirname(os.path.dirname(__file__))
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def load_openapi(service_dir=SERVICE_DIR):
    with open(os.path.join(service_dir, "openapi.yaml"), encoding="utf-8") as file:
        return yaml.safe_load(file)


def routes_in_code(app):
    """("GET", "/courts/{court_id}/bookings") for every Flask route.

    Flask writes path parameters as <int:court_id>, OpenAPI as {court_id}.
    HEAD and OPTIONS are added by Flask on its own, so they are left out.
    """
    routes = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", rule.rule)
        routes |= {(method, path) for method in rule.methods - {"HEAD", "OPTIONS"}}
    return routes


def routes_in_document(document):
    return {
        (method.upper(), path)
        for path, operations in document["paths"].items()
        for method in operations
        if method in HTTP_METHODS
    }


def test_openapi_lists_exactly_the_routes_in_the_code(client):
    assert routes_in_document(load_openapi()) == routes_in_code(client.application)


def test_every_route_documents_its_status_codes():
    for path, operations in load_openapi()["paths"].items():
        for method, operation in operations.items():
            assert operation["responses"], f"{method.upper()} {path} has no responses"


def test_the_bookings_endpoint_the_ladder_calls_is_in_the_bookings_document():
    # The ladder calls GET /auth/me on bookings and reads "id" and "username"
    # from the answer (padel/bookings_client.py). The bookings document must
    # promise exactly that, or the two services have drifted apart.
    bookings = load_openapi(os.path.join(SERVICE_DIR, "..", "bookings"))
    me = bookings["paths"]["/auth/me"]["get"]["responses"]
    member = bookings["components"]["schemas"]["Member"]

    assert me["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/Member"
    assert {"id", "username"} <= set(member["required"])
    assert "404" in me  # the ladder turns this into its own 404
