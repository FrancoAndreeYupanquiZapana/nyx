import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time

pyautogui.FAILSAFE = False

# Mediapipe
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# Pantalla
screen_w, screen_h = pyautogui.size()

# Suavizado del movimiento
smooth_factor = 5
prev_x, prev_y = 0, 0

# Estados
dragging = False

def distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))

cap = cv2.VideoCapture(0)

with mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6
) as hands:

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w, c = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        if result.multi_hand_landmarks:
            mano = result.multi_hand_landmarks[0]

            # landmarks importantes
            dedo_indice = mano.landmark[8]   # punta del índice
            dedo_medio = mano.landmark[12] # punta del medio
            dedo_pulgar  = mano.landmark[4]  # punta del pulgar

            # coordenadas en píxeles
            ix, iy = int(dedo_indice.x * w), int(dedo_indice.y * h)
            mx, my = int(dedo_medio.x * w), int(dedo_medio.y * h)
            tx, ty = int(dedo_pulgar.x * w), int(dedo_pulgar.y * h)

            mp_draw.draw_landmarks(frame, mano, mp_hands.HAND_CONNECTIONS)
            
            # 1. cursor (dedo índice)
            
            screen_x = np.interp(ix, (0, w), (0, screen_w))
            screen_y = np.interp(iy, (0, h), (0, screen_h))

            final_x = prev_x + (screen_x - prev_x) / smooth_factor
            final_y = prev_y + (screen_y - prev_y) / smooth_factor
            pyautogui.moveTo(final_x, final_y)
            prev_x, prev_y = final_x, final_y

            # 2. click (pulgar + índice)
            
            d_thumb_index = distance((ix, iy), (tx, ty))
            if d_thumb_index < 45:
                cv2.putText(frame, "CLICK IZQUIERDO", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                pyautogui.click()
                time.sleep(0.25)

            # 3. click dercho (pulgar + dedo medio)

            d_thumb_middle = distance((mx, my), (tx, ty))
            if d_thumb_middle < 45:
                cv2.putText(frame, "CLICK DERECHO", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255), 2)
                pyautogui.click(button='right')
                time.sleep(0.25)

            # 4. click sostenido (arrastrar)
            # Pulgar + índice mantenidos cerrados por más tiempo

            if d_thumb_index < 45 and not dragging:
                dragging = True
                pyautogui.mouseDown()
                cv2.putText(frame, "DRAG START", (10, 140), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,100,255), 2)

            elif d_thumb_index > 70 and dragging:
                dragging = False
                pyautogui.mouseUp()
                cv2.putText(frame, "DRAG END", (10, 140), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,100,255), 2)

        cv2.imshow("Control Mouse con Gestos", frame)
        if cv2.waitKey(1) == 27:  # ESC
            break

cap.release()
cv2.destroyAllWindows()
