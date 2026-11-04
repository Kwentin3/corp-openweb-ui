"""Actual finite usage wires over the existing owned HTTP fixture; no billing."""
import copy
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest

import test_responses_provider as HTTP


class PricingUsageProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        HTTP.ResponsesHTTPTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        HTTP.ResponsesHTTPTests.tearDownClass()

    def setUp(self):
        self.boundary = HTTP.ResponsesHTTPTests()
        self.boundary.setUp()

    def payload(self, model):
        return self.boundary.payload(model=model, tools=[])

    def test_three_actual_wires_preserve_absence_null_and_positive_details(self):
        expected = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
            "input_tokens_details": {"cached_tokens": 6}, "output_tokens_details": {"reasoning_tokens": 2}}
        for index, model in enumerate(HTTP.P.USAGE_MODELS):
            with self.subTest(model=model):
                payload = self.payload(model)
                payload.update(metadata={"synthetic_context": "retained"}, temperature=.2, top_p=.9)
                before = copy.deepcopy(payload)
                code, result = self.boundary.http('/v1/responses', payload)
                self.assertEqual(code, 200)
                self.assertEqual(payload, before)
                parsed = HTTP.Response.model_validate(result)
                self.assertEqual(result['model'], model)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(len(result['output']), 1)
                self.assertEqual(result['output'][0]['content'], [{"type": "output_text", "text": "Proof", "annotations": []}])
                if index == 0:
                    self.assertEqual(result['usage'], expected)
                    self.assertEqual(parsed.usage.input_tokens_details.cached_tokens, 6)
                    self.assertEqual(parsed.usage.output_tokens_details.reasoning_tokens, 2)
                else:
                    self.assertIsNone(result.get('usage'))
                    self.assertIsNone(parsed.usage)
                    self.assertEqual('usage' in result, index == 2)
                    self.assertEqual('usage' in parsed.model_fields_set, index == 2)
                row = self.boundary.terminal(result['id'])
                self.assertEqual(row['body'], before)
                self.assertEqual(row['response'], result)
                self.assertEqual(row['usage'], expected if index == 0 else None)
                self.assertIs(row['lifecycle']['usage_sent'], index == 0)
                self.assertIs(row['lifecycle']['terminal'], True)
                self.assertEqual(row['lifecycle']['outcome'], 'completed')
        self.assertEqual(len(self.boundary.rows()), 3)

    def test_native_hi_representations_are_captured_without_rewriting(self):
        for content in ('Hi', [{"role": "user", "content": "Hi"}],
                        [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Hi"}]}]):
            with self.subTest(input=content):
                payload = self.payload(HTTP.P.USAGE_MODELS[0])
                payload['input'] = content
                code, response = self.boundary.http('/v1/responses', payload)
                self.assertEqual(code, 200)
                self.assertEqual(self.boundary.terminal(response['id'])['body'], payload)

    def test_invalid_usage_requests_reject_before_receipt_arrival(self):
        mutations = [lambda p: p.update(stream=True), lambda p: p.update(tools=[HTTP.TOOL]),
            lambda p: p.update(input='Other'), lambda p: p.update(input=[{"role": "assistant", "content": "Hi"}]),
            lambda p: p.update(input=[{"role": "user", "content": [{"type": "output_text", "text": "Hi"}]}]),
            lambda p: p['input'].append({"role": "user", "content": "Hi"}),
            lambda p: p['input'][0].update(unexpected=True), lambda p: p.update(store=True),
            lambda p: p.update(previous_response_id='foreign'), lambda p: p.update(max_output_tokens=True),
            lambda p: p.pop('max_output_tokens'), lambda p: p.update(reasoning={"effort": "low"}),
            lambda p: p.update(include=['reasoning.encrypted_content']), lambda p: p.update(unexpected=True)]
        for model in HTTP.P.USAGE_MODELS:
            for index, mutate in enumerate(mutations):
                with self.subTest(model=model, mutation=index):
                    payload = self.payload(model)
                    mutate(payload)
                    self.assertEqual(self.boundary.http('/v1/responses', payload)[0], 400)
        self.assertEqual(self.boundary.rows(), [])

    def test_controlled_500_keeps_absent_usage_for_every_usage_model(self):
        self.assertEqual(self.boundary.http('/__proof/control', {"response_status": 500})[0], 200)
        for model in HTTP.P.USAGE_MODELS:
            with self.subTest(model=model):
                code, result = self.boundary.http('/v1/responses', self.payload(model))
                self.assertEqual(code, 500)
                self.assertEqual(result['error']['code'], 'proof_provider_500')
                row = self.boundary.terminal(result['id'])
                self.assertIsNone(row['usage'])
                self.assertIs(row['lifecycle']['usage_sent'], False)
                self.assertEqual(row['lifecycle']['outcome'], 'controlled_error')
        self.assertEqual(len(self.boundary.rows()), 3)

    def test_pending_before_headers_keeps_the_same_finite_usage_contract(self):
        self.assertEqual(self.boundary.http('/__proof/control', {"delay_ms": 150})[0], 200)
        for index, model in enumerate(HTTP.P.USAGE_MODELS):
            with self.subTest(model=model), ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.boundary.http, '/v1/responses', self.payload(model))
                deadline = time.monotonic() + 2
                pending = None
                while time.monotonic() < deadline:
                    matches = [r for r in self.boundary.rows() if r['body']['model'] == model]
                    if matches and matches[0]['lifecycle']['stage'] == 'before_headers_delay':
                        pending = matches[0]
                        break
                    threading.Event().wait(.005)
                self.assertIsNotNone(pending)
                if index == 0:
                    self.assertEqual(pending['usage']['input_tokens_details'], {"cached_tokens": 6})
                    self.assertEqual(pending['usage']['output_tokens_details'], {"reasoning_tokens": 2})
                else:
                    self.assertIsNone(pending['usage'])
                self.assertIs(pending['lifecycle']['headers_sent'], False)
                self.assertIs(pending['lifecycle']['usage_sent'], False)
                code, response = future.result(timeout=3)
                self.assertEqual(code, 200)
                self.assertEqual(self.boundary.terminal(response['id'])['lifecycle']['usage_sent'], index == 0)

    def test_usage_models_do_not_expand_old_routes_catalog_controls_or_r_usage(self):
        self.assertEqual(self.boundary.http('/v1/models')[1]['data'], [
            {"id": model, "object": "model", "created": 0, "owned_by": "goal584-proof"} for model in HTTP.P.MODELS])
        self.assertEqual(self.boundary.http('/__proof/requests')[1],
            {"synthetic": True, "requests": [], "control": HTTP.DEFAULT})
        self.assertEqual(self.boundary.http('/__proof/control', {"usage_mode": True})[0], 400)
        for model in HTTP.P.USAGE_MODELS:
            self.assertEqual(self.boundary.http('/v1/chat/completions', {"model": model, "messages": [{"role": "user", "content": "Hi"}]})[0], 404)
            self.assertEqual(self.boundary.http('/v1/embeddings', {"model": model, "input": 'Hi'})[0], 404)
        code, result = self.boundary.http('/v1/responses', self.boundary.payload())
        self.assertEqual(code, 200)
        self.assertEqual(result['model'], HTTP.P.RESPONSES_MODEL)
        self.assertEqual(result['usage'], HTTP.USAGE)
        self.assertIs(self.boundary.terminal(result['id'])['lifecycle']['usage_sent'], True)


if __name__ == '__main__':
    unittest.main()
