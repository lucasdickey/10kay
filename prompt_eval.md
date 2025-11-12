# Prompt Evaluation Log

This document tracks changes to the prompts used for generating financial analysis to evaluate their effectiveness over time.

## Change Details

- **Date:** 2025-11-12
- **Engineer:** Jules
- **Reason for Change:** To improve the quality and clarity of the generated analysis based on user feedback.

## Summary of Changes

1.  **ARR Acronym:** Ensured that "Arr" is always capitalized as "ARR" when referring to Annual Recurring Revenue.
2.  **Product Descriptions:** Added a requirement for brief descriptions of named products (e.g., Shop Pay, Plus) to provide context for readers.
3.  **Gross Value for Percentages:** Mandated the inclusion of gross values alongside percentages for large KPIs to add necessary context.
4.  **Clarity in "Bottom Line":** Updated the "Bottom Line" (conclusion) section to avoid vague business jargon (e.g., "headwinds") and instead provide specific, impactful details.

## Original DEEP_ANALYSIS Prompt

```python
# Deep analysis prompt (paid tier)
prompt = f"""Perform a comprehensive, substantive analysis of this {filing_type} filing for {company_name} ({fiscal_period}). This should be a 5-7 minute read with deep insights.

**Context:**
- Company: {company_name} ({{filing_metadata['ticker']}})
- Filing: {filing_type} for {fiscal_period} {{filing_metadata['fiscal_year']}}
- Filing Date: {{filing_metadata['filing_date']}}

**Filing Sections:**
{self._format_sections_for_prompt(sections)}

**Task:**
Generate a deep analysis in JSON format:
{{
  "headline": "Compelling headline (8-15 words)",
  "tldr": {{
    "summary": "4-6 sentence overview providing substantive context. Start with the headline insight, then explain what changed and why it matters. Include 2-3 specific metrics or examples. End with forward-looking implications.",
    "key_points": [
      {{
        "title": "Financial Performance Overview",
        "description": "Full paragraph (4-6 sentences) with headline insight and specific YoY/QoQ numbers. Explain margin trends and growth drivers with basis point changes. Include segment-level details. Discuss sustainability of metrics and changes from prior periods. End with implications for future trajectory."
      }},
      {{
        "title": "Strategic Initiatives and Operational Changes",
        "description": "Full paragraph (4-6 sentences) describing operational or strategic shifts. Explain why management made these changes and competitive implications. Include forward-looking indicators from commentary. Connect strategy to financial performance. Discuss execution risks and timeline."
      }},
      {{
        "title": "Market Position and Competitive Dynamics",
        "description": "Full paragraph (4-6 sentences) analyzing market share trends and positioning. Discuss customer concentration and retention metrics. Explain TAM expansion opportunities. Include competitive threats and advantages. Assess how the company is gaining or losing ground."
      }},
      {{
        "title": "Operational Efficiency and Profitability",
        "description": "Full paragraph (4-6 sentences) explaining operational leverage and cost structure. Discuss efficiency improvements or headwinds. Analyze gross and operating margin trends. Include productivity metrics if available. Assess sustainability of profitability improvements."
      }},
      {{
        "title": "Growth Catalysts and Material Risks",
        "description": "Full paragraph (4-6 sentences) identifying near and medium-term growth drivers. Discuss macro headwinds or tailwinds. Explain key risks material to investment thesis. Assess management's mitigation strategies. Provide forward-looking perspective on key metrics."
      }}
    ]
  }},
  "intro": "4-6 substantive paragraphs (250-350 words total) setting up the key themes. Start with the headline insight in context. Explain what changed YoY/QoQ with specific numbers. Identify 2-3 major themes. Provide competitive context. End with what this means for the business trajectory.",
  "sections": [
    {{
      "title": "Financial Performance Deep Dive",
      "content": "6-8 paragraphs (400-600 words). Break down revenue by segment with YoY/QoQ trends. Analyze margin expansion/compression with drivers. Discuss cash flow and capital allocation. Compare to peers. Identify inflection points or concerning trends. Include specific numbers, percentages, and basis point changes throughout."
    }},
    {{
      "title": "Strategic Shifts and Product Evolution",
      "content": "6-8 paragraphs (400-600 words). Analyze new product launches, R&D investments, strategic pivots. Discuss go-to-market changes. Examine partnerships and M&A. Connect product strategy to financials. Assess competitive positioning. Include forward-looking indicators from management commentary."
    }},
    {{
      "title": "Market Dynamics and Competitive Position",
      "content": "5-7 paragraphs (350-500 words). Assess market share trends. Analyze competitive threats and advantages. Discuss regulatory environment. Examine customer concentration and churn. Include macroeconomic factors affecting the business."
    }},
    {{
      "title": "Risk Factors and Headwinds",
      "content": "5-7 paragraphs (350-500 words). Deep dive into material risks from filing. Assess likelihood and potential impact. Discuss management's mitigation strategies. Compare to prior periods. Include second-order effects."
    }},
    {{
      "title": "Growth Opportunities and Catalysts",
      "content": "5-7 paragraphs (350-500 words). Identify untapped markets and expansion opportunities. Analyze operational leverage potential. Discuss innovation pipeline. Assess M&A potential. Include TAM analysis where relevant."
    }}
  ],
  "conclusion": "5-6 paragraphs (300-400 words) synthesizing insights and forward-looking implications. Recap the 2-3 most important themes. Assess whether the business is accelerating or decelerating. Identify key metrics to watch in next quarter. Provide actionable takeaways for operators. End with contrarian or non-obvious insight.",
  "key_metrics": {{
    "revenue": "$XXX.XB (±X.X% YoY, ±X.X% QoQ) with segment breakdown and trend analysis",
    "gross_margin": "XX.X% (±XXbps YoY) with drivers explanation",
    "operating_margin": "XX.X% (±XXbps YoY) with efficiency analysis",
    "free_cash_flow": "$XXB (±X% YoY) with conversion rate",
    "growth_indicators": {{
      "customer_count": "details with growth rate",
      "arr_or_bookings": "details with trends",
      "retention_metrics": "details with cohort analysis"
    }},
    // 8-12 critical metrics total with full context
  }},
  "sentiment_score": 0.5,
  "risk_factors": [
    "Specific risk 1 with quantified impact assessment",
    "Specific risk 2 with likelihood and mitigation strategy",
    "Specific risk 3 with industry context",
    "Specific risk 4 if material"
  ],
  "opportunities": [
    "Specific opportunity 1 with TAM/market size context",
    "Specific opportunity 2 with timeline and barriers to entry",
    "Specific opportunity 3 with competitive advantage analysis",
    "Specific opportunity 4 if material"
  ]
}}

**Analysis Framework:**
1. **What Changed**: YoY/QoQ comparisons, inflection points, trend reversals
2. **Why It Matters**: Strategic implications, competitive dynamics, market share shifts
3. **What's Next**: Forward-looking indicators, management guidance, pipeline visibility
4. **The Nuance**: What others might miss, second-order effects, non-obvious correlations
5. **The Contrarian Take**: Challenge conventional wisdom, identify misunderstood aspects

**Style Guide:**
- Tone: Bloomberg Terminal meets Stratechery - authoritative, insightful, opinionated, substantive
- Audience: Sophisticated tech operators, founders, investors who want deep understanding
- Length: Each section should be 350-600 words for a total 5-7 minute read (2000-3000 words)
- Focus: Strategic narrative woven with numbers, not just data dumps
- Include: Specific figures, YoY/QoQ comparisons, segment breakdowns, direct quotes, concrete examples
- Avoid: Hedging language, surface-level observations, obvious points, filler content

**Critical**: This is PAID tier content. Make it substantially deeper and more insightful than a free summary.

Respond with only valid JSON, no additional text."""
```

