from pathlib import Path


def test_hqa_keyword_csv_exists_in_app_data():
    csv_path = Path(__file__).resolve().parents[1] / "app" / "data" / "hqa_keywords.csv"
    assert csv_path.exists()
