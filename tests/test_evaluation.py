import unittest

from docguard.evaluation import score_pairs
from docguard.schema import Document, empty_document


def document(**changes):
    data = empty_document().model_dump()
    data.update(changes)
    return Document.model_validate(data)


class EvaluationTests(unittest.TestCase):
    def test_hallucination_omission_wrong_value_are_separate(self):
        expected = document(supplier_name='A', total_amount=0)
        predicted = document(supplier_bin='123456789012', supplier_name='B')
        report = score_pairs([('controlled', expected, predicted)])
        self.assertEqual(report['hallucinations'], 1)
        self.assertEqual(report['omissions'], 1)
        self.assertEqual(report['fields']['supplier_name']['wrong_values'], 1)
        self.assertEqual(report['fields']['total_amount']['omissions'], 1)

    def test_zero_prediction_against_null_is_hallucination(self):
        report = score_pairs([('zero', empty_document(), document(total_amount=0))])
        self.assertEqual(report['hallucinations'], 1)
        self.assertEqual(report['omissions'], 0)

    def test_nested_null_fields_are_counted(self):
        gold = document(line_items=[{'name': 'X', 'qty': None, 'price': 100}])
        pred = document(line_items=[{'name': 'X', 'qty': 1, 'price': None}])
        report = score_pairs([('nested', gold, pred)])
        self.assertEqual(report['hallucinations'], 1)
        self.assertEqual(report['omissions'], 1)
        self.assertEqual(report['fields']['line_items']['correct'], 0)

    def test_missing_and_extra_rows_are_collection_errors(self):
        with_item = document(line_items=[{'name': 'X', 'qty': 2, 'price': 100}])
        report = score_pairs([('missing', with_item, empty_document()), ('extra', empty_document(), with_item)])
        self.assertEqual(report['extra_line_items'], 1)
        self.assertEqual(report['missing_line_items'], 1)
        self.assertEqual(report['hallucinations'], 0)
        self.assertEqual(report['omissions'], 0)

    def test_null_accuracy_does_not_hide_populated_accuracy(self):
        report = score_pairs([('empty', empty_document(), empty_document()),
                              ('missed', document(total_amount=10), empty_document())])
        metric = report['fields']['total_amount']
        self.assertEqual(metric['accuracy'], .5)
        self.assertEqual(metric['populated_accuracy'], 0)
