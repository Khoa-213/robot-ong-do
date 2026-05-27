from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.text_trajectory import _font_properties, _text_polygons


def test_outline_text_falls_back_when_configured_font_path_is_missing() -> None:
    missing_font = Path("C:/Windows/Fonts/UTM ThuPhap Thien An")

    font = _font_properties("DejaVu Sans", str(missing_font))
    assert font.get_file() is None

    polygons = _text_polygons("Tam", "DejaVu Sans", str(missing_font), 1.0)
    assert polygons


if __name__ == "__main__":
    test_outline_text_falls_back_when_configured_font_path_is_missing()
    print("[TEXT_TRAJECTORY] Missing font fallback OK")
