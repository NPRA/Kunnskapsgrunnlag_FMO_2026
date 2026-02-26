import geopandas as gpd


geopackage = r"NAVN PÅ DIN GPKG-FIL"

veg = gpd.read_file(geopackage, layer="felt2_midtrekkverk_motorveg_fart_bredde").to_crs(25833)
veg = veg[(veg["Fartsgrense"].isin((70,80)))]

for i in [7.0,7.5,8.0,8.5,9.0,9.5,10.0,10.5,11.0,11.5,12.0]:

    veg = veg[(veg["Dekkebredde"] > i)]

    motefri = veg[(~veg["Midtdeler"].isna()) & (~veg["Motorvegtype"].isna())]

    andel = motefri.geometry.length.sum() / veg.geometry.length.sum() * 100
    print(f"Andel møtefriveg på veger bredere enn {i} meter:", andel)
