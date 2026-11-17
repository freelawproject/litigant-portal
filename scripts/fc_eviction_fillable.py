"""Build fillable copies of Franklin County's flat eviction forms (#610).

The Self Help Center's forms are flat PDFs: printed blanks, no AcroForm
fields. The packet needs fillable PDFs (#535), so this adds the fields.
FormFyxer's ``auto_add_fields`` found the blanks and checkboxes once; its
names come from nearby text and shift onto the wrong label, so the
positions it found are kept here under names read off the page. Rerun this
when the court revises a form, then re-check every field by eye.

FormFyxer is not a project dependency. Run it from its own environment:

    uv venv --python 3.12 ~/.venvs/formfyxer
    uv pip install --python ~/.venvs/formfyxer formfyxer \
        "opencv-python<5" "opencv-python-headless<5"
    ~/.venvs/formfyxer/bin/python scripts/fc_eviction_fillable.py

OpenCV 5 dropped ``groupRectangles``, which FormFyxer's checkbox detection
still calls, hence the pin.

The fillable PDFs land in ``docassemble/fc-eviction/`` (the interview's
copy) and ``litigant_portal/corpus/forms/`` (the corpus copy), and both are
committed. Nothing in the app runs this script.
"""

# FormFyxer lives in its own environment (above), so the project's type
# checker can't resolve it.
# pyright: reportMissingImports=false

import shutil
from pathlib import Path

from formfyxer.pdf_wrangling import FieldType, FormField, set_fields

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "corpus-sources/franklin-county-oh/eviction"
INTERVIEW_DIR = REPO / "docassemble/fc-eviction"
CORPUS_FORMS = REPO / "litigant_portal/corpus/forms"

TEXT_HEIGHT = 12

# No border or fill: the printed blank already shows where to write, and the
# filled form goes to the court. ReportLab draws a border and FormFyxer a
# pink fill unless told not to.
PLAIN = {"borderWidth": 0, "fillColor": None}


def _text(name, x, y, width, font_size=10):
    return FormField(
        name,
        FieldType.TEXT,
        x,
        y,
        font_size=font_size,
        configs={
            **PLAIN,
            "width": width,
            "height": TEXT_HEIGHT,
            "fieldFlags": "doNotScroll",
        },
    )


def _area(name, x, y, width, height, font_size=10):
    return FormField(
        name,
        FieldType.AREA,
        x,
        y,
        font_size=font_size,
        configs={
            **PLAIN,
            "width": width,
            "height": height,
            "fieldFlags": "multiline",
        },
    )


def _check(name, x, y, size=6):
    # ReportLab sizes a checkbox with ``size``, not width and height.
    return FormField(
        name,
        FieldType.CHECK_BOX,
        x,
        y,
        configs={**PLAIN, "size": size, "buttonStyle": "check"},
    )


# Answer of Defendant(s), "Rev. December 2021", pages 10-11 of the Self
# Help Center's 14-page answer packet. Positions are FormFyxer's, in PDF
# points from the bottom-left corner.
ANSWER = [
    # Page 1: caption, then the defenses in the order printed.
    [
        _text("plaintiff_landlord", 73, 703, 180),
        _text("case_number", 374, 703, 126),
        _text("judge", 355, 661, 144),
        _text("defendant_tenants", 73, 620, 180),
        _check("defense_paid_in_full", 72, 468),
        _check("defense_paid_in_part", 72, 440),
        _text("paid_in_part_amount", 68, 426, 84),
        _check("defense_repairs", 72, 397),
        _text("repairs_amount", 297, 370, 162),
        _check("defense_work_for_rent", 72, 327),
        _check("defense_deposit_not_credited", 72, 285),
        _text("deposit_not_credited_amount", 304, 285, 84),
        _check("defense_deposit_withheld", 72, 243),
        _text("deposit_withheld_amount", 373, 243, 66),
        _text("deposit_withheld_double_amount", 243, 215, 72),
        _check("defense_late_charges", 72, 171),
        _check("defense_no_damage", 72, 113),
    ],
    # Page 2: other reasons, signature block, proof of service.
    [
        _check("defense_other", 72, 743),
        _text("other_reasons_first_line", 273, 743, 264),
        _area("other_reasons", 73, 664, 468, 68),
        _text("defendant_signature", 328, 554, 150),
        _text("defendant_name", 312, 512, 168),
        _text("defendant_address_line_1", 312, 485, 168),
        _text("defendant_address_line_2", 312, 457, 168),
        _text("defendant_phone", 312, 416, 168),
        _text("service_date", 218, 347, 114),
        _check("served_landlord_attorney", 73, 292, size=7),
        _check("served_landlord", 325, 292, size=7),
        _text("landlord_attorney_name", 75, 264, 228),
        _text("landlord_attorney_address_line_1", 75, 236, 228),
        _text("landlord_attorney_address_line_2", 75, 223, 228),
        _text("landlord_attorney_address_line_3", 75, 209, 228),
        _text("landlord_name", 327, 264, 210),
        _text("landlord_address_line_1", 327, 236, 210),
        _text("landlord_address_line_2", 327, 223, 210),
        _text("landlord_address_line_3", 327, 209, 210),
        _text("tenant_signature", 342, 154, 126),
    ],
]

FORMS = {
    # output slug: (source file, fields per page)
    "fc-eviction-answer": ("LL-T Answr.pdf", ANSWER),
}


def main():
    for slug, (source, fields) in FORMS.items():
        built = INTERVIEW_DIR / f"{slug.removeprefix('fc-eviction-')}.pdf"
        set_fields(SOURCES / source, built, fields, overwrite=True)
        shutil.copyfile(built, CORPUS_FORMS / f"{slug}.pdf")
        print(f"{slug}: {sum(len(page) for page in fields)} fields → {built}")


if __name__ == "__main__":
    main()
