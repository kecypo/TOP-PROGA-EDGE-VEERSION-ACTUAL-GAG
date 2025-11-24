import tkinter as tk
import json
import os

SETTINGS_FILE = "events_settings.json"


class EventsControllerWindow(tk.Toplevel):
    def __init__(self, master, hp_action_controller):
        super().__init__(master)
        self.title("Контроллер событий HP")
        self.resizable(True, True)
        self.hp_action_controller = hp_action_controller

        # Команды и cooldown (Entry поддерживает ';' разделение для последовательности)
        tk.Label(self, text="Команда при отсутствии цели (для последовательности разделяйте ';'): ").pack(anchor="w", padx=10, pady=(10, 0))
        self.no_target_var = tk.StringVar()
        tk.Entry(self, textvariable=self.no_target_var).pack(fill=tk.X, padx=10)

        tk.Label(self, text="Команда при мёртвой цели (для последовательности разделяйте ';'): ").pack(anchor="w", padx=10, pady=(10, 0))
        self.dead_target_var = tk.StringVar()
        tk.Entry(self, textvariable=self.dead_target_var).pack(fill=tk.X, padx=10)

        tk.Label(self, text="Команда при живой цели (для последовательности разделяйте ';'): ").pack(anchor="w", padx=10, pady=(10, 0))
        self.alive_target_var = tk.StringVar()
        tk.Entry(self, textvariable=self.alive_target_var).pack(fill=tk.X, padx=10)

        tk.Label(self, text="Cooldown (сек): ").pack(anchor="w", padx=10, pady=(10, 0))
        self.cooldown_var = tk.DoubleVar()
        tk.Entry(self, textvariable=self.cooldown_var).pack(fill=tk.X, padx=10)

        # Spoil
        self.spoil_enabled_var = tk.BooleanVar()
        self.spoil_enabled_check = tk.Checkbutton(
            self,
            text="Включить спойл мобов",
            variable=self.spoil_enabled_var,
            command=self.on_spoil_enabled_changed,
        )
        self.spoil_enabled_check.pack(anchor="w", padx=10, pady=(15, 0))

        tk.Label(self, text="Клавиша Spoil: ").pack(anchor="w", padx=10, pady=(10, 0))
        self.spoil_key_var = tk.StringVar()
        tk.Entry(self, textvariable=self.spoil_key_var).pack(fill=tk.X, padx=10)

        tk.Label(self, text="Клавиша Sweep: ").pack(anchor="w", padx=10, pady=(10, 0))
        self.sweep_key_var = tk.StringVar()
        tk.Entry(self, textvariable=self.sweep_key_var).pack(fill=tk.X, padx=10)

        # Новые поля: far_target и пороги HP
        tk.Label(self, text="Команда при далёкой цели (far_target) (для последовательности разделяйте ';'): ").pack(anchor="w", padx=10, pady=(15, 0))
        self.far_target_var = tk.StringVar()
        tk.Entry(self, textvariable=self.far_target_var).pack(fill=tk.X, padx=10)

        tk.Label(self, text="Время стабильности HP (сек): ").pack(anchor="w", padx=10, pady=(10, 0))
        self.hp_stable_var = tk.DoubleVar()
        self.hp_stable_var.set(2.0)
        tk.Entry(self, textvariable=self.hp_stable_var).pack(fill=tk.X, padx=10)

        tk.Label(self, text="Чувствительность изменения HP (epsilon): ").pack(anchor="w", padx=10, pady=(10, 0))
        self.hp_epsilon_var = tk.DoubleVar()
        self.hp_epsilon_var.set(0.01)
        tk.Entry(self, textvariable=self.hp_epsilon_var).pack(fill=tk.X, padx=10)

        # far transient option
        self.far_transient_var = tk.BooleanVar()
        tk.Checkbutton(self, text="far — одноразовое действие (transient)", variable=self.far_transient_var).pack(anchor="w", padx=10, pady=(10, 0))

        # Buttons
        self.save_btn = tk.Button(self, text="Сохранить настройки", command=self.save_settings)
        self.save_btn.pack(pady=10)

        self.toggle_btn = tk.Button(self, text="Старт обработки", command=self.toggle_processing)
        self.toggle_btn.pack(pady=5)

        self.status_label = tk.Label(self, text="Обработка событий: ВЫКЛ")
        self.status_label.pack(pady=10)

        self.processing_active = self.hp_action_controller.enabled
        self.update_toggle_button()

        self.load_settings()

        # Auto-fit window
        try:
            self.update_idletasks()
            w = min(self.winfo_reqwidth(), self.winfo_screenwidth() - 100)
            h = min(self.winfo_reqheight(), self.winfo_screenheight() - 100)
            self.geometry(f"{{w}}x{{h}}")
            self.minsize(self.winfo_reqwidth(), min(self.winfo_reqheight(), h))
        except Exception:
            pass

    def _parse_sequence_field(self, value):
        """Parse stored setting value: accept either list or ';' separated string."""
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return ";".join([str(x) for x in value])
        return str(value)

    def _to_list(self, s: str):
        if s is None:
            return []
        if isinstance(s, (list, tuple)):
            return [str(x) for x in s if x is not None and str(x).strip()]
        # split by ';'
        parts = [p.strip() for p in str(s).split(";")]
        return [p for p in parts if p]

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # for backward compatibility accept both string and list
                self.no_target_var.set(self._parse_sequence_field(data.get("no_target_command", "")))
                self.dead_target_var.set(self._parse_sequence_field(data.get("dead_target_command", "")))
                self.alive_target_var.set(self._parse_sequence_field(data.get("alive_target_command", "")))
                self.cooldown_var.set(float(data.get("cooldown_sec", 1)))

                self.spoil_enabled_var.set(data.get("spoil_enabled", False))
                self.spoil_key_var.set(data.get("spoil_key", ""))
                self.sweep_key_var.set(data.get("sweep_key", ""))

                self.far_target_var.set(self._parse_sequence_field(data.get("far_target_command", "")))
                self.hp_stable_var.set(float(data.get("hp_stable_threshold_sec", 2.0)))
                self.hp_epsilon_var.set(float(data.get("hp_change_epsilon", 0.01)))
                self.far_transient_var.set(data.get("far_transient", True))

                # apply to controller
                self.hp_action_controller.set_no_target_command(self._to_list(self.no_target_var.get()))
                self.hp_action_controller.set_dead_target_command(self._to_list(self.dead_target_var.get()))
                self.hp_action_controller.set_alive_target_command(self._to_list(self.alive_target_var.get()))
                self.hp_action_controller.set_cooldown(self.cooldown_var.get())

                self.hp_action_controller.set_spoil_enabled(self.spoil_enabled_var.get())
                self.hp_action_controller.set_spoil_key(self.spoil_key_var.get())
                self.hp_action_controller.set_sweep_key(self.sweep_key_var.get())

                self.hp_action_controller.set_far_target_command(self._to_list(self.far_target_var.get()))
                self.hp_action_controller.set_hp_stable_threshold(self.hp_stable_var.get())
                self.hp_action_controller.set_hp_change_epsilon(self.hp_epsilon_var.get())
                self.hp_action_controller.set_far_transient(self.far_transient_var.get())

                self.status_label.config(text="Настройки загружены из файла")
            except Exception as e:
                self.status_label.config(text=f"Ошибка загрузки: {{e}}")
                self.update_fields_from_controller()
        else:
            self.update_fields_from_controller()

    def update_fields_from_controller(self):
        self.no_target_var.set(";".join(getattr(self.hp_action_controller, "no_target_sequence", [])))
        self.dead_target_var.set(";".join(getattr(self.hp_action_controller, "dead_target_sequence", [])))
        self.alive_target_var.set(";".join(getattr(self.hp_action_controller, "alive_target_sequence", [])))
        self.cooldown_var.set(getattr(self.hp_action_controller, "cooldown_sec", 0.5))

        self.spoil_enabled_var.set(getattr(self.hp_action_controller, "spoil_enabled", False))
        self.spoil_key_var.set(getattr(self.hp_action_controller, "spoil_key", ""))
        self.sweep_key_var.set(getattr(self.hp_action_controller, "sweep_key", ""))

        self.far_target_var.set(";".join(getattr(self.hp_action_controller, "far_target_sequence", [])))
        self.hp_stable_var.set(getattr(self.hp_action_controller, "hp_stable_threshold_sec", 2.0))
        self.hp_epsilon_var.set(getattr(self.hp_action_controller, "hp_change_epsilon", 0.01))
        self.far_transient_var.set(getattr(self.hp_action_controller, "far_transient", True))

    def save_settings(self):
        # apply to controller (pass lists)
        self.hp_action_controller.set_no_target_command(self._to_list(self.no_target_var.get()))
        self.hp_action_controller.set_dead_target_command(self._to_list(self.dead_target_var.get()))
        self.hp_action_controller.set_alive_target_command(self._to_list(self.alive_target_var.get()))
        self.hp_action_controller.set_cooldown(self.cooldown_var.get())

        self.hp_action_controller.set_spoil_enabled(self.spoil_enabled_var.get())
        self.hp_action_controller.set_spoil_key(self.spoil_key_var.get())
        self.hp_action_controller.set_sweep_key(self.sweep_key_var.get())

        self.hp_action_controller.set_far_target_command(self._to_list(self.far_target_var.get()))
        self.hp_action_controller.set_hp_stable_threshold(self.hp_stable_var.get())
        self.hp_action_controller.set_hp_change_epsilon(self.hp_epsilon_var.get())
        self.hp_action_controller.set_far_transient(self.far_transient_var.get())

        # Save to file: prefer storing lists for sequences (backwards compatible)
        data = {
            "no_target_command": self._to_list(self.no_target_var.get()),
            "dead_target_command": self._to_list(self.dead_target_var.get()),
            "alive_target_command": self._to_list(self.alive_target_var.get()),
            "cooldown_sec": self.cooldown_var.get(),
            "spoil_enabled": self.spoil_enabled_var.get(),
            "spoil_key": self.spoil_key_var.get(),
            "sweep_key": self.sweep_key_var.get(),
            "far_target_command": self._to_list(self.far_target_var.get()),
            "hp_stable_threshold_sec": self.hp_stable_var.get(),
            "hp_change_epsilon": self.hp_epsilon_var.get(),
            "far_transient": self.far_transient_var.get(),
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.status_label.config(text="Настройки сохранены (и применены)")
        except Exception as e:
            self.status_label.config(text=f"Ошибка сохранения: {{e}}")

    def on_spoil_enabled_changed(self):
        self.hp_action_controller.set_spoil_enabled(self.spoil_enabled_var.get())

    def toggle_processing(self):
        if self.processing_active:
            self.hp_action_controller.stop()
            self.processing_active = False
        else:
            self.hp_action_controller.start()
            self.processing_active = True
        self.update_toggle_button()

    def update_toggle_button(self):
        if self.processing_active:
            self.toggle_btn.config(text="Стоп обработки")
            self.status_label.config(text="Обработка событий: ВКЛ")
        else:
            self.toggle_btn.config(text="Старт обработки")
            self.status_label.config(text="Обработка событий: ВЫКЛ")
