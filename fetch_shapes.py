import os 
import sys 
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QFileDialog, QComboBox, QStyle, QDialog, QMessageBox, QProgressBar, QHeaderView
)
from PyQt6.QtCore import QThread, pyqtSignal

class FetchState:
    base_url = "https://www.bundeswahlleiterin.de/"
    urls = [f"https://www.bundeswahlleiterin.de/bundestagswahlen/{jahr}/wahlkreiseinteilung/downloads.html" for jahr in range(2017, datetime.now().year+1)]
    found_files = []
    table_data = pd.DataFrame(found_files, columns=["URL", "Jahr"])
    zielpfad = os.path.join(os.path.dirname(__file__), 'output.zip')

def fetch_shapes():
    for url in FetchState.urls:
        # Website abrufen
        response = requests.get(url)
        html = response.text

        # HTML parsen
        soup = BeautifulSoup(html, "html.parser")

        # Beispiel: Alle Links extrahieren
        alle_links = soup.find_all("a")

        for link in alle_links:
            href = link.get("href")
            if re.search("geometrie_wahlkreise_vg250_(geo_shp|shp_geo)\.zip", href):
                FetchState.found_files.append([re.search("btw\d\d", href).group(0)[:3].upper(), "20"+re.search("btw\d\d", href).group(0)[-2:], FetchState.base_url+href.lstrip("./")])
    FetchState.table_data = pd.DataFrame(FetchState.found_files, columns=["Wahl", "Jahr", "URL"])
                

class dialogue_fetch(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Fetcher")
        self.resize(800, 600)

        # Widgets
        #self.label = QLabel("Suchbegriff (PLZ oder Wahlkreis):")
        #self.input = QLineEdit()
        #self.search_button = QPushButton("Suchen")
        #self.load_button = QPushButton("CSV laden")
        self.table = QTableWidget()
        self.choose_button = QPushButton("Auswahl anzeigen")
        
        #self.dropdownWahl = QComboBox()


        # Layout
        layout = QVBoxLayout()
        #layout.addWidget(self.load_button)
        #layout.addWidget(self.label)
        #layout.addWidget(self.input)
        #layout.addWidget(self.search_button)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.choose_button)
        #layout.addWidget(self.dropdownWahl)
        self.setLayout(layout)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        fetch_shapes()
        self.table.resizeColumnsToContents()

        self.populate_table(FetchState.table_data)

        # Events
        self.choose_button.clicked.connect(self.zeige_auswahl)
        

    def zeige_auswahl(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            QMessageBox.information(self, "Keine Auswahl", "Bitte eine Zeile auswählen.")
            return

        wahl = self.table.item(selected_row, 0).text()
        jahr = self.table.item(selected_row, 1).text()
        url = self.table.item(selected_row, 2).text()

        self.Downloader = Downloader(url, wahl+" "+jahr)
        self.Downloader.show()
        self.close()
        
    def populate_table(self, df):
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        for row in range(len(df)):
            for col, column_name in enumerate(df.columns):
                item = QTableWidgetItem(str(df.iloc[row][column_name]))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)


class DownloadThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

    def __init__(self, url, zielpfad):
        super().__init__()
        self.url = url
        self.zielpfad = zielpfad

    def run(self):
        try:
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status()
                content_length = r.headers.get('content-length')

                total = int(content_length) if content_length and content_length.isdigit() else 0
                downloaded = 0

                if total == 0:
                    # Setze ProgressBar in "unbestimmt" Modus (animated)
                    self.progress.emit(-1)  # Signal an GUI: "animieren statt rechnen"

                with open(self.zielpfad, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total > 0:
                                percent = int(downloaded * 100 / total)
                                self.progress.emit(percent)
                            else:
                                # Wenn kein Content-Length vorhanden ist: alle 1 MB Fortschritt anzeigen
                                mb = downloaded / (1024 * 1024)
                                self.status.emit(f"{mb:.2f} MB heruntergeladen …")

            self.progress.emit(100)
            self.status.emit("Download abgeschlossen.")

        except Exception as e:
            self.status.emit(f"Fehler: {e}")

class Downloader(QWidget):
    def __init__(self, wkurl, kwchoice):
        super().__init__()
        self.kwurl = wkurl
        self.choice = kwchoice
        self.setWindowTitle("Downloader mit Fortschritt")
        self.resize(400, 150)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.choiceLabel = QLabel(self.choice)
        self.label = QLabel("Klicke auf 'Download starten'")
        self.progress_bar = QProgressBar()
        self.button = QPushButton("Download starten")

        self.layout.addWidget(self.choiceLabel)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.button)
        self.button.clicked.connect(lambda: self.starte_download(self.kwurl))

    def starte_download(self, kwurl):
        url = kwurl
        zielpfad = FetchState.zielpfad

        if not zielpfad:
            return

        self.thread = DownloadThread(url, zielpfad)
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.status.connect(self.label.setText)
        self.thread.start()
        self.label.setText("Download läuft...")





if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    
    sys.exit(app.exec())
