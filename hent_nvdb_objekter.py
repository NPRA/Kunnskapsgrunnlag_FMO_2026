import os
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import MultiLineString, LineString, Point, MultiPoint, MultiPolygon, Polygon

file_dir = os.path.dirname(__file__)

from collections import defaultdict
import re

import nvdbapiv3
import json

import os


print("Ferdig!")
geopackage = r"NAVN PÅ DIN GEOPACKAGE-FIL HER"

with open(file_dir + r'\vegobjekttype.json', 'r', encoding='utf-8') as f:
    vegobjekttype = {value: key for key, value in json.load(f).items()}

with open(file_dir + r'\kommuner.json', 'r', encoding='utf-8') as f:
    kommuner = {value: key for key, value in json.load(f).items()}

with open(file_dir + r'\fylker.json', 'r', encoding='utf-8') as f:
    fylker = {value: key for key, value in json.load(f).items()}




def tolk_geografi(kommune=None, fylke=None, vegsystemreferanse=None):
    kommune_id = fylke_id = None
    vegref = vegsystemreferanse

    if isinstance(kommune, str):
        if kommune in kommuner:
            kommune_id = kommuner[kommune]
        elif kommune in fylker:
            fylke_id = fylker[kommune]
        else:
            vegref = kommune
    elif isinstance(kommune, int):
        if kommune in kommuner.values():
            kommune_id = kommune
        elif kommune in fylker.values():
            fylke_id = kommune
        else:
            raise ValueError(f"Ukjent kommune- eller fylke-ID: {kommune}")

    if isinstance(fylke, str):
        if fylke in fylker:
            fylke_id = fylker[fylke]
        else:
            raise ValueError(f"Ukjent fylke: '{fylke}'")
    elif fylke is not None:
        fylke_id = fylke

    return kommune_id, fylke_id, vegref

def bruk_filter(obj, kommune_id=None, fylke_id=None, vegref=None):
    filters = {}
    if kommune_id:
        filters['kommune'] = kommune_id
    if fylke_id:
        filters['fylke'] = fylke_id
    if vegref:
        filters['vegsystemreferanse'] = vegref
    print(filters)
    obj.filter(filters)


def hent_egenskap(egenskaper, navn):
    for e in egenskaper:
        if e.get("navn") == navn:
            return e.get("verdi")
    return None


def tolk_meterområde(m_str):
    """Tolk meter eller meterområde fra kortform string."""
    match = re.search(r'm(\d+)(?:-(\d+))?', m_str)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else start
    return start, end

def match_objekter(vegref_full, område):
    if vegref_full is None:
        return None
    parts = vegref_full.rsplit(' ', 1)
    if len(parts) != 2:
        return None
    prefix, m_str = parts
    m_point = tolk_meterområde(m_str)
    if not m_point:
        return None
    m_val = m_point[0]

    for start, slutt, grense in område.get(prefix, []):
        if start <= m_val <= slutt:
            return grense
    return None


def hent_vegref(veg):
    segmenter = veg.get("vegsegmenter", [])
    if not segmenter or "kortform" not in segmenter[0].get("vegsystemreferanse", {}):
        return None
    vegref_full = segmenter[0]["vegsystemreferanse"]["kortform"]
    
    
    if vegref_full[0] in ["K", "P", "S"]: 
        vegref_full = str(segmenter[0]["kommune"]) + vegref_full
    return vegref_full 
    
def bygg_område(objekttype, egenskapsnavn, **kwargs):
    data = nvdbapiv3.nvdbFagdata(objekttype)
    kommune_id, fylke_id, vegref = tolk_geografi(**kwargs)
    bruk_filter(data, kommune_id, fylke_id, vegref)

    result = defaultdict(list)

    for entry in data:
        
        vegref_full = hent_vegref(entry)
        if vegref_full is None:
            continue

        parts = vegref_full.rsplit(" ", 1)
        if len(parts) != 2:
            continue

        prefix, m_part = parts
        m_range = tolk_meterområde(m_part)
        if not m_range:
            continue

        verdi = hent_egenskap(entry.get("egenskaper", []), egenskapsnavn)
        result[prefix].append((m_range[0], m_range[1], verdi))

    return result


