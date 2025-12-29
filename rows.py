# rows.py
from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy

from backend import PipeWireHubBackend
from models import InputChoice
from widgets import ToggleSwitch, ElideComboBox, StatusPill


LinkPairs = List[Tuple[str, str]]


class InputRow(QWidget):
    remove_requested = Signal(QWidget)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("RowCard")

        self.combo = ElideComboBox()
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.switch = ToggleSwitch()
        self.status = StatusPill()

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setObjectName("Remove")
        self.remove_btn.setFixedSize(32, 28)
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))

        self._applied_choice_key: Optional[str] = None
        self._pairs: LinkPairs = []
        self._actual_on = False

        self._remove_pending = False
        self._error: Optional[str] = None

        row = QHBoxLayout()
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)
        row.addWidget(self.combo, 1)
        row.addWidget(self.status, 0, Qt.AlignVCenter)
        row.addWidget(self.switch, 0, Qt.AlignVCenter)
        row.addWidget(self.remove_btn, 0, Qt.AlignVCenter)
        self.setLayout(row)

        self.switch.toggled.connect(lambda _v: self._on_user_change())
        self.combo.currentIndexChanged.connect(lambda _i: self._on_user_change())
        self._sync_ui()

    def _on_user_change(self) -> None:
        self._error = None
        self._sync_ui()

    def toggle_remove_pending(self) -> None:
        self._remove_pending = not self._remove_pending
        self._error = None
        self._sync_ui()

    def selected_choice(self) -> Optional[InputChoice]:
        d = self.combo.currentData()
        return d if isinstance(d, InputChoice) else None

    def _desired_on(self) -> bool:
        return bool(self.switch.isChecked()) and not self._remove_pending

    def _sel_key(self) -> Optional[str]:
        c = self.selected_choice()
        return c.key if c else None

    def reconcile(self, backend: PipeWireHubBackend) -> None:
        try:
            self._actual_on = bool(self._pairs) and backend.pairs_exist(self._pairs, refresh=False)
        except Exception:
            self._actual_on = False
        self._sync_ui()

    def _is_pending(self) -> bool:
        if self._remove_pending:
            return True
        d, a = self._desired_on(), self._actual_on
        if d != a:
            return True
        if d and a:
            sk = self._sel_key()
            return (sk is None) or (self._applied_choice_key != sk)
        return False

    def _sync_ui(self) -> None:
        if self._remove_pending:
            self.remove_btn.setObjectName("RemovePending")
            self.remove_btn.setToolTip("Pending removal (Apply to remove).")
            self.combo.setEnabled(False)
            self.switch.setEnabled(False)
        else:
            self.remove_btn.setObjectName("Remove")
            self.remove_btn.setToolTip("Remove row (pending until Apply).")
            self.combo.setEnabled(True)
            self.switch.setEnabled(True)

        self.remove_btn.style().unpolish(self.remove_btn)
        self.remove_btn.style().polish(self.remove_btn)

        if self._error is not None:
            self.status.setText("Error")
            self.status.set_state("error")
            self.status.setToolTip(self._error)
            return

        if self._is_pending():
            self.status.setText("Pending")
            self.status.set_state("pending")
            self.status.setToolTip("Pending changes (Apply to commit).")
            return

        if self._actual_on:
            self.status.setText("On")
            self.status.set_state("on")
        else:
            self.status.setText("Off")
            self.status.set_state("off")
            self.status.setToolTip("")

    def disconnect_now(self, backend: PipeWireHubBackend) -> None:
        try:
            backend.disconnect_pairs(self._pairs)
        except Exception:
            pass
        self._pairs = []
        self._actual_on = False
        self._applied_choice_key = None
        self._error = None
        self._remove_pending = False
        self._sync_ui()

    def apply(self, backend: PipeWireHubBackend) -> bool:
        self._error = None

        if self._remove_pending:
            try:
                backend.disconnect_pairs(self._pairs)
            except Exception:
                pass
            self._pairs = []
            self._actual_on = False
            self._applied_choice_key = None
            self._sync_ui()
            return True

        if not self._desired_on():
            if self._pairs:
                try:
                    backend.disconnect_pairs(self._pairs)
                except Exception:
                    pass
            self._pairs = []
            self._actual_on = False
            self._applied_choice_key = None
            self._sync_ui()
            return False

        choice = self.selected_choice()
        if choice is None:
            self._error = "No selection."
            self._sync_ui()
            return False

        sel_key = choice.key
        needs = (not self._actual_on) or (self._applied_choice_key != sel_key)
        if not needs:
            self._sync_ui()
            return False

        if self._pairs:
            try:
                backend.disconnect_pairs(self._pairs)
            except Exception:
                pass
        self._pairs = []
        self._actual_on = False
        self._applied_choice_key = None

        try:
            kind = choice.kind
            node_id = int(sel_key.split(":", 1)[1])

            if kind == "stream":
                pairs = backend.connect_stream_to_hub(node_id)
                tip = "PipeWire links: stream outputs → aSyphon inputs."
            elif kind == "source":
                pairs = backend.connect_source_to_hub(node_id)
                tip = "PipeWire links: source outputs → aSyphon inputs."
            elif kind == "sink":
                pairs = backend.connect_sink_tap_to_hub(node_id)
                tip = "PipeWire links: sink monitor outputs → aSyphon inputs."
            else:
                raise RuntimeError("Unknown input kind.")

            self._pairs = pairs
            self._actual_on = True
            self._applied_choice_key = sel_key
            self.status.setToolTip(tip)
        except Exception as e:
            self._pairs = []
            self._actual_on = False
            self._applied_choice_key = None
            self._error = str(e)

        self._sync_ui()
        return False


