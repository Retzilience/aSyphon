# main_window.py
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QCheckBox,
)

from backend import PipeWireHubBackend
from models import InputChoice, OutputChoice
from rows import InputRow, OutputRow
from widgets import StatusPill


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("aSyphon")
        self.resize(1220, 640)

        self.backend = PipeWireHubBackend()
        self._input_choices: List[InputChoice] = []
        self._output_choices: List[OutputChoice] = []

        # Hub desired presence (None = no pending change)
        self._hub_desired_present: bool | None = None

        root = QWidget()
        outer = QVBoxLayout()
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)
        root.setLayout(outer)
        self.setCentralWidget(root)

        header = QHBoxLayout()
        header.setSpacing(10)

        title = QLabel("aSyphon")
        title.setObjectName("Title")

        self.server = QLabel(self.backend.server_label())
        self.server.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.auto_refresh = QCheckBox("Auto refresh")
        self.auto_refresh.setChecked(True)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_everything)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.clicked.connect(self.apply_all)

        header.addWidget(title)
        header.addSpacing(8)
        header.addWidget(QLabel("Backend:"))
        header.addWidget(self.server, 2)
        header.addStretch(1)
        header.addWidget(self.auto_refresh)
        header.addWidget(refresh_btn)
        header.addWidget(self.apply_btn)

        outer.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(12)

        self.inputs_panel = self._make_panel("Inputs → aSyphon", "+ Input", self.add_input_row)
        self.inputs_list = self._make_scroll_list()
        self.inputs_panel_layout.addWidget(self.inputs_list, 1)

        self.hub_panel = self._make_hub_panel()

        self.outputs_panel = self._make_panel("aSyphon → Outputs", "+ Output", self.add_output_row)
        self.outputs_list = self._make_scroll_list()
        self.outputs_panel_layout.addWidget(self.outputs_list, 1)

        body.addWidget(self.inputs_panel, 3)
        body.addWidget(self.hub_panel, 2)
        body.addWidget(self.outputs_panel, 3)

        outer.addLayout(body, 1)

        self.add_input_row()
        self.add_output_row()

        self.refresh_everything()

        self.timer = QTimer(self)
        self.timer.setInterval(1200)
        self.timer.timeout.connect(self.refresh_streams_only)
        self.timer.start()

    def _make_panel(self, title: str, add_label: str, add_cb) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        frame.setLayout(layout)

        top = QHBoxLayout()
        top.setSpacing(10)

        t = QLabel(title)
        f = QFont()
        f.setPointSize(12)
        f.setWeight(QFont.DemiBold)
        t.setFont(f)

        add_btn = QPushButton(add_label)
        add_btn.clicked.connect(add_cb)

        top.addWidget(t)
        top.addStretch(1)
        top.addWidget(add_btn)

        layout.addLayout(top)

        if "Inputs" in title:
            self.inputs_panel_layout = layout
        else:
            self.outputs_panel_layout = layout

        return frame

    def _make_scroll_list(self) -> QScrollArea:
        container = QWidget()
        v = QVBoxLayout()
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        container.setLayout(v)
        v.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(container)
        scroll._container = container  # type: ignore[attr-defined]
        scroll._layout = v             # type: ignore[attr-defined]
        return scroll

    def _make_hub_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        frame.setLayout(layout)

        h = QLabel("aSyphon (hub sink)")
        f = QFont()
        f.setPointSize(12)
        f.setWeight(QFont.DemiBold)
        h.setFont(f)
        layout.addWidget(h)

        ctl = QHBoxLayout()
        ctl.setSpacing(10)

        self.hub_status = StatusPill()
        self.hub_btn = QPushButton("")
        self.hub_btn.clicked.connect(self._toggle_hub_desired)

        ctl.addWidget(self.hub_status, 0, Qt.AlignVCenter)
        ctl.addWidget(self.hub_btn, 1)

        layout.addLayout(ctl)

        self.hub_info = QLabel("")
        self.hub_info.setWordWrap(True)
        self.hub_info.setStyleSheet("color: #cfd3da;")
        layout.addWidget(self.hub_info)

        hint = QLabel(
            "• Routing uses PipeWire links (qpwgraph-style), not Pulse loopback modules.\n"
            "• aSyphon sink is created via pipewire-pulse for Pulse app compatibility.\n"
            "• Per-row remove and hub create/destroy are pending until Apply."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #aeb3bc;")
        layout.addWidget(hint)

        layout.addStretch(1)
        return frame

    def _toggle_hub_desired(self) -> None:
        actual = self.backend.hub_exists()
        if self._hub_desired_present is None:
            self._hub_desired_present = (not actual)
        else:
            # Second click cancels pending hub change.
            self._hub_desired_present = None
        self._update_hub_controls()

    def _update_hub_controls(self) -> None:
        actual = self.backend.hub_exists()
        desired = self._hub_desired_present  # None or bool

        if desired is None:
            if actual:
                self.hub_status.setText("On")
                self.hub_status.set_state("on")
                self.hub_status.setToolTip("Hub sink exists.")
                self.hub_btn.setText("Destroy aSyphon sink")
                self.hub_btn.setObjectName("Danger")
            else:
                self.hub_status.setText("Off")
                self.hub_status.set_state("off")
                self.hub_status.setToolTip("Hub sink does not exist.")
                self.hub_btn.setText("Create aSyphon sink")
                self.hub_btn.setObjectName("Primary")
        else:
            # Pending hub change: unified semantics (yellow status + yellow action button)
            self.hub_status.setText("Pending")
            self.hub_status.set_state("pending")
            if desired:
                self.hub_status.setToolTip("Hub sink missing; pending create (Apply to commit).")
                self.hub_btn.setText("Create aSyphon sink")
            else:
                self.hub_status.setToolTip("Hub sink exists; pending destroy (Apply to commit).")
                self.hub_btn.setText("Destroy aSyphon sink")
            self.hub_btn.setObjectName("PendingAction")

        self.hub_btn.style().unpolish(self.hub_btn)
        self.hub_btn.style().polish(self.hub_btn)

    def _apply_hub_action_create_if_needed(self) -> None:
        desired = self._hub_desired_present
        if desired is True:
            try:
                self.backend.ensure_hub_sink()
            except Exception:
                pass

    def _input_container_layout(self):
        return self.inputs_list._layout  # type: ignore[attr-defined]

    def _output_container_layout(self):
        return self.outputs_list._layout  # type: ignore[attr-defined]

    def input_rows(self) -> List[InputRow]:
        rows: List[InputRow] = []
        lay = self._input_container_layout()
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if isinstance(w, InputRow):
                rows.append(w)
        return rows

    def output_rows(self) -> List[OutputRow]:
        rows: List[OutputRow] = []
        lay = self._output_container_layout()
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if isinstance(w, OutputRow):
                rows.append(w)
        return rows

    def add_input_row(self) -> None:
        row = InputRow()
        row.remove_requested.connect(self.remove_input_row)
        lay = self._input_container_layout()
        lay.insertWidget(lay.count() - 1, row)
        self._populate_input_combo(row)

    def add_output_row(self) -> None:
        row = OutputRow()
        row.remove_requested.connect(self.remove_output_row)
        lay = self._output_container_layout()
        lay.insertWidget(lay.count() - 1, row)
        self._populate_output_combo(row)

    def remove_input_row(self, w: QWidget) -> None:
        if isinstance(w, InputRow):
            w.toggle_remove_pending()

    def remove_output_row(self, w: QWidget) -> None:
        if isinstance(w, OutputRow):
            w.toggle_remove_pending()

    def _finalize_row_removals(self, widgets: List[QWidget]) -> None:
        for w in widgets:
            w.setParent(None)
            w.deleteLater()

    def refresh_streams_only(self) -> None:
        if not self.auto_refresh.isChecked():
            return
        try:
            self.backend.refresh()
            self._rebuild_choices()

            for row in self.input_rows():
                self._populate_input_combo(row)
            for row in self.output_rows():
                # Outputs are not "stream-based", but the link graph can change (hub destroy/create),
                # so we still reconcile them.
                pass

            # Reconcile actual-vs-remembered state (prevents false "On")
            for row in self.input_rows():
                row.reconcile(self.backend)
            for row in self.output_rows():
                row.reconcile(self.backend)

            self._update_hub_controls()
            self._update_hub_info()
        except Exception:
            pass

    def refresh_everything(self) -> None:
        try:
            self.backend.refresh()
            self.server.setText(self.backend.server_label())

            self._rebuild_choices()
            self._update_hub_controls()
            self._update_hub_info()

            for row in self.input_rows():
                self._populate_input_combo(row)
            for row in self.output_rows():
                self._populate_output_combo(row)

            for row in self.input_rows():
                row.reconcile(self.backend)
            for row in self.output_rows():
                row.reconcile(self.backend)
        except Exception as e:
            QMessageBox.critical(self, "Backend error", str(e))

    def _update_hub_info(self) -> None:
        hub = self.backend.hub_node_optional()
        if hub is None:
            self.hub_info.setText("Hub sink does not exist.")
            return
        in_ch = self.backend._node_channel_count(hub.id, "in")
        out_ch = self.backend._node_channel_count(hub.id, "out")
        self.hub_info.setText(
            f"Sink: {hub.description}  [{hub.name}]  ({in_ch}ch in)\n"
            f"Monitor: ({out_ch}ch out)"
        )

    def _rebuild_choices(self) -> None:
        streams = self.backend.list_stream_nodes()
        sources = self.backend.list_source_nodes()
        sinks = self.backend.list_sink_nodes()
        hub = self.backend.hub_node_optional()
        hub_id = hub.id if hub is not None else None

        stream_choices: List[InputChoice] = [
            InputChoice(kind="stream", key=f"stream:{n.id}", display=self.backend.stream_label(n))
            for n in sorted(streams, key=lambda x: self.backend.stream_label(x).lower())
        ]

        source_choices: List[InputChoice] = [
            InputChoice(kind="source", key=f"source:{n.id}", display=self.backend.node_label_with_ch(n, "out"))
            for n in sorted(sources, key=lambda x: (x.description.lower(), x.name.lower()))
        ]

        sink_choices: List[InputChoice] = []
        for n in sorted(sinks, key=lambda x: (x.description.lower(), x.name.lower())):
            if hub_id is not None and n.id == hub_id:
                continue
            try:
                tap_ports = self.backend._sink_monitor_output_ports(n.id)
            except Exception:
                tap_ports = []
            if not tap_ports:
                continue
            sink_choices.append(
                InputChoice(kind="sink", key=f"sink:{n.id}", display=f"Tap sink: {self.backend.node_label_with_ch(n, 'in')}")
            )

        self._input_choices = stream_choices + source_choices + sink_choices

        self._output_choices = [
            OutputChoice(key=f"sink:{n.id}", display=self.backend.node_label_with_ch(n, "in"))
            for n in sorted(sinks, key=lambda x: (x.description.lower(), x.name.lower()))
            if hub_id is None or n.id != hub_id
        ]

    def _populate_input_combo(self, row: InputRow) -> None:
        prev = row.selected_choice()
        prev_key = prev.key if prev else None

        streams = [c for c in self._input_choices if c.kind == "stream"]
        sources = [c for c in self._input_choices if c.kind == "source"]
        sinks = [c for c in self._input_choices if c.kind == "sink"]

        row.combo.blockSignals(True)
        row.combo.clear()

        def add_group(title: str, items: List[InputChoice]) -> None:
            if not items:
                return
            row.combo.addItem(title, None)
            row.combo.model().item(row.combo.count() - 1).setEnabled(False)  # type: ignore[attr-defined]
            for it in items:
                row.combo.addItem(it.display, it)
            row.combo.insertSeparator(row.combo.count())

        add_group("— App streams —", streams)
        add_group("— Capture sources —", sources)
        add_group("— Tap sinks (monitor) —", sinks)

        if prev_key:
            for i in range(row.combo.count()):
                d = row.combo.itemData(i)
                if isinstance(d, InputChoice) and d.key == prev_key:
                    row.combo.setCurrentIndex(i)
                    break
        else:
            for i in range(row.combo.count()):
                if isinstance(row.combo.itemData(i), InputChoice):
                    row.combo.setCurrentIndex(i)
                    break

        row.combo.blockSignals(False)

    def _populate_output_combo(self, row: OutputRow) -> None:
        prev_id = row.selected_sink_node_id()
        prev_key = f"sink:{prev_id}" if prev_id is not None else None

        row.combo.blockSignals(True)
        row.combo.clear()

        for c in self._output_choices:
            row.combo.addItem(c.display, c.key)

        if prev_key:
            idx = row.combo.findData(prev_key)
            if idx >= 0:
                row.combo.setCurrentIndex(idx)

        row.combo.blockSignals(False)

    def apply_all(self) -> None:
        errors: List[str] = []
        input_remove: List[QWidget] = []
        output_remove: List[QWidget] = []

        try:
            # Reconcile against reality before deciding what needs rewiring.
            self.backend.refresh()
            for r in self.input_rows():
                r.reconcile(self.backend)
            for r in self.output_rows():
                r.reconcile(self.backend)

            # If hub has a pending create, do it first.
            self._apply_hub_action_create_if_needed()

            # Refresh after potential hub creation, so subsequent applies see coherent state.
            self.backend.refresh()

            # Apply row changes first (destroy is applied last so destroy "wins").
            for r in self.input_rows():
                try:
                    if r.apply(self.backend):
                        input_remove.append(r)
                except Exception as e:
                    errors.append(str(e))

            for r in self.output_rows():
                try:
                    if r.apply(self.backend):
                        output_remove.append(r)
                except Exception as e:
                    errors.append(str(e))

            # If hub has a pending destroy, do it last.
            if self._hub_desired_present is False:
                try:
                    self.backend.destroy_hub_sink()
                except Exception:
                    pass

            # Commit hub action state
            if self._hub_desired_present is not None:
                self._hub_desired_present = None

            # Final refresh + reconcile so UI shows truth (prevents false "On")
            self.backend.refresh()
            for r in self.input_rows():
                r.reconcile(self.backend)
            for r in self.output_rows():
                r.reconcile(self.backend)

            # Remove rows after apply
            self._finalize_row_removals(input_remove + output_remove)

            # Full UI refresh (choices, hub panel, etc.)
            self.refresh_everything()

        except Exception as e:
            errors.append(str(e))

        if errors:
            QMessageBox.critical(self, "Apply issues", "\n".join(errors))

    def closeEvent(self, event) -> None:
        try:
            for r in self.input_rows():
                r.disconnect_now(self.backend)
            for r in self.output_rows():
                r.disconnect_now(self.backend)
        except Exception:
            pass

        try:
            self.backend.destroy_hub_sink_if_owned()
        except Exception:
            pass

        try:
            self.backend.close()
        except Exception:
            pass

        super().closeEvent(event)