def lagre_objekt(gdb_path, navn, objekt_str, **kwargs):
    if not isinstance(objekt_str, int):
        objektid = vegobjekttype[objekt_str]
    else: 
        objektid = objekt_str
    sokeobjekt = nvdbapiv3.nvdbFagdata(objektid)

    kommune_id, fylke_id, vegref = tolk_geografi(**kwargs)
    
    bruk_filter(sokeobjekt, kommune_id, fylke_id, vegref)
    objekt = pd.DataFrame(nvdbapiv3.nvdbfagdata2records([o for o in sokeobjekt]))
    def safe_wkt_loads(x):
        try:
            return wkt.loads(x) if pd.notnull(x) else None
        except Exception:
            return None
    
    geom_col = None
    for c in ["geometri", "geometri_wkt", "wkt"]:
        if c in objekt.columns:
            geom_col = c
            break

    if geom_col is None:
        print(f"Objekttype {objektid} har ingen geometri-kolonne")
    else:
        objekt["geometry"] = objekt[geom_col].apply(safe_wkt_loads)


    objekt = gpd.GeoDataFrame(objekt, geometry='geometry', crs=5973)
    valid_types = {
        "Point", "LineString", "Polygon",
        "MultiPoint", "MultiLineString", "MultiPolygon"
    }

    objekt = objekt[
        objekt.geometry.notnull()
        & objekt.geometry.is_valid
        & objekt.geometry.geom_type.isin(valid_types)
    ]
    def normalize_to_linestring(geom):
        if geom is None:
            return None
        if geom.geom_type == "MultiLineString":
            coords = []
            for line in geom.geoms:
                coords.extend(line.coords)
            return LineString(coords)
        return geom

    objekt["geometry"] = objekt["geometry"].apply(normalize_to_linestring)
    if not str(objektid) in navn:
        navn = str(objektid) + "_" + navn
    
    def remove_z(geom):
        """Return geometry without Z values."""
        if geom is None or geom.is_empty:
            return geom

        gtype = geom.geom_type

        if gtype == "Point":
            x, y = geom.x, geom.y
            return Point(x, y)

        if gtype == "MultiPoint":
            return MultiPoint([Point(p.x, p.y) for p in geom.geoms])

        if gtype == "LineString":
            return LineString([(x, y) for x, y, *_ in geom.coords])

        if gtype == "MultiLineString":
            return MultiLineString([
                LineString([(x, y) for x, y, *_ in line.coords])
                for line in geom.geoms
            ])

        if gtype == "Polygon":
            exterior = [(x, y) for x, y, *_ in geom.exterior.coords]
            interiors = [
                [(x, y) for x, y, *_ in ring.coords]
                for ring in geom.interiors
            ]
            return Polygon(exterior, interiors)

        if gtype == "MultiPolygon":
            return MultiPolygon([remove_z(poly) for poly in geom.geoms])
        return geom

    objekt["geometry"] = objekt["geometry"].apply(remove_z)

    for gtype, subset in objekt.groupby(objekt.geometry.geom_type):
        layer_name = f"{navn}_{gtype}"

        try:
            subset.to_file(
                gdb_path,
                layer=layer_name,
                driver="GPKG"
            )
            print(f"Saved: {layer_name} ({len(subset)} rader)")
        except Exception as e:
            print(f"Failed for {gtype}: {e}")
        


def område_veger(kommune_id, fylke_id, vegref):
    objektid = vegobjekttype["Fartsgrense"]

    fartdata = nvdbapiv3.nvdbFagdata(objektid)
    bruk_filter(fartdata, kommune_id, fylke_id, vegref)
    fartsgrense_ranges = defaultdict(list)
    for f in fartdata:
        if "vegsystemreferanse" not in f["vegsegmenter"][0]:
            continue
        if "kortform" not in f["vegsegmenter"][0]["vegsystemreferanse"]:
            continue
        vegref_full = f["vegsegmenter"][0]["vegsystemreferanse"]["kortform"]
        
        parts = vegref_full.rsplit(' ', 1)

        if len(parts) != 2:
            continue
        
        prefix, m_part = parts
        m_range = tolk_meterområde(m_part)
        if not m_range:
            continue
        wkt_text = f["geometri"]["wkt"]
        geometry = wkt.loads(wkt_text)

        if isinstance(geometry, MultiLineString):
            line = LineString([pt for line in geometry.geoms for pt in line.coords])
        elif isinstance(geometry, LineString):
            line = geometry
        else:
            continue
        if prefix not in fartsgrense_ranges:    
            fartsgrense_ranges[prefix] = [(m_range[0], line.coords[0]), (m_range[1], line.coords[-1])]
        else:
            if m_range[0] < fartsgrense_ranges[prefix][0][0]:
                fartsgrense_ranges[prefix][0] = (m_range[0], line.coords[0])
            if m_range[1] > fartsgrense_ranges[prefix][1][0]:
                fartsgrense_ranges[prefix][1] = (m_range[1], line.coords[-1])

    return fartsgrense_ranges


lagre_objekt(geopackage, "Fartsgrense_105", 105)
lagre_objekt(geopackage, "Rekkverk_5", 5)
lagre_objekt(geopackage, "Motorveg_595", 595)
lagre_objekt(geopackage, "Vegkryss_37", 37)
lagre_objekt(geopackage, "Belysningsstrekning_86", 86)
lagre_objekt(geopackage, "Fylke_945", 945)
lagre_objekt(geopackage, "Vegoppmerking_forsterket_836", 836)
lagre_objekt(geopackage, "ATK-punkt_162", 162)
lagre_objekt(geopackage, "Streknings-ATK_823", 823)
lagre_objekt(geopackage, "Trafikkmengde_540", 540)
lagre_objekt(geopackage, "Belysningspunkt_87", 87)
lagre_objekt(geopackage, "Trafikkulykke_570", 570)
lagre_objekt(geopackage, "Vegbredde_beregnet_838", 838)
lagre_objekt(geopackage, "Feltstrekning_616", 616)
lagre_objekt(geopackage, "Streknings_ATK_823", 823)
lagre_objekt(geopackage, "ATK_influensstrekning_775", 775)
lagre_objekt(geopackage, "Tunnelløp_67", 67)
lagre_objekt(geopackage, "Bru_60", 60)