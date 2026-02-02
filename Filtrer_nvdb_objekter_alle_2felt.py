import pandas as pd
import geopandas as gpd
import json
from shapely.ops import linemerge
from shapely.geometry import LineString, MultiLineString, GeometryCollection
from shapely.ops import substring
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import re
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge

geopackage = r"NAVN PÅ DIN GPKG-FIL"
excel_geopackage = r"NAVN PÅ DIN GPKG-FIL FOR EXCEL-ARK"


def parse_all(gdf, felt = None, punkt = False):
    """Bruker smart_parse_vref og bygger en ren DataFrame."""
    rows = []
    for idx, row in gdf.iterrows():
        """
        rows.append({
            "index": idx,
            "header": p["header"],
            "from_m": p["from_m"],
            "to_m": p["to_m"],
        })
        """
        startposisjon = "startposisjon"
        sluttposisjon = "sluttposisjon"
        if punkt:
            startposisjon = "relativPosisjon"
            sluttposisjon = "relativPosisjon"
        if felt is None:
            rows.append({
                "index": idx,
                "header": row["veglenkesekvensid"],
                "from_m": row[startposisjon],
                "to_m": row[sluttposisjon],
            })
        else: 
            rows.append({
                "index": idx,
                "header": row["veglenkesekvensid"],
                "from_m": row[startposisjon],
                "to_m": row[sluttposisjon],
                "felt" : row[felt]
            })
        
    return pd.DataFrame(rows)

def normaliser_nvdb_id(s):
    return (
        pd.to_numeric(s, errors="coerce")  
        .astype("Int64")                   
        .astype(str)                       
    )


def kopier_felt_fra_csv(
    gdf,
    csv_path,
    id_csv,
    felt_csv,
    id_gdf = None,
    felt_gdf=None
):
    """
    Kopierer ett felt fra CSV til GeoDataFrame basert på lik ID.

    gdf      : GeoDataFrame
    csv_path: sti til CSV-fil
    id_csv  : ID-felt i CSV
    felt_csv: felt som kopieres FRA CSV  
    id_gdf  : ID-felt i gdf (default = id_csv) 
    felt_gdf: felt som kopieres TIL i gdf (default = felt_csv)
    """

    if felt_gdf is None:
        felt_gdf = felt_csv

    if id_gdf is None:
        id_gdf = id_csv

    csv = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig")
    print(csv.columns.tolist())
    duplikater = csv[id_csv][csv[id_csv].duplicated()]
    print("Antall dupliserte ID-er:", duplikater.nunique())
    print("Eksempler:", duplikater.unique()[:10])
    csv = csv.drop_duplicates(subset=id_csv, keep="first")

    gdf[id_gdf] = normaliser_nvdb_id(gdf[id_gdf])
    csv[id_csv] = normaliser_nvdb_id(csv[id_csv])

    mapping = csv.set_index(id_csv)[felt_csv]


    gdf[felt_gdf] = gdf[id_gdf].map(mapping)

    return gdf

def legg_til_alvorlighetsgrad_fra_filer(
    gdf,
    id_gdf,
    dod_path,
    mas_path,
    as_path,
    id_csv="nvdbId"
):
    """
    Setter feltet 'alvorlighetsgrad' i GeoDataFrame basert på
    hvilken CSV-fil ulykken finnes i.

    Prioritet:
      1. Dødsulykke
      2. Meget alvorlig skadd
      3. Alvorlig skadd
      4. Lettere skadde (default)
    """

    def les_ider(path):
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
        df[id_csv] = normaliser_nvdb_id(df[id_csv])
        return set(df[id_csv].dropna())

    # Les ID-sett
    dod_ider = les_ider(dod_path)
    mas_ider = les_ider(mas_path)
    as_ider  = les_ider(as_path)

    # Normaliser ID i gdf
    gdf[id_gdf] = normaliser_nvdb_id(gdf[id_gdf])

    # Default
    gdf["alvorlighetsgrad"] = "lettere skadde"

    # Prioritert overskriving
    gdf.loc[gdf[id_gdf].isin(as_ider),  "alvorlighetsgrad"] = "alvorlig skadd"
    gdf.loc[gdf[id_gdf].isin(mas_ider), "alvorlighetsgrad"] = "meget alvorlig skadd"
    gdf.loc[gdf[id_gdf].isin(dod_ider), "alvorlighetsgrad"] = "dødsulykke"

    return gdf



