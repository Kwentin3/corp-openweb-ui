"""Compare native success receipts to the actual synthetic provider boundary."""
import argparse
import json
from pathlib import Path


def verify(native, provider):
    assert native.get('passed') is True, 'Native proof did not pass'
    assert provider.get('synthetic') is True, 'Expected synthetic provider receipt'
    successes = [call for call in native['calls'] if call['outcome'] == 'success']
    assert len(successes) == 7, 'The declared two-user scenario must complete seven calls'
    requests = provider.get('requests')
    assert isinstance(requests, list), 'Missing provider requests'
    actual = {request['id']: request for request in requests}
    expected = {call['provider_response_id']: call for call in successes}
    assert len(actual) == len(requests), 'Duplicate provider response IDs'
    assert len(expected) == len(successes), 'Duplicate native response IDs'
    assert set(actual) == set(expected), 'Provider calls differ from successful native calls'
    models = {'goal584-a': 'goal584-fake-a', 'goal584-b': 'goal584-fake-b'}
    for response_id, call in expected.items():
        request = actual[response_id]
        body = request['body']
        assert body['model'] == models[call['model']], 'Provider model mismatch'
        assert body['messages'] == [{'role': 'user', 'content': 'Hi'}], 'Provider context mismatch'
        assert body.get('stream', False) is False, 'Unexpected streaming request'
        assert body.get('max_tokens', body.get('max_completion_tokens')) == 5, 'Output cap changed'
        assert request['usage'] == {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}, 'Provider usage mismatch'
    blocked = [call for call in native['calls'] if call['outcome'] == 'budget_blocked']
    assert len(blocked) == 2, 'The declared scenario must reject two further calls'
    assert {call['scope'] for call in blocked} == {'key', 'user'}, 'Both cap failures must be observed'
    return {'passed': True, 'scope': 'Native scalar-budget proof against actual synthetic provider calls',
            'successful_calls': len(successes), 'budget_rejections': len(blocked),
            'unexpected_provider_calls': 0, 'context': 'One synthetic user message; no tool loop or WebUI acceptance'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native', type=Path)
    parser.add_argument('provider', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = verify(json.loads(args.native.read_text(encoding='utf-8')),
                    json.loads(args.provider.read_text(encoding='utf-8')))
    rendered = json.dumps(result, indent=2) + '\n'
    args.receipt.write_text(rendered, encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    main()
