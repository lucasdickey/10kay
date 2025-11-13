#!/usr/bin/env python3
"""
Generate clean SVG logos for companies based on their ticker symbols
"""

import os
import json
import hashlib
from pathlib import Path

def ticker_to_color(ticker):
    """Generate a consistent color for a ticker"""
    # Use hash to get consistent color
    hash_val = int(hashlib.md5(ticker.encode()).hexdigest()[:6], 16)

    # Generate pleasant, muted colors
    hue = hash_val % 360
    saturation = 45 + (hash_val % 20)  # 45-65%
    lightness = 40 + (hash_val % 15)    # 40-55%

    return f"hsl({hue}, {saturation}%, {lightness}%)"

def generate_svg_logo(ticker, size=128):
    """Generate a clean SVG logo for a ticker"""
    bg_color = ticker_to_color(ticker)

    # Font size based on ticker length
    if len(ticker) <= 2:
        font_size = size * 0.5
    elif len(ticker) <= 4:
        font_size = size * 0.4
    else:
        font_size = size * 0.3

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" fill="{bg_color}" rx="{size * 0.15}"/>
  <text
    x="50%"
    y="50%"
    dominant-baseline="central"
    text-anchor="middle"
    font-family="system-ui, -apple-system, sans-serif"
    font-size="{font_size}"
    font-weight="700"
    fill="white"
    letter-spacing="-0.05em"
  >{ticker}</text>
</svg>'''
    return svg

def generate_logos():
    # Load companies
    with open('companies.json', 'r') as f:
        data = json.load(f)
        companies = data['companies']

    # Create logo directory
    logo_dir = Path('public/company-logos')
    logo_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating SVG logos for {len(companies)} companies...")

    for company in companies:
        ticker = company['ticker']
        svg_content = generate_svg_logo(ticker)

        output_path = logo_dir / f"{ticker.lower()}.svg"
        with open(output_path, 'w') as f:
            f.write(svg_content)

        print(f"✓ {ticker}: Generated SVG logo")

    print(f"\n{'='*60}")
    print(f"Generated {len(companies)} SVG logos")
    print(f"Logos saved to: {logo_dir.absolute()}")

if __name__ == "__main__":
    generate_logos()