def rens_gemoetrier(gdf):
    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[gdf.geometry.is_valid]

    def fix_geom(g):
        if g.geom_type == "GeometryCollection":
            for part in g.geoms:
                if part.geom_type in ("Point", "LineString", "Polygon"):
                    return part
            return None
        return g
    
    gdf["geometry"] = gdf["geometry"].apply(fix_geom)

    gdf = gdf[gdf.geometry.notnull()]

    types = gdf.geometry.geom_type.value_counts()
    if len(types) == 0:
        return gdf

    dominerende = types.idxmax()

    gdf = gdf[gdf.geometry.geom_type == dominerende].copy()

    return gdf



def fjern_overlapp_vegobjekt(vegobjekt):
    nye_rader = []

    for header, gruppe in vegobjekt.groupby("veglenkesekvensid"):
        # Legg til absolutt meter
        gruppe = gruppe.copy()
        gruppe["s_m"] = gruppe["startposisjon"] * gruppe["segmentlengde"]
        gruppe["e_m"] = gruppe["sluttposisjon"] * gruppe["segmentlengde"]

        # Sorter etter start i meter
        gruppe = gruppe.sort_values("s_m")

        gjeldende_slutt = None

        for _, rad in gruppe.iterrows():
            v_from = rad["s_m"]
            v_to   = rad["e_m"]

            if gjeldende_slutt is None:
                ny_from = v_from
            else:
                ny_from = max(v_from, gjeldende_slutt)

            if ny_from >= v_to:
                continue  # Hele raden er overlapp

            # Oppdater startposisjon i fraksjon
            ny_rad = rad.to_dict()
            ny_rad["startposisjon"] = ny_from / rad["segmentlengde"]
            ny_rad["sluttposisjon"] = rad["sluttposisjon"]  # beholder opprinnelig sluttposisjon
            nye_rader.append(ny_rad)

            gjeldende_slutt = v_to

    return gpd.GeoDataFrame(nye_rader, crs=vegobjekt.crs)



