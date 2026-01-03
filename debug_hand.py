from src.interpreters.hand_interpreter import HandInterpreter
import logging

logging.basicConfig(level=logging.ERROR)

def test_debug():
    interpreter = HandInterpreter()
    
    # 1. TEST FIST
    test_landmarks = [{'id': i, 'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 1.0} for i in range(21)]
    hand_fist = [{
        'hand_info': {'landmarks': test_landmarks, 'handedness': 'right', 'confidence': 0.9, 'frame_width': 640, 'frame_height': 480},
        'gestures': [{'gesture': 'fist', 'confidence': 0.9, 'hand': 'right'}]
    }]
    interpreter.interpret(hand_fist)
    gestures_fist = interpreter.interpret(hand_fist)
    print(f"FIST Result: {gestures_fist[0]['gesture'] if gestures_fist else 'None'}")

    # 2. TEST POINT
    test_landmarks_point = [{'id': i, 'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 1.0} for i in range(21)]
    test_landmarks_point[8]['x'] = 100/640 # Normalized in test? 
    test_landmarks_point[8]['y'] = 200/480
    # User logic: d_it > 60 and rd and pd and md
    # Tx = 320, Ty = 240
    # Ix = 100, Iy = 200
    # d_it = 223 > 60. ry(240) > iy(200). OK.
    
    hand_point = [{
        'hand_info': {'landmarks': test_landmarks_point, 'handedness': 'right', 'confidence': 0.8, 'frame_width': 640, 'frame_height': 480},
        'gestures': [{'gesture': 'point', 'confidence': 0.8, 'hand': 'right'}]
    }]
    gestures_point = interpreter.interpret(hand_point)
    print(f"POINT Result: {gestures_point[0]['gesture'] if gestures_point else 'None'}")
    if gestures_point:
        print(f"POINT Cursor: {gestures_point[0]['cursor']}")

if __name__ == "__main__":
    test_debug()
