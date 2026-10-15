"""Report whether native compaction detaches reasoning from its retained tool batch.

This probe does not enable compaction, generate a summary or contact a provider.
Exit 1 identifies the native boundary gap; it is not part of the passing overlay
suite when qualification explicitly keeps production compaction disabled.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

from verify_context import load_functions, output


def probe(root: Path) -> dict:
    path = root / 'utils/context_compaction.py'
    source = path.read_text(encoding='utf-8')
    names = {'_clamp_retention_percentage', '_find_compaction_boundary'}
    tree = ast.parse(source)
    selected = [node for node in tree.body if getattr(node, 'name', None) in names]
    if len(selected) != len(names):
        raise RuntimeError('Native compaction boundary functions changed')
    namespace = {'Any': object}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    native = load_functions(root)
    messages = [
        {'role': 'system', 'content': 'Keep approved content intact.'},
        {'role': 'user', 'content': 'Format, render and correct the file.'},
        *native['convert_output_to_messages'](
            output(), raw=True, reasoning_format='responses', flatten_tool_images=False),
    ]
    boundary = namespace['_find_compaction_boundary'](messages, retention_percentage=40)
    retained = messages[boundary:]
    retained_calls = [call['id'] for message in retained for call in message.get('tool_calls', [])]
    retained_reasoning = [item['id'] for message in retained for item in message.get('output', [])
                          if item.get('type') == 'reasoning']
    # In this fixed two-round actual-converter sequence rs_second belongs to edit-2.
    lost = ['rs_second'] if 'edit-2' in retained_calls and 'rs_second' not in retained_reasoning else []
    return {
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'boundary': boundary, 'retained_calls': retained_calls,
        'retained_reasoning': retained_reasoning, 'lost_required_reasoning': lost,
        'scope': 'native pure boundary selection, synthetic two-round actual-converter input',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/app/backend/open_webui'))
    args = parser.parse_args()
    result = probe(args.root)
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result['lost_required_reasoning']))
