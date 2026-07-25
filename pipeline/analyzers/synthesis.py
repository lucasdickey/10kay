"""
Synthesis: turning Claude's response into a validated ``AnalysisResult``.

The analyzer used to do this::

    analysis_data = json.loads(response['text'])   # or a regex for ``` fences
    result = AnalysisResult(
        tldr_headline=analysis_data['headline'],   # KeyError -> whole filing lost
        deep_intro=analysis_data['intro'],
        deep_sections=analysis_data['sections'],
    )

Three things go wrong with that, and all three are the *common* case, not the
edge case:

1. **Truncation.** The deep-analysis prompt asks for 2000-3000 words. Once the
   response hits ``max_tokens`` the JSON simply stops mid-string, ``json.loads``
   raises, and a filing that cost real Bedrock tokens is thrown away. This
   module repairs a truncated object by closing the open string and brackets at
   the last complete value, so a long-but-cut-off analysis is still usable.

2. **Shape drift.** ``key_points`` comes back sometimes as ``["a", "b"]`` and
   sometimes as ``[{"title": ..., "description": ...}]``; ``sections`` sometimes
   uses ``content`` and sometimes ``body``; ``sentiment_score`` arrives as
   ``0.5``, ``"0.5"``, ``"+0.5"`` or ``"75%"``. Coercers normalize each into one
   shape so downstream renderers do not need ``isinstance`` checks.

3. **Silent partial data.** A missing ``conclusion`` should be a warning; a
   missing headline *and* summary should be a hard failure. ``validate()``
   separates the two, so incomplete-but-useful analyses get stored with their
   gaps recorded in ``key_takeaways.synthesis`` instead of being discarded.

Everything here is pure Python with no database or AWS dependency, which is what
makes it directly testable — see ``tests/test_synthesis.py``.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

__all__ = [
    'SynthesisError',
    'SynthesisReport',
    'extract_json_object',
    'normalize_analysis',
    'as_text',
    'as_key_points',
    'as_sections',
    'as_sentiment',
    'as_string_list',
    'as_metrics',
]

#: Longest value we will keep for a short field like bull_case/bear_case.
SHORT_FIELD_LIMIT = 400

_FENCE_RE = re.compile(r'```(?:json|JSON)?\s*(.*?)```', re.DOTALL)
_PERCENT_RE = re.compile(r'^([+-]?\d+(?:\.\d+)?)\s*%$')


class SynthesisError(Exception):
    """The model response could not be turned into usable structured data."""


@dataclass
class SynthesisReport:
    """
    What normalization had to do to the response.

    Persisted alongside the analysis so data-quality problems are queryable
    (``key_takeaways->'synthesis'``) instead of living only in a log line that
    scrolled past three weeks ago.
    """

    repaired_json: bool = False
    missing_fields: List[str] = field(default_factory=list)
    coerced_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (
            self.repaired_json
            or self.missing_fields
            or self.coerced_fields
            or self.warnings
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'repaired_json': self.repaired_json,
            'missing_fields': self.missing_fields,
            'coerced_fields': self.coerced_fields,
            'warnings': self.warnings,
        }


# --------------------------------------------------------------------------
# JSON extraction and repair
# --------------------------------------------------------------------------

def extract_json_object(text: str) -> Tuple[Dict[str, Any], bool]:
    """
    Pull a JSON object out of a model response.

    Returns ``(data, repaired)`` where ``repaired`` is True if the response was
    truncated and had to be closed off.

    Strategies, in order:

    1. Parse the whole response.
    2. Parse the contents of a ``` fence.
    3. Parse the first balanced ``{...}`` span, ignoring braces inside strings.
    4. Repair a truncated object by rewinding to the last complete value and
       closing the open containers.

    Raises ``SynthesisError`` if none of these yield an object.
    """
    if not text or not text.strip():
        raise SynthesisError("Model returned an empty response")

    for candidate in _candidate_payloads(text):
        parsed = _try_parse_object(candidate)
        if parsed is not None:
            return parsed, False

    # Nothing parsed cleanly; the response is most likely cut off mid-value.
    for candidate in _candidate_payloads(text):
        repaired = _repair_truncated_object(candidate)
        if repaired is not None:
            log.warning(
                "Repaired a truncated JSON response (%d chars); "
                "raise max_tokens if this recurs",
                len(candidate),
            )
            return repaired, True

    preview = text.strip()[:300]
    raise SynthesisError(
        f"Response contained no parsable JSON object. First 300 chars: {preview!r}"
    )


def _candidate_payloads(text: str) -> List[str]:
    """Ordered list of substrings that might be the JSON payload."""
    candidates: List[str] = [text.strip()]

    for match in _FENCE_RE.finditer(text):
        inner = match.group(1).strip()
        if inner:
            candidates.append(inner)

    # An unterminated fence (```json with no closing fence) is what truncation
    # usually looks like, so take everything after the opening fence too.
    fence_start = text.find('```')
    if fence_start != -1:
        tail = text[fence_start + 3:]
        tail = re.sub(r'^(?:json|JSON)\s*', '', tail).strip()
        if tail:
            candidates.append(tail)

    brace = text.find('{')
    if brace != -1:
        candidates.append(text[brace:].strip())

    # Preserve order, drop duplicates.
    seen = set()
    unique = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _try_parse_object(candidate: str) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        span = _balanced_object_span(candidate)
        if span is None:
            return None
        try:
            value = json.loads(span)
        except (json.JSONDecodeError, ValueError):
            return None
    return value if isinstance(value, dict) else None


