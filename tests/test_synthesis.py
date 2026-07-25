"""
Tests for the synthesis layer (pipeline/analyzers/synthesis.py).

These run with no database, no AWS credentials and no network — the whole point
of pulling parsing out of ``ClaudeAnalyzer`` was to make the fragile part
testable in isolation.

Run: python3 -m pytest tests/test_synthesis.py -q
     python3 tests/test_synthesis.py          (no pytest installed)
"""
import importlib.util
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# Load synthesis.py directly rather than via ``pipeline.analyzers`` — the
# package __init__ imports ClaudeAnalyzer, which pulls in boto3. Synthesis is
# deliberately dependency-free so it can be tested without AWS installed.
_spec = importlib.util.spec_from_file_location(
    'synthesis', os.path.join(_ROOT, 'pipeline', 'analyzers', 'synthesis.py')
)
synthesis = importlib.util.module_from_spec(_spec)
sys.modules['synthesis'] = synthesis  # dataclasses resolves annotations via sys.modules
_spec.loader.exec_module(synthesis)

SynthesisError = synthesis.SynthesisError
as_key_points = synthesis.as_key_points
as_metrics = synthesis.as_metrics
as_sections = synthesis.as_sections
as_sentiment = synthesis.as_sentiment
as_string_list = synthesis.as_string_list
as_text = synthesis.as_text
extract_json_object = synthesis.extract_json_object
normalize_analysis = synthesis.normalize_analysis


# ---------------------------------------------------------------- extraction

def test_plain_json_parses():
    data, repaired = extract_json_object('{"headline": "Hi", "summary": "There"}')
    assert data['headline'] == 'Hi'
    assert repaired is False


def test_fenced_json_parses():
    text = 'Here is the analysis:\n```json\n{"headline": "Hi"}\n```\nDone.'
    data, repaired = extract_json_object(text)
    assert data['headline'] == 'Hi'
    assert repaired is False


def test_prose_wrapped_json_parses():
    text = 'Sure! {"headline": "Hi", "nested": {"a": [1, 2]}} Hope that helps.'
    data, _ = extract_json_object(text)
    assert data['nested']['a'] == [1, 2]


def test_braces_inside_strings_do_not_confuse_the_scanner():
    text = '{"headline": "Revenue grew {a lot}", "summary": "}{"} trailing'
    data, _ = extract_json_object(text)
    assert data['headline'] == 'Revenue grew {a lot}'
    assert data['summary'] == '}{'


def test_truncated_response_is_repaired_and_keeps_complete_fields():
    # This is the max_tokens case: generation stopped mid-string.
    text = (
        '{"headline": "Strong quarter", '
        '"sections": [{"title": "Financials", "content": "Revenue rose 20%"}], '
        '"conclusion": "The company is well positio'
    )
    data, repaired = extract_json_object(text)
    assert repaired is True
    assert data['headline'] == 'Strong quarter'
    assert data['sections'][0]['title'] == 'Financials'
    assert 'conclusion' not in data  # dropped: it was never complete


def test_truncation_inside_a_nested_array_keeps_earlier_elements():
    """
    Repair rewinds to the last *complete* value, which may be a key/value pair
    inside the partially written element — so the trailing element can survive
    with only the fields that finished. as_sections() then drops it for having
    no body, which is why recovering as much as possible is safe here.
    """
    text = (
        '{"headline": "H", "sections": ['
        '{"title": "A", "content": "aaa"}, '
        '{"title": "B", "content": "bbb"}, '
        '{"title": "C", "content": "cc'
    )
    data, repaired = extract_json_object(text)
    assert repaired is True
    assert [s['title'] for s in data['sections'][:2]] == ['A', 'B']
    assert data['sections'][0]['content'] == 'aaa'
    assert [s['title'] for s in as_sections(data['sections'])] == ['A', 'B']


def test_truncated_fenced_response_is_repaired():
    text = '```json\n{"headline": "H", "summary": "S", "intro": "partial te'
    data, repaired = extract_json_object(text)
    assert repaired is True
    assert data['summary'] == 'S'