def finn_nvdbulykker_langs_objekt(geopackage, vegobjekt, ulykker, navn = "objekt"):
    vegobjekt = fjern_overlapp_vegobjekt(vegobjekt)

    vegobjekt["ulykker_for"] = 0
    vegobjekt["ulykker_etter"] = 0
    vegobjekt["ulykker_id"] = ""
    vegobjekt["ulykker_år_etter_etableringsår"] = ""
    ulykker["ulykkesår"] = pd.to_datetime(ulykker["Ulykkesdato"], errors="coerce").dt.year

    alle_relevante_ulykker = []

    ulykker_parsed_list = []
    for _, ulykke_rad in ulykker.iterrows():
        geom = getattr(ulykke_rad, "geometry", None)
        if geom is None or geom.is_empty:
            continue
        
        ulykke_dict = ulykke_rad.to_dict()
        ulykke_dict.update({
            "header": ulykke_rad["veglenkesekvensid"],
            "position": ulykke_rad["relativPosisjon"],
            "geometry": geom
        })
        ulykker_parsed_list.append(ulykke_dict)

    ulykker_parsed = gpd.GeoDataFrame(ulykker_parsed_list, geometry="geometry", crs=ulykker.crs)

    allerede_telt_for = set()
    allerede_telt_etter = set()
    p_fmo = parse_all(vegobjekt)  
    for idx, rad in vegobjekt.iterrows():
        p_fmo = {
            "header": rad["veglenkesekvensid"],
            "from_m": rad["startposisjon"],
            "to_m": rad["sluttposisjon"],
        }

        år = rad.get("Etableringsår")
        if pd.isna(år) or int(år) > 2019:
            continue
        år = int(år)
        
        if p_fmo is None:
            continue

        subset = ulykker_parsed[
            (ulykker_parsed["header"] == p_fmo["header"]) &
            (ulykker_parsed["position"] <= p_fmo["to_m"]) &
            (ulykker_parsed["position"] >= p_fmo["from_m"])
        ].copy()

        if len(subset) == 0:
            continue

        subset["aar_etter_etablering_FMO"] = subset["ulykkesår"] - år
        subset["nvdbId"] = subset["nvdbId"].astype(str)

        før = subset[
            (~subset["nvdbId"].isin(allerede_telt_for))
        ]
        etter = subset[
            (~subset["nvdbId"].isin(allerede_telt_etter))
        ]

        allerede_telt_for.update(før["nvdbId"].tolist())
        allerede_telt_etter.update(etter["nvdbId"].tolist())

        vegobjekt.loc[idx, "ulykker_for"] = len(før)
        vegobjekt.loc[idx, "ulykker_etter"] = len(etter)

        fmo_ulykker_ids = pd.concat([før, etter], ignore_index=True)["nvdbId"].tolist()
        vegobjekt.loc[idx, "ulykker_id"] = json.dumps(fmo_ulykker_ids)
        vegobjekt.loc[idx, "ulykker_aar_etter_etableringsår"] = json.dumps(subset["aar_etter_etablering_FMO"].tolist())
        vegobjekt.loc[idx, "ulykker_meta"] = json.dumps(
            subset[["nvdbId", "aar_etter_etablering_FMO", "alvorlighetsgrad"]].to_dict("records")
        )

        alle_relevante_ulykker.append(subset)

    if alle_relevante_ulykker:
        alle_relevante_ulykker = gpd.GeoDataFrame(pd.concat(alle_relevante_ulykker, ignore_index=True),
                                                  geometry="geometry", crs=ulykker.crs)
    else:
        alle_relevante_ulykker = gpd.GeoDataFrame(columns=ulykker.columns)

    alle_relevante_ulykker = rens_gemoetrier(alle_relevante_ulykker)

    alle_relevante_ulykker = alle_relevante_ulykker.drop_duplicates(
        subset=["nvdbId"]
    ).reset_index(drop=True)

    if len(alle_relevante_ulykker) > 0:
        vegobjekt.to_file(geopackage, layer=navn + "_med_ulykker", driver="GPKG")
        alle_relevante_ulykker.to_file(geopackage, layer="ulykker_ved_" + navn, driver="GPKG")
    else:
        print("Ingen ulykker å lagre – hopper over lagring.")



    
    return vegobjekt, alle_relevante_ulykker


def ensure_linestring(geom):
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, LineString):
        return geom
    if isinstance(geom, MultiLineString):
        merged = linemerge(geom)
        if isinstance(merged, LineString):
            return merged
    return None

def klipp_linje(line, f_start, f_end):
    """
    Klipper LineString basert på fraksjon av lengde [0–1].
    """

    # --- Robust type-sjekk ---
    if line is None:
        return None

    if not isinstance(line, (LineString, MultiLineString)):
        return None

    if line.is_empty:
        return None

    if f_start < 0:
        f_start = 0
    if f_end > 1:
        f_end = 1
    if f_start >= f_end:
        return None

    geom = ensure_linestring(line)
    if geom is None or geom.is_empty:
        return None

    length = geom.length
    if length == 0:
        return None

    start_dist = f_start * length
    end_dist   = f_end   * length

    return substring(geom, start_dist, end_dist)


def klipp_intervall(target_from, target_to, sources, felt = False):
    """
    target_from, target_to: meterintervall for target
    sources: DataFrame med kolonner [from_m, to_m, felt]

    Returnerer liste med dict:
      {from_m, to_m, felt}
    """
    # Samle alle bruddpunkter
    cuts = {target_from, target_to}
    for _, r in sources.iterrows():
        cuts.add(max(target_from, r["from_m"]))
        cuts.add(min(target_to, r["to_m"]))

    cuts = sorted(cuts)

    segments = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if a >= b:
            continue

        # Finn source som dekker dette delintervallet
        hit = sources[
            (sources["from_m"] <= a) &
            (sources["to_m"] >= b)
        ]

        if felt and len(hit) > 0:
            feltverdi = hit.iloc[0]["felt"]
        else:
            feltverdi = None
        if felt:
            segments.append({
                "from_m": a,
                "to_m": b,
                "felt": feltverdi
            })
        else:
            segments.append({
                "from_m": a,
                "to_m": b
            })

    return segments

