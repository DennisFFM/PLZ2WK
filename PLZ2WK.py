import sys
import os
import re
import zipfile
import requests
import tempfile
from bs4 import BeautifulSoup
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QHBoxLayout, QSplashScreen, QFileDialog, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPixmap
import pandas as pd
from functools import partial
import geopandas as gpd

STARTJAHR = 2017
AKTUELLES_JAHR = datetime.now().year
BASIS_URL = "https://www.bundeswahlleiterin.de/bundestagswahlen/{}/wahlkreiseinteilung/downloads.html"
DOWNLOAD_REGEX = re.compile(r"geometrie_wahlkreise_vg250_(geo_shp|shp_geo)\.zip", re.IGNORECASE)
PLZ_URL = "https://services2.arcgis.com/jUpNdisbWqRpMo35/arcgis/rest/services/PLZ_Gebiete/FeatureServer/replicafilescache/PLZ_Gebiete_-6414732440474739110.zip"

class ScraperThread(QThread):
    progress = pyqtSignal(int, int)
    url_checked = pyqtSignal(str, bool)
    finished = pyqtSignal(list)

    def run(self):
        self.links = []
        jahre = list(range(STARTJAHR, AKTUELLES_JAHR + 1))
        for index, jahr in enumerate(jahre):
            url = BASIS_URL.format(jahr)
            try:
                r = requests.get(url, timeout=10)
                soup = BeautifulSoup(r.text, 'html.parser')
                link_tags = soup.find_all('a', href=True)
                matching_links = [tag['href'] for tag in link_tags if DOWNLOAD_REGEX.search(tag['href'])]
                if matching_links:
                    for link in matching_links:
                        full_link = requests.compat.urljoin(url, link)
                        self.links.append((jahr, full_link))
                    self.url_checked.emit(url, True)
                else:
                    self.url_checked.emit(url, False)
            except Exception as e:
                print(f"Fehler beim Abrufen von {url}: {e}")
                self.url_checked.emit(url, False)
            self.progress.emit(index + 1, len(jahre))
        self.finished.emit(self.links)

from PyQt6.QtWidgets import QLineEdit

class SplashScreen(QWidget):
    def __init__(self, total):
        super().__init__()
        self.setWindowTitle("Daten werden geladen ...")
        self.resize(600, 200)
        self.setStyleSheet("background-color: black; color: white;")

        self.layout = QVBoxLayout()



        
        
        self.label = QLabel("Initialisiere ...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 12))

        self.progress = QProgressBar()
        self.progress.setRange(0, total)
        self.progress.setValue(0)
        self.progress.setStyleSheet("QProgressBar::chunk { background-color: white; }")

        self.log = QLabel("")
        self.log.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log.setWordWrap(True)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.progress)
        self.layout.addWidget(self.log)
        self.setLayout(self.layout)

    def update_progress(self, current, total):
        self.label.setText(f"{current} von {total} Jahren verarbeitet ...")
        self.progress.setValue(current)

    def log_url(self, url, success):
        color = "green" if success else "red"
        self.log.setText(f"<span style='color:{color}'>{url}</span>")

from PyQt6.QtWidgets import QLineEdit