class OutputRow(QWidget):
    remove_requested = Signal(QWidget)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("RowCard")

        self.combo = ElideComboBox()
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.switch = ToggleSwitch()
        self.status = StatusPill()

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setObjectName("Remove")
        self.remove_btn.setFixedSize(32, 28)
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))

        self._applied_sink_id: Optional[int] = None
        self._pairs: LinkPairs = []
        self._actual_on = False

        self._remove_pending = False
        self._error: Optional[str] = None

        row = QHBoxLayout()
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)
        row.addWidget(self.combo, 1)
        row.addWidget(self.status, 0, Qt.AlignVCenter)
        row.addWidget(self.switch, 0, Qt.AlignVCenter)
        row.addWidget(self.remove_btn, 0, Qt.AlignVCenter)
        self.setLayout(row)

        self.switch.toggled.connect(lambda _v: self._on_user_change())
        self.combo.currentIndexChanged.connect(lambda _i: self._on_user_change())
        self._sync_ui()

    def _on_user_change(self) -> None:
        self._error = None
        self._sync_ui()

    def toggle_remove_pending(self) -> None:
        self._remove_pending = not self._remove_pending
        self._error = None
        self._sync_ui()

    def _desired_on(self) -> bool:
        return bool(self.switch.isChecked()) and not self._remove_pending

    def _selected_sink_id(self) -> Optional[int]:
        d = self.combo.currentData()
        if not isinstance(d, str) or not d.startswith("sink:"):
            return None
        try:
            return int(d.split(":", 1)[1])
        except Exception:
            return None

    def selected_sink_node_id(self) -> Optional[int]:
        return self._selected_sink_id()

    def reconcile(self, backend: PipeWireHubBackend) -> None:
        try:
            self._actual_on = bool(self._pairs) and backend.pairs_exist(self._pairs, refresh=False)
        except Exception:
            self._actual_on = False
        self._sync_ui()

    def _is_pending(self) -> bool:
        if self._remove_pending:
            return True
        d, a = self._desired_on(), self._actual_on
        if d != a:
            return True
        if d and a:
            sel = self._selected_sink_id()
            return (sel is None) or (sel != self._applied_sink_id)
        return False

    def _sync_ui(self) -> None:
        if self._remove_pending:
            self.remove_btn.setObjectName("RemovePending")
            self.remove_btn.setToolTip("Pending removal (Apply to remove).")
            self.combo.setEnabled(False)
            self.switch.setEnabled(False)
        else:
            self.remove_btn.setObjectName("Remove")
            self.remove_btn.setToolTip("Remove row (pending until Apply).")
            self.combo.setEnabled(True)
            self.switch.setEnabled(True)

        self.remove_btn.style().unpolish(self.remove_btn)
        self.remove_btn.style().polish(self.remove_btn)

        if self._error is not None:
            self.status.setText("Error")
            self.status.set_state("error")
            self.status.setToolTip(self._error)
            return

        if self._is_pending():
            self.status.setText("Pending")
            self.status.set_state("pending")
            self.status.setToolTip("Pending changes (Apply to commit).")
            return

        if self._actual_on:
            self.status.setText("On")
            self.status.set_state("on")
        else:
            self.status.setText("Off")
            self.status.set_state("off")
            self.status.setToolTip("")

    def disconnect_now(self, backend: PipeWireHubBackend) -> None:
        try:
            backend.disconnect_pairs(self._pairs)
        except Exception:
            pass
        self._pairs = []
        self._actual_on = False
        self._applied_sink_id = None
        self._error = None
        self._remove_pending = False
        self._sync_ui()

    def apply(self, backend: PipeWireHubBackend) -> bool:
        self._error = None

        if self._remove_pending:
            try:
                backend.disconnect_pairs(self._pairs)
            except Exception:
                pass
            self._pairs = []
            self._actual_on = False
            self._applied_sink_id = None
            self._sync_ui()
            return True

        if not self._desired_on():
            if self._pairs:
                try:
                    backend.disconnect_pairs(self._pairs)
                except Exception:
                    pass
            self._pairs = []
            self._actual_on = False
            self._applied_sink_id = None
            self._sync_ui()
            return False

        sink_id = self._selected_sink_id()
        if sink_id is None:
            self._error = "No selection."
            self._sync_ui()
            return False

        needs = (not self._actual_on) or (sink_id != self._applied_sink_id)
        if not needs:
            self._sync_ui()
            return False

        if self._pairs:
            try:
                backend.disconnect_pairs(self._pairs)
            except Exception:
                pass
        self._pairs = []
        self._actual_on = False
        self._applied_sink_id = None

        try:
            self._pairs = backend.connect_hub_to_sink(sink_id)
            self._actual_on = True
            self._applied_sink_id = sink_id
            self.status.setToolTip("PipeWire links: aSyphon monitor outputs → sink inputs.")
        except Exception as e:
            self._pairs = []
            self._actual_on = False
            self._applied_sink_id = None
            self._error = str(e)

        self._sync_ui()
        return False
