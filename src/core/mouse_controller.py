from actions.mouse_actions import MouseActions

class MouseController:
    def __init__(self):
        self.mouse = MouseActions()
        self.dragging = False
        self.prev_x = 0
        self.prev_y = 0
        self.smooth_factor = 5

    def handle(self, gesture, pos, scroll):
        if gesture == "MOVE" and pos:
            # Suavizado del movimiento
            screen_x = pos[0]  # Ya viene interpolado
            screen_y = pos[1]
            
            final_x = self.prev_x + (screen_x - self.prev_x) / self.smooth_factor
            final_y = self.prev_y + (screen_y - self.prev_y) / self.smooth_factor
            
            self.mouse.move(final_x, final_y)
            self.prev_x, self.prev_y = final_x, final_y

        elif gesture == "CLICK_LEFT":
            self.mouse.left_click()

        elif gesture == "CLICK_RIGHT":
            self.mouse.right_click()

        elif gesture == "DRAG_START" and not self.dragging:
            self.dragging = True
            self.mouse.drag_start()

        elif gesture == "DRAG_END" and self.dragging:
            self.dragging = False
            self.mouse.drag_end()

        elif gesture == "SCROLL":
            self.mouse.scroll(scroll)