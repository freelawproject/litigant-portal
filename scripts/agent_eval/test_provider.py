"""
Regression checks for observed stream cleanup, without provider or database calls.
"""

import unittest
from types import SimpleNamespace
from typing import Protocol, runtime_checkable

from .provider import Stream, close_stream


@runtime_checkable
class AsyncCloseable(Protocol):
    async def aclose(self) -> None: ...


class Resource:
    def __init__(self, fail=False):
        self.closed = False
        self.fail = fail

    async def aclose(self):
        self.closed = True
        if self.fail:
            raise RuntimeError("Iterator close failed.")


class StreamCloseTests(unittest.IsolatedAsyncioTestCase):
    async def test_observed_native_stream_satisfies_closing_protocol(self):
        iterator, response = Resource(), Resource()
        native = SimpleNamespace(stream_iterator=iterator, response=response)
        observed = Stream(native, lambda event: None)
        self.assertIsInstance(observed, AsyncCloseable)
        await observed.aclose()
        self.assertTrue(iterator.closed)
        self.assertTrue(response.closed)

    async def test_response_closes_even_when_iterator_close_fails(self):
        iterator, response = Resource(fail=True), Resource()
        native = SimpleNamespace(stream_iterator=iterator, response=response)
        with self.assertRaisesRegex(RuntimeError, "Iterator close failed"):
            await Stream(native, lambda event: None).aclose()
        self.assertTrue(response.closed)

    async def test_observed_translated_stream_closes_underlying_resource(self):
        underlying = Resource()
        translated = SimpleNamespace(litellm_custom_stream_wrapper=underlying)
        await Stream(translated, lambda event: None).aclose()
        self.assertTrue(underlying.closed)

    async def test_synchronous_close_is_supported(self):
        closed = []
        await close_stream(SimpleNamespace(close=lambda: closed.append(True)))
        self.assertEqual(closed, [True])