class DownloaderApp(QWidget):
    def __init__(self, links):
        super().__init__()
        self.links = links
        self.plz_shapefile = None
        self.wk_shapefile = None
        self.ensure_plz_shapefile_exists()
        self.setWindowTitle("Wahlkreis-Downloader")
        self.resize(1200, 600)


        self.layout = QVBoxLayout()

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter nach PLZ oder Wahlkreis...")
        self.filter_input.textChanged.connect(self.filter_table)
        self.filter_input.hide()
        self.layout.addWidget(self.filter_input)

        self.tabelle = QTableWidget()
        self.tabelle.setSortingEnabled(True)
        self.tabelle.setColumnCount(3)
        self.tabelle.setHorizontalHeaderLabels(["Jahr", "Download-Link", "Mit PLZ matchen"])

        self.tabelle.setRowCount(len(self.links))
        
        for row, (jahr, url) in enumerate(self.links):
            jahr_text = f"BTW {jahr}" if "bundestagswahlen" in url else str(jahr)
            self.tabelle.setItem(row, 0, QTableWidgetItem(jahr_text))
            self.tabelle.setItem(row, 1, QTableWidgetItem(url))

            if DOWNLOAD_REGEX.search(url):
                match_btn = QPushButton("Mit PLZ matchen")
                match_btn.clicked.connect(partial(self.download_extract_and_map, url))
                self.tabelle.setCellWidget(row, 2, match_btn)
                match_btn.setProperty("removable", True)

        self.download_label = QLabel("Download-Status")
        self.download_bar = QProgressBar()

        self.layout.addWidget(self.tabelle)
        self.layout.addWidget(self.download_label)
        self.layout.addWidget(self.download_bar)

        self.setLayout(self.layout)
        self.tabelle.resizeColumnsToContents()

    def ensure_plz_shapefile_exists(self):
        local_filename = os.path.join(tempfile.gettempdir(), os.path.basename(PLZ_URL))
        extract_path = os.path.join(tempfile.gettempdir(), "plz_shapefiles")

        if self.plz_shapefile and os.path.exists(self.plz_shapefile):
            return

        if not os.path.exists(extract_path):
            os.makedirs(extract_path, exist_ok=True)

        if not os.path.exists(local_filename):
            self.download_label.setText("PLZ-Daten werden heruntergeladen...")
            try:
                with requests.get(PLZ_URL, stream=True) as r:
                    r.raise_for_status()
                    with open(local_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
            except Exception as e:
                self.download_label.setText(f"Fehler beim PLZ-Download: {e}")
                return

        try:
            with zipfile.ZipFile(local_filename, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            for root, dirs, files in os.walk(extract_path):
                for file in files:
                    if file.endswith(".shp"):
                        self.plz_shapefile = os.path.join(root, file)
                        return

        except Exception as e:
            self.download_label.setText(f"Fehler beim Entpacken der PLZ-Daten: {e}")

    def download_file(self, url):
        self.download_label.setText(f"Lade: {url}")
        local_filename = os.path.join(tempfile.gettempdir(), os.path.basename(url))
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                downloaded = 0
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                percent = int(downloaded * 100 / total)
                                self.download_bar.setValue(percent)
            self.download_label.setText(f"Download abgeschlossen: {local_filename}")
        except Exception as e:
            self.download_label.setText(f"Fehler: {e}")

    def download_and_extract_plz(self):
        self.download_label.setText("Lade PLZ-Daten...")
        local_filename = os.path.join(tempfile.gettempdir(), os.path.basename(PLZ_URL))
        try:
            with requests.get(PLZ_URL, stream=True) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                downloaded = 0
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                percent = int(downloaded * 100 / total)
                                self.download_bar.setValue(percent)

            with zipfile.ZipFile(local_filename, 'r') as zip_ref:
                extract_path = os.path.join(tempfile.gettempdir(), "plz_shapefiles")
                zip_ref.extractall(extract_path)

            self.download_label.setText(f"PLZ-Daten entpackt: {extract_path}")

            # Suche nach der .shp-Datei
            for root, dirs, files in os.walk(extract_path):
                for file in files:
                    if file.endswith(".shp"):
                        self.plz_shapefile = os.path.join(root, file)
                        break
        except Exception as e:
            self.download_label.setText(f"Fehler beim PLZ-Download: {e}")

        
    def filter_table(self, text):
        text = text.strip().lower()
        for row in range(self.tabelle.rowCount()):
            match = False
            for col in range(self.tabelle.columnCount()):
                item = self.tabelle.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            self.tabelle.setRowHidden(row, not match)

    def download_extract_and_map(self, url):
        if not self.plz_shapefile:
            self.download_label.setText("PLZ-Shapefile nicht gefunden. Bitte zuerst PLZ-Daten laden.")
            return

        self.download_label.setText("Lade Wahlkreisdaten...")
        local_filename = os.path.join(tempfile.gettempdir(), os.path.basename(url))
        extract_path = os.path.join(tempfile.gettempdir(), os.path.splitext(os.path.basename(url))[0])

        try:
            if not os.path.exists(local_filename):
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(local_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

            with zipfile.ZipFile(local_filename, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            wk_shapefile = None
            for root, dirs, files in os.walk(extract_path):
                for file in files:
                    if file.endswith(".shp"):
                        wk_shapefile = os.path.join(root, file)
                        break

            if not wk_shapefile:
                self.download_label.setText("Keine Shapefile in ZIP gefunden.")
                return

            self.download_label.setText("Verarbeite Geodaten...")

            gdf_plz = gpd.read_file(self.plz_shapefile).to_crs("EPSG:25832")
            gdf_wk = gpd.read_file(wk_shapefile).to_crs("EPSG:25832")

            gdf_joined = gpd.sjoin(gdf_plz, gdf_wk, how="inner", predicate="intersects")

            # Versuche dynamisch eine geeignete Spalte für den Wahlkreis zu identifizieren
            wk_spalten = [col for col in gdf_joined.columns if col.lower() in ["wknr", "wkr_nr", "nummer", "wahlkreis", "wkr"] or col.lower().startswith("wk")]

            if not wk_spalten:
                raise ValueError(f"Keine geeignete Wahlkreis-Spalte gefunden. Verfügbare Spalten: {list(gdf_joined.columns)}")

            wkr_spalte = wk_spalten[0]
            result_df = gdf_joined[["plz", wkr_spalte, "note", "einwohner", "qkm"]].drop_duplicates()

            self.tabelle.setRowCount(len(result_df))
            self.tabelle.setColumnCount(5)
            self.tabelle.setHorizontalHeaderLabels(["PLZ", "Wahlkreis", "Hinweis", "Einwohner", "Fläche (qkm)"])


            # Entferne alle vorherigen Buttons
            for row in range(self.tabelle.rowCount()):
                widget = self.tabelle.cellWidget(row, 2)
                if widget and widget.property("removable"):
                    self.tabelle.removeCellWidget(row, 2)
            for i, row in result_df.iterrows():
                self.tabelle.setItem(i, 0, QTableWidgetItem(str(row["plz"])))
                self.tabelle.setItem(i, 1, QTableWidgetItem(str(row[wkr_spalte])))
                self.tabelle.setItem(i, 2, QTableWidgetItem(str(row.get("note", ""))))
                self.tabelle.setItem(i, 3, QTableWidgetItem(str(row.get("einwohner", ""))))
                self.tabelle.setItem(i, 4, QTableWidgetItem(str(row.get("qkm", ""))))

                self.download_label.setText("Mapping abgeschlossen.")
                self.filter_input.show()

        except Exception as e:
            self.download_label.setText(f"Fehler beim Mapping: {e}")

        self.tabelle.resizeColumnsToContents()


    def load_and_map_shapefiles(self):
        if not self.plz_shapefile:
            self.download_label.setText("PLZ-Shapefile nicht gefunden. Bitte zuerst PLZ-Daten laden.")
            return

        shp_path, _ = QFileDialog.getOpenFileName(self, "Wahlkreis-Shapefile auswählen", "", "Shapefiles (*.shp)")
        if not shp_path:
            return

        self.download_label.setText("Lade und verarbeite Shapefiles...")

        try:
            gdf_plz = gpd.read_file(self.plz_shapefile).to_crs("EPSG:25832")
            gdf_wk = gpd.read_file(shp_path).to_crs("EPSG:25832")

            gdf_joined = gpd.sjoin(gdf_plz, gdf_wk, how="inner", predicate="intersects")
            result_df = gdf_joined[["plz", "WKNR"]].drop_duplicates()

            # Ergebnis anzeigen (z. B. als neue Tabelle)
            self.tabelle.setRowCount(len(result_df))
            self.tabelle.setColumnCount(2)
            self.tabelle.setHorizontalHeaderLabels(["PLZ", "Wahlkreis"])
            for i, row in result_df.iterrows():
                self.tabelle.setItem(i, 0, QTableWidgetItem(str(row["plz"])))
                self.tabelle.setItem(i, 1, QTableWidgetItem(str(row["WKNR"])))

            self.download_label.setText("Mapping abgeschlossen.")
        except Exception as e:
            self.download_label.setText(f"Fehler beim Mapping: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)

    splash = SplashScreen(total=AKTUELLES_JAHR - STARTJAHR + 1)
    splash.show()

    def show_main_window(links):
      global hauptfenster  # Referenz behalten, sonst wird das Fenster geschlossen
      splash.close()
      hauptfenster = DownloaderApp(links)
      hauptfenster.show()


    scraper = ScraperThread()
    scraper.progress.connect(splash.update_progress)
    scraper.url_checked.connect(splash.log_url)
    scraper.finished.connect(show_main_window)
    scraper.start()

    sys.exit(app.exec())
