import numpy as np
import pytest

from app.ocr_engine import OcrLine
from repayment_slip_ocr import main
from repayment_slip_ocr.schemas import RepaymentResult


def line(text, x0=240, y0=841, x1=704, y1=869, confidence=0.95):
    return OcrLine(text=text, confidence=confidence, box=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def test_conflict_requires_distinct_readings_of_same_labelled_row():
    first = line("ACC0UNT NUMBER: 1234567890")
    alternative = line("ACCOUNT NUMBER1234567898")
    unrelated = line("ACCOUNT NUMBER1234567898", y0=950, y1=978)
    assert main._cdm_conflicting_account_row([first, unrelated]) is None
    assert main._cdm_conflicting_account_row([first, line(first.text)]) is None
    _, values = main._cdm_conflicting_account_row([first, alternative])
    assert values == {"1234567890", "1234567898"}


@pytest.mark.parametrize(
    ("crop_results", "expected"),
    [
        (["1234567898", "1234567898"], "1234567898"),
        (["1234567890", "1234567898"], None),
        (["1234567897", "1234567897"], None),
        (["1234567898", ""], None),
    ],
)
def test_account_recheck_needs_agreement_on_an_original_candidate(monkeypatch, crop_results, expected):
    first = line("ACCOUNT NUMBER: 1234567890")
    conflict = (first, {"1234567890", "1234567898"})
    image = np.zeros((1600, 1200, 3), dtype=np.uint8)
    variants = [{"name": "color_raw", "img": image}, {"name": "enhanced", "img": image}]
    pending = iter(crop_results)
    monkeypatch.setattr(main, "_run_cdm_direct_line_windows", lambda *args, **kwargs: [line(next(pending))])
    assert main._verify_cdm_account_conflict(None, variants, conflict) == expected


@pytest.mark.parametrize("confirmed", ["1234567898", None])
def test_conflict_uses_rechecked_account_or_omits_unresolved_value(monkeypatch, confirmed):
    original = [line("ACCOUNT NUMBER: 1234567890"), line("ACCOUNT NUMBER: 1234567898")]
    result = RepaymentResult(
        success=True, bank="commercial_bank", doc_type="cash_deposit_slip",
        fields={"ACCOUNT NUMBER": "1234567890", "CUSTOMER NAME": "Example", "DATE": "2026-11-26"},
    )
    image = np.zeros((1600, 1200, 3), dtype=np.uint8)
    class FakeEngine:
        def recognize(self, _image):
            return original
    monkeypatch.setattr(main, "_engine", FakeEngine())
    monkeypatch.setattr(main, "load_image", lambda buf: image)
    monkeypatch.setattr(main, "build_variants", lambda *args, **kwargs: [{"name": "color_raw", "img": image}])
    monkeypatch.setattr(main, "_extract_timed", lambda *args, **kwargs: result)
    monkeypatch.setattr(main, "_verify_cdm_account_conflict", lambda *args: confirmed)
    monkeypatch.setattr(main, "_cdm_missing_party_fields", lambda result: False)
    monkeypatch.setattr(main, "_cdm_missing_deposit_amount", lambda result, lines: False)
    monkeypatch.setattr(main, "_cdm_missing_header_fields", lambda result: False)

    response = main._recognize_impl(b"image")
    assert response.get("ACCOUNT NUMBER") == confirmed