def _balanced_object_span(text: str) -> Optional[str]:
    """Return the first complete ``{...}`` span, respecting strings and escapes."""
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in '{[':
            depth += 1
        elif char in '}]':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]

    return None


def _repair_truncated_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Close off a JSON object that was cut off mid-generation.

    One pass records every position where a *complete* value ends, along with
    the closers needed at that point. Then we walk those checkpoints newest
    first, append the closers, and take the first prefix that parses — i.e. the
    most content we can keep. Checkpoints are capped so a huge malformed blob
    cannot turn this into a quadratic scan.
    """
    start = text.find('{')
    if start == -1:
        return None

    stack: List[str] = []
    checkpoints: List[Tuple[int, str]] = []  # (cut index, closing suffix)
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
                # A closed string is a complete value if it is not a key; we
                # cannot tell yet, so rely on the ',' and '}' checkpoints.
            continue

        if char == '"':
            in_string = True
        elif char == '{':
            stack.append('}')
        elif char == '[':
            stack.append(']')
        elif char in '}]':
            if stack:
                stack.pop()
            # Everything up to and including this bracket is complete.
            checkpoints.append((index + 1, ''.join(reversed(stack))))
        elif char == ',':
            # Everything before the comma is complete.
            checkpoints.append((index, ''.join(reversed(stack))))

    if not checkpoints:
        return None

    for cut, closers in reversed(checkpoints[-400:]):
        candidate = text[start:cut].rstrip().rstrip(',')
        try:
            value = json.loads(candidate + closers)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            return value

    return None


# --------------------------------------------------------------------------
# Field coercion
# --------------------------------------------------------------------------

def as_text(value: Any, *, joiner: str = '\n\n', limit: Optional[int] = None) -> Optional[str]:
    """
    Coerce any model output into a text block.

    Handles the shapes Claude actually returns for a "string" field: a string, a
    list of paragraphs, a ``{"content": ...}`` wrapper, or a number.
    """
    text: Optional[str]

    if value is None:
        text = None
    elif isinstance(value, str):
        text = value.strip() or None
    elif isinstance(value, (int, float)):
        text = str(value)
    elif isinstance(value, list):
        parts = [as_text(item, joiner=joiner) for item in value]
        text = joiner.join(p for p in parts if p) or None
    elif isinstance(value, dict):
        for key in ('content', 'text', 'description', 'body', 'summary'):
            if key in value:
                return as_text(value[key], joiner=joiner, limit=limit)
        parts = [as_text(item, joiner=joiner) for item in value.values()]
        text = joiner.join(p for p in parts if p) or None
    else:
        text = str(value).strip() or None

    if text and limit and len(text) > limit:
        text = text[:limit].rstrip()
    return text


def as_key_points(value: Any) -> List[Dict[str, str]]:
    """
    Normalize key points to ``[{"title": ..., "description": ...}]``.

    Accepts a list of strings, a list of dicts under various key names, or a
    single dict keyed by title. The renderers already branch on str-vs-dict;
    normalizing here lets that branch eventually go away.
    """
    if value is None:
        return []

    if isinstance(value, dict):
        return [
            {'title': str(title), 'description': as_text(body) or ''}
            for title, body in value.items()
        ]

    if isinstance(value, str):
        text = value.strip()
        return [{'title': _headline_from(text), 'description': text}] if text else []

    if not isinstance(value, list):
        return []

    points: List[Dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                points.append({'title': _headline_from(text), 'description': text})
        elif isinstance(item, dict):
            title = as_text(
                item.get('title') or item.get('heading') or item.get('name')
            )
            description = as_text(
                item.get('description') or item.get('content')
                or item.get('detail') or item.get('body') or item.get('text')
            )
            if not title and not description:
                continue
            if not description:
                description = title or ''
            if not title:
                title = _headline_from(description)
            points.append({'title': title, 'description': description})

    return points


def as_sections(value: Any) -> List[Dict[str, str]]:
    """Normalize deep-analysis sections to ``[{"title": ..., "content": ...}]``."""
    if value is None:
        return []

    if isinstance(value, dict):
        return [
            {'title': str(title), 'content': as_text(body) or ''}
            for title, body in value.items()
            if as_text(body)
        ]

    if not isinstance(value, list):
        text = as_text(value)
        return [{'title': 'Analysis', 'content': text}] if text else []

    sections: List[Dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                sections.append({'title': _headline_from(text), 'content': text})
        elif isinstance(item, dict):
            title = as_text(item.get('title') or item.get('heading') or item.get('name'))
            content = as_text(
                item.get('content') or item.get('body')
                or item.get('text') or item.get('description')
            )
            if not content:
                continue
            sections.append({'title': title or _headline_from(content), 'content': content})

    return sections


def as_sentiment(value: Any) -> Optional[float]:
    """
    Coerce a sentiment score into ``[-1.0, 1.0]``.

    Accepts floats, numeric strings, ``"+0.5"``, and percentages (``"75%"`` ->
    0.75). Anything out of range is clamped rather than dropped: a model that
    says ``5`` means "very positive", and storing None loses that.
    """
    if value is None or isinstance(value, bool):
        return None

    number: Optional[float] = None

    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip()
        percent = _PERCENT_RE.match(text)
        if percent:
            number = float(percent.group(1)) / 100.0
        else:
            try:
                number = float(text.lstrip('+'))
            except ValueError:
                return None

    if number is None:
        return None
    return max(-1.0, min(1.0, number))


def as_string_list(value: Any, *, limit: Optional[int] = None) -> List[str]:
    """Coerce risk factors / opportunities into a flat list of non-empty strings."""
    if value is None:
        return []

    items: List[str] = []

    if isinstance(value, str):
        # A model that ignored the array instruction returns newline-separated text.
        items = [line.strip(' -*\t') for line in value.split('\n')]
    elif isinstance(value, dict):
        items = [as_text(v) or '' for v in value.values()]
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                items.append(item)
            else:
                items.append(as_text(item) or '')
    else:
        items = [str(value)]

    cleaned = [item.strip() for item in items if item and item.strip()]
    return cleaned[:limit] if limit else cleaned


def as_metrics(value: Any) -> Dict[str, Any]:
    """
    Normalize ``key_metrics`` into a JSON-safe dict.

    Nested groups (``growth_indicators``) are kept one level deep; anything
    deeper or non-serializable is stringified, because this lands in a JSONB
    column and a stray object would fail the write after the tokens were spent.
    """
    if not isinstance(value, dict):
        return {}

    metrics: Dict[str, Any] = {}
    for key, raw in value.items():
        name = str(key)
        if isinstance(raw, (str, int, float)) and not isinstance(raw, bool):
            metrics[name] = raw
        elif isinstance(raw, bool) or raw is None:
            metrics[name] = raw
        elif isinstance(raw, dict):
            metrics[name] = {
                str(k): v if isinstance(v, (str, int, float, bool, type(None))) else as_text(v)
                for k, v in raw.items()
            }
        elif isinstance(raw, list):
            metrics[name] = as_text(raw, joiner='; ')
        else:
            metrics[name] = str(raw)

    return metrics


def _headline_from(text: str, words: int = 8) -> str:
    """Derive a short title from a body of text when the model omitted one."""
    tokens = text.replace('\n', ' ').split()
    if not tokens:
        return 'Key Point'
    title = ' '.join(tokens[:words]).rstrip('.,;:')
    return title


# --------------------------------------------------------------------------
# Whole-response normalization
# --------------------------------------------------------------------------

def normalize_analysis(
    data: Dict[str, Any],
    *,
    deep: bool,
    repaired: bool = False,
) -> Tuple[Dict[str, Any], SynthesisReport]:
    """
    Turn a parsed response into the canonical field set, with a quality report.

    ``deep`` selects the deep-analysis schema (``tldr`` nested object, ``intro``,
    ``sections``, ``conclusion``) versus the quick-summary schema (flat
    ``summary`` and ``key_points``).

    A response is usable when it has a headline *or* a summary and at least some
    body text. Anything less raises ``SynthesisError`` — storing a content row
    whose ``executive_summary`` is empty would violate NOT NULL anyway, and
    would render as a blank page if it did not.
    """
    if not isinstance(data, dict):
        raise SynthesisError(f"Expected a JSON object, got {type(data).__name__}")

    report = SynthesisReport(repaired_json=repaired)

    tldr_block = data.get('tldr') if deep else data
    if not isinstance(tldr_block, dict):
        tldr_block = data
        if deep:
            report.warnings.append("deep response had no 'tldr' object; read from top level")

    headline = as_text(data.get('headline') or data.get('title'), limit=SHORT_FIELD_LIMIT)
    summary = as_text(tldr_block.get('summary') or data.get('summary'))
    intro = as_text(data.get('intro') or data.get('introduction'))
    conclusion = as_text(data.get('conclusion') or data.get('synthesis'))
    sections = as_sections(data.get('sections'))
    key_points = as_key_points(tldr_block.get('key_points') or data.get('key_points'))

    # A deep response with no summary can still be published off its intro.
    if deep and not summary and intro:
        summary = intro[:1000]
        report.coerced_fields.append('tldr_summary<-intro')
    if deep and not key_points and sections:
        key_points = [
            {'title': section['title'], 'description': section['content'][:600]}
            for section in sections[:5]
        ]
        report.coerced_fields.append('tldr_key_points<-sections')
    if not headline and summary:
        headline = _headline_from(summary, words=12)
        report.coerced_fields.append('headline<-summary')

    normalized = {
        'headline': headline,
        'summary': summary,
        'key_points': key_points,
        'intro': intro,
        'sections': sections,
        'conclusion': conclusion,
        'key_metrics': as_metrics(data.get('key_metrics')),
        'sentiment_score': as_sentiment(data.get('sentiment_score') or data.get('sentiment')),
        'bull_case': as_text(data.get('bull_case'), limit=SHORT_FIELD_LIMIT),
        'bear_case': as_text(data.get('bear_case'), limit=SHORT_FIELD_LIMIT),
        'risk_factors': as_string_list(data.get('risk_factors') or data.get('risks')),
        'opportunities': as_string_list(data.get('opportunities')),
    }

    _record_gaps(normalized, deep=deep, report=report)

    if not normalized['headline'] and not normalized['summary']:
        raise SynthesisError(
            "Response has neither a headline nor a summary; "
            f"keys present: {sorted(data.keys())[:15]}"
        )

    body_present = bool(
        normalized['summary'] or normalized['intro']
        or normalized['sections'] or normalized['key_points']
    )
    if not body_present:
        raise SynthesisError(
            "Response has a headline but no body content "
            "(no summary, intro, sections or key points)"
        )

    return normalized, report


def _record_gaps(normalized: Dict[str, Any], *, deep: bool, report: SynthesisReport) -> None:
    """Note which optional fields the model skipped, without failing the run."""
    expected = ['headline', 'summary', 'key_points', 'key_metrics', 'sentiment_score']
    if deep:
        expected += ['intro', 'sections', 'conclusion', 'risk_factors', 'opportunities']

    for name in expected:
        value = normalized.get(name)
        if value is None or (isinstance(value, (list, dict, str)) and not value):
            report.missing_fields.append(name)

    if normalized['sentiment_score'] is None:
        report.warnings.append('no sentiment score returned; UI will render as neutral')
    if deep and len(normalized['sections']) < 3:
        report.warnings.append(
            f"deep analysis returned only {len(normalized['sections'])} sections (expected 5)"
        )
