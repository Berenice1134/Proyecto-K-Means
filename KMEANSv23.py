# Importación de módulos necesarios
import pandas as pd  # Módulo para manipulación y análisis de datos
import numpy as np  # Módulo para cálculos numéricos
from PyQt5.QtWidgets import (  # Importación de widgets de PyQt5
    QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel,
    QFileDialog, QLineEdit, QTextEdit, QScrollArea, QScrollBar, QTableWidget,
    QTableWidgetItem, QSplitter, QDialog, QMessageBox
)
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread  # Importación de clases de PyQt5 para manejo de eventos
from PyQt5.QtGui import QFont  # Importación de la clase QFont de PyQt5 para manejar fuentes
import qdarkstyle  # Módulo para aplicar estilos oscuros a la interfaz gráfica
import sys  # Módulo para interactuar con el sistema operativo
import os  # Módulo para interactuar con el sistema operativo (sistema de archivos)


class SegundoPlano(QObject):
    # Señales para comunicación entre el hilo de trabajo y la interfaz de usuario
    finished = pyqtSignal()  # Señal emitida cuando el trabajo ha finalizado
    update_signal = pyqtSignal(dict, pd.DataFrame)  # Señal para actualizar la interfaz con los resultados
    centroids_updated_signal = pyqtSignal(pd.DataFrame)  # Señal para actualizar los centroides

    def __init__(self, df, centroides):
        super().__init__()
        self.df = df  # DataFrame de entrada
        self.centroides = centroides  # Centroides iniciales
        self.cat_ix = None  # Índices de columnas categóricas
        self.range = None  # Rango de características numéricas

    def iniciaKM(self):
        # Método para ejecutar el algoritmo K-Means y emitir señales de actualización
        clusters = self.KMEAN(self.df, self.centroides)  # Ejecutar el algoritmo K-Means
        self.update_signal.emit(clusters, self.centroides)  # Emitir señal para actualizar la interfaz
        self.finished.emit()  # Emitir señal de finalización del trabajo

    def HEOM(self, centroide, objeto):
        # Función para calcular la distancia de Heom entre un centroide y un objeto
        resultados_arreglo = np.zeros(len(self.df.columns))  # Arreglo para almacenar los resultados de las distancias

        # Iterar sobre las columnas del DataFrame
        for i, columna in enumerate(self.df.columns):
            centroide[columna] = pd.to_numeric(centroide[columna], errors='coerce')  # Convertir a numérico si es posible
            objeto[columna] = pd.to_numeric(objeto[columna], errors='coerce')  # Convertir a numérico si es posible
            
            # Calcular la distancia de Heom para la columna actual
            if pd.isna(centroide[columna]) or pd.isna(objeto[columna]):  # Manejar valores faltantes
                resultados_arreglo[i] = 1  # Asignar un valor de 1 si hay valores faltantes
            elif columna in self.cat_ix:  # Si la columna es categórica
                resultados_arreglo[i] = int(centroide[columna] != objeto[columna])  # Calcular la diferencia de categoría
            else:  # Si la columna es numérica
                resultados_arreglo[i] = abs(centroide[columna] - objeto[columna]) / self.range[columna]  # Calcular la diferencia normalizada

        return np.sum(np.square(resultados_arreglo))  # Sumar los cuadrados de los resultados para obtener la distancia

    def KMEAN(self, df, centroides):
        # Implementación del algoritmo K-Means
        clusters = {}  # Diccionario para almacenar los clusters
        centroides_antiguos = centroides.copy()  # Copiar los centroides iniciales
        max_comprobaciones = len(centroides) * 4  # Límite de iteraciones para el algoritmo

        comprobaciones = 0  # Contador de iteraciones

        # Bucle principal del algoritmo K-Means
        while comprobaciones < max_comprobaciones:
            for i in range(len(centroides)):
                clusters[i] = []  # Inicializar los clusters vacíos

            # Asignar cada objeto al cluster más cercano
            for index, objeto in df.iterrows():
                # Calcular las distancias de Heom a cada centroide y asignar al cluster más cercano
                distancias = [self.HEOM(centroide, objeto) for _, centroide in centroides.iterrows()]
                cluster_asignado = distancias.index(min(distancias))  # Encontrar el índice del cluster más cercano
                clusters[cluster_asignado].append(objeto)  # Agregar el objeto al cluster correspondiente

            nuevos_centroides = []  # Lista para almacenar los nuevos centroides
            for cluster_id, cluster in clusters.items():
                if not cluster:  # Si el cluster está vacío, continuar con el siguiente
                    continue

                media_caracteristicas = []  # Lista para almacenar las medias de las características
                for columna in self.df.columns:
                    if columna not in self.cat_ix:  # Si la columna no es categórica
                        suma = sum([objeto[columna] for objeto in cluster])  # Sumar los valores de la característica
                        media = suma / len(cluster)  # Calcular la media de la característica en el cluster
                        media_caracteristicas.append(media)  # Agregar la media al lista
                    else:  # Si la columna es categórica
                        media_caracteristicas.append(cluster[0][columna])  # Usar el primer valor del cluster como media

                nuevo_centroide = pd.Series(media_caracteristicas, index=self.df.columns)  # Crear un nuevo centroide
                nuevos_centroides.append(nuevo_centroide)  # Agregar el nuevo centroide a la lista

            nuevos_centroides = pd.DataFrame(nuevos_centroides)  # Convertir la lista de centroides en DataFrame
            self.centroids_updated_signal.emit(nuevos_centroides)  # Emitir señal para actualizar los centroides

            if centroides.equals(nuevos_centroides):  # Si los centroides no cambian, terminar el algoritmo
                self.finished.emit()  # Emitir señal de finalización
                break
            else:
                centroides = nuevos_centroides.copy()  # Actualizar los centroides

            if centroides.equals(centroides_antiguos):  # Si los centroides no cambian entre iteraciones, terminar
                self.finished.emit()  # Emitir señal de finalización
                break
            else:
                centroides_antiguos = centroides.copy()  # Actualizar los centroides antiguos

            comprobaciones += 1  # Incrementar el contador de iteraciones

        return clusters  # Devolver los clusters calculados