def test_non_json_response_raises_with_a_preview():
    try:
        extract_json_object("I can't analyze this filing because it appears empty.")
    except SynthesisError as exc:
        assert 'no parsable JSON' in str(exc)
    else:
        raise AssertionError('expected SynthesisError')


def test_empty_response_raises():
    try:
        extract_json_object('   ')
    except SynthesisError as exc:
        assert 'empty' in str(exc)
    else:
        raise AssertionError('expected SynthesisError')


# ----------------------------------------------------------------- coercion

def test_as_text_handles_every_shape_claude_returns():
    assert as_text('  hi  ') == 'hi'
    assert as_text(['a', 'b']) == 'a\n\nb'
    assert as_text({'content': 'inner'}) == 'inner'
    assert as_text(42) == '42'
    assert as_text(None) is None
    assert as_text('') is None
    assert as_text('abcdef', limit=3) == 'abc'


def test_as_key_points_normalizes_strings_and_dicts_alike():
    from_strings = as_key_points(['Revenue grew sharply this quarter'])
    assert from_strings[0]['description'] == 'Revenue grew sharply this quarter'
    assert from_strings[0]['title']  # derived, never empty

    from_dicts = as_key_points([{'title': 'T', 'description': 'D'}])
    assert from_dicts == [{'title': 'T', 'description': 'D'}]

    # Alternate key names the model uses interchangeably.
    assert as_key_points([{'heading': 'T', 'body': 'D'}]) == [{'title': 'T', 'description': 'D'}]

    # A bare object keyed by title.
    assert as_key_points({'Margins': 'Up 200bps'}) == [
        {'title': 'Margins', 'description': 'Up 200bps'}
    ]

    assert as_key_points(None) == []
    assert as_key_points([{}]) == []


def test_as_sections_drops_entries_with_no_body():
    sections = as_sections([
        {'title': 'A', 'content': 'body a'},
        {'title': 'B'},                       # no content -> dropped
        {'title': 'C', 'body': 'body c'},     # alternate key
    ])
    assert [s['title'] for s in sections] == ['A', 'C']
    assert sections[1]['content'] == 'body c'


def test_as_sentiment_accepts_the_formats_seen_in_production():
    assert as_sentiment(0.5) == 0.5
    assert as_sentiment('0.5') == 0.5
    assert as_sentiment('+0.5') == 0.5
    assert as_sentiment('75%') == 0.75
    assert as_sentiment(5) == 1.0        # clamped, not discarded
    assert as_sentiment(-9) == -1.0
    assert as_sentiment('bullish') is None
    assert as_sentiment(None) is None
    assert as_sentiment(True) is None    # bool is not a score


def test_as_string_list_flattens_and_cleans():
    assert as_string_list(['a', '', '  b  ']) == ['a', 'b']
    assert as_string_list('- risk one\n- risk two') == ['risk one', 'risk two']
    assert as_string_list([{'description': 'd'}]) == ['d']
    assert as_string_list(None) == []
    assert as_string_list(['a', 'b', 'c'], limit=2) == ['a', 'b']


def test_as_metrics_stays_json_serializable():
    metrics = as_metrics({
        'revenue': '$57B',
        'growth': {'yoy': 0.62, 'qoq': 0.34},
        'segments': ['DC', 'Gaming'],
        'count': 5,
    })
    json.dumps(metrics)  # must not raise — this column is JSONB
    assert metrics['revenue'] == '$57B'
    assert metrics['growth']['yoy'] == 0.62
    assert metrics['segments'] == 'DC; Gaming'
    assert as_metrics('not a dict') == {}


# ------------------------------------------------------------- normalization

def _deep_response(**overrides):
    payload = {
        'headline': 'NVIDIA rides data center demand',
        'tldr': {
            'summary': 'Revenue rose sharply.',
            'key_points': [{'title': 'Revenue', 'description': 'Up 62% YoY'}],
        },
        'intro': 'Intro paragraph.',
        'sections': [
            {'title': 'Financials', 'content': 'Deep dive.'},
            {'title': 'Strategy', 'content': 'Deep dive.'},
            {'title': 'Market', 'content': 'Deep dive.'},
        ],
        'conclusion': 'Wrap up.',
        'key_metrics': {'revenue': '$57B'},
        'sentiment_score': 0.8,
        'bull_case': 'Dominant AI position',
        'bear_case': 'Supply constraints',
        'risk_factors': ['Concentration risk'],
        'opportunities': ['Inference workloads'],
    }
    payload.update(overrides)
    return payload


