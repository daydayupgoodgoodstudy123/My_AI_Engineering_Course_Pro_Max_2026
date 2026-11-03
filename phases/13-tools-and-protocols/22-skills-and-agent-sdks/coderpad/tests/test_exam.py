"""Behavior tests for 22-skills-and-agent-sdks; default target is starter."""
import unittest
from _support import m

TEXT = '---\nname: review-notes\ndescription: Review a note: carefully\n---\n\nRead the note.\n'

class CoreTests(unittest.TestCase):

    def test_parse(self):
        self.assertEqual(m.parse(TEXT), {'name': 'review-notes', 'description': 'Review a note: carefully', 'body': 'Read the note.'})

    def test_bundle(self):
        self.assertEqual(m.validate_bundle('review-notes', TEXT)['name'], 'review-notes')

    def test_directory_mismatch(self):
        with self.assertRaises(ValueError):
            m.validate_bundle('other', TEXT)

    def test_delimiters(self):
        for t in ('name: a', TEXT.replace('---', '', 1), '---\nname: a'):
            with self.subTest(t=t), self.assertRaises(ValueError):
                m.parse(t)

    def test_invalid_metadata(self):
        for t in (TEXT.replace('review-notes', 'Bad_Name'), TEXT.replace('description:', 'extra:'), TEXT.replace('---\n\nRead', 'name: x\n---\n\nRead'), TEXT.replace('Read the note.', '')):
            with self.subTest(t=t), self.assertRaises(ValueError):
                m.parse(t)

    def test_trim(self):
        self.assertEqual(m.parse(TEXT.replace('name: review-notes', 'name:   review-notes  '))['name'], 'review-notes')

class BonusTests(unittest.TestCase):

    def test_classification(self):
        self.assertEqual(m.classify('external action'), 'tool')
        self.assertEqual(m.classify('reusable workflow'), 'skill')

    def test_default(self):
        self.assertEqual(m.classify('sum a list'), 'ordinary code')
