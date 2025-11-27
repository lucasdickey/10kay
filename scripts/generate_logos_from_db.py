#!/usr/bin/env python3
"""
Generate fallback SVG/PNG logos for all companies in the database.
"""

import os
import psycopg2
import hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('.env.local')

DATABASE_URL = os.getenv('DATABASE_URL')

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

def main():
    """Generate fallback logos for missing companies"""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Get all active companies
    cursor.execute("""
        SELECT ticker FROM companies
        WHERE enabled = true AND status = 'active'
        ORDER BY ticker
    """)

    companies = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    logo_dir = Path('public/company-logos')
    logo_dir.mkdir(parents=True, exist_ok=True)

    # Find existing PNG logos
    existing_logos = set()
    for f in logo_dir.glob('*.png'):
        existing_logos.add(f.stem.lower())

    # Also check for SVG files
    existing_svgs = set()
    for f in logo_dir.glob('*.svg'):
        existing_svgs.add(f.stem.lower())

    print(f"Found {len(existing_logos)} PNG logos")
    print(f"Found {len(existing_svgs)} SVG logos")
    print(f"Total active companies: {len(companies)}")
    print("=" * 60)

    missing = [t for t in companies if t.lower() not in existing_logos and t.lower() not in existing_svgs]

    print(f"Generating {len(missing)} missing logos...\n")

    for i, ticker in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] {ticker}...", end=" ", flush=True)

        svg_content = generate_svg_logo(ticker)
        ticker_lower = ticker.lower()

        # Save as SVG (no dependency on cairosvg)
        svg_path = logo_dir / f"{ticker_lower}.svg"
        with open(svg_path, 'w') as f:
            f.write(svg_content)
        print("✓ SVG")

    print("\n" + "=" * 60)
    print(f"✅ Complete!")
    print(f"   Generated: {len(missing)} logos")
    print(f"   Total PNG: {len(existing_logos)}")
    print(f"   Total SVG: {len(existing_svgs) + len(missing)}")

if __name__ == "__main__":
    main()