## Modified DEEP_ANALYSIS Prompt

```python
# Deep analysis prompt (paid tier)
prompt = f"""Perform a comprehensive, substantive analysis of this {filing_type} filing for {company_name} ({fiscal_period}). This should be a 5-7 minute read with deep insights.

**Context:**
- Company: {company_name} ({{filing_metadata['ticker']}})
- Filing: {filing_type} for {fiscal_period} {{filing_metadata['fiscal_year']}}
- Filing Date: {{filing_metadata['filing_date']}}

**Filing Sections:**
{self._format_sections_for_prompt(sections)}

**Task:**
Generate a deep analysis in JSON format:
{{
  "headline": "Compelling headline (8-15 words)",
  "tldr": {{
    "summary": "4-6 sentence overview providing substantive context. Start with the headline insight, then explain what changed and why it matters. Include 2-3 specific metrics or examples. End with forward-looking implications.",
    "key_points": [
      {{
        "title": "Financial Performance Overview",
        "description": "Full paragraph (4-6 sentences) with headline insight and specific YoY/QoQ numbers. Explain margin trends and growth drivers with basis point changes. Include segment-level details. Discuss sustainability of metrics and changes from prior periods. End with implications for future trajectory."
      }},
      {{
        "title": "Strategic Initiatives and Operational Changes",
        "description": "Full paragraph (4-6 sentences) describing operational or strategic shifts. Explain why management made these changes and competitive implications. Include forward-looking indicators from commentary. Connect strategy to financial performance. Discuss execution risks and timeline."
      }},
      {{
        "title": "Market Position and Competitive Dynamics",
        "description": "Full paragraph (4-6 sentences) analyzing market share trends and positioning. Discuss customer concentration and retention metrics. Explain TAM expansion opportunities. Include competitive threats and advantages. Assess how the company is gaining or losing ground."
      }},
      {{
        "title": "Operational Efficiency and Profitability",
        "description": "Full paragraph (4-6 sentences) explaining operational leverage and cost structure. Discuss efficiency improvements or headwinds. Analyze gross and operating margin trends. Include productivity metrics if available. Assess sustainability of profitability improvements."
      }},
      {{
        "title": "Growth Catalysts and Material Risks",
        "description": "Full paragraph (4-6 sentences) identifying near and medium-term growth drivers. Discuss macro headwinds or tailwinds. Explain key risks material to investment thesis. Assess management's mitigation strategies. Provide forward-looking perspective on key metrics."
      }}
    ]
  }},
  "intro": "4-6 substantive paragraphs (250-350 words total) setting up the key themes. Start with the headline insight in context. Explain what changed YoY/QoQ with specific numbers. Identify 2-3 major themes. Provide competitive context. End with what this means for the business trajectory.",
  "sections": [
    {{
      "title": "Financial Performance Deep Dive",
      "content": "6-8 paragraphs (400-600 words). Break down revenue by segment with YoY/QoQ trends. Analyze margin expansion/compression with drivers. Discuss cash flow and capital allocation. Compare to peers. Identify inflection points or concerning trends. Include specific numbers, percentages, and basis point changes throughout. When a percentage of a KPI is large, present the gross value as well for context."
    }},
    {{
      "title": "Strategic Shifts and Product Evolution",
      "content": "6-8 paragraphs (400-600 words). Analyze new product launches (e.g., Shop Pay, Plus), R&D investments, strategic pivots. When mentioning a product, include a brief, one-sentence description of what it is. Discuss go-to-market changes. Examine partnerships and M&A. Connect product strategy to financials. Assess competitive positioning. Include forward-looking indicators from management commentary."
    }},
    {{
      "title": "Market Dynamics and Competitive Position",
      "content": "5-7 paragraphs (350-500 words). Assess market share trends. Analyze competitive threats and advantages. Discuss regulatory environment. Examine customer concentration and churn. Include macroeconomic factors affecting the business."
    }},
    {{
      "title": "Risk Factors and Headwinds",
      "content": "5-7 paragraphs (350-500 words). Deep dive into material risks from filing. Assess likelihood and potential impact. Discuss management's mitigation strategies. Compare to prior periods. Include second-order effects."
    }},
    {{
      "title": "Growth Opportunities and Catalysts",
      "content": "5-7 paragraphs (350-500 words). Identify untapped markets and expansion opportunities. Analyze operational leverage potential. Discuss innovation pipeline. Assess M&A potential. Include TAM analysis where relevant."
    }}
  ],
  "conclusion": "5-6 paragraphs (300-400 words) synthesizing insights and forward-looking implications. Recap the 2-3 most important themes. Assess whether the business is accelerating or decelerating. Identify key metrics to watch in next quarter. Provide actionable takeaways for operators. End with contrarian or non-obvious insight. Avoid business jargon like 'facing headwinds' and instead provide specific, clarifying details (e.g., consumer spending changes due to employment numbers).",
  "key_metrics": {{
    "revenue": "$XXX.XB (±X.X% YoY, ±X.X% QoQ) with segment breakdown and trend analysis",
    "gross_margin": "XX.X% (±XXbps YoY) with drivers explanation",
    "operating_margin": "XX.X% (±XXbps YoY) with efficiency analysis",
    "free_cash_flow": "$XXB (±X% YoY) with conversion rate",
    "growth_indicators": {{
      "customer_count": "details with growth rate",
      "arr_or_bookings": "details with trends",
      "retention_metrics": "details with cohort analysis"
    }},
    // 8-12 critical metrics total with full context
  }},
  "sentiment_score": 0.5,
  "risk_factors": [
    "Specific risk 1 with quantified impact assessment",
    "Specific risk 2 with likelihood and mitigation strategy",
    "Specific risk 3 with industry context",
    "Specific risk 4 if material"
  ],
  "opportunities": [
    "Specific opportunity 1 with TAM/market size context",
    "Specific opportunity 2 with timeline and barriers to entry",
    "Specific opportunity 3 with competitive advantage analysis",
    "Specific opportunity 4 if material"
  ]
}}

**Analysis Framework:**
1. **What Changed**: YoY/QoQ comparisons, inflection points, trend reversals
2. **Why It Matters**: Strategic implications, competitive dynamics, market share shifts
3. **What's Next**: Forward-looking indicators, management guidance, pipeline visibility
4. **The Nuance**: What others might miss, second-order effects, non-obvious correlations
5. **The Contrarian Take**: Challenge conventional wisdom, identify misunderstood aspects

**Style Guide:**
- Tone: Bloomberg Terminal meets Stratechery - authoritative, insightful, opinionated, substantive
- Audience: Sophisticated tech operators, founders, investors who want deep understanding
- Length: Each section should be 350-600 words for a total 5-7 minute read (2000-3000 words)
- Focus: Strategic narrative woven with numbers, not just data dumps
- Include: Specific figures, YoY/QoQ comparisons, segment breakdowns, direct quotes, concrete examples. 'Arr' should always be 'ARR' when used as an acronym for annual recurring revenue. When a percentage of a KPI is large, present the gross value as well for context.
- Avoid: Hedging language, surface-level observations, obvious points, filler content.

**Critical**: This is PAID tier content. Make it substantially deeper and more insightful than a free summary.

Respond with only valid JSON, no additional text."""
```

## Evaluation Plan

- **Monitor new analyses:** Review the next 5-10 generated analyses for companies with significant product lines and revenue streams to assess the impact of these changes.
- **Check for regressions:** Ensure that the changes have not negatively impacted the overall quality or coherence of the analysis.
- **Gather user feedback:** Solicit feedback from users on the clarity and usefulness of the updated analysis format.

**Success Metrics:**

- **ARR capitalization:** 100% of "ARR" acronyms are capitalized correctly.
- **Product descriptions:** Named products are consistently accompanied by a brief description.
- **Gross value context:** Gross values are included for large percentages where appropriate.
- **"Bottom Line" clarity:** The "Bottom Line" section is free of vague jargon and provides specific, actionable insights.
