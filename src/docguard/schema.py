"""Strict contracts for the public result and the untrusted model response."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FieldName = Literal[
    "doc_type", "supplier_name", "supplier_bin", "doc_number", "doc_date",
    "currency", "total_amount", "vat_amount", "line_items",
]
FIELDS = tuple(FieldName.__args__)
Number = Annotated[float, Field(ge=0, le=1_000_000_000_000)]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class LineItem(StrictModel):
    name: Text
    qty: Number | None
    price: Number | None


class Document(StrictModel):
    doc_type: Literal["invoice", "commercial_offer", "act", "unknown"]
    supplier_name: Text | None
    supplier_bin: Annotated[str, Field(pattern=r"^[0-9]{12}$")] | None
    doc_number: Text | None
    doc_date: Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")] | None
    currency: Literal["KZT", "USD", "EUR"] | None
    total_amount: Number | None
    vat_amount: Number | None
    line_items: list[LineItem]
    field_confidence: dict[FieldName, Confidence]
    warnings: list[Text]

    @field_validator("doc_date")
    @classmethod
    def real_calendar_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def complete_confidence(self) -> "Document":
        if set(self.field_confidence) != set(FIELDS):
            raise ValueError("field_confidence must contain every extraction field")
        for field in FIELDS:
            value = getattr(self, field)
            if value in (None, "unknown", []) and self.field_confidence[field] != 0:
                raise ValueError("abstained fields must have zero confidence")
        return self


class Evidence(StrictModel):
    field: FieldName
    line: Annotated[int, Field(ge=1)]


class Proposal(StrictModel):
    # A model may point at source lines, but may never supply invented values.
    evidence: Annotated[list[Evidence], Field(max_length=5000)]


def empty_document(*warnings: str) -> Document:
    return Document(
        doc_type="unknown", supplier_name=None, supplier_bin=None,
        doc_number=None, doc_date=None, currency=None, total_amount=None,
        vat_amount=None, line_items=[],
        field_confidence={field: 0.0 for field in FIELDS}, warnings=list(warnings),
    )
