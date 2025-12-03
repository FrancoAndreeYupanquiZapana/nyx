from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt
import sys
import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time

class GestureThread(QThread):
    frame_update = pyqtSignal(np.ndarray)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        pyautogui.FAILSAFE = False

        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils

        screen_w, screen_h = pyautogui.size()
        smooth_factor = 6
        prev_x, prev_y = 0, 0
        prev_scroll_y = 0
        dragging = False

        cap = cv2.VideoCapture(0)

        def dist(p1, p2):
            return np.linalg.norm(np.array(p1) - np.array(p2))

        with mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        ) as hands:

            while self.running:
                ret, frame = cap.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)

                if result.multi_hand_landmarks:
                    hand = result.multi_hand_landmarks[0]

                    index_f = hand.landmark[8]
                    middle_f = hand.landmark[12]
                    thumb_f  = hand.landmark[4]

                    ix, iy = int(index_f.x * w), int(index_f.y * h)
                    mx, my = int(middle_f.x * w), int(middle_f.y * h)
                    tx, ty = int(thumb_f.x * w), int(thumb_f.y * h)

                    mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

                    # ---- MOVIMIENTO SUAVE + ALCANCE TOTAL ----
                    screen_x = np.interp(ix, (0, w), (0, screen_w * 1.35))
                    screen_y = np.interp(iy, (0, h), (0, screen_h * 1.35))

                    final_x = prev_x + (screen_x - prev_x) / smooth_factor
                    final_y = prev_y + (screen_y - prev_y) / smooth_factor
                    pyautogui.moveTo(final_x, final_y)
                    prev_x, prev_y = final_x, final_y

                    # ---- DISTANCIAS ----
                    d1 = dist((ix, iy), (tx, ty))   # pulgar + índice
                    d2 = dist((mx, my), (tx, ty))   # pulgar + medio
                    d3 = dist((ix, iy), (mx, my))   # índice + medio

                    # ---- CLICK IZQUIERDO ----
                    if d1 < 40 and not dragging:
                        pyautogui.click()
                        time.sleep(0.25)

                    # ---- CLICK DERECHO ----
                    if d2 < 40:
                        pyautogui.click(button='right')
                        time.sleep(0.25)

                    # ---- DRAG ----
                    if d1 < 40 and not dragging:
                        dragging = True
                        pyautogui.mouseDown()
                    elif d1 > 70 and dragging:
                        dragging = False
                        pyautogui.mouseUp()

                    # ---- SCROLL (pulgar + índice + medio) ----
                    if d1 < 40 and d2 < 40 and d3 < 40:
                        delta_y = iy - prev_scroll_y
                        if delta_y < -5:
                            pyautogui.scroll(40)
                        elif delta_y > 5:
                            pyautogui.scroll(-40)
                        prev_scroll_y = iy

                self.frame_update.emit(frame)

            cap.release()
        self.finished.emit()

    def stop(self):
        self.running = False



class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Control de Mouse por Gestos")
        self.resize(900, 600)

        self.thread = None

        # ---------- UI ----------
        main_layout = QVBoxLayout()

        self.label_estado = QLabel("Estado: Inactivo")
        main_layout.addWidget(self.label_estado)

        self.label_camera = QLabel()
        self.label_camera.setFixedSize(800, 450)
        self.label_camera.setStyleSheet("background-color: black;")
        self.label_camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.label_camera)

        self.btn_start = QPushButton("Iniciar detección")
        self.btn_start.clicked.connect(self.start_detection)
        main_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Detener")
        self.btn_stop.clicked.connect(self.stop_detection)
        main_layout.addWidget(self.btn_stop)

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.close_app)
        main_layout.addWidget(self.btn_close)

        self.setLayout(main_layout)

    def start_detection(self):
        if self.thread and self.thread.isRunning():
            return

        self.thread = GestureThread()
        self.thread.frame_update.connect(self.update_camera)
        self.thread.finished.connect(self.thread_finished)
        self.thread.start()
        self.label_estado.setText("Estado: Detectando...")

    def stop_detection(self):
        if self.thread:
            self.thread.stop()
            self.label_estado.setText("Estado: Detenido")

    def thread_finished(self):
        self.label_estado.setText("Estado: Inactivo")

    def close_app(self):
        if self.thread:
            self.thread.stop()
            self.thread.wait()
        self.close()

    def update_camera(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.label_camera.setPixmap(pixmap.scaled(
            self.label_camera.width(),
            self.label_camera.height(),
            Qt.AspectRatioMode.KeepAspectRatio
        ))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
