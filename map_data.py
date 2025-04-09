import os
import csv
import geopandas as gpd

# Arbeitsverzeichnis
dirname = os.path.dirname(__file__)
print(dirname)

# Shapefile PLZ
PLZshapefile = os.path.join(dirname, 'PLZGebiete\OSM_PLZ.shp')
print(PLZshapefile)

# Shapefile WK
WKshapefile = os.path.join(dirname, 'hsl_landtagswahlkreise_2023\HSL_Landtagswahlkreise_2023.shp')
print(WKshapefile)

# Output File Path
CSVfile = os.path.join(dirname, 'output.csv')

# Shapefiles laden – Pfade anpassen!
#wahlkreise = gpd.read_file("C:\\Users\\denni\\Desktop\\PLZ2WK\\BTW25WK\\btw25_geometrie_wahlkreise_vg250_shp_geo.shp")
wahlkreise = gpd.read_file(WKshapefile)
plz = gpd.read_file(PLZshapefile)

# Beide in dasselbe CRS bringen (z.B. ETRS89 / UTM zone 32N)
wahlkreise = wahlkreise.to_crs(epsg=25832)
plz = plz.to_crs(epsg=25832)

# Geometrische Schnittmenge berechnen
intersect = gpd.overlay(plz, wahlkreise, how="intersection")
#print(intersect.info())

# Fläche berechnen (optional, zur Gewichtung oder Genauigkeitsprüfung)
intersect["area_km2"] = intersect.area / 1_000_000  # in Quadratkilometer

# Ergebnis z.B. als CSV exportieren
intersect[["plz", "LWK", "LWK_NAME", "qkm", "einwohner", "note"]].to_csv(CSVfile, index=False)

input_file = csv.DictReader(open(CSVfile))

print(type(input_file))