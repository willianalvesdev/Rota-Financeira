"""Public information and install metadata must remain usable without sign-in."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.theme = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta" and values.get("name"):
            self.meta[values["name"].lower()] = values.get("content", "")
        if tag == "html":
            self.theme = values.get("data-theme")


@pytest.mark.parametrize("path", ["/privacidade", "/contato"])
def test_public_information_pages_render_without_login_with_description_and_dark_default(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    parser = PageMetadata()
    parser.feed(response.get_data(as_text=True))
    assert parser.meta.get("description")
    assert parser.theme == "dark"


def test_personal_dashboard_is_not_indexable_or_cacheable(authenticated_client):
    response = authenticated_client.get("/")
    assert response.status_code == 200
    parser = PageMetadata()
    parser.feed(response.get_data(as_text=True))
    robots = f"{parser.meta.get('robots', '')},{response.headers.get('X-Robots-Tag', '')}"
    assert "noindex" in robots.lower()
    assert "no-store" in response.headers["Cache-Control"]


def test_robots_and_llms_resources_are_public_text(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert robots.mimetype == "text/plain"
    assert "user-agent:" in robots.get_data(as_text=True).lower()
    llms = client.get("/llms.txt")
    assert llms.status_code == 200
    assert llms.mimetype == "text/plain"
    assert "rota" in llms.get_data(as_text=True).lower()


def test_web_manifest_has_local_reachable_start_page_and_icons(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.mimetype in {"application/manifest+json", "application/json"}
    manifest = response.get_json()
    assert manifest["name"]
    assert manifest["display"] in {"standalone", "fullscreen", "minimal-ui"}
    start = urlsplit(manifest["start_url"])
    assert not start.scheme and not start.netloc
    assert client.get(manifest["start_url"]).status_code in {200, 302}
    assert manifest["icons"], "Installation must have a real local application icon."
    icon_sizes = {size for icon in manifest["icons"] for size in icon.get("sizes", "").split()}
    assert "any" in icon_sizes or {"192x192", "512x512"} <= icon_sizes
    for icon in manifest["icons"]:
        source = urlsplit(icon["src"])
        assert not source.scheme and not source.netloc
        image = client.get(icon["src"])
        assert image.status_code == 200
        assert image.mimetype.startswith("image/")
        assert len(image.data) > 100


def test_installation_prompts_and_service_worker_are_not_exposed(client):
    assert client.get("/instalar").status_code == 404
    assert client.get("/service-worker.js").status_code == 404
    assert client.get("/static/service-worker.js").status_code == 404
    response = client.get("/login")
    assert response.status_code == 200
    assert b"data-install-app" not in response.data
    assert b"/instalar" not in response.data
    assert b"install.js" not in response.data
