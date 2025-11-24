import time


class HpActionController:
    def __init__(
        self,
        send_command_callback,
        spoil_key="F2",
        no_target_command=None,
        dead_target_command=None,
        alive_target_command=None,
        spoil_enabled=True,
        cooldown_sec=0.5,
        # Новые опции:
        far_target_command=None,
        hp_stable_threshold_sec=2.0,
        hp_change_epsilon=0.01,
    ):
        """
        Контроллер для управления действиями по HP цели с поддержкой спойла и свипа.

        :param send_command_callback: функция для отправки команды (строка, например 'F2')
        :param spoil_key: команда для спойла (например, 'F2')
        :param no_target_command: команда при отсутствии цели
        :param dead_target_command: команда при мёртвой цели
        :param alive_target_command: команда при живой цели (атака)
        :param spoil_enabled: включён ли спойл
        :param cooldown_sec: минимальный интервал между отправками команд
        :param far_target_command: команда при состоянии "далеко" (цель жива, но HP стабильный)
        :param hp_stable_threshold_sec: сколько секунд HP должен не изменяться, чтобы считаться "далеко"
        :param hp_change_epsilon: порог изменения HP, считающийся значимым (float)
        """
        self.send_command_callback = send_command_callback

        self.spoil_key = spoil_key
        self.no_target_command = no_target_command
        self.dead_target_command = dead_target_command
        self.alive_target_command = alive_target_command

        # Новое:
        self.far_target_command = far_target_command
        self.hp_stable_threshold_sec = hp_stable_threshold_sec
        self.hp_change_epsilon = hp_change_epsilon

        self.spoil_enabled = spoil_enabled
        self.cooldown_sec = cooldown_sec

        self.current_state = None  # "no_target", "dead_target", "alive_target", None
        self.last_command = None
        self.last_command_time = 0

        self.spoil_active = None
        self.waiting_for_sweep = False

        # Для трекинга изменений HP (новое)
        self.hp_last_value = None
        self.hp_last_change_time = 0.0

        self.enabled = True  # общий флаг включения контроллера

    def set_spoil_key(self, key: str):
        print(f"[HpActionController] Установлен spoil_key: {key}")
        self.spoil_key = key.strip()

    def set_no_target_command(self, cmd: str):
        print(f"[HpActionController] Установлена команда no_target: {cmd}")
        self.no_target_command = cmd.strip() if cmd else None

    def set_dead_target_command(self, cmd: str):
        print(f"[HpActionController] Установлена команда dead_target: {cmd}")
        self.dead_target_command = cmd.strip() if cmd else None

    def set_alive_target_command(self, cmd: str):
        print(f"[HpActionController] Установлена команда alive_target: {cmd}")
        self.alive_target_command = cmd.strip() if cmd else None

    # Новый сеттер для far_target
    def set_far_target_command(self, cmd: str):
        print(f"[HpActionController] Установлена команда far_target: {cmd}")
        self.far_target_command = cmd.strip() if cmd else None

    def set_sweep_key(self, key: str):
        print(f"[HpActionController] Установлен sweep_key: {key}")
        self.sweep_key = key.strip() if key else None

    def set_cooldown(self, cooldown: float):
        print(f"[HpActionController] Установлен cooldown: {cooldown}")
        self.cooldown_sec = cooldown

    def set_spoil_enabled(self, enabled: bool):
        print(f"[HpActionController] Установлен spoil_enabled: {enabled}")
        self.spoil_enabled = enabled

    # Сеттеры для порога и eps (новые)
    def set_hp_stable_threshold(self, seconds: float):
        print(f"[HpActionController] Установлен hp_stable_threshold_sec: {seconds}")
        try:
            self.hp_stable_threshold_sec = float(seconds)
        except Exception:
            pass

    def set_hp_change_epsilon(self, eps: float):
        print(f"[HpActionController] Установлен hp_change_epsilon: {eps}")
        try:
            self.hp_change_epsilon = float(eps)
        except Exception:
            pass

    def set_spoil_state(self, is_spoiled: bool, can_sweep: bool):
        self.spoil_active = is_spoiled
        self.waiting_for_sweep = can_sweep
        print(
            f"[HpActionController] set_spoil_state: spoil_active={self.spoil_active}, waiting_for_sweep={self.waiting_for_sweep}"
        )

    def update(self, target_state: str, hp_percent: float):
        print(
            f"[HpActionController] update start: spoil_active={self.spoil_active}, current_state={self.current_state}, target_state={target_state}"
        )

        if not self.enabled:
            print("[HpActionController] update: обработка выключена, ничего не делаем")
            return

        now = time.time()

        if self.spoil_enabled:
            if (
                self.current_state != target_state
            ) and target_state == "alive_target":  # цель изменилась
                print("[HpActionController] Новая цель — сброс состояния спойла")
                self.spoil_active = False
                self.waiting_for_sweep = False

        """
        Обновить состояние цели и отправить команду при необходимости.
        Также управляет логикой спойла и свипа.

        :param target_state: "no_target", "dead_target", "alive_target"
        :param hp_percent: процент HP (float)
        """
        print(
            f"[HpActionController] update: target_state={target_state}, hp_percent={hp_percent}, enabled={self.enabled}"
        )

        if not self.enabled:
            print("[HpActionController] update: обработка выключена, ничего не делаем")
            return

        now = time.time()

        # Сброс спойла при смене цели на живую
        if self.spoil_enabled:
            if (
                self.current_state in [None, "no_target", "dead_target"]
                and target_state == "alive_target"
                and not self.spoil_active  # Добавлено условие
            ):
                print("[HpActionController] Новая цель — сброс состояния спойла")
                self.spoil_active = False
                self.waiting_for_sweep = False

            # Если цель умерла и спойл активен и можно свипать, отправляем свип
            if (
                target_state == "dead_target"
                and self.spoil_active
                and self.waiting_for_sweep
            ):
                self.try_sweep()
                self.waiting_for_sweep = False

        cmd_map = {
            "no_target": self.no_target_command,
            "dead_target": self.dead_target_command,
            "alive_target": None,  # обработаем отдельно
            # поддержка far_target (новое)
            "far_target": self.far_target_command,
        }

        # --- Новая логика: определение effective_state с учётом стабильности HP ---
        effective_state = target_state

        if target_state == "alive_target":
            # инициализация трекинга HP при заходе на живую цель
            if self.hp_last_value is None or self.current_state not in ["alive_target", "far_target"]:
                self.hp_last_value = hp_percent
                self.hp_last_change_time = now
                print("[HpActionController] Инициализирован трекинг HP для живой цели")

            # если HP изменился существенно — обновляем время изменения
            if abs(hp_percent - (self.hp_last_value if self.hp_last_value is not None else hp_percent)) > getattr(self, "hp_change_epsilon", 0.01):
                self.hp_last_value = hp_percent
                self.hp_last_change_time = now
                print(f"[HpActionController] HP изменился: {hp_percent} (сброс таймера стабильности)")
                if self.current_state == "far_target":
                    print("[HpActionController] Цель перестала быть 'далеко' — HP пошёл")
            else:
                # HP не изменился существенно — проверяем длительность стабильности
                stable_duration = now - (self.hp_last_change_time or now)
                print(f"[HpActionController] HP стабилен уже {stable_duration:.2f}s (порог {getattr(self, 'hp_stable_threshold_sec', 2.0)}s)")
                if stable_duration >= getattr(self, "hp_stable_threshold_sec", 2.0):
                    effective_state = "far_target"
        else:
            # если цели нет или она мертва — сбрасываем трекинг HP
            if self.hp_last_value is not None:
                print("[HpActionController] Сбрасываю трекинг HP (цель не жива или отсутствует)")
            self.hp_last_value = None
            self.hp_last_change_time = 0.0

        # Отправка команд для no_target, dead_target, far_target
        if effective_state in ["no_target", "dead_target", "far_target"]:
            cmd = cmd_map.get(effective_state)
            if cmd and (
                self.last_command != cmd
                or now - self.last_command_time > self.cooldown_sec
            ):
                print(f"[HpActionController] Отправляю команду {effective_state}: {cmd}")
                self.send_command_callback(cmd)
                self.last_command = cmd
                self.last_command_time = now

                # Новая логика: far_target — одноразовое (транзиентное) событие.
                # После отправки команды для далёкой цели, если целевая сущность по-прежнему жива,
                # мы сбрасываем статус "далеко" и продолжаем работу как для живой цели:
                # просто перезапускаем трекинг HP и не шлём немедленно команду для alive.
                if effective_state == "far_target" and target_state == "alive_target":
                    print("[HpActionController] После команды far_target: выполняем транзиентный сброс far-статуса и перезапускаем трекинг HP")
                    # Считаем текущее значение HP стартовым для нового ожидания
                    self.hp_last_value = hp_percent
                    self.hp_last_change_time = now
                    # Вернёмся к состоянию alive — дальнейшая логика будет работать на следующих вызовах update
                    effective_state = "alive_target"
                    # Обновляем current_state, но не выполняем атаку сейчас — завершаем update,
                    # чтобы следующая итерация уже шла с обновлённым трекингом.
                    self.current_state = "alive_target"
                    return

        # Обработка alive_target с учётом спойла
        if effective_state == "alive_target":
            if self.spoil_enabled:
                if not self.spoil_active:
                    print(
                        "[HpActionController] Спойл не активен, пытаемся применить спойл"
                    )
                    self.try_spoil()
                else:
                    if self.alive_target_command and (
                        self.last_command != self.alive_target_command
                        or now - self.last_command_time > self.cooldown_sec
                    ):
                        print("[HpActionController] Спойл активен — атакуем цель")
                        self.send_command_callback(self.alive_target_command)
                        self.last_command = self.alive_target_command
                        self.last_command_time = now
            else:
                if self.alive_target_command and (
                    self.last_command != self.alive_target_command
                    or now - self.last_command_time > self.cooldown_sec
                ):
                    print(
                        f"[HpActionController] Отправляю команду alive_target: {self.alive_target_command}"
                    )
                    self.send_command_callback(self.alive_target_command)
                    self.last_command = self.alive_target_command
                    self.last_command_time = now
        else:
            if effective_state not in ["no_target", "dead_target", "far_target", "alive_target"]:
                print(f"[HpActionController] Неизвестное состояние: {effective_state}")

        self.current_state = effective_state

    def try_spoil(self):
        if self.spoil_key and not self.spoil_active:
            print(f"[HpActionController] Отправляю Spoil: {self.spoil_key}")
            self.send_command_callback(self.spoil_key)
        else:
            print("[HpActionController] Спойл уже активен или ключ не задан")

    def try_sweep(self):
        if hasattr(self, "sweep_key") and self.sweep_key:
            print(f"[HpActionController] Отправляю Sweep: {self.sweep_key}")
            self.send_command_callback(self.sweep_key)
        else:
            print("[HpActionController] Ключ свипа не задан")

    def stop(self):
        self.enabled = False
        self.spoil_active = False
        self.waiting_for_sweep = False
        self.current_state = None
        self.last_command = None
        self.last_command_time = 0
        self.hp_last_value = None
        self.hp_last_change_time = 0.0
        print("[HpActionController] Контроллер остановлен")

    def start(self):
        self.enabled = True
        print("[HpActionController] Контроллер запущен")
