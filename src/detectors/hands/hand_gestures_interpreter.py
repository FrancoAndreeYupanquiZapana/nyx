import time
import numpy as np

class HandGestureInterpreter:
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