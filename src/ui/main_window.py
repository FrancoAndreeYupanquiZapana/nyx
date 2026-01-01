# src/ui/main_window.py
from pathlib import Path

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QSystemTrayIcon, 
                             QMenu, QApplication, QGraphicsDropShadowEffect,
                             QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QPoint, QSettings
from PyQt6.QtGui import QImage, QPixmap, QIcon, QAction, QColor, QFont, QPainter, QPen, QBrush
import cv2
import numpy as np
import json
import sys
import webbrowser

from detectors.hands.hand_detector import HandDetector
from detectors.hands.hand_gestures_interpreter import HandGestureInterpreter
from core.mouse_controller import MouseController


class GestureThread(QThread):
    frame_update = pyqtSignal(np.ndarray)
    status_update = pyqtSignal(str)
    gesture_detected = pyqtSignal(str)
    fps_update = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.running = False
        self.frame_count = 0
        self.fps = 0

    def run(self):
        self.running = True
        detector = HandDetector() # detecta que posiciones usa la mano
        interpretador = HandGestureInterpreter() # interpreta gesto esta haciendo
        controlador = MouseController() # de acuerdo al interpretacion controla el mouse

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.status_update.emit("Error: No se puede abrir cámara")
            return

        screen_w, screen_h = controlador.mouse.screen_w, controlador.mouse.screen_h
        self.status_update.emit("Detectando...")
        
        fps_timer = QTimer()
        fps_timer.timeout.connect(self.calculate_fps)
        fps_timer.start(1000)

        while self.running:
            ret, frame = cap.read()
            if not ret:
                break

            self.frame_count += 1
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # Detectar
            frame, landmarks = detector.detect(frame)
            
            # Interpretar gestos
            if landmarks is not None:
                gesture, pos, scroll = interpretador.interpret(landmarks, w, h)
                self.gesture_detected.emit(gesture)

                # Ejecutar acción
                if gesture == "MOVE" and pos:
                    px = np.interp(pos[0], (0, w), (0, screen_w))
                    py = np.interp(pos[1], (0, h), (0, screen_h))
                    controlador.handle(gesture, (px, py), scroll)
                elif gesture != "NONE":
                    controlador.handle(gesture, None, scroll)

            # frame de 80x60
            mini_frame = cv2.resize(frame, (80, 60))
            self.frame_update.emit(mini_frame)

        fps_timer.stop()
        cap.release()
        self.status_update.emit("Inactivo")

    def calculate_fps(self):
        self.fps = self.frame_count
        self.frame_count = 0
        self.fps_update.emit(self.fps)

    def stop(self):
        self.running = False
        self.wait(500)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Configuración
        self.settings = QSettings("NYX", "MouseVirtual")
        self.ui_mode = self.settings.value("ui_mode", "hud", type=str)
        self.current_theme = self.settings.value("theme", "dark", type=str)
        self.is_dragging = False
        self.drag_position = QPoint()
        
        # Inicializar
        self.setup_window()
        self.setup_tray_icon()
        self.setup_themes()
        self.setup_ui()
        self.apply_theme(self.current_theme)
        
        # Thread
        self.thread = GestureThread()
        self.setup_connections()
        
        # Cargar configuración guardada
        self.load_settings()

    def setup_window(self):
        """Configura la ventana según el modo"""
        self.setWindowTitle("Non-contact Y-coordinate eXecution")

        # Ícono de la ventana
        icon_path = Path(__file__).parent.parent.parent / "assets" / "icons" / "favicon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        if self.ui_mode == "hud":
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                              Qt.WindowType.WindowStaysOnTopHint |
                              Qt.WindowType.Tool)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.resize(350, 250)
        else:  # Modo compacto
            self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
            self.resize(400, 350)
        
        self.move_to_corner()
        
        # Sombra para modo HUD
        if self.ui_mode == "hud":
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(0, 0, 0, 150))
            shadow.setOffset(0, 0)
            self.setGraphicsEffect(shadow)

    def setup_tray_icon(self):
        """Configura el ícono en la bandeja"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Menú de bandeja
        tray_menu = QMenu()
        
        # Acciones
        show_hide_action = QAction("Mostrar/Ocultar", self)
        mode_hud_action = QAction("Modo HUD", self)
        mode_compact_action = QAction("Modo Compacto", self)
        theme_dark_action = QAction("Tema Oscuro", self)
        theme_light_action = QAction("Tema Claro", self)
        save_action = QAction("Guardar Configuración", self)
        quit_action = QAction("Salir", self)
        
        # Conectar
        show_hide_action.triggered.connect(self.toggle_visibility)
        mode_hud_action.triggered.connect(lambda: self.switch_mode("hud"))
        mode_compact_action.triggered.connect(lambda: self.switch_mode("compact"))
        theme_dark_action.triggered.connect(lambda: self.apply_theme("dark"))
        theme_light_action.triggered.connect(lambda: self.apply_theme("light"))
        save_action.triggered.connect(self.save_settings)
        quit_action.triggered.connect(self.quit_app)
        
        # Menú jerárquico
        tray_menu.addAction(show_hide_action)
        tray_menu.addSeparator()
        
        mode_menu = tray_menu.addMenu("Modo")
        mode_menu.addAction(mode_hud_action)
        mode_menu.addAction(mode_compact_action)
        
        theme_menu = tray_menu.addMenu("Tema")
        theme_menu.addAction(theme_dark_action)
        theme_menu.addAction(theme_light_action)
        
        tray_menu.addAction(save_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        # Ícono
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setIcon(self.create_tray_icon())
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def create_tray_icon(self):
        """Crea un ícono para la bandeja"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fondo circular
        painter.setBrush(QBrush(QColor(79, 204, 163)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
        
        # Ícono de mano
        painter.setPen(QPen(QColor(255, 255, 255), 3))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        
        # Dibujar mano simple
        painter.drawEllipse(20, 15, 10, 10)  # Punta índice
        painter.drawEllipse(30, 20, 8, 8)    # Punta medio
        painter.drawLine(25, 25, 25, 35)     # Dedo
        
        painter.end()
        return QIcon(pixmap)

    def setup_themes(self):
        """Define temas"""
        self.themes = {
            "dark": {
                "window": "#1a1a2e",
                "header": "#0f3460",
                "text": "#eeeeee",
                "accent": "#4ecca3",
                "danger": "#e74c3c",
                "success": "#2ecc71",
                "warning": "#f39c12",
                "camera_border": "#4ecca3",
                "button": "#16213e"
            },
            "light": {
                "window": "#f5f7fa",
                "header": "#4a69bd",
                "text": "#2c3e50",
                "accent": "#3498db",
                "danger": "#e74c3c",
                "success": "#27ae60",
                "warning": "#f39c12",
                "camera_border": "#3498db",
                "button": "#dfe6e9"
            }
        }

    def setup_ui(self):
        """Configura la interfaz de usuario"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # === CABECERA (arrastrable) ===
        self.header = QLabel("🖱️ NYX - Control Gestual")
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.setFixedHeight(40)
        self.header.mousePressEvent = self.mouse_press_event
        self.header.mouseMoveEvent = self.mouse_move_event
        self.header.mouseReleaseEvent = self.mouse_release_event
        main_layout.addWidget(self.header)
        
        # === PANEL DE INFORMACIÓN ===
        info_layout = QHBoxLayout()
        
        # Estado y FPS
        status_layout = QVBoxLayout()
        self.label_status = QLabel("⏸️ Inactivo")
        self.label_fps = QLabel("FPS: 0")
        status_layout.addWidget(self.label_status)
        status_layout.addWidget(self.label_fps)
        info_layout.addLayout(status_layout)
        
        # Mini cámara
        self.label_cam = QLabel()
        self.label_cam.setFixedSize(120, 90)
        self.label_cam.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.label_cam)
        
        main_layout.addLayout(info_layout)
        
        # === GESTO ACTUAL ===
        self.label_gesture = QLabel("Gesto: Ninguno")
        self.label_gesture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.label_gesture)
        
        # === BOTONES DE CONTROL ===
        controls_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ Iniciar")
        self.btn_start.clicked.connect(self.start_detection)
        
        self.btn_stop = QPushButton("⏸ Detener")
        self.btn_stop.clicked.connect(self.stop_detection)
        self.btn_stop.setEnabled(False)  # Inicialmente deshabilitado
        
        self.btn_mode = QPushButton("🔄")
        self.btn_mode.setToolTip("Cambiar modo HUD/Compacto")
        self.btn_mode.clicked.connect(self.toggle_mode)
        
        self.btn_theme = QPushButton("🎨")
        self.btn_theme.setToolTip("Cambiar tema")
        self.btn_theme.clicked.connect(self.toggle_theme)
        
        self.btn_save = QPushButton("💾")
        self.btn_save.setToolTip("Guardar configuración")
        self.btn_save.clicked.connect(self.save_settings)
        
        for btn in [self.btn_start, self.btn_stop, self.btn_mode, 
                   self.btn_theme, self.btn_save]:
            btn.setFixedHeight(35)
            controls_layout.addWidget(btn)
        
        main_layout.addLayout(controls_layout)

        # === BOTONES PARA GESTOS ===
        gestures_buttons_layout = QHBoxLayout()

        # === PANEL ===
        self.btn_show_gestures = QPushButton("👁️ Ver Gestos")
        self.btn_show_gestures.clicked.connect(self.toggle_gestures_info)
        self.btn_show_gestures.setCheckable(True)
        gestures_buttons_layout.addWidget(self.btn_show_gestures)

        # Botón para abrir página web
        self.btn_open_web = QPushButton("🌐 Tutorial Web")
        self.btn_open_web.setToolTip("Abrir guía de gestos en el navegador")
        self.btn_open_web.clicked.connect(self.open_gestures_webpage)
        gestures_buttons_layout.addWidget(self.btn_open_web)

        main_layout.addLayout(gestures_buttons_layout)

        # === PANEL DE GESTOS (oculto inicialmente) ===
        self.gestures_info = QLabel()
        self.gestures_info.setWordWrap(True)
        self.gestures_info.setText("""
        <b>GESTOS DISPONIBLES:</b><br>
        • ✋ Mano abierta + L = Mover cursor<br>
        • 🤏 Pinza índice-pulgar = Click izquierdo<br>
        • 👌 Pinza medio-pulgar = Click derecho<br>
        • 🤏 Mantener pinza = Arrastrar<br>
        • ✌️ Todos dedos arriba = Scroll<br>
        <i>Mantén la mano estable para mejor precisión</i>
        """)
        self.gestures_info.setVisible(False)
        main_layout.addWidget(self.gestures_info)
        
        self.setLayout(main_layout)

    def open_gestures_webpage(self):
        """Abre la página de gestos en el navegador"""
        webbrowser.open("https://lunexacorp.github.io//#/nyx/docs")

    def setup_connections(self):
        """Conecta las señales"""
        self.thread.frame_update.connect(self.update_camera)
        self.thread.status_update.connect(self.update_status)
        self.thread.gesture_detected.connect(self.update_gesture)
        self.thread.fps_update.connect(self.update_fps)
        self.thread.finished.connect(self.on_thread_finished)

    def apply_theme(self, theme_name):
        """Aplica un tema"""
        if theme_name not in self.themes:
            theme_name = "dark"
        
        self.current_theme = theme_name
        theme = self.themes[theme_name]
        
        style = f"""
            QWidget {{
                background-color: {theme['window']};
                color: {theme['text']};
                font-family: 'Segoe UI', Arial;
                border-radius: 12px;
            }}
            QLabel {{
                color: {theme['text']};
            }}
            QLabel#header {{
                background-color: {theme['header']};
                color: {theme['text']};
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }}
            QPushButton {{
                background-color: {theme['button']};
                color: {theme['text']};
                border: none;
                border-radius: 6px;
                padding: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme['accent']};
            }}
            QPushButton:pressed {{
                background-color: {theme['header']};
            }}
            QPushButton:disabled {{
                background-color: #555;
                color: #999;
            }}
        """
        
        self.setStyleSheet(style)
        
        # Estilos específicos
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {theme['header']};
                color: {theme['text']};
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        
        self.label_cam.setStyleSheet(f"""
            QLabel {{
                background-color: black;
                border: 2px solid {theme['camera_border']};
                border-radius: 6px;
            }}
        """)
        
        # Colores de botones específicos
        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['success']};
                color: white;
            }}
        """)
        
        self.btn_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['danger']};
                color: white;
            }}
        """)

    # === EVENTOS DE VENTANA ===
    def mouse_press_event(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouse_move_event(self, event):
        if self.is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)

    def mouse_release_event(self, event):
        self.is_dragging = False

    def move_to_corner(self):
        """Mueve a esquina superior derecha"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 20
        y = 50
        self.move(x, y)

    # === CONTROL DE VENTANA ===
    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_visibility()

    def toggle_mode(self):
        """Cambia entre HUD y Compacto"""
        self.ui_mode = "compact" if self.ui_mode == "hud" else "hud"
        self.settings.setValue("ui_mode", self.ui_mode)
        
        # Recrear ventana
        self.setup_window()
        self.apply_theme(self.current_theme)
        self.show()

    def switch_mode(self, mode):
        """Cambia a modo específico"""
        self.ui_mode = mode
        self.settings.setValue("ui_mode", mode)
        self.setup_window()
        self.apply_theme(self.current_theme)
        self.show()

    def toggle_theme(self):
        """Alterna entre temas"""
        themes = list(self.themes.keys())
        current_index = themes.index(self.current_theme)
        next_index = (current_index + 1) % len(themes)
        new_theme = themes[next_index]
        
        self.apply_theme(new_theme)
        self.settings.setValue("theme", new_theme)

    def toggle_gestures_info(self):
        """Muestra/oculta información de gestos"""
        visible = not self.gestures_info.isVisible()
        self.gestures_info.setVisible(visible)
        self.btn_show_gestures.setText(
            "👁️ Ocultar Gestos" if visible else "👁️ Ver Gestos"
        )


    # === CONFIGURACIÓN ===
    def save_settings(self):
        """Guarda la configuración actual"""
        try:
            # Guardar posición
            self.settings.setValue("window_pos", self.pos())
            
            # Guardar otros ajustes
            config = {
                "ui_mode": self.ui_mode,
                "theme": self.current_theme,
                "gestures_visible": self.gestures_info.isVisible()
            }
            
            self.settings.setValue("config", json.dumps(config))
            
            # Mostrar mensaje
            QMessageBox.information(self, "Configuración Guardada", 
                                  "La configuración se ha guardado correctamente.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar: {str(e)}")

    def load_settings(self):
        """Carga la configuración guardada"""
        try:
            # Cargar posición
            saved_pos = self.settings.value("window_pos")
            if saved_pos:
                self.move(saved_pos)
            
            # Cargar configuración
            config_str = self.settings.value("config")
            if config_str:
                config = json.loads(config_str)
                self.ui_mode = config.get("ui_mode", self.ui_mode)
                self.current_theme = config.get("theme", self.current_theme)
                
                if config.get("gestures_visible", False):
                    self.toggle_gestures_info()
                
                self.apply_theme(self.current_theme)
        except:
            pass  # Si hay error, usar valores por defecto

    # === CONTROL DE DETECCIÓN ===
    def start_detection(self):
        """Inicia la detección de gestos"""
        if not self.thread.isRunning():
            self.thread.start()
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)

    def stop_detection(self):
        """Detiene la detección"""
        self.thread.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def on_thread_finished(self):
        """Cuando el thread termina"""
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    # === ACTUALIZACIÓN DE UI ===
    def update_camera(self, frame):
        """Actualiza la mini-cámara"""
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_img)
            self.label_cam.setPixmap(pixmap)
        except:
            pass

    def update_status(self, text):
        """Actualiza el estado"""
        icons = {
            "Inactivo": "⏸️",
            "Detectando...": "🔍",
            "Error": "❌"
        }
        icon = icons.get(text, "❓")
        self.label_status.setText(f"{icon} {text}")

    def update_gesture(self, gesture):
        """Actualiza el gesto detectado"""
        if gesture != "NONE":
            icons = {
                "MOVE": "↔ Mover",
                "CLICK_LEFT": "👆 Click Izq",
                "CLICK_RIGHT": "👉 Click Der",
                "DRAG_START": "🔽 Arrastrar",
                "DRAG_END": "🔼 Soltar",
                "SCROLL": "🔄 Scroll"
            }
            display_text = icons.get(gesture, f"❓ {gesture}")
            self.label_gesture.setText(f"Gesto: {display_text}")
        else:
            self.label_gesture.setText("Gesto: Ninguno")

    def update_fps(self, fps):
        """Actualiza el FPS"""
        color = "#2ecc71" if fps > 20 else "#f39c12" if fps > 10 else "#e74c3c"
        self.label_fps.setText(f'<span style="color: {color}">FPS: {fps}</span>')

    # === SALIDA ===
    def closeEvent(self, event):
        """Maneja el cierre"""
        self.hide()
        # Acepta el cierre
        event.close()

    def quit_app(self):
        """Cierra completamente"""
        self.thread.stop()
        self.tray_icon.hide()
        self.settings.sync()  # Guardar antes de salir
        QApplication.quit()


# principal
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Evita que la aplicación se cierre automáticamente cuando se cierra la última ventana
    # app.setQuitOnLastWindowClosed(False)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())