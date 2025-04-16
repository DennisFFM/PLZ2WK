import sys
import os
import re
import zipfile
import requests
import tempfile
from bs4 import BeautifulSoup
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QMenu, QMessageBox,
    QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QHBoxLayout, QSplashScreen, QFileDialog, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPixmap, QAction
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lade Daten...")
        self.setGeometry(100, 100, 400, 100)
        layout = QVBoxLayout()
        label = QLabel("Daten werden geladen, bitte warten...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)


class DownloaderApp(QMainWindow):
    def __init__(self, links):
        super().__init__()
        self.setWindowTitle("Wahlkreis-PLZ-Mapper")
        self.resize(600, 200)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c2c2c;
            }
            QLabel {
                color: #f0f0f0;
                font-size: 14px;
            }
            QPushButton {
                background-color: #3a77c3;
                color: white;
                padding: 6px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2e5ea1;
            }
            QLineEdit {
                padding: 4px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #444;
                color: #f0f0f0;
            }
            QTableWidget {
                gridline-color: #444;
                background-color: #3a3a3a;
                alternate-background-color: #2e2e2e;
                selection-background-color: #5a5a5a;
                color: #f0f0f0;
            }
            QHeaderView::section {
                background-color: #444;
                padding: 4px;
                border: 1px solid #666;
                color: #f0f0f0;
            }
        """)

        # Menüleiste
        menubar = self.menuBar()
        datei_menu = menubar.addMenu("Datei")
        info_menu = menubar.addMenu("Info")

        export_action = QAction("Export als CSV", self)
        export_action.triggered.connect(self.export_csv)
        datei_menu.addAction(export_action)

        neustarten_action = QAction("Neustarten", self)
        neustarten_action.triggered.connect(self.reset_to_start)
        datei_menu.addAction(neustarten_action)

        beenden_action = QAction("Beenden", self)
        beenden_action.triggered.connect(QApplication.instance().quit)
        datei_menu.addAction(beenden_action)

        about_action = QAction("Über", self)
        about_action.triggered.connect(self.show_about_dialog)
        info_menu.addAction(about_action)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout()
        central_widget.setLayout(self.layout)

        self.label = QLabel("Initialisiere ...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 12))

        

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter nach PLZ oder Wahlkreis...")
        self.filter_input.textChanged.connect(self.filter_table)
        self.filter_input.hide()
        self.layout.addWidget(self.filter_input)

        self.links = links
        self.plz_shapefile = None
        self.wk_shapefile = None
        self.ensure_plz_shapefile_exists()
        self.back_button = QPushButton("Zurück")
        self.back_button.clicked.connect(self.reset_to_start)
        self.back_button.hide()
        self.layout.addWidget(self.back_button)

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

        
        self.tabelle.resizeColumnsToContents()
        total_width = sum([self.tabelle.columnWidth(i) for i in range(self.tabelle.columnCount())])
        self.resize(total_width + 60, self.tabelle.sizeHint().height() + 150)
        

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
        self.tabelle.setRowCount(len(self.links))
        self.tabelle.setColumnCount(3)
        self.tabelle.setHorizontalHeaderLabels(["Jahr", "Download-Link", "Mit PLZ matchen"])
        self.filter_input.hide()
        self.back_button.hide()

        for row, (jahr, url) in enumerate(self.links):
            jahr_text = f"BTW {jahr}" if "bundestagswahlen" in url else str(jahr)
            self.tabelle.setItem(row, 0, QTableWidgetItem(jahr_text))
            self.tabelle.setItem(row, 1, QTableWidgetItem(url))

            if DOWNLOAD_REGEX.search(url):
                match_btn = QPushButton("Mit PLZ matchen")
                match_btn.clicked.connect(partial(self.download_extract_and_map, url))
                match_btn.setProperty("removable", True)
                self.tabelle.setCellWidget(row, 2, match_btn)

        self.tabelle.resizeColumnsToContents()
        total_width = sum([self.tabelle.columnWidth(i) for i in range(self.tabelle.columnCount())])
        self.resize(total_width + 80, self.tabelle.sizeHint().height() + 150)

    def reset_to_start(self):
        self.tabelle.setRowCount(len(self.links))
        self.tabelle.setColumnCount(3)
        self.tabelle.setHorizontalHeaderLabels(["Jahr", "Download-Link", "Mit PLZ matchen"])
        self.filter_input.hide()
        self.back_button.hide()

        for row, (jahr, url) in enumerate(self.links):
            jahr_text = f"BTW {jahr}" if "bundestagswahlen" in url else str(jahr)
            self.tabelle.setItem(row, 0, QTableWidgetItem(jahr_text))
            self.tabelle.setItem(row, 1, QTableWidgetItem(url))

            if DOWNLOAD_REGEX.search(url):
                match_btn = QPushButton("Mit PLZ matchen")
                match_btn.clicked.connect(partial(self.download_extract_and_map, url))
                match_btn.setProperty("removable", True)
                self.tabelle.setCellWidget(row, 2, match_btn)

        self.tabelle.resizeColumnsToContents()
        total_width = sum([self.tabelle.columnWidth(i) for i in range(self.tabelle.columnCount())])
        self.resize(total_width + 80, self.tabelle.sizeHint().height() + 150)

    def show_about_dialog(self):
        QMessageBox.about(self, "Über", "Wahlkreis-PLZ-Mapper\n© 2025 Deine Firma oder Name")

    def show_about_dialog(self):
        QMessageBox.about(self, "Über", "Wahlkreis-PLZ-Mapper \n© 2025 Deine Firma oder Name")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV speichern", "ergebnisse.csv", "CSV-Dateien (*.csv)")
        if not path:
            return

        headers = [self.tabelle.horizontalHeaderItem(i).text() for i in range(self.tabelle.columnCount())]
        rows = []
        for row in range(self.tabelle.rowCount()):
            if self.tabelle.isRowHidden(row):
                continue
            data = []
            for col in range(self.tabelle.columnCount()):
                item = self.tabelle.item(row, col)
                data.append(item.text() if item else "")
            rows.append(data)

        df = pd.DataFrame(rows, columns=headers)
        df.to_csv(path, index=False)

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

            self.back_button.show()

        except Exception as e:
            self.download_label.setText(f"Fehler beim Mapping: {e}")

        self.tabelle.resizeColumnsToContents()
        total_width = sum([self.tabelle.columnWidth(i) for i in range(self.tabelle.columnCount())])
        self.resize(total_width + 80, self.tabelle.sizeHint().height() + 450)

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

    splash = SplashScreen()
    splash.show()

    def show_main_window(links):
        global hauptfenster
        splash.close()
        hauptfenster = DownloaderApp(links)
        hauptfenster.show()


    scraper = ScraperThread()
    # Verknüpfung entfällt für SplashScreen
    # Verknüpfung entfällt für SplashScreen
    scraper.finished.connect(lambda links: show_main_window(links))
    scraper.start()

    sys.exit(app.exec())