def kopier_felt_ved_overlapp(source, target, felt, target_feltnavn  = None, sourcePunkt = False, targetPunkt = False):
    """
    Kopierer et felt fra 'source' til 'target' hvis det er overlapp i veglenke.
    
    source: GeoDataFrame med feltet som skal kopieres
    target: GeoDataFrame som skal få feltet kopiert
    felt: navn på felt i source som skal kopieres
    """

    df_source = parse_all(source, felt, punkt=sourcePunkt)
    df_target = parse_all(target, punkt=targetPunkt)
    
    # Lagre mapping fra target-index til felt-verdi
    kopierte_verdier = {}
    
    # Grupper source på header for raskere søk
    grupper_source = df_source.groupby("header")
    
    for _, r_target in df_target.iterrows():
        header = r_target["header"]
        if header not in grupper_source.groups:
            continue
        kandidater = df_source.loc[grupper_source.groups[header]]
        overlapp = kandidater[
            (kandidater["from_m"] <= r_target["to_m"]) &
            (kandidater["to_m"] >= r_target["from_m"])
        ]
        if len(overlapp) > 0:
            # Hvis flere overlapp, ta første
            kopierte_verdier[r_target["index"]] = overlapp.iloc[0]["felt"]
    
    # Oppdater target
    if target_feltnavn is None:
        target_feltnavn = felt
    for idx, verdi in kopierte_verdier.items():
        target.at[idx, target_feltnavn] = verdi
    
    return target

def kopier_felt_ved_lik_id(source, target, felt):
    """
    Kopierer et felt fra 'source' til 'target' hvis det er lik nvdbid.
    
    source: GeoDataFrame med feltet som skal kopieres
    target: GeoDataFrame som skal få feltet kopiert
    felt: navn på felt i source som skal kopieres
    """

    kopierte_verdier = {}
    nvdbid_set = set(source["nvdbid"])
    for idx, r_target in target.iterrows():
        header = str(int(float(r_target["nvdbId"])))
        if header not in nvdbid_set:
            continue

        kandidater = source[source["nvdbid"] == header]
        if not kandidater.empty:
            target.at[idx, felt] = kandidater.iloc[0][felt]

    for idx, verdi in kopierte_verdier.items():
        target.at[idx, felt] = verdi
    
    return target

def kopier_felt_ved_overlapp_klipp_geometri(source, target, felt, target_feltnavn  = None):
    """
    Klipper target både metrisk og geometrisk, og kopierer felt fra source.
    """
    df_source = parse_all(source, felt)
    df_target = parse_all(target)

    grupper_source = df_source.groupby("header")

    nye_rader = []

    for _, t in df_target.iterrows():
        header = t["header"]
        t_from = t["from_m"]
        t_to = t["to_m"]

        t_row = target.loc[t["index"]]
        geom = t_row.geometry

        if header not in grupper_source.groups:
            r = t_row.copy()
            r[felt] = None
            nye_rader.append(r)
            continue

        kandidater = df_source.loc[grupper_source.groups[header]]
        overlapp = kandidater[(kandidater["from_m"] <= t_to) & (kandidater["to_m"] >= t_from)]

        if len(overlapp) == 0:
            r = t_row.copy()
            r[felt] = None
            nye_rader.append(r)
            continue

        delsegmenter = klipp_intervall(t_from, t_to, overlapp, felt=True)

        for seg in delsegmenter:
            seg_from = seg["from_m"]
            seg_to = seg["to_m"]

            g_start = (seg_from - t_from) / (t_to - t_from)
            g_end   = (seg_to   - t_from) / (t_to - t_from)

            new_geom = klipp_linje(geom, g_start, g_end)
            if new_geom is None or new_geom.is_empty:
                continue
            if not isinstance(new_geom, (LineString, MultiLineString)):
                nvdb = t_row.get("nvdbId", "Ukjent ID")
                print(f"Hopper over nvdbId={nvdb} pga ugyldig geometri type: {type(new_geom)}")
                continue

            r = t_row.copy()
            r["startposisjon"] = seg_from
            r["sluttposisjon"] = seg_to
            r["geometry"] = new_geom
            r[target_feltnavn if target_feltnavn else felt] = seg["felt"]

            try:
                nye_rader.append(r)
            except Exception as e:
                nvdb = getattr(r, "nvdbId", "Ukjent ID")
                print(f"Hoppa over rad med nvdbId={nvdb} pga feil: {e}")
                continue

    # Lag GeoDataFrame fra Series i stedet for dict
    return gpd.GeoDataFrame(nye_rader, crs=target.crs)

