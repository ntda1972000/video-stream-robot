from typing import Iterable

from controllable_components.gpio_backend import GPIOBackend


class OutputController:
    """Manages 4 digital GPIO outputs used by web I/O toggles."""

    def __init__(self, backend: GPIOBackend, pins: Iterable[int]):
        self._backend = backend
        self._pins = list(pins)
        self._setup()

    def _setup(self) -> None:
        for pin in self._pins:
            self._backend.setup_output(pin)
            self._backend.write_output(pin, False)

    def apply_states(self, states: Iterable[bool]) -> None:
        for index, state in enumerate(states):
            if index >= len(self._pins):
                break
            self._backend.write_output(self._pins[index], bool(state))

    def set_state(self, index: int, state: bool) -> None:
        if not (0 <= index < len(self._pins)):
            raise IndexError("IO index out of range")
        self._backend.write_output(self._pins[index], bool(state))
