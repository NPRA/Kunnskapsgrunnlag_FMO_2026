import geopandas as gpd
import matplotlib.pyplot as plt

geopackage = r"NAVN_PÅ_DIN_GEOPACKAGE_FIL"

veg = gpd.read_file(geopackage, layer="FMO_2felts_dekkebredde_u_atk_midtrekkverk_motorveg").to_crs(25833)
print(veg[(veg["Etableringsår"] == 2025) & (veg["Dekkebredde"] < 7.5)]["nvdbId"].unique())
veg = veg[veg["vegkategori"].isin(["E", "R", "F"])]
veg["lengde_km"] = veg.geometry.length / 1000
veg["Etableringsår"] = veg["Etableringsår"].astype("Int64")
veg = veg[veg["Etableringsår"] <= 2025]
#veg = veg[veg["Dekkebredde"] < 7.5]


fylker = {
  3: "Oslo",
  11: "Rogaland",
  15: "Møre og Romsdal",
  18: "Nordland",
  31: "Østfold",
  32: "Akershus",
  33: "Buskerud",
  34: "Innlandet",
  39: "Vestfold",
  40: "Telemark",
  42: "Agder",
  46: "Vestland",
  50: "Trøndelag",
  55: "Troms",
  56: "Finnmark"
}

region_sør = ["Agder", "Vestfold", "Telemark", "Buskerud"]
region_nord = ["Troms", "Finnmark", "Nordland"]
region_midt = ["Trøndelag", "Møre og Romsdal"]
region_vest = ["Vestland", "Rogaland"]
region_aust = ["Oslo", "Akershus", "Hedemark", "Innlandet", "Østfold"]

veg["fylke_navn"] = veg["fylke"].map(fylker)

fylke_til_region = {}

for f in region_sør:
    fylke_til_region[f] = "Sør"

for f in region_nord:
    fylke_til_region[f] = "Nord"

for f in region_midt:
    fylke_til_region[f] = "Midt"

for f in region_vest:
    fylke_til_region[f] = "Vest"

for f in region_aust:
    fylke_til_region[f] = "Øst"

veg["region"] = veg["fylke_navn"].map(fylke_til_region)

def plot(veg, regioner = False, smal = False):
    if smal:
        veg = veg[veg["Dekkebredde"] < 7.5]
    sorter = "fylke_navn"
    if regioner:
        sorter = "region"
    grouped = (
        veg.groupby(["Etableringsår", sorter])["lengde_km"]
        .sum()
        .unstack(fill_value=0)
        .sort_index()
    )

    if regioner:
        ønsket_rekkefølge = ["Vest", "Øst", "Midt", "Sør", "Nord"]

        grouped = grouped.reindex(columns=ønsket_rekkefølge, fill_value=0)
    print(grouped)
    grouped.to_csv(geopackage + "veglengde_per_aar_region_bre_veg.csv", sep=";", decimal=".")
    ax = grouped.plot(
        kind="bar",
        stacked=True,
        figsize=(12, 6),
    )

    ax.set_xlabel("Årstall")
    ax.set_ylabel("Antall kilometer veg")
    ax.set_title(f"Etablering av FMO (km) {'på smale veger ' if smal else ''}per region og år")
    ax.legend(title="Regioner")

    plt.tight_layout()
    plt.grid(axis="y")
    plt.show()

for smal in [False, True]:
    for regioner in [False, True]:
        plot(veg, regioner=regioner, smal=smal)