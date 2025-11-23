import cv2
import numpy as np
import mss
import pyautogui


class MobSearcher:
    def __init__(self, template_path):
        img = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Template not found: {template_path}")
        if len(img.shape) == 3:
            self.template = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            self.template = img
        self.template_w, self.template_h = self.template.shape[::-1]

    def exclude_areas(self, img, exclude_rects):
        h, w = img.shape[:2]
        for x, y, width, height in exclude_rects:
            cv2.rectangle(img, (x, y), (x + width, y + height), (0, 0, 0), thickness=-1)
        return img

    def find_possible_targets(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 252, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 1))
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        morph = cv2.erode(morph, kernel)
        morph = cv2.dilate(morph, kernel)
        contours, _ = cv2.findContours(morph, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        filtered = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 30 < w < 200 and h < 30:
                filtered.append((x, y, w, h))

        filtered.sort(key=lambda r: r[1] + r[3])  # сортировка по нижней координате y+h
        return filtered, morph

    def check_circle_near_name(self, gray_img, rect):
        x, y, w, h = rect
        region_x = x + w
        region_y = y
        region_w = 20
        region_h = h
        if region_y + region_h > gray_img.shape[0]:
            region_h = gray_img.shape[0] - region_y
        if region_x + region_w > gray_img.shape[1]:
            region_w = gray_img.shape[1] - region_x
        if region_h <= 0 or region_w <= 0:
            return False, None
        roi = gray_img[region_y : region_y + region_h, region_x : region_x + region_w]
        res = cv2.matchTemplate(roi, self.template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > 0.8:
            return True, (region_x + max_loc[0], region_y + max_loc[1])
        return False, None

    def search(self, monitor_region, exclude_rects, arduino_controller=None):
        with mss.mss() as sct:
            img = np.array(sct.grab(monitor_region))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            img = self.exclude_areas(img, exclude_rects)
            targets, morph_img = self.find_possible_targets(img)
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            debug_img = img.copy()
            found_targets = []

            for rect in targets:
                x, y, w, h = rect
                found_circle, circle_pos = self.check_circle_near_name(gray_img, rect)
                color = (0, 255, 0) if found_circle else (0, 0, 255)
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), color, 2)
                if found_circle:
                    cv2.circle(debug_img, circle_pos, 10, (255, 0, 0), 2)
                    abs_x = monitor_region["left"] + x + w // 2
                    abs_y = monitor_region["top"] + y + h // 2
                    found_targets.append((abs_x, abs_y))
                    if (
                        arduino_controller
                        and arduino_controller.ser
                        and arduino_controller.ser.is_open
                    ):
                        dx, dy = self.calculate_relative_move(abs_x, abs_y)
                        arduino_controller.move_mouse(dx, dy)

            cv2.imshow("Targets", debug_img)
            cv2.imshow("Morphology", morph_img)
            cv2.waitKey(10000)

            return found_targets

    def calculate_relative_move(self, target_x, target_y):
        current_x, current_y = pyautogui.position()
        dx = max(-127, min(127, target_x - current_x))
        dy = max(-127, min(127, target_y - current_y))
        return dx, dy


# Функция для задания исключаемых областей (например, чат и центр)
def get_exclude_rects(monitor_region):
    width = monitor_region["width"]
    height = monitor_region["height"]

    left_rect = (0, height - height // 2, width // 4, height // 2)
    center_rect = (width // 2 - 40, height // 2 - 20, 80, 80)

    return [left_rect, center_rect]


# Пример использования
if __name__ == "__main__":
    monitor_region = {"left": 100, "top": 100, "width": 800, "height": 600}
    exclude_rects = get_exclude_rects(monitor_region)
    mob_searcher = MobSearcher(template_path="E:/Projectx/src/cross.png")
    arduino_controller = None  # инициализируйте при необходимости

    while True:
        targets = mob_searcher.search(monitor_region, exclude_rects, arduino_controller)
        print("Found targets:", targets)
