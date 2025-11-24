import time
from typing import Callable, Optional, Sequence


class HpActionController:
    STATE_NO_TARGET = "no_target"
    STATE_DEAD_TARGET = "dead_target"
    STATE_ALIVE_TARGET = "alive_target"
    STATE_FAR_TARGET = "far_target"

    def __init__(
        self,
        send_command_callback: Callable[[str], None],
        spoil_key: str = "F2",
        no_target_command: Optional[Sequence[str]] = None,
        dead_target_command: Optional[Sequence[str]] = None,
        alive_target_command: Optional[Sequence[str]] = None,
        spoil_enabled: bool = True,
        cooldown_sec: float = 0.5,
        far_target_command: Optional[Sequence[str]] = None,
        hp_stable_threshold_sec: float = 2.0,
        hp_change_epsilon: float = 0.01,
        far_transient: bool = True,
    ):
        """
        Контроллер действий по HP цели.
        Поддерживает последовательности команд для каждого состояния — список команд отправляется по очереди.
        """
        self.send_command_callback = send_command_callback

        self.spoil_key = spoil_key
        # команды храним как списки (последовательности). Для совместимости допускаем и строки в сеттерах.
        self.no_target_sequence = list(no_target_command) if no_target_command else []
        self.dead_target_sequence = (
            list(dead_target_command) if dead_target_command else []
        )
        self.alive_target_sequence = (
            list(alive_target_command) if alive_target_command else []
        )
        self.far_target_sequence = (
            list(far_target_command) if far_target_command else []
        )

        self.spoil_enabled = spoil_enabled
        self.cooldown_sec = float(cooldown_sec)

        # far detection params
        self.hp_stable_threshold_sec = float(hp_stable_threshold_sec)
        self.hp_change_epsilon = float(hp_change_epsilon)
        self.far_transient = bool(far_transient)

        # runtime
        self.current_state: Optional[str] = None
        self.last_command: Optional[str] = None
        self.last_command_time: float = 0.0

        self.spoil_active: Optional[bool] = None
        self.waiting_for_sweep: bool = False

        # hp tracking
        self.hp_last_value: Optional[float] = None
        self.hp_last_change_time: float = 0.0

        # far sent time to avoid duplicate far sends for same stability period
        self.far_sent_time: Optional[float] = None

        # indices for sequences: rotate through each sequence
        self._seq_indices = {
            self.STATE_NO_TARGET: 0,
            self.STATE_DEAD_TARGET: 0,
            self.STATE_ALIVE_TARGET: 0,
            self.STATE_FAR_TARGET: 0,
        }

        self.enabled: bool = True

    def set_spoil_key(self, key: str):
        print(f"[HpActionController] set_spoil_key: {key}")
        self.spoil_key = key.strip() if key else None

    # --- Public setters (UI uses these) ---
    def _to_sequence(self, val) -> list:
        """Normalize input to list of strings. Accept string with ';' as delimiter or a sequence."""
        if val is None:
            return []
        if isinstance(val, (list, tuple)):
            return [str(x) for x in val if x is not None and str(x).strip()]
        s = str(val)
        # поддержка старого формата: разделитель ';'
        parts = [p.strip() for p in s.split(";")]
        return [p for p in parts if p]

    def set_no_target_command(self, cmd):
        seq = self._to_sequence(cmd)
        print(f"[HpActionController] set_no_target_command -> {seq}")
        self.no_target_sequence = seq
        self._seq_indices[self.STATE_NO_TARGET] = 0

    def set_dead_target_command(self, cmd):
        seq = self._to_sequence(cmd)
        print(f"[HpActionController] set_dead_target_command -> {seq}")
        self.dead_target_sequence = seq
        self._seq_indices[self.STATE_DEAD_TARGET] = 0

    def set_alive_target_command(self, cmd):
        seq = self._to_sequence(cmd)
        print(f"[HpActionController] set_alive_target_command -> {seq}")
        self.alive_target_sequence = seq
        self._seq_indices[self.STATE_ALIVE_TARGET] = 0

    def set_far_target_command(self, cmd):
        seq = self._to_sequence(cmd)
        print(f"[HpActionController] set_far_target_command -> {seq}")
        self.far_target_sequence = seq
        self._seq_indices[self.STATE_FAR_TARGET] = 0

    def set_sweep_key(self, key: str):
        print(f"[HpActionController] set_sweep_key: {key}")
        self.sweep_key = key.strip() if key else None

    def set_cooldown(self, cooldown: float):
        print(f"[HpActionController] set_cooldown: {cooldown}")
        self.cooldown_sec = float(cooldown)

    def set_spoil_enabled(self, enabled: bool):
        print(f"[HpActionController] set_spoil_enabled: {enabled}")
        self.spoil_enabled = bool(enabled)

    def set_hp_stable_threshold(self, seconds: float):
        print(f"[HpActionController] set_hp_stable_threshold: {seconds}")
        try:
            self.hp_stable_threshold_sec = float(seconds)
        except Exception:
            pass

    def set_hp_change_epsilon(self, eps: float):
        print(f"[HpActionController] set_hp_change_epsilon: {eps}")
        try:
            self.hp_change_epsilon = float(eps)
        except Exception:
            pass

    def set_far_transient(self, transient: bool):
        print(f"[HpActionController] set_far_transient: {transient}")
        self.far_transient = bool(transient)

    def set_spoil_state(self, is_spoiled: bool, can_sweep: bool):
        self.spoil_active = bool(is_spoiled)
        self.waiting_for_sweep = bool(can_sweep)
        print(
            f"[HpActionController] set_spoil_state: spoil_active={self.spoil_active}, waiting_for_sweep={self.waiting_for_sweep}"
        )

    # --- Internal helpers ---
    def _send_command(self, cmd: str, now: float) -> None:
        """Send a single command, respect cooldown/last_command."""
        if not cmd:
            return
        if (
            self.last_command == cmd
            and (now - self.last_command_time) <= self.cooldown_sec
        ):
            print(f"[HpActionController] skip send '{cmd}' due cooldown")
            return
        print(f"[HpActionController] send command: {cmd}")
        self.send_command_callback(cmd)
        self.last_command = cmd
        self.last_command_time = now

    def _send_next_in_sequence(self, state: str, now: float) -> None:
        """Pick next command from sequence assigned to state and send it (round-robin)."""
        seq_map = {
            self.STATE_NO_TARGET: self.no_target_sequence,
            self.STATE_DEAD_TARGET: self.dead_target_sequence,
            self.STATE_ALIVE_TARGET: self.alive_target_sequence,
            self.STATE_FAR_TARGET: self.far_target_sequence,
        }
        seq = seq_map.get(state, [])
        if not seq:
            return
        idx = self._seq_indices.get(state, 0) % len(seq)
        cmd = seq[idx]
        self._send_command(cmd, now)
        # advance index
        self._seq_indices[state] = (idx + 1) % len(seq)

    def _is_hp_stable(self, hp_percent: float, now: float) -> bool:
        if self.hp_last_value is None:
            return False
        if abs(hp_percent - self.hp_last_value) > self.hp_change_epsilon:
            # hp changed -> reset baseline
            self.hp_last_value = hp_percent
            self.hp_last_change_time = now
            print(f"[HpActionController] HP changed -> reset baseline to {hp_percent}")
            return False
        stable_duration = now - (self.hp_last_change_time or now)
        print(
            f"[HpActionController] HP stable for {stable_duration:.2f}s (threshold {self.hp_stable_threshold_sec}s)"
        )
        return stable_duration >= self.hp_stable_threshold_sec

    def _enter_far_and_forget(self, now: float, hp_percent: float) -> None:
        """Send far sequence next and 'forget' far: reset baseline so controller continues normal alive processing."""
        # avoid duplicate for same stability window
        if self.far_sent_time is not None and (
            self.far_sent_time >= (self.hp_last_change_time or 0)
        ):
            print("[HpActionController] far already sent for this stability -> skip")
            return
        # send next command in far sequence
        self._send_next_in_sequence(self.STATE_FAR_TARGET, now)
        self.far_sent_time = now
        print(f"[HpActionController] far sent at {self.far_sent_time}")
        # FORGET far: reset hp tracking baseline and mark state as changed so controller treats subsequent alive as new target.
        # Important: we set hp_last_value = None so next update will initialize tracking as for a new target.
        self.hp_last_value = None
        self.hp_last_change_time = 0.0
        # mark that controller should not consider itself currently in alive/far, so next update triggers "new target" logic
        self.current_state = None
        print(
            "[HpActionController] Forgot far: hp baseline cleared and current_state set to None (new target will be treated on next update)"
        )

    # --- Main update logic ---
    def update(self, target_state: str, hp_percent: float):
        print(
            f"[HpActionController] update: {self.current_state} -> {target_state}, hp={hp_percent}"
        )

        if not self.enabled:
            print("[HpActionController] controller disabled, skipping update")
            return

        now = time.time()

        # spoil reset on new live target
        if (
            self.spoil_enabled
            and self.current_state != target_state
            and target_state == self.STATE_ALIVE_TARGET
        ):
            print("[HpActionController] New target -> reset spoil state")
            self.spoil_active = False
            self.waiting_for_sweep = False

        # handle no_target and dead_target
        if target_state in (self.STATE_NO_TARGET, self.STATE_DEAD_TARGET):
            # reset hp tracking and far marker
            self.hp_last_value = None
            self.hp_last_change_time = 0.0
            self.far_sent_time = None

            if target_state == self.STATE_NO_TARGET:
                self._send_next_in_sequence(self.STATE_NO_TARGET, now)
            else:
                self._send_next_in_sequence(self.STATE_DEAD_TARGET, now)

            if (
                target_state == self.STATE_DEAD_TARGET
                and self.spoil_active
                and self.waiting_for_sweep
            ):
                self.try_sweep()
                self.waiting_for_sweep = False

            self.current_state = target_state
            return

        # now target_state == alive
        # init tracking baseline if necessary
        if self.hp_last_value is None or self.current_state not in (
            self.STATE_ALIVE_TARGET,
            self.STATE_FAR_TARGET,
        ):
            self.hp_last_value = hp_percent
            self.hp_last_change_time = now
            self.far_sent_time = None
            print("[HpActionController] Init HP tracking for live target")

        # check HP stability
        if self._is_hp_stable(hp_percent, now):
            # send far command once and forget far (return to alive processing)
            self._enter_far_and_forget(now, hp_percent)
            # after this we treat target as new on next update (current_state was set to None inside helper)
            return

        # HP changed -> normal alive processing (spoil/attack)
        if self.spoil_enabled:
            if not self.spoil_active:
                print("[HpActionController] try to spoil")
                self.try_spoil()
            else:
                # send next alive command in sequence
                self._send_next_in_sequence(self.STATE_ALIVE_TARGET, now)
        else:
            self._send_next_in_sequence(self.STATE_ALIVE_TARGET, now)

        self.current_state = self.STATE_ALIVE_TARGET

    # spoil / sweep
    def try_spoil(self):
        if self.spoil_key and not self.spoil_active:
            print(f"[HpActionController] try_spoil send {self.spoil_key}")
            self.send_command_callback(self.spoil_key)
        else:
            print("[HpActionController] try_spoil: already spoiled or no key")

    def try_sweep(self):
        if hasattr(self, "sweep_key") and self.sweep_key:
            print(f"[HpActionController] try_sweep send {self.sweep_key}")
            self.send_command_callback(self.sweep_key)
        else:
            print("[HpActionController] try_sweep: sweep key not set")

    # control
    def stop(self):
        self.enabled = False
        self.spoil_active = False
        self.waiting_for_sweep = False
        self.current_state = None
        self.last_command = None
        self.last_command_time = 0.0
        self.hp_last_value = None
        self.hp_last_change_time = 0.0
        self.far_sent_time = None
        # reset indices
        for k in self._seq_indices:
            self._seq_indices[k] = 0
        print("[HpActionController] stopped")

    def start(self):
        self.enabled = True
        print("[HpActionController] started")
