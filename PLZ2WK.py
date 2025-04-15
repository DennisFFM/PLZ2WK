import time
import sys
import os
import glob
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QHeaderView, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import map_data as md
import fetch_shapes


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class AppState:
    #Paths
    base_dir = os.path.dirname(__file__)
    BLTW = "LTW"
    BL = "Hessen"
    JAHR = "2023"
    WKfilesPath = resource_path(os.path.join(base_dir, "data\\shapefiles\\WK\\"+BLTW+"\\Hessen\\"+JAHR))
    PLZfilesPath = resource_path(os.path.join(base_dir, "data\\shapefiles\\PLZGebiete\\OSM_PLZ.shp"))
    WKfiles = os.listdir(WKfilesPath)
    WKFile = glob.glob(WKfilesPath+'\\\\*.shp')
    CSVfile = os.path.join(base_dir, 'output.csv')
    SelectedElection = "XXX"

    def UpdatePath():
        if AppState.BLTW == "BTW":
            AppState.WKfilesPath = resource_path(os.path.join(AppState.base_dir, "data\\shapefiles\\WK\\"+AppState.BLTW+"\\"+AppState.JAHR))
            AppState.WKFile = glob.glob(AppState.WKfilesPath+'\\*.shp')
        else:
            AppState.WKfilesPath = resource_path(os.path.join(AppState.base_dir, "data\\shapefiles\\WK\\"+AppState.BLTW+"\\"+AppState.BL+"\\"+AppState.JAHR))
            AppState.WKFile = glob.glob(AppState.WKfilesPath+'\\*.shp')

class SplashScreen(QWidget):
    def __init__(self, datenmenge):
        super().__init__()
        self.setWindowTitle("Lade Anwendung …")
        self.setFixedSize(800, 200)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: black; color: white;")

        self.datenmenge = datenmenge
        self.zähler = 0

        self.label = QLabel("Starte …")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 16))

        self.label2 = QLabel("")
        self.label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label2.setFont(QFont("Arial", 8))

        self.progress = QProgressBar()
        self.progress.setRange(0, len(self.datenmenge))
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #444;
                border: 1px solid white;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: white;
            }
        """)

        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addWidget(self.label2)
        layout.addWidget(self.progress)
        layout.addStretch()
        self.setLayout(layout)

        QTimer.singleShot(0, self.lade_daten)

    def lade_daten(self):
        for index, eintrag in enumerate(self.datenmenge):
            self.label.setText(f"Lade Daten {index} von {len(self.datenmenge)} …")
            self.label2.setText(f"Aktuell: {eintrag}")
            self.progress.setValue(index + 1)

            QApplication.processEvents()  # ⬅️ wichtig, damit GUI aktualisiert wird
            time.sleep(0.1)

        self.close()
        self.hauptfenster = PLZ2WK()
        self.hauptfenster.show()

class SelectElection(QWidget):

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setWindowTitle("Startup")
        self.textBox = QLabel("Bitte wähle eine Wahl")
        self.submit_button = QPushButton("Select")

        self.dropdownWahl = QComboBox()
        self.dropdownWahl.addItem("LTW Hessen 2023")
        self.dropdownWahl.addItem("LTW Baden-Württemberg 2023")
        self.dropdownWahl.addItem("BTW 2025")
        
        cs = self.dropdownWahl.currentText()
        AppState.SelectedElection = cs
        AppState.BLTW = cs.split()[0]
        AppState.BL = cs.split()[1]
        AppState.JAHR = cs.split()[-1]
        AppState.UpdatePath()

        layout.addWidget(self.textBox)
        layout.addWidget(self.dropdownWahl)
        layout.addWidget(self.submit_button)

        # Events
        #self.dropdownWahl.currentIndexChanged.connect( self.index_changed )
        self.dropdownWahl.currentTextChanged.connect( self.text_changed )
        self.submit_button.clicked.connect(self.submit_button_click)

        self.setLayout(layout)


    def text_changed(self, s): # s is a str
        self.textBox.setText(s)
        AppState.SelectedElection = s
        AppState.BLTW = s.split()[0]
        AppState.BL = s.split()[1]
        AppState.JAHR = s.split()[-1]

    def submit_button_click(self, s):
        viewer.setWindowTitle("CSV-Wahlkreis Viewer - "+ AppState.SelectedElection)
        AppState.UpdatePath()
        md.map_data(AppState.PLZfilesPath, AppState.WKFile, AppState.CSVfile)
        self.close()


class PLZ2WK(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSV-Wahlkreis Viewer")
        self.resize(800, 600)

        # Widgets
        self.label = QLabel("Suchbegriff (PLZ oder Wahlkreis):")
        self.input = QLineEdit()
        self.search_button = QPushButton("Suchen")
        self.load_button = QPushButton("CSV laden")
        self.table = QTableWidget()
        self.dropdownWahl = QComboBox()
        

        for f in AppState.WKfiles:
            self.dropdownWahl.addItem(f)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.load_button)
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.search_button)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.dropdownWahl)
        self.setLayout(layout)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.resizeColumnsToContents()

        # Events
        self.load_button.clicked.connect(self.load_csv)
        self.search_button.clicked.connect(self.search_data)

        self.df = pd.DataFrame()  # Leerer DataFrame beim Start


    def load_csv(self):
        #file_path, _ = QFileDialog.getOpenFileName(self, "CSV-Datei auswählen", "", "CSV Files (*.csv)")
        #if file_path:
        self.df = pd.read_csv(AppState.CSVfile, dtype=str)  # Lese alle Spalten als Text
        self.populate_table(self.df)

    def search_data(self):
        query = self.input.text().strip()
        if self.df.empty or not query:
            return

        filtered = self.df[
            self.df.apply(lambda row: row.astype(str).str.contains(query, case=False, na=False).any(), axis=1)
        ]
        self.populate_table(filtered)

    def populate_table(self, df):
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        for row in range(len(df)):
            for col, column_name in enumerate(df.columns):
                item = QTableWidgetItem(str(df.iloc[row][column_name]))
                self.table.setItem(row, col, item)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    viewer = PLZ2WK()
    daten = list(range(1, 11))  # Dummy-Zahlen 1 bis 10
    splash = SplashScreen(fetch_shapes.FetchState.urls)
    print(fetch_shapes.FetchState.urls)
    splash.show()

    
    #viewer.show()
    #popup = SelectElection()
    #popup.show()
    #dialogue_fetch = fetch_shapes.dialogue_fetch()
    #dialogue_fetch.show()
    sys.exit(app.exec())
