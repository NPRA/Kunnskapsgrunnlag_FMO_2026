from matplotlib.colors import LinearSegmentedColormap
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib as mpl
import matplotlib.font_manager as fm

mappe = r"NAVN PÅ MAPPA"
geopackage = mappe + r"DIN GPKG-FIL"

def annotate_heatmap(ax, data, fmt="{:.1f}"):
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data.iloc[i, j]

            color = "#000000"

            ax.text(
                j, i, fmt.format(val),
                ha="center",
                va="center",
                fontsize=14,
                color=color,
            )

mpl.rcParams.update({
    "font.size": 18,
    "axes.titlesize": 18,
    "axes.labelsize": 16,
    "xtick.labelsize": 16,
    "ytick.labelsize": 16,
    "legend.fontsize": 18,
    "figure.titlesize": 22
})


fylke_map = {
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

COL_FMO = "#FFE233"
COL_POT = "#FA9F00"
COL_GRID = "#d0d0d0"

cmap_fmo = LinearSegmentedColormap.from_list(
    "fmo_warm",
    ["#FFF8CC", "#FFE233", "#FA9F00"]
)

mpl.rcParams["font.family"] = "sans-serif"
mpl.rcParams["font.sans-serif"] = ["Calibri"]

[f.name for f in fm.findSystemFonts() if "Calibri" in f]

def plot(veg, filnavn):
    gyldige_farter = [60, 70, 80]
    veg = veg[veg["Fartsgrense"].isin(gyldige_farter)]

    veg["lengde_km"] = veg.geometry.length / 1000

    veg["har_fmo"] = veg["FMO"].notna()
    veg["fylkenavn"] = veg["fylke"].map(fylke_map)
    breddegrenser = [7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 100.0]
    breddeetiketter = ["7.0–7.1", "7.1–7.2", "7.2–7.3", "7.3–7.4", "7.4–7.5", "≥ 7.5"]

    veg["breddeklasse"] = pd.cut(
        veg["Dekkebredde"],
        bins=breddegrenser,
        labels=breddeetiketter,
        include_lowest=True,
        right=False

    )
    

    veg["fartsgruppe"] = veg["Fartsgrense"].map(
        lambda x: "60" if x == 60 else "70 + 80"
    )

    veg["fartsgruppe"] = "70 + 80"
    veg.loc[veg["Fartsgrense"] == 60, "fartsgruppe"] = "60"


    heat_a = (
        veg[~veg["har_fmo"]]
        .pivot_table(
            values="lengde_km",
            index="fartsgruppe",
            columns="breddeklasse",
            aggfunc="sum",
            fill_value=0,
            observed=False
        )
        .reindex(["60", "70 + 80"])
    )

    heat_c = (
        veg[veg["har_fmo"]]
        .pivot_table(
            values="lengde_km",
            index="fartsgruppe",
            columns="breddeklasse",
            aggfunc="sum",
            fill_value=0,
            observed=False
        )
        .reindex(["60", "70 + 80"])
    )


    bredde_niva = [7.5, 7.4, 7.3, 7.2, 7.1, 7.0]



    bredde_terskler = [7.0, 7.1, 7.2, 7.3, 7.4, 7.5]

    rows = []


    for terskel in bredde_terskler:
        subset = veg[(veg["Dekkebredde"] >= terskel) & (veg["har_fmo"])].copy()

        grp = (
            subset
            .groupby("fylkenavn")["lengde_km"]
            .sum()
            .reset_index()
        )

        grp["breddeklasse"] = f"≥ {terskel:.1f}"
        rows.append(grp)

    heat_d = (
        pd.concat(rows)
        .pivot(index="fylkenavn", columns="breddeklasse", values="lengde_km")
        .fillna(0)
    )

    rows = []


    for terskel in bredde_terskler:
        subset = veg[(veg["Dekkebredde"] >= terskel) & (~veg["har_fmo"])].copy()
        grp = (
            subset
            .groupby("fylkenavn")["lengde_km"]
            .sum()
            .reset_index()
        )
        grp["breddeklasse"] = f"≥ {terskel:.1f}"
        rows.append(grp)

    heat_f = (
        pd.concat(rows)
        .pivot(index="fylkenavn", columns="breddeklasse", values="lengde_km")
        .fillna(0)
    )

    kolonner_i_rekkefolge = ["≥ 7.5", "7.4–7.5", "7.3–7.4", "7.2–7.3", "7.1–7.2", "7.0–7.1"]
    kolonner = [f"≥ {b:.1f}" for b in bredde_terskler[::-1]]

    alle_fylker = sorted(veg["fylkenavn"].dropna().unique())

    heat_d = heat_d.reindex(alle_fylker, fill_value=0)
    heat_f = heat_f.reindex(alle_fylker, fill_value=0)

    fylke_rekkefolge = (
        heat_d.sum(axis=1)
        .sort_values()
        .index
    )

    heat_a = heat_a.reindex(columns=breddeetiketter, fill_value=0)
    heat_c = heat_c.reindex(columns=breddeetiketter, fill_value=0)
    heat_d = heat_d.loc[fylke_rekkefolge]
    heat_f = heat_f.loc[fylke_rekkefolge]

    heat_d = heat_d[kolonner]
    heat_f = heat_f[kolonner]
    heat_a = heat_a[kolonner_i_rekkefolge]
    heat_c = heat_c[kolonner_i_rekkefolge]


    fig = plt.figure(figsize=(20, 14))
    gs = GridSpec(2, 2, width_ratios=[1.2, 1.8], height_ratios=[1.2, 1.2])

    ax_a = fig.add_subplot(gs[1, 0])
    ax_b = fig.add_subplot(gs[1, 1])
    ax_c = fig.add_subplot(gs[0, 0])
    ax_d = fig.add_subplot(gs[0, 1])

    data_for_scale = heat_a.drop(columns=["≥ 7.5"], errors="ignore")

    vmin = data_for_scale.min().min()
    vmax = data_for_scale.max().max()

    im_a = ax_a.imshow(heat_a, aspect="auto", origin="lower", cmap=cmap_fmo, vmin=vmin, vmax=vmax)
    annotate_heatmap(ax_a, heat_a)

    ax_a.set_title("(c) Potensiell FMO (km) fordelt på fartsgrense og bredde", weight='bold')

    ax_a.set_xticks(range(len(heat_a.columns)))
    ax_a.set_xticklabels(heat_a.columns)

    ax_a.set_yticks(range(len(heat_a.index)))
    ax_a.set_yticklabels(heat_a.index)
    ax_a.set_xlabel("Dekkebredde (m)")
    ax_a.set_ylabel("Fartsgrense (km/t)")

    fig.colorbar(im_a, ax=ax_a, label="Lengde (km)")


    im_b = ax_b.imshow(heat_f, aspect="auto", origin="lower", cmap=cmap_fmo)
    annotate_heatmap(ax_b, heat_f)
    ax_b.set_title("(d) Potensiell FMO (km) per fylke og breddekrav", weight='bold')



    ax_b.set_xticks(range(len(heat_f.columns)))
    ax_b.set_xticklabels(heat_f.columns)

    ax_b.set_yticks(range(len(heat_f.index)))
    ax_b.set_yticklabels(heat_f.index)

    ax_b.set_xlabel("Dekkebredde (m)")
    ax_b.set_ylabel("Fylke")

    fig.colorbar(im_b, ax=ax_b, label="Lengde (km)")

    data_for_scale = heat_c.drop(columns=["≥ 7.5"], errors="ignore")

    vmin = data_for_scale.min().min()
    vmax = data_for_scale.max().max()

    im_c = ax_c.imshow(heat_c, aspect="auto", origin="lower", cmap=cmap_fmo, vmin=vmin, vmax=vmax)
    annotate_heatmap(ax_c, heat_c)
    ax_c.set_title("(a) Etablert FMO (km) fordelt på fartsgrense og bredde", weight='bold')

    ax_c.set_xticks(range(len(heat_c.columns)))
    ax_c.set_xticklabels(heat_c.columns)

    ax_c.set_yticks(range(len(heat_c.index)))
    ax_c.set_yticklabels(heat_c.index)
    ax_c.set_xlabel("Dekkebredde (m)")
    ax_c.set_ylabel("Fartsgrense (km/t)")

    fig.colorbar(im_c, ax=ax_c, label="Lengde (km)")

    im_d = ax_d.imshow(heat_d, aspect="auto", origin="lower", cmap=cmap_fmo)
    annotate_heatmap(ax_d, heat_d)

    ax_d.set_title("(b) Etablert FMO (km) per fylke og breddekrav", weight='bold')

    ax_d.set_xticks(range(len(heat_d.columns)))
    ax_d.set_xticklabels(heat_d.columns)

    ax_d.set_yticks(range(len(heat_d.index)))
    ax_d.set_yticklabels(heat_d.index)

    ax_d.set_xlabel("Dekkebredde (m)")
    ax_d.set_ylabel("Fylke")

    fig.colorbar(im_d, ax=ax_d, label="Lengde (km)")


    # Hovedtittel – bold
    fig.text(
        0.5, 0.975,
        "Analyse av etablert og potensiell FMO",
        ha="center",
        va="top",
        fontsize=24,
        fontweight="bold"
    )

    # Undertittel linje 1 – italic, mindre skrift
    fig.text(
        0.5, 0.945,
        ""
        "",
        ha="center",
        va="top",
        fontsize=16,
        style="italic"
    )

    # Undertittel linje 2 – italic, mindre skrift
    fig.text(
        0.5, 0.920,
        "",
        ha="center",
        va="top",
        fontsize=16,
        style="italic"
    )

    for ax in [ax_b, ax_d]:
        for spine in ax.spines.values():
            spine.set_visible(False)
    plt.subplots_adjust(top=0.88, hspace=0.45, wspace=0.45)
    plt.savefig(filnavn, dpi=300)


veg_ER = gpd.read_file(geopackage, layer="felt2_ER_FMO_dekkebredde_adt_fart_u_atk_midtrekkverk_motorveg").to_crs(25833)
veg_F = gpd.read_file(geopackage, layer="felt2_F_FMO_dekkebredde_adt_fart_u_atk_midtrekkverk_motorveg").to_crs(25833)

plot(veg_ER, mappe + r"\andel_FMO_ER.png")
plot(veg_F, mappe + r"\andel_FMO_F.png")
