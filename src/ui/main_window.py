from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap
import cv2
import numpy as np

from detectors.hands.hand_detector import HandDetector
from detectors.hands.hand_gestures import HandGestureInterpreter
from core.mouse_controller import MouseController


class GestureThread(QThread):
    frame_update = pyqtSignal(np.ndarray)
    status_update = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False

    def run(self):
        self.running = True
        detector = HandDetector()
        interpreter = HandGestureInterpreter()
        controller = MouseController()

        cap = cv2.VideoCapture(0)
        screen_w, screen_h = controller.mouse.screen_w, controller.mouse.screen_h

        self.status_update.emit("Detectando...")

        while self.running:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # Detectar (devuelve frame y landmarks)
            frame, landmarks = detector.detect(frame)
            
            # Interpretar gestos
            gesture, pos, scroll = interpreter.interpret(landmarks, w, h)

            # Convertir posición de pantalla si hay gesto MOVE
            if gesture == "MOVE" and pos:
                px = np.interp(pos[0], (0, w), (0, screen_w))
                py = np.interp(pos[1], (0, h), (0, screen_h))
                controller.handle(gesture, (px, py), scroll)
            else:
                controller.handle(gesture, None, scroll)

            # Dibujar texto del gesto en el frame
            if gesture != "NONE":
                cv2.putText(frame, gesture, (20, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            self.frame_update.emit(frame)

        cap.release()
        self.status_update.emit("Inactivo")

    def stop(self):
        self.running = False


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NYX - Control por Gestos")
        self.resize(900, 600)

        self.thread = GestureThread()

        layout = QVBoxLayout()

        self.label_status = QLabel("Estado: Inactivo")
        layout.addWidget(self.label_status)

        self.label_cam = QLabel()
        self.label_cam.setFixedSize(800, 450)
        self.label_cam.setStyleSheet("background:black;")
        self.label_cam.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_cam)

        self.btn_start = QPushButton("Iniciar")
        self.btn_stop = QPushButton("Detener")

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_stop)

        self.setLayout(layout)

        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)

        self.thread.frame_update.connect(self.update_frame)
        self.thread.status_update.connect(self.update_status)

    def start(self):
        if not self.thread.isRunning():
            self.thread.start()

    def stop(self):
        self.thread.stop()

    def update_status(self, text):
        self.label_status.setText(f"Estado: {text}")

    def update_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        self.label_cam.setPixmap(
            pixmap.scaled(self.label_cam.size(), 
                         Qt.AspectRatioMode.KeepAspectRatio)
        )