import json
import sys

import numpy as np
import pytest

from repayment_slip_ocr import cli, main
from repayment_slip_ocr.schemas import RepaymentResult


@pytest.mark.parametrize("include_lines", [False, True])
@pytest.mark.parametrize("has_fields", [False, True])
def test_api_omits_warnings_even_when_extractor_reports_them(monkeypatch, include_lines, has_fields):
    result = RepaymentResult(
        success=True,
        bank="ndb",
        amount=1200.0,
        fields={"Amount": "1,200.00"} if has_fields else {},
        warnings=["纸币明细校验不一致"],
    )
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    monkeypatch.setattr(main, "load_image", lambda buf: image)
    monkeypatch.setattr(main, "build_variants", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "_extract_timed", lambda *args, **kwargs: result)

    response = main._recognize_impl(b"image", include_lines=include_lines)

    assert response["success"] is True
    assert response["bank"] == "NDB"
    assert response.get("Amount", response.get("amount")) in ("1,200.00", 1200.0)
    assert "warnings" not in response
    assert result.warnings == ["纸币明细校验不一致"]


def test_cli_omits_warnings(monkeypatch, tmp_path, capsys):
    class FakeEngine:
        def warmup(self):
            pass

        def recognize(self, image):
            return []

    image_path = tmp_path / "receipt.jpg"
    image_path.write_bytes(b"image")
    result = RepaymentResult(success=True, amount=1200, warnings=["纸币明细校验不一致"])
    monkeypatch.setattr(sys, "argv", ["cli", str(image_path)])
    monkeypatch.setattr(cli, "create_engine", lambda settings: FakeEngine())
    monkeypatch.setattr(cli, "load_image", lambda buf: None)
    monkeypatch.setattr(cli, "build_variants", lambda image: [{"img": image}])
    monkeypatch.setattr(cli, "extract", lambda lines: result)

    assert cli.main() == 0
    response = json.loads(capsys.readouterr().out)
    assert response["amount"] == 1200
    assert "warnings" not in response
