import sys
import os
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QFileDialog, QComboBox, QStyle, QDialog
)

class AppState:
    #Paths
    dirname = os.path.dirname(__file__)
    BLTW = "BTW"
    BL = "Hessen"
    JAHR = "2025"
    WKfilesPath = "C:\\Users\\denni\\Desktop\\PLZ2WK\\shapefiles\\WK\\"+BLTW+"\\"+JAHR
    PLZfilesPath = "C:\\Users\\denni\\Desktop\\PLZ2WK\\shapefiles\\PLZGebiete\\OSM_PLZ.shp"
    WKfiles = os.listdir(WKfilesPath)
    CSVfile = os.path.join(dirname, 'output.csv')
    SelectedElection = "XXX"

    def UpdatePath():
        print(AppState.BL)
        if AppState.BLTW == "BTW":
            AppState.WKfilesPath = "C:\\Users\\denni\\Desktop\\PLZ2WK\\shapefiles\\WK\\"+AppState.BLTW+"\\"+AppState.JAHR
        else:
            AppState.WKfilesPath = "C:\\Users\\denni\\Desktop\\PLZ2WK\\shapefiles\\WK\\"+AppState.BLTW+"\\"+AppState.BL+"\\"+AppState.JAHR
        print(AppState.WKfilesPath)


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

    #def index_changed(self, i): # i is an int
    #   print(i)

    def text_changed(self, s): # s is a str
        self.textBox.setText(s)
        AppState.SelectedElection = s
        AppState.BLTW = s.split()[0]
        AppState.BL = s.split()[1]
        AppState.JAHR = s.split()[-1]

    def submit_button_click(self, s):
        viewer.setWindowTitle("CSV-Wahlkreis Viewer - "+ AppState.SelectedElection)
        AppState.UpdatePath()
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
        layout.addWidget(self.table)
        layout.addWidget(self.dropdownWahl)
        self.setLayout(layout)
        
        
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
    viewer.show()
    popup = SelectElection()
    popup.show()
    #viewer.show()
    sys.exit(app.exec())
