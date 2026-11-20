"""HTTP layer. Skipped where FastAPI or httpx is not installed; scripts/verify.py reports the skip as a release gate."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.mark.parametrize("path", ["/", "/carbon", "/carbon?horizon=today&price=600", "/method", "/plants/P01", "/plants/p09"])
def test_pages_return_html(path):
    r = client.get(path)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "Nimbus Cement" in r.text


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["plants"] == 9


@pytest.mark.parametrize("path", ["/plants/P99", "/nope", "/plants/%3Cscript%3E"])
def test_unknown_paths_return_a_helpful_404(path):
    r = client.get(path)
    assert r.status_code == 404 and "not in this register" in r.text and "<script>" not in r.text.split("</style>")[1]


def test_bad_query_values_do_not_error():
    assert client.get("/carbon?price=abc&horizon=zzz").status_code == 200
    assert client.get("/carbon?price=-1").status_code == 200
