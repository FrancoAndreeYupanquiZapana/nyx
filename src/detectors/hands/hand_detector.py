import cv2
import mediapipe as mp

class HandDetector:
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