def inverter_segments(base_from, base_to, segments):
    """
    Gitt base-intervallet [base_from, base_to] og en liste av
    overlappende segmenter (from_m, to_m),
    returner delene som IKKE overlapper.
    """

    if not segments:
        return [{"from_m": base_from, "to_m": base_to}]

    segs = sorted(
        [(max(base_from, s["from_m"]), min(base_to, s["to_m"])) for s in segments],
        key=lambda x: x[0]
    )

    out = []
    cursor = base_from

    for s_from, s_to in segs:
        if s_from > cursor:
            out.append({"from_m": cursor, "to_m": s_from})
        cursor = max(cursor, s_to)

    if cursor < base_to:
        out.append({"from_m": cursor, "to_m": base_to})

    return out

def row_to_dict(row):
    d = row.to_dict()
    d["geometry"] = row.geometry
    return d



def finn_overlapp_klipp_geometri(vegobjekt1, vegobjekt2, modus="fjern"):
    """
    Klipper vegobjekt1 metrisk og geometrisk basert på overlapp med vegobjekt2.

    modus:
      - "fjern"  : fjerner overlappende deler
      - "behold" : beholder kun overlappende deler
    """
    df1 = parse_all(vegobjekt1)
    df2 = parse_all(vegobjekt2)

    grupper2 = df2.groupby("header")
    nye_rader = []

    for _, r1 in df1.iterrows():
        header = r1["header"]
        v_from = r1["from_m"]
        v_to   = r1["to_m"]
        row = vegobjekt1.loc[r1["index"]]
        geom = row.geometry

        if geom is None or not hasattr(geom, "geom_type"):
            continue

        if header not in grupper2.groups:
            if modus == "fjern":
                nye_rader.append(row_to_dict(row))
            continue

        kandidater = df2.loc[grupper2.groups[header]]

        overlapp = kandidater[
            (kandidater["from_m"] <= v_to) & (kandidater["to_m"] >= v_from)
        ]

        if len(overlapp) == 0:
            if modus == "fjern":
                nye_rader.append(row_to_dict(row))
            continue

        overlapp_segs = []
        for _, o in overlapp.iterrows():
            o_from = max(v_from, o["from_m"])
            o_to   = min(v_to,   o["to_m"])
            if o_to > o_from:
                overlapp_segs.append({"from_m": o_from, "to_m": o_to})

        if not overlapp_segs:
            if modus == "fjern":
                nye_rader.append(row_to_dict(row))
            continue

        if modus == "behold":
            delsegmenter = overlapp_segs
        else:
            delsegmenter = inverter_segments(v_from, v_to, overlapp_segs)

        for seg in delsegmenter:
            seg_from = seg["from_m"]
            seg_to   = seg["to_m"]
            if seg_to <= seg_from:
                continue

            g_start = (seg_from - v_from) / (v_to - v_from)
            g_end   = (seg_to   - v_from) / (v_to - v_from)

            new_geom = klipp_linje(geom, g_start, g_end)
            if new_geom is None or new_geom.is_empty:
                continue

            if isinstance(new_geom, GeometryCollection):
                linjer = [g for g in new_geom.geoms if isinstance(g, LineString)]
                if not linjer:
                    nvdb = getattr(row, "nvdbId", "Ukjent ID")
                    print(f"Hopper over nvdbId={nvdb} pga tom GeometryCollection")
                    continue
                new_geom = MultiLineString(linjer)
            elif not isinstance(new_geom, (LineString, MultiLineString)):
                nvdb = getattr(row, "nvdbId", "Ukjent ID")
                print(f"Hopper over nvdbId={nvdb} pga ugyldig geometri type: {type(new_geom)}")
                continue

            r = row.to_dict()
            r["startposisjon"] = seg_from
            r["sluttposisjon"] = seg_to
            r["geometry"] = new_geom

            nye_rader.append(r)

    return gpd.GeoDataFrame(nye_rader, crs=vegobjekt1.crs)


