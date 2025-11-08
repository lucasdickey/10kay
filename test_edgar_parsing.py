#!/usr/bin/env python3
"""
Test SEC EDGAR page parsing to understand structure
"""
import requests
from bs4 import BeautifulSoup

# Test with Apple's CIK
cik = "0000320193"
url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=exclude&count=5"

headers = {
    'User-Agent': '10KAY Test (contact@10kay.com)',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'www.sec.gov'
}

print("Fetching:", url)
print()

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

# Find the filings table
table = soup.find('table', {'class': 'tableFile2'})

if table:
    print("Found filings table!")
    print()

    rows = table.find_all('tr')[1:3]  # Get first 2 filing rows

    for i, row in enumerate(rows, 1):
        print(f"Filing {i}:")
        print("-" * 60)
        cols = row.find_all('td')

        if len(cols) >= 5:
            print(f"Column 0 (Form Type): {cols[0].text.strip()}")
            print(f"Column 1 (Documents): ", end="")
            doc_link = cols[1].find('a')
            if doc_link:
                print(f"<a href='{doc_link.get('href')}' id='{doc_link.get('id')}'>")
                print(f"  Link text: {doc_link.text.strip()}")
            print(f"Column 2 (Description): {cols[2].text.strip()}")
            print(f"Column 3 (Filing Date): {cols[3].text.strip()}")
            print(f"Column 4 (File/Film Number): {cols[4].text.strip()}")

            # Check if there are more columns
            if len(cols) > 5:
                print(f"Column 5+: ", [c.text.strip() for c in cols[5:]])

        print()
else:
    print("No filings table found!")
