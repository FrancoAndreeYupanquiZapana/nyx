import pyautogui

class MouseActions:
    def __init__(self):
        self.screen_w, self.screen_h = pyautogui.size()
        pyautogui.FAILSAFE = False

    def move(self, x, y):
        pyautogui.moveTo(x, y)

    def left_click(self):
        pyautogui.click()

    def right_click(self):
        pyautogui.click(button="right")

    def drag_start(self):
        pyautogui.mouseDown()

    def drag_end(self):
        pyautogui.mouseUp()

    def scroll(self, amount):
        pyautogui.scroll(amount)