class MiApp(QMainWindow):
    def __init__(self):
        """
        Inicializa la aplicación.
        """
        super().__init__()
        self.iGUI()
        
        self.datos_hepatitis = None  # Almacena los datos del archivo Excel
        self.cat_ix = None  # Índices de columnas categóricas
        self.iGUI()
        self.SegundoPlano_thread = None  # Hilo de trabajo para el cálculo de K-Means

    def iGUI(self):
        """
        Configura la interfaz de usuario.
        """
        # Configuración de la ventana principal
        self.setWindowTitle('K-Means Clustering')
        self.setWindowTitle('Aplicación en Pantalla Completa')
        self.showFullScreen()
    
        # Widget central y splitter para la interfaz
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        splitter = QSplitter(Qt.Horizontal)

        # Estilo de la interfaz
        self.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

        # Configuración del widget de la izquierda
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        # Etiqueta y botón para cargar el archivo Excel
        self.label = QLabel('Cargar archivo Excel:')
        fuente = QFont("Arial", 20)  
        self.setFont(fuente)
        left_layout.addWidget(self.label)
        self.load_button = QPushButton('Cargar Archivo')
        self.load_button.clicked.connect(self.cargar_archivo)
        left_layout.addWidget(self.load_button)

        # Etiqueta y campo de entrada para el número de centroides
        self.num_centroides_label = QLabel('Número de centroides:')
        fuente = QFont("Arial", 20)  
        self.setFont(fuente)
        left_layout.addWidget(self.num_centroides_label)
        self.num_centroides_input = QLineEdit()
        left_layout.addWidget(self.num_centroides_input)

        # Área de desplazamiento para mostrar los resultados
        self.result_scroll_area = QScrollArea()
        self.result_scroll_area.setWidgetResizable(True)
        left_layout.addWidget(self.result_scroll_area)
        self.result_widget = QWidget()
        self.result_scroll_area.setWidget(self.result_widget)
        self.result_layout = QVBoxLayout()
        self.result_widget.setLayout(self.result_layout)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.result_scrollbar = QScrollBar(Qt.Horizontal)
        self.result_scrollbar.valueChanged.connect(lambda value: self.result_text.horizontalScrollBar().setValue(value))
        self.result_layout.addWidget(self.result_text)

        # Botón para calcular K-Means
        self.calcular_button = QPushButton('Calcular K-Means')
        self.calcular_button.clicked.connect(self.sKM)
        left_layout.addWidget(self.calcular_button)
       
        # Botón para cerrar la aplicación
        self.boton_cerrar = QPushButton('Cerrar', self)
        self.boton_cerrar.setGeometry(700, 550, 80, 40)  
        self.boton_cerrar.clicked.connect(self.close)
        left_layout.addWidget(self.boton_cerrar)
        
        # Estilo de los botones
        fuente = QFont("Arial", 20)
        self.setFont(fuente)
        button_style = """
        QPushButton {
            background-color: #5CDB95;
            color: #05386B;
            border-radius: 10px;
            padding: 10px;
            border: 2px solid #05386B;
        }
        QPushButton:hover {
            background-color: #379683;
        }
        """
        self.load_button.setStyleSheet(button_style)
        self.calcular_button.setStyleSheet(button_style)

        # Tabla para mostrar los resultados
        self.resultados_table = QTableWidget()
        
        splitter.addWidget(left_widget)

        # Configuración del widget de la derecha
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        self.cluster_table = QTableWidget()
        self.cluster_table.setColumnCount(2)
        self.cluster_table.setHorizontalHeaderLabels(['Cluster', 'Número de Objetos'])
        right_layout.addWidget(self.cluster_table)
        
        # Estilo de la tabla
        table_style = """
QTableWidget {
    font-size: 14px; /* Ajusta el tamaño de la fuente */
    color: #EEE; /* Color del texto */
    background-color:#333; /* Color de fondo */
    border: 1px solid #ddd; /* Bordes de la tabla */
}

QTableWidget::item {
    padding: 5px; /* Espaciado interno de las celdas */
    border-color: #ddd; /* Color de los bordes de las celdas */
}

QTableWidget::item:selected {
    background-color: #555; /* Color de fondo de las celdas seleccionadas */
}

QHeaderView::section {
    background-color: #333; /* Color de fondo de los encabezados de columna */
    padding: 5px;
    border: 1px solid #ddd;
    font-size: 14px; /* Tamaño de la fuente de los encabezados */
    font-weight: bold; /* Negrita para los encabezados */
    color: #EEE;
}
"""
        # Aplicar el estilo a la tabla
        self.cluster_table.setStyleSheet(table_style)

        splitter.addWidget(right_widget)

        splitter.setSizes([int(3 * self.width() / 4), int(self.width() / 4)])
        self.layout = QVBoxLayout()
        self.layout.addWidget(splitter)
        self.central_widget.setLayout(self.layout)  
        
        # Aplicar el estilo de qdarkstyle a toda la ventana
        self.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

        # Ajustar el ancho de las columnas al contenido
        self.cluster_table.resizeColumnsToContents()
  

    def clusters(self, clusters):
        """
        Actualiza la tabla de clusters en la interfaz de usuario.

        Parameters:
            clusters (dict): Diccionario que contiene los clusters y el número de objetos en cada uno.
        """
        self.cluster_table.setRowCount(len(clusters))
        for i, (cluster_id, cluster) in enumerate(clusters.items()):
            self.cluster_table.setItem(i, 0, QTableWidgetItem(str(cluster_id)))
            self.cluster_table.setItem(i, 1, QTableWidgetItem(str(len(cluster))))

    def cargar_archivo(self):
        """
        Abre un cuadro de diálogo para cargar un archivo Excel y procesa los datos.

        Returns:
            None
        """
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_name, _ = QFileDialog.getOpenFileName(self, 'Seleccionar archivo Excel', '', 'Excel Files (*.xlsx);;All Files (*)', options=options)
        if file_name:
            df = self.abrir_archivo(file_name)
            if df is not None:
                self.result_text.append('Archivo cargado exitosamente.')
            else:
                self.result_text.append('Error al cargar el archivo.')

    def abrir_archivo(self, direccion):
        """
        Abre un archivo Excel y devuelve un DataFrame de pandas.

        Parameters:
            direccion (str): La dirección del archivo Excel.

        Returns:
            DataFrame: El DataFrame que contiene los datos del archivo Excel.
        """
        try:
            df = pd.read_excel(direccion)
            df.replace('?', np.nan, inplace=True)
            self.datos_hepatitis = df

            # Índices de columnas categóricas
            self.cat_ix = ['DIE', 'LIVE', 'SPLEEN PALPABLE', 'SPIDERS', 'ASCITES', 'VARICES', 'BILIRUBIN', 'ALK PHOSPHATE', 'SGOT', 'ALBUMIN', 'PROTIME', 'HISTOLOGY']
            self.range = {}  # Rango de características numéricas

            for columna in df.columns:
                if columna not in self.cat_ix:
                    try:
                        df[columna] = pd.to_numeric(df[columna], errors='coerce')
                        self.range[columna] = df[columna].max() - df[columna].min()
                    except ValueError:
                        self.result_text.append(f"Error al convertir la columna {columna} a valores numéricos.")

            return df
        except ValueError:
            self.result_text.append('Formato incorrecto')
            return None
        except FileNotFoundError:
            self.result_text.append('El archivo está malogrado')
            return None


    def iCent(self):
        # Pide al usuario el número de centroides
        try:
            numCentroides = int(self.num_centroides_input.text())
            if numCentroides <= 0:
                self.result_text.append("El número de centroides debe ser mayor a 0.")
                return None
            else:
                return numCentroides
        except ValueError:
            self.result_text.append("Ingresa un número válido.")
            return None

    def eCent(self, df, numCentroides):
        # Elige centroides aleatorios
        centroides = df.sample(n=numCentroides)
        return centroides

    def tablaI(self, tabla, text_widget):
        # Muestra una tabla en un widget de texto
        tabla_csv = tabla.to_csv(index=False, sep='\t')  # Se convierte el DataFrame a una cadena CSV
        text_widget.setPlainText(tabla_csv)  # Se establece el texto del widget

    def interfaz(self, clusters, centroides):
        # Actualiza la interfaz con los resultados del algoritmo
        self.clusters(clusters)

        objetos_ordenados = []

        for cluster_id, cluster in clusters.items():
            for objeto in cluster:
                objeto_con_cluster = objeto.copy()
                objeto_con_cluster['Cluster'] = cluster_id
                objetos_ordenados.append(objeto_con_cluster)

        resultado_df = pd.DataFrame(objetos_ordenados)

        # Mapeo para convertir los valores 2 y 1 a "YES" y "NO" respectivamente
        mapping = {2: "YES", 1: "NO"}

        # Remplazar los valores en las columnas específicas
        resultado_df.replace({"CLAS (DIE,LIVE)": mapping, "SEX": mapping, "STEROID": mapping, "ANTIVIRALS": mapping,
                              "FATIGUE": mapping, "MALAISE": mapping, "ANOREXIA": mapping, "LIVER BIG": mapping, "LIVER FIRM": mapping,
                              "SPLEEN PALPABLE": mapping, "SPIDERS": mapping, "ASCITES": mapping, "VARICES": mapping, "HISTOLOGY": mapping}, inplace=True)

        #self.tablaI(resultado_df, self.result_text)

        self.dialogo_resultados = ResultadosDialog(self)
        self.dialogo_resultados.mostrar_resultados(resultado_df)  
        self.dialogo_resultados.show()
        
        for row_idx, row_data in resultado_df.iterrows():
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                self.resultados_table.setItem(row_idx, col_idx, item)

        try:
            archivo_resultados = r'C:\Users\Alberto\Desktop\8vo Semestre\Mineria de Datos\Practica 2\resultados_kmeans.xlsx'
            resultado_df.to_excel(archivo_resultados, index=False)
            self.result_text.append(f"Resultados guardados en {archivo_resultados}.")
            print(f"El archivo resultados_kmeans.xlsx se guardó en: {os.path.abspath(archivo_resultados)}")

        except Exception as e:
            self.result_text.append(f"Error al guardar los resultados en un archivo Excel: {str(e)}")
            print(f"Error al guardar los resultados en un archivo Excel: {str(e)}")

    def sKM(self):
        # Inicia el cálculo de K-Means
        if self.datos_hepatitis is not None:
            numCentroides = self.iCent()
            if numCentroides is not None:
                centroidesAleatorios = self.eCent(self.datos_hepatitis, numCentroides)
                self.result_text.append("\nCentroides iniciales:")
                self.result_text.append(str(centroidesAleatorios))

                if self.SegundoPlano_thread is not None and self.SegundoPlano_thread.isRunning():
                    self.result_text.append("El cálculo de K-Means ya está en progreso.")
                else:
                    self.result_text.append("Iniciando el cálculo de K-Means en segundo plano...")
                    self.SegundoPlano_thread = QThread()

                    self.SegundoPlano = SegundoPlano(self.datos_hepatitis, centroidesAleatorios)
                    self.SegundoPlano.cat_ix = self.cat_ix
                    self.SegundoPlano.range = self.range
                    self.SegundoPlano.datos_hepatitis = self.datos_hepatitis
                    self.SegundoPlano.cat_ix = self.cat_ix
                    self.SegundoPlano.range = self.range

                    self.SegundoPlano.moveToThread(self.SegundoPlano_thread)
                    self.SegundoPlano_thread.started.connect(self.SegundoPlano.iniciaKM)
                    self.SegundoPlano.update_signal.connect(self.interfaz)
                    self.SegundoPlano.centroids_updated_signal.connect(self.actCent)
                    self.SegundoPlano.finished.connect(self.SegundoPlano_thread.quit)
                    self.SegundoPlano.finished.connect(self.SegundoPlano.deleteLater)
                    self.SegundoPlano_thread.finished.connect(self.SegundoPlano_thread.deleteLater)
                    self.SegundoPlano_thread.start()

    def actCent(self, nuevos_centroides):
        # Actualiza el texto con los nuevos centroides
        self.result_text.append("\nNuevos centroides:")
        self.result_text.append(str(nuevos_centroides))
        
 

