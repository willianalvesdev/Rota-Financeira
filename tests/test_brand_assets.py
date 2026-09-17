"""Guard the user's explicit visual identity without asserting page structure."""

import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_COLORS = {"#0C0C0C", "#232323", "#49494B", "#B3B3B3", "#FFFFFF", "#4BD964", "#FF443A"}
FONT_WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}


@pytest.fixture(autouse=True)
def clean_database():
    """Override the integration fixture: these asset checks never need MySQL."""


def stylesheets():
    files = sorted((ROOT / "static" / "css").rglob("*.css"))
    assert files, "The application must include its own local CSS."
    return {
        path: re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL) for path in files
    }


def templates():
    files = sorted((ROOT / "templates").rglob("*.html"))
    assert files
    return {path: path.read_text(encoding="utf-8") for path in files}


def test_css_uses_requested_palette_without_shadows_or_non_chart_gradients():
    colors_found = set()
    for path, css in stylesheets().items():
        colors = set(re.findall(r"#[0-9a-f]{3,8}\b", css, flags=re.IGNORECASE))
        # A shorthand literal such as #fff is still the same requested white.
        normalized = {
            ("#" + "".join(char * 2 for char in color[1:]) if len(color) == 4 else color).upper()
            for color in colors
        }
        assert normalized <= ALLOWED_COLORS, (
            f"Unexpected colors in {path.name}: {normalized - ALLOWED_COLORS}"
        )
        colors_found.update(normalized)
        assert not re.search(
            r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\s*\(", css, re.IGNORECASE
        ), f"Use the approved hex colors instead of generated colors in {path.name}."
        assert not re.search(
            r"\b(?:box-shadow|text-shadow|drop-shadow)\b|"
            r"\b(?:repeating-)?(?:linear|radial|conic)-gradient\s*\(",
            css,
            re.IGNORECASE,
        ), f"Shadows are forbidden; gradients belong only to SVG charts, not {path.name}."
    assert colors_found, "The requested palette must be defined in the local CSS."


def test_poppins_is_local_licensed_and_available_in_all_four_weights():
    css = "\n".join(stylesheets().values())
    faces = re.findall(r"@font-face\s*\{([^{}]+)\}", css, flags=re.IGNORECASE | re.DOTALL)
    poppins_faces = [
        face for face in faces if re.search(r"font-family\s*:\s*['\"]?Poppins['\"]?\s*;", face, re.IGNORECASE)
    ]
    assert poppins_faces, "Poppins must be declared as a locally loaded font."
    for name, weight in FONT_WEIGHTS.items():
        filename = f"Poppins-{name}.ttf"
        font_file = ROOT / "static" / "fonts" / filename
        assert font_file.is_file(), f"Missing local font: {filename}"
        font_bytes = font_file.read_bytes()
        assert len(font_bytes) > 1024 and font_bytes[:4] in {b"\x00\x01\x00\x00", b"OTTO"}, (
            f"{filename} must contain a real font, not an empty file or download error."
        )
        matching_faces = [
            face
            for face in poppins_faces
            if filename in face and re.search(rf"font-weight\s*:\s*{weight}\s*;", face)
        ]
        assert matching_faces, f"Declare a local @font-face for Poppins {weight}."
        for face in matching_faces:
            assert not re.search(r"(?:https?:)?//", face, re.IGNORECASE), "Poppins must work offline."
            assert re.search(r"\bsrc\s*:\s*[^;]*url\(", face, re.IGNORECASE)
    font_free_css = re.sub(r"@font-face\s*\{[^{}]+\}", "", css, flags=re.IGNORECASE | re.DOTALL)
    assert re.search(
        r"(?:font-family|--[\w-]+)\s*:\s*['\"]?Poppins['\"]?\s*[,;}]",
        font_free_css,
        re.IGNORECASE,
    ), "Poppins must be used by the interface, not only declared."
    license_text = (ROOT / "static" / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in license_text.upper()


class InterfaceResources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.urls.append(values["src"])
        if tag == "link" and values.get("rel") in {"stylesheet", "preload"} and values.get("href"):
            self.urls.append(values["href"])


def test_templates_use_local_resources_without_bootstrap_or_chartjs():
    for path, source in templates().items():
        assert not re.search(r"bootstrap|chart(?:\.min)?\.js|chartjs", source, re.IGNORECASE), path.name
        parser = InterfaceResources()
        parser.feed(source)
        assert not any(re.match(r"(?:https?:)?//", url, re.IGNORECASE) for url in parser.urls), (
            f"Interface resources in {path.name} must work without a CDN."
        )


def test_supplied_logo_files_are_valid_svg_and_used_in_templates():
    source = "\n".join(templates().values())
    for relative in ("img/logo-symbol-white.svg", "img/logo-symbol-black.svg", "favicon.svg"):
        path = ROOT / "static" / relative
        assert path.is_file(), f"Missing supplied identity asset: {relative}"
        svg = ElementTree.parse(path).getroot()
        assert svg.tag.rsplit("}", 1)[-1] == "svg"
        assert svg.get("viewBox") and len(svg), f"Invalid or empty SVG: {relative}"
        assert path.name in source, f"The supplied asset must be referenced by the interface: {relative}"
