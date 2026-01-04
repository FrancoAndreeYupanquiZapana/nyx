"""
🎮 SIMPLE MOUSE CONTROL - Basado en el código del usuario que funcionaba
===========================================================================
Control directo del mouse sin la complejidad del pipeline NYX.
"""

import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time
import threading

pyautogui.FAILSAFE = False


class SimpleHandDetector:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils

    def detect(self, frame):
        """Devuelve solo el frame procesado y los landmarks"""
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb)

        landmarks = None

        if result.multi_hand_landmarks:
            hand = result.multi_hand_landmarks[0]
            landmarks = hand.landmark
            self.mp_draw.draw_landmarks(frame, hand, self.mp_hands.HAND_CONNECTIONS)

        return frame, landmarks


class SimpleGestureInterpreter:
    def __init__(self):
        self.dragging = False
        self.last_click_time = 0
        self.prev_scroll_y = 0

    def interpret(self, landmarks, w, h):
        if landmarks is None:
            return "NONE", None, 0

        index_f  = landmarks[8]
        middle_f = landmarks[12]
        thumb_f  = landmarks[4]
        ring_f   = landmarks[16]
        pinky_f  = landmarks[20]

        ix, iy = int(index_f.x * w), int(index_f.y * h)
        mx, my = int(middle_f.x * w), int(middle_f.y * h)
        tx, ty = int(thumb_f.x * w), int(thumb_f.y * h)
        rx, ry = int(ring_f.x * w), int(ring_f.y * h)
        px, py = int(pinky_f.x * w), int(pinky_f.y * h)

        d_it = np.hypot(ix - tx, iy - ty)
        d_mt = np.hypot(mx - tx, my - ty)

        ring_down  = ry > iy
        pinky_down = py > iy
        middle_down = my > iy

        gesture = "NONE"
        pos = None
        scroll = 0

        # --------- MOVER (ÍNDICE + PULGAR EN L) ---------
        if d_it > 60 and ring_down and pinky_down and middle_down:
            gesture = "MOVE"
            pos = (ix, iy)

        # --------- CLICK IZQUIERDO ---------
        elif d_it < 35 and ring_down and pinky_down:
            now = time.time()
            if now - self.last_click_time > 0.35:
                gesture = "CLICK_LEFT"
                self.last_click_time = now

        # --------- CLICK DERECHO ---------
        elif d_mt < 35 and ring_down and pinky_down:
            gesture = "CLICK_RIGHT"

        # --------- DRAG ---------
        elif d_it < 35:
            if not self.dragging:
                self.dragging = True
                gesture = "DRAG_START"

        elif d_it > 70 and self.dragging:
            self.dragging = False
            gesture = "DRAG_END"

        # --------- SCROLL ---------
        elif d_it > 60 and d_mt > 60:
            delta = iy - self.prev_scroll_y
            if delta > 10:
                scroll = -40
                gesture = "SCROLL"
            elif delta < -10:
                scroll = 40
                gesture = "SCROLL"
            self.prev_scroll_y = iy

        return gesture, pos, scroll


class SimpleMouseController:
    def __init__(self):
        self.screen_w, self.screen_h = pyautogui.size()
        self.dragging = False
        self.prev_x = 0
        self.prev_y = 0
        self.smooth_factor = 5

    def handle(self, gesture, pos, scroll, frame_w, frame_h):
        if gesture == "MOVE" and pos:
            # Convertir de coordenadas de frame a coordenadas de pantalla
            screen_x = int((pos[0] / frame_w) * self.screen_w)
            screen_y = int((pos[1] / frame_h) * self.screen_h)
            
            # Suavizado del movimiento
            final_x = self.prev_x + (screen_x - self.prev_x) / self.smooth_factor
            final_y = self.prev_y + (screen_y - self.prev_y) / self.smooth_factor
            
            pyautogui.moveTo(final_x, final_y)
            self.prev_x, self.prev_y = final_x, final_y
            print(f"🖱️ MOVE: ({final_x:.0f}, {final_y:.0f})")

        elif gesture == "CLICK_LEFT":
            pyautogui.click()
            print("🖱️ CLICK LEFT")

        elif gesture == "CLICK_RIGHT":
            pyautogui.click(button="right")
            print("🖱️ CLICK RIGHT")

        elif gesture == "DRAG_START" and not self.dragging:
            self.dragging = True
            pyautogui.mouseDown()
            print("🖱️ DRAG START")

        elif gesture == "DRAG_END" and self.dragging:
            self.dragging = False
            pyautogui.mouseUp()
            print("🖱️ DRAG END")

        elif gesture == "SCROLL":
            pyautogui.scroll(scroll)
            print(f"🖱️ SCROLL: {scroll}")


class SimpleMouseControlSystem:
    """Sistema simple de control de mouse por gestos"""
    
    def __init__(self):
        self.detector = SimpleHandDetector()
        self.interpreter = SimpleGestureInterpreter()
        self.controller = SimpleMouseController()
        self.running = False
        self.thread = None
        self.cap = None
        
    def start(self):
        """Inicia el sistema de control"""
        if self.running:
            print("⚠️ Sistema ya está corriendo")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("✅ Sistema de control de mouse iniciado")
        
    def stop(self):
        """Detiene el sistema de control"""
        self.running = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("🛑 Sistema de control de mouse detenido")
        
    def _run_loop(self):
        """Loop principal de detección y control"""
        self.cap = cv2.VideoCapture(0)
        
        if not self.cap.isOpened():
            print("❌ No se pudo abrir la cámara")
            self.running = False
            return
            
        print("📹 Cámara abierta - Mostrando feed...")
        
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break
                
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            
            # Detectar mano
            frame, landmarks = self.detector.detect(frame)
            
            # Interpretar gesto
            gesture, pos, scroll = self.interpreter.interpret(landmarks, w, h)
            
            # Ejecutar acción
            if gesture != "NONE":
                self.controller.handle(gesture, pos, scroll, w, h)
            
            # Mostrar gesto actual
            cv2.putText(frame, f"Gesture: {gesture}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            cv2.imshow("Simple Mouse Control", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        self.stop()


# Para usar desde NYX o standalone
if __name__ == "__main__":
    print("🎮 Iniciando control simple de mouse...")
    system = SimpleMouseControlSystem()
    system.start()
    
    try:
        # Mantener el programa corriendo
        while system.running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo...")
        system.stop()
