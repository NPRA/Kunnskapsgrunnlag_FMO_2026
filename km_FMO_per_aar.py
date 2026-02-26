import re
import geopandas as gpd
import pandas as pd
from matplotlib import ticker
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.font_manager as fm

def hent_aar(verdi):
    if pd.isna(verdi):
        return None
    match = re.search(r"\b(19|20)\d{2}\b", str(verdi))
    return int(match.group()) if match else None

mpl.rcParams["font.family"] = "sans-serif"
mpl.rcParams["font.sans-serif"] = ["Calibri"]

mpl.rcParams.update({
    "font.size": 18,
    "axes.titlesize": 18,
    "axes.labelsize": 14,
    "xtick.labelsize": 16,
    "ytick.labelsize": 16,
    "legend.fontsize": 16,
    "figure.titlesize": 22
})



[f.name for f in fm.findSystemFonts() if "Calibri" in f]
folder = r"C:\Users\hfyhn\Documents\Jobb\For-etter-analyse-av-FMO-main\For_etter_analyse_FMO"
geopackage = folder + r"\objekter.gpkg"
excel_geopackage = r"C:\Users\hfyhn\Documents\Jobb\For-etter-analyse-av-FMO-main\For_etter_analyse_FMO\excel-ark"


FMO = gpd.read_file(geopackage, layer="Vegoppmerking_forsterket_836_LineString").to_crs(25833)

FMO.to_file(geopackage, layer="FMO", driver="GPKG")   
FOM_etableringsaar = pd.read_excel(excel_geopackage + r"\Mangler etableringsår FMO i Sogn og Fjordane.xlsx")

FOM_etableringsaar["Etableringsår"] = FOM_etableringsaar.iloc[:, 2].apply(hent_aar)

FOM_etableringsaar = FOM_etableringsaar[["ID", "Etableringsår"]].dropna(subset=["Etableringsår"])

FMO = FMO.merge(
    FOM_etableringsaar,
    how="left",
    left_on="nvdbId",
    right_on="ID",
    suffixes=("", "_excel")
)

print(sum(FMO[(FMO["Etableringsår"] <= 2012) & ((FMO["Type"] == "Forsterket midtoppmerking") | (FMO["Type"] == "Forsterket oppmerking mot midtdeler"))].geometry.length) / 1000)

veg = gpd.read_file(geopackage, layer="FMO_2felts_dekkebredde_u_atk_midtrekkverk_motorveg").to_crs(25833)
print(veg[(veg["Etableringsår"] == 2025) & (veg["Dekkebredde"] < 7.5)]["nvdbId"].unique())
veg = veg[veg["vegkategori"].isin(["E", "R", "F"])]
veg = veg[veg["Fartsgrense"].isin([60, 70, 80])]
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
FMO["fylke_navn"] = FMO["fylke"].map(fylker)

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
FMO["region"] = FMO["fylke_navn"].map(fylke_til_region)
print("tidlige fylker:", FMO[(FMO["Etableringsår"] < 2010) & ((FMO["Type"] == "Forsterket midtoppmerking") | (FMO["Type"] == "Forsterket oppmerking mot midtdeler"))]["fylke_navn"].unique())
print("km med FMO i Norge:", sum(FMO[(FMO["region"] == "Vest") & (FMO["Etableringsår"].isna()) & ((FMO["Type"] == "Forsterket midtoppmerking") | (FMO["Type"] == "Forsterket oppmerking mot midtdeler"))].geometry.length) / 1000)
print("km med FMO i Vest:", sum(FMO[(FMO["region"] == "Vest") & (FMO["Etableringsår"] <= 2013) & ((FMO["Type"] == "Forsterket midtoppmerking") | (FMO["Type"] == "Forsterket oppmerking mot midtdeler"))].geometry.length) / 1000)
print("km med FVO i Vest:", sum(FMO[(FMO["region"] == "Vest") & (FMO["Etableringsår"] <= 2013)].geometry.length) / 1000)
print("km med FKO i Vest:", sum(FMO[(FMO["region"] == "Vest") & (FMO["Etableringsår"] <= 2013) & ((FMO["Type"] == "Forsterket kantoppmerking"))].geometry.length) / 1000)



def plot(veg, sorter = "regioner", smal = False):
    if smal:
        veg = veg[veg["Dekkebredde"] < 7.5]
   
    grouped = (
        veg.groupby(["Etableringsår", sorter])["lengde_km"]
        .sum()
        .unstack(fill_value=0)
        .sort_index()
    )

    if sorter == "region":
        ønsket_rekkefølge = ["Vest", "Øst", "Midt", "Sør", "Nord"]

        grouped = grouped.reindex(columns=ønsket_rekkefølge, fill_value=0)
    if sorter == "vegkategori":
        ønsket_rekkefølge = ["E", "R", "F"]
        bar_colors = ['tab:blue', 'tab:orange', '0.6']
        
        grouped = grouped.reindex(columns=ønsket_rekkefølge, fill_value=0)
    print(grouped)
    grouped.to_csv(geopackage + f"veglengde_per_aar_{sorter}_bre_veg.csv", sep=";", decimal=".")
    ax = grouped.plot(
        kind="bar",
        stacked=True,
        figsize=(12, 6),
        zorder=3,
        color=bar_colors if sorter == "vegkategori" else None
    )
    if sorter == "vegkategori":
        new_labels = {'E': 'Europaveg', 'R': 'Riksveg', 'F': 'Fylkesveg'}
        handles, labels = ax.get_legend_handles_labels()
        updated_labels = [new_labels[label] for label in labels]
    plt.grid(axis="y", zorder=0)
    if sorter == "fylke_navn":
        sorter = "fylke"
    ax.set_xlabel("Årstall")
    ax.set_ylabel("Antall kilometer veg")
    ax.set_title(f"Etablering av FMO (km) {'på veger mellom 7,0 og 7,5 meter bredde ' if smal else ''}per {sorter} og år")
    ax.legend(title=sorter.capitalize())
    ax.tick_params(axis='x', labelrotation=0)
    plt.box(on=None) 
    plt.tick_params(
        axis='both',         
        which='both',      
        bottom=False,     
        top=False,    
        left=False,     
        right=False,         
        labelbottom=True  
        ) 
    if smal:
        ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
    else:
        ax.yaxis.set_major_locator(ticker.MultipleLocator(20))
    ax.legend(loc='upper center', labels=updated_labels if sorter == "vegkategori" else None, bbox_to_anchor=(0.5, -0.15),
          fancybox=False, shadow=False, ncol=5)
    plt.tight_layout()
    plt.savefig(folder + rf"\veglengde_per_aar_{sorter}_{'smale_' if smal else 'bred_'}veg_2.png", dpi=300, bbox_inches='tight')
    #plt.show()

#for smal in [False, True]:
#    for regioner in [False, True]:
#        plot(veg, regioner=regioner, smal=smal)
#for regioner in ["vegkategori", "fylke_navn", "region"]:
#    plot(veg, sorter=regioner, smal=True)    
