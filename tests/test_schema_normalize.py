import unittest

from pydantic import ValidationError

from docguard.normalize import calendar_date, money, number
from docguard.schema import Document, Proposal, empty_document


class SchemaTests(unittest.TestCase):
    def test_invalid_public_values_rejected(self):
        cases = [('supplier_bin', '123'), ('supplier_bin', '１２３４５６７８９０１２'),
                 ('doc_date', '2026-02-30'), ('currency', 'RUB'),
                 ('total_amount', '12'), ('total_amount', True),
                 ('total_amount', -1), ('total_amount', float('nan')),
                 ('total_amount', float('inf')), ('total_amount', 1e13),
                 ('supplier_name', ''), ('doc_type', 'receipt')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = empty_document().model_dump()
                data[field] = value
                with self.assertRaises(ValidationError):
                    Document.model_validate(data)

    def test_missing_and_extra_keys_rejected(self):
        data = empty_document().model_dump()
        del data['vat_amount']
        with self.assertRaises(ValidationError):
            Document.model_validate(data)
        with self.assertRaises(ValidationError):
            Document.model_validate(empty_document().model_dump() | {'unexpected': 1})

    def test_confidence_contract(self):
        for confidence in ({'supplier_bin': .9}, {'supplier_bin': 2}, {}):
            with self.subTest(confidence=confidence), self.assertRaises(ValidationError):
                Document.model_validate(empty_document().model_dump() | {'field_confidence': confidence})

    def test_evidence_line_is_strict_positive_integer(self):
        for line in (True, '1', 0, -1, 1.5):
            with self.subTest(line=line), self.assertRaises(ValidationError):
                Proposal.model_validate({'evidence': [{'field': 'doc_date', 'line': line}]})

    def test_line_item_numbers_are_strict(self):
        for qty in (True, '2', -1):
            data = empty_document().model_dump()
            data['line_items'] = [{'name': 'X', 'qty': qty, 'price': None}]
            with self.subTest(qty=qty), self.assertRaises(ValidationError):
                Document.model_validate(data)


class NormalizationTests(unittest.TestCase):
    def test_grouped_and_decimal_numbers(self):
        self.assertEqual(number('12\u00a0345,67'), 12345.67)
        self.assertEqual(number('12\u202f345.67'), 12345.67)
        self.assertEqual(number('2,5'), 2.5)
        self.assertEqual(number('0'), 0)

    def test_ambiguous_numbers_not_partially_parsed(self):
        for value in ('1O0', '12 34', '1,234', '-12', 'nan', '1e6', '１２３', '100 USD trailing'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                number(value)

    def test_ru_kz_words_and_minor_units(self):
        self.assertEqual(money('Үш жүз қырық мың теңге 00 тиын'), 340000)
        self.assertEqual(money('Сто двадцать пять тысяч тенге 50 тиын'), 125000.5)
        self.assertEqual(money('Один миллион двести тысяч тенге'), 1200000)
        self.assertEqual(money('Екі жүз отыз бес теңге 09 тиын'), 235.09)
        self.assertEqual(money('Ноль тенге'), 0)

    def test_unrecognized_words_abstain(self):
        for value in ('один один тенге', 'примерно сто тенге', 'тысяча миллион тенге', 'сто тенге 120 тиын'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                money(value)

    def test_calendar_dates(self):
        self.assertEqual(calendar_date('29.02.2024'), '2024-02-29')
        self.assertEqual(calendar_date('09 қазан 2026'), '2026-10-09')
        self.assertEqual(calendar_date('12 ноября 2026'), '2026-11-12')
        with self.assertRaises(ValueError):
            calendar_date('29.02.2026')
