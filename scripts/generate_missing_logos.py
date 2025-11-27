#!/usr/bin/env python3
"""
Generate fallback SVG logos for companies missing real logos.
Converts them to PNG format using cairosvg if available.
"""

import os
import json
import hashlib
from pathlib import Path

def ticker_to_color(ticker):
    """Generate a consistent color for a ticker"""
    hash_val = int(hashlib.md5(ticker.encode()).hexdigest()[:6], 16)
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

def convert_svg_to_png(svg_content, output_path):
    """Try to convert SVG to PNG using cairosvg"""
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg_content.encode(), write_to=str(output_path))
        return True
    except Exception as e:
        # cairosvg not available, just save as SVG
        print(f"  ℹ  cairosvg not available, saving as SVG instead")
        return False

def main():
    """Generate fallback logos for missing companies"""
    logo_dir = Path('public/company-logos')
    logo_dir.mkdir(parents=True, exist_ok=True)

    # Load all companies
    with open('companies.json', 'r') as f:
        data = json.load(f)
        companies = data['companies']

    # Find existing PNG logos
    existing_logos = set()
    for f in logo_dir.glob('*.png'):
        existing_logos.add(f.stem)

    # Also check for SVG files
    existing_svgs = set()
    for f in logo_dir.glob('*.svg'):
        existing_svgs.add(f.stem)

    print(f"Found {len(existing_logos)} PNG logos")
    print(f"Found {len(existing_svgs)} SVG logos")
    print(f"Total companies: {len(companies)}")
    print("=" * 60)

    missing = []
    for company in companies:
        ticker_lower = company['ticker'].lower()
        if ticker_lower not in existing_logos and ticker_lower not in existing_svgs:
            missing.append(company['ticker'])

    print(f"Generating {len(missing)} missing logos...\n")

    for ticker in missing:
        print(f"[{missing.index(ticker) + 1}/{len(missing)}] {ticker}...", end=" ", flush=True)

        svg_content = generate_svg_logo(ticker)
        ticker_lower = ticker.lower()

        # Try to save as PNG first
        png_path = logo_dir / f"{ticker_lower}.png"
        if convert_svg_to_png(svg_content, png_path):
            print("✓ PNG")
        else:
            # Fallback to SVG
            svg_path = logo_dir / f"{ticker_lower}.svg"
            with open(svg_path, 'w') as f:
                f.write(svg_content)
            print("✓ SVG")

    print("\n" + "=" * 60)
    print(f"✅ Complete!")
    print(f"   Generated: {len(missing)} logos")
    print(f"   Total available: {len(existing_logos) + len(missing)} PNG, {len(existing_svgs) + len([m for m in missing if not (logo_dir / f'{m.lower()}.png').exists()])} SVG")

if __name__ == "__main__":
    main()
