# -*- coding: utf-8 -*-
"""
Created on Wed May  7 14:58:05 2025

@author: havfyh
"""

import json
import re

def extract_and_write_variables(html_str, fylkesfil="fylker.py", kommunefil="kommuner.py"):
    # Finn JSON-strengen i 'table-data'-attributtet
    match = re.search(r'table-data="([^"]+)"', html_str)
    if not match:
        raise ValueError("Fant ikke table-data i HTML-strengen.")
    
    json_data_str = match.group(1)
    
    # Erstatt HTML escape-tegn
    json_data_str = json_data_str.replace('&quot;', '"').replace('&nbsp;', ' ')
    
    # Last inn som JSON
    data = json.loads(json_data_str)
    print(data)
    fylker = {}
    kommuner = {}

    for entry in data:
        fylkesnavn = entry.get("Fylkesnamn").split('–')[0].split('-')[0].strip()
        fylkesnr = int(float(entry.get("Fylkesnr. ")))
        
        print(fylkesnavn, fylkesnr)
        kommunenavn = entry.get("Kommunenamn").split('–')[0].split('-')[0].strip()
        kommunenr = int(float(entry.get("Kommunenr.")))

        # Legg til fylke hvis ikke allerede lagt til
        fylker[fylkesnavn] = fylkesnr
        kommuner[kommunenavn] = kommunenr
        print(fylkesnavn, fylkesnr, kommunenavn, kommunenr)
    # Skriv fylkesfil
    with open(fylkesfil, 'w', encoding='utf-8') as f:
        for navn, nummer in sorted(fylker.items()):
            varnavn = navn.replace(" ", "_")
            f.write(f'{varnavn} = {nummer}\n')

    # Skriv kommunefil
    with open(kommunefil, 'w', encoding='utf-8') as f:
        for navn, nummer in sorted(kommuner.items()):
            varnavn = navn.replace(" ", "_")
            f.write(f'{varnavn} = {nummer}\n')

    print(f"Skrev fylkesvariabler til {fylkesfil} og kommunevariabler til {kommunefil}.")


html = open(r"C:\python\nvdbapi-V3-master\fylkestabell.txt")
html_string = html.read()

extract_and_write_variables(html_string)