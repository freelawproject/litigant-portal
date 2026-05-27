from django.test import SimpleTestCase


class HelloWorldTests(SimpleTestCase):
    def test_hello(self):
        self.assertEqual(1 + 1, 2)
