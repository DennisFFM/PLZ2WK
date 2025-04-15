import os
import csv
import glob
import geopandas as gpd

def map_data(a:str, b:str, c:str):

    # Shapefile PLZ
    PLZshapefile = a

    # Shapefile WK
    WKshapefile = b[0]

    # Output File Path
    CSVfile = c

    # Shapefiles laden – Pfade anpassen!
    wahlkreise = gpd.read_file(WKshapefile)
    plz = gpd.read_file(PLZshapefile)

    # Beide in dasselbe CRS bringen (z.B. ETRS89 / UTM zone 32N)
    wahlkreise = wahlkreise.to_crs(epsg=25832)
    plz = plz.to_crs(epsg=25832)

    # Geometrische Schnittmenge berechnen
    intersect = gpd.overlay(plz, wahlkreise, how="intersection")

    # Fläche berechnen (optional, zur Gewichtung oder Genauigkeitsprüfung)
    intersect["area_km2"] = intersect.area / 1_000_000  # in Quadratkilometer

    # Ergebnis z.B. als CSV exportieren
    ### HIER DYNAMISCH MACHEN
    intersect[["plz", "LWK", "LWK_NAME", "qkm", "einwohner", "note"]].to_csv(CSVfile, index=False)

    input_file = csv.DictReader(open(CSVfile))