class ResultadosDialog(QDialog):
    def __init__(self, parent=None):
        super(ResultadosDialog, self).__init__(parent)
        self.setWindowTitle('Resultados K-Means')
        self.setGeometry(500, 500, 1200, 1000)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(self)
        table_style = """
        QTableWidget {
            font-size: 14px; /* Ajusta el tamaño de la fuente */
            color: #333; /* Color del texto */
            background-color: #F8F8F8; /* Color de fondo */
            border: 1px solid #ddd; /* Bordes de la tabla */
        }
        QTableWidget::item {
            padding: 5px; /* Espaciado interno de las celdas */
            border-color: #ddd; /* Color de los bordes de las celdas */
        }
        QTableWidget::item:selected {
            background-color: #f0f0f0; /* Color de fondo de las celdas seleccionadas */
        }
        QHeaderView::section {
            background-color: #F8F8F8; /* Color de fondo de los encabezados de columna */
            padding: 5px;
            border: 1px solid #ddd;
            font-size: 14px; /* Tamaño de la fuente de los encabezados */
            font-weight: black; /* Negrita para los encabezados */
            color: #05386B;
        }
        """
        self.table.setStyleSheet(table_style)
        layout.addWidget(self.table)

        self.close_button = QPushButton('Cerrar')
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)

        self.setLayout(layout)

    def mostrar_resultados(self, df):
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)
        self.table.setRowCount(len(df))
        for row_idx, row in df.iterrows():
            for col_idx, value in enumerate(row):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
                
        
                

def main():
    # Función principal para iniciar la aplicación
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    window = MiApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