def test_normalize_deep_response_produces_the_canonical_shape():
    normalized, report = normalize_analysis(_deep_response(), deep=True)
    assert normalized['headline'].startswith('NVIDIA')
    assert normalized['summary'] == 'Revenue rose sharply.'
    assert normalized['key_points'][0]['title'] == 'Revenue'
    assert len(normalized['sections']) == 3
    assert normalized['sentiment_score'] == 0.8
    assert report.missing_fields == []


def test_normalize_falls_back_to_intro_when_tldr_is_missing():
    payload = _deep_response()
    del payload['tldr']
    normalized, report = normalize_analysis(payload, deep=True)
    assert normalized['summary'].startswith('Intro paragraph')
    assert 'tldr_summary<-intro' in report.coerced_fields
    assert 'tldr_key_points<-sections' in report.coerced_fields


def test_normalize_derives_a_headline_when_the_model_omits_one():
    payload = _deep_response()
    del payload['headline']
    normalized, report = normalize_analysis(payload, deep=True)
    assert normalized['headline']
    assert 'headline<-summary' in report.coerced_fields


def test_normalize_reports_but_tolerates_a_short_truncated_analysis():
    payload = _deep_response(sections=[{'title': 'A', 'content': 'x'}], conclusion=None)
    normalized, report = normalize_analysis(payload, deep=True, repaired=True)
    assert report.repaired_json is True
    assert 'conclusion' in report.missing_fields
    assert any('only 1 sections' in w for w in report.warnings)
    assert normalized['summary']  # still usable


def test_normalize_rejects_a_response_with_no_usable_content():
    try:
        normalize_analysis({'key_metrics': {'revenue': '$1'}}, deep=True)
    except SynthesisError as exc:
        assert 'headline' in str(exc)
    else:
        raise AssertionError('expected SynthesisError')


def test_normalize_rejects_a_headline_with_no_body():
    try:
        normalize_analysis({'headline': 'Just a title'}, deep=True)
    except SynthesisError as exc:
        assert 'no body content' in str(exc)
    else:
        raise AssertionError('expected SynthesisError')


def test_quick_summary_reads_flat_fields():
    payload = {
        'headline': 'Solid quarter',
        'summary': 'Everything grew.',
        'key_points': ['Revenue up', 'Margins up'],
        'sentiment_score': '0.4',
        'key_metrics': {'revenue': '$1B'},
    }
    normalized, report = normalize_analysis(payload, deep=False)
    assert normalized['summary'] == 'Everything grew.'
    assert len(normalized['key_points']) == 2
    assert normalized['sentiment_score'] == 0.4
    # Deep-only fields are not reported missing for a quick summary.
    assert 'sections' not in report.missing_fields


def test_end_to_end_truncated_bedrock_response_still_yields_content():
    """The regression this whole module exists for."""
    raw = (
        '```json\n'
        '{"headline": "Meta doubles down on AI capex", '
        '"tldr": {"summary": "Capex guidance raised.", '
        '"key_points": [{"title": "Capex", "description": "Up 40%"}]}, '
        '"intro": "Meta entered the quarter...", '
        '"sections": [{"title": "Financials", "content": "Revenue of $40B..."}], '
        '"conclusion": "Investors should watch the depreciation sched'
    )
    data, repaired = extract_json_object(raw)
    normalized, report = normalize_analysis(data, deep=True, repaired=repaired)

    assert repaired is True
    assert normalized['headline'] == 'Meta doubles down on AI capex'
    assert normalized['summary'] == 'Capex guidance raised.'
    assert normalized['sections'][0]['title'] == 'Financials'
    assert 'conclusion' in report.missing_fields


def _run_without_pytest():
    tests = [
        (name, obj) for name, obj in sorted(globals().items())
        if name.startswith('test_') and callable(obj)
    ]
    failures = []
    for name, fn in tests:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - this is a test runner
            failures.append((name, exc))
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok   {name}")

    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(_run_without_pytest())