felt = gpd.read_file(geopackage, layer="Feltstrekning_616_LineString").to_crs(25833)
felt = felt[felt["vegkategori"].isin(["F", "E", "R"])]
felt_2 = felt[felt["Type"] == "2-feltsveg"]
felt_2.to_file(geopackage, layer="felt_2", driver="GPKG")    
felt_2 = gpd.read_file(geopackage, layer="felt_2").to_crs(25833)

vegopp = gpd.read_file(geopackage, layer="Vegoppmerking_forsterket_836_LineString").to_crs(25833)
FMO = vegopp[vegopp["Type"] == "Forsterket midtoppmerking"]
FMO.to_file(geopackage, layer="FMO", driver="GPKG") 
print("FMO")

felt2_FMO = kopier_felt_ved_overlapp_klipp_geometri(FMO, felt_2, "Type", target_feltnavn="FMO")
felt2_FMO.to_file(geopackage, layer="felt2_FMO", driver="GPKG")
print("felt2_FMO")

rekkverk = gpd.read_file(geopackage, layer="Rekkverk_5_LineString").to_crs(25833)
midtdeler_midtrekkverk = rekkverk[(rekkverk["Bruksområde"] == "Midtdeler") | (rekkverk["Bruksområde"] == "Midtrekkverk")]
midtdeler_midtrekkverk.to_file(geopackage, layer="midtdeler_midtrekkverk", driver="GPKG")    

felt2_FMO_u_midtrekkverk = finn_overlapp_klipp_geometri(felt2_FMO, midtdeler_midtrekkverk, "fjern")
felt2_FMO_u_midtrekkverk.to_file(geopackage, layer="felt2_FMO_u_midtrekkverk", driver="GPKG")  
print("felt2_FMO_u_midtrekkverk")

motorveg = gpd.read_file(geopackage, layer="Motorveg_595_LineString").to_crs(25833)
felt2_FMO_u_midtrekkverk_motorveg = finn_overlapp_klipp_geometri(felt2_FMO_u_midtrekkverk, motorveg, "fjern")
felt2_FMO_u_midtrekkverk_motorveg.to_file(geopackage, layer="felt2_FMO_u_midtrekkverk_motorveg", driver="GPKG")
print("felt2_FMO_u_midtrekkverk_motorveg")

vegbredde = gpd.read_file(geopackage, layer="Vegbredde_beregnet_838_LineString").to_crs(25833)
felt2_FMO_dekkebredde_u_midtrekkverk_motorveg = kopier_felt_ved_overlapp_klipp_geometri(vegbredde, felt2_FMO_u_midtrekkverk_motorveg, "Dekkebredde")
felt2_FMO_dekkebredde_u_midtrekkverk_motorveg.to_file(geopackage, layer="felt2_FMO_dekkebredde_u_midtrekkverk_motorveg", driver="GPKG")
print("felt2_FMO_dekkebredde_u_midtrekkverk_motorveg")

fart = gpd.read_file(geopackage, layer="Fartsgrense_105_LineString").to_crs(25833)
felt2_FMO_dekkebredde_fart_u_midtrekkverk_motorveg = kopier_felt_ved_overlapp_klipp_geometri(fart, felt2_FMO_dekkebredde_u_midtrekkverk_motorveg, "Fartsgrense")
felt2_FMO_dekkebredde_fart_u_midtrekkverk_motorveg.to_file(geopackage, layer="felt2_FMO_dekkebredde_fart_u_midtrekkverk_motorveg", driver="GPKG")
print("felt2_FMO_dekkebredde_fart_u_midtrekkverk_motorveg")

