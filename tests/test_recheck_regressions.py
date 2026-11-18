"""Regressions discovered by checking inputs outside the original corpus."""

import io
import unittest
from http.client import IncompleteRead
from unittest.mock import patch

from docguard.evaluation import score_pairs
from docguard.pipeline import extract
from docguard.providers import MockProvider, OllamaProvider, ProviderError
from docguard.schema import Document, empty_document


class EvidenceRoleTests(unittest.TestCase):
    def parse(self, text):
        result = extract(text, MockProvider())
        self.assertFalse(result.failed)
        return result.document

    def test_currency_in_product_name_is_not_payment_currency(self):
        for text in ('Курс USD    1    100', '- Курс USD — 100', 'Курс USD - 1 ед. - 100'):
            with self.subTest(text=text):
                doc = self.parse(text)
                self.assertIsNone(doc.currency)
                self.assertEqual(len(doc.line_items), 1)

    def test_price_currency_over_product_name(self):
        doc = self.parse('Курс USD    1    100 KZT')
        self.assertEqual(doc.currency, 'KZT')
        self.assertEqual(doc.warnings, [])

    def test_currency_in_line_total_column_is_retained(self):
        doc = self.parse('Консультация    2    100    200 EUR')
        self.assertEqual(doc.currency, 'EUR')

    def test_metadata_is_not_an_item(self):
        for label in ('Поставщик: Example', 'Покупатель: Example', 'Валюта:', 'Дата документа:'):
            with self.subTest(label=label):
                doc = self.parse(f'{label}    1    100')
                self.assertEqual(doc.line_items, [])

    def test_heading_prefix_does_not_establish_number_or_date(self):
        for heading in ('Счетчик', 'Шот-фактурация', 'Коммерческое предложениеXYZ'):
            with self.subTest(heading=heading):
                doc = self.parse(f'{heading} № 555 от 01.11.2026')
                self.assertEqual(doc.doc_type, 'unknown')
                self.assertIsNone(doc.doc_number)
                self.assertIsNone(doc.doc_date)

    def test_issue_and_expiry_on_one_line(self):
        doc = self.parse('Счет № A от 01.11.2026, оплатить до 15.11.2026')
        self.assertEqual(doc.doc_date, '2026-11-01')
        self.assertTrue(any(w.startswith('CONFLICT:doc_date:') for w in doc.warnings))

    def test_contract_date_is_not_document_date(self):
        doc = self.parse('Акт № A к договору № B от 01.10.2026')
        self.assertIsNone(doc.doc_date)
        self.assertIn('DATE_NOT_ISSUE', doc.warnings[0])

    def test_explicit_issue_marker_after_contract_date(self):
        doc = self.parse('Акт № A к договору № B от 01.10.2026, дата акта: 02.11.2026')
        self.assertEqual(doc.doc_date, '2026-11-02')

    def test_issue_date_before_contract_reference(self):
        doc = self.parse('Акт № A от 02.11.2026 по договору № B от 01.10.2026')
        self.assertEqual(doc.doc_date, '2026-11-02')

    def test_padded_offer_delimiters_are_not_table_cells(self):
        doc = self.parse('- Консультация  —  100 KZT')
        self.assertEqual(len(doc.line_items), 1)
        self.assertEqual(doc.line_items[0].price, 100)
        self.assertIsNone(doc.line_items[0].qty)


class RobustnessTests(unittest.TestCase):
    @patch('docguard.providers.urllib.request.urlopen')
    def test_invalid_url_fails_without_network_or_traceback(self, urlopen):
        for url in ('nonsense', 'http://', 'file:///tmp/model', 'http://[invalid'):
            with self.subTest(url=url):
                result = extract('Итого: 1 KZT', OllamaProvider('test', url))
                self.assertTrue(result.failed)
                self.assertIn('PROVIDER_ERROR', result.document.warnings[0])
        urlopen.assert_not_called()

    @patch('docguard.providers.urllib.request.urlopen')
    def test_incomplete_http_body_is_handled(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.side_effect = IncompleteRead(b'private', 500)
        with self.assertRaisesRegex(ProviderError, 'Ollama request failed'):
            OllamaProvider('test').generate('text')

    @patch('docguard.providers.urllib.request.urlopen')
    def test_excessive_json_nesting_is_handled(self, urlopen):
        urlopen.return_value = io.BytesIO(b'[' * 2000 + b']' * 2000)
        with self.assertRaises(ProviderError):
            OllamaProvider('test').generate('text')

    @patch('docguard.providers.urllib.request.urlopen')
    def test_short_body_with_valid_json_is_rejected(self, urlopen):
        class Response(io.BytesIO):
            headers = {'Content-Length': '9999'}
        urlopen.return_value = Response(b'{"done":true,"response":"{\\"evidence\\":[]}"}')
        with self.assertRaisesRegex(ProviderError, 'incomplete Ollama HTTP'):
            OllamaProvider('test').generate('text')

    def test_absent_rows_never_earn_correct_null_leaf_scores(self):
        data = empty_document().model_dump()
        data['line_items'] = [{'name': 'X', 'qty': None, 'price': None}]
        with_item = Document.model_validate(data)
        report = score_pairs([('missing', with_item, empty_document()),
                              ('extra', empty_document(), with_item)])
        for key in ('name', 'qty', 'price'):
            metric = report['fields'][f'line_items[].{key}']
            self.assertEqual(metric['total'], 2)
            self.assertEqual(metric['correct'], 0)
        self.assertEqual(report['extra_line_items'], 1)
        self.assertEqual(report['missing_line_items'], 1)
        self.assertEqual(report['hallucinations'], 0)
        self.assertEqual(report['omissions'], 0)
