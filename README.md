# aSyphon

[Latest release](https://github.com/Retzilience/aSyphon/releases/latest)

![aSyphon flow](https://github.com/Retzilience/aSyphon/raw/main/assets/flow.jpg)

aSyphon is… a siphon. More specifically: a virtual audio siphon for PipeWire / pipewire-pulse on Linux. It creates (or expects) a dedicated “hub” sink named `asyphon`, lets you feed that hub from app streams, capture sources, or sink monitor taps, and optionally routes the hub’s monitor output to one or more output sinks.

It is not a mixer UI in the PulseAudio sense and it is not trying to replace qpwgraph/Helvum. It is a small, explicit router: select inputs, select outputs, click **Apply**, and it commits the exact PipeWire links required to make that routing real.

## What it does

aSyphon provides a simple model:

- **Inputs → hub sink**: You select one or more inputs and connect them into the `asyphon` sink.
- **Hub monitor → outputs**: You select one or more output sinks and connect the hub’s monitor ports to them. This is optional, everything you input to aSyphon will be streaming audio to it even if it is not connected to an output. (You can capture audio directly from the aSyphon sink on OBS without having to connect an output, for example).
- **Apply = commit**: aSyphon does not “live edit” links. It stages intent and applies it by creating/removing PipeWire links via `pw-link`.

The practical result is a persistent “bus” you can treat as an internal audio junction: throw things into it, then decide where they go.

![aSyphon UI](https://github.com/Retzilience/aSyphon/raw/main/assets/ui.png)

## Concepts

### Hub sink (`asyphon`)
The hub sink is a null sink created via **pipewire-pulse** (`module-null-sink`) for broad compatibility with Pulse-oriented applications. Most apps can target it like any other output device.

Even though the sink is created via Pulse, routing is done using **native PipeWire links**.

### PipeWire links
Routing is implemented by creating and destroying links (port-to-port connections) in the PipeWire graph using `pw-link`. aSyphon is deliberately explicit about this: if a link exists, audio flows; if it does not, it does not.

### Monitor output
Outputs are driven from the hub sink’s monitor ports. The monitor is “what is playing into the sink”, exposed as output ports in the PipeWire graph. Sending the hub monitor to outputs effectively “duplicates” whatever you fed into the hub.

## Input types

aSyphon supports three classes of input:

- **App streams**: per-application audio outputs (for example: a media player, a browser’s audio stream, a game, etc.).
- **Capture sources**: PipeWire sources (microphones, capture cards, virtual sources).
- **Tap sinks (monitor)**: you can tap a sink’s monitor output to siphon audio that is already going to some sink.

## Routing behavior

- **Multiple inputs are mixed**: enabling several inputs sums them into the hub sink.
- **Multiple outputs duplicate**: enabling several outputs sends the hub monitor to each selected sink.
- **Channel mapping is sane**: links are created 1:1 by channel when possible (FL/FR/FC/LFE/SL/SR/RL/RR/AUX*). If channel tags are missing or inconsistent, it falls back to port order.

## UI model

### Inputs panel
Each input row represents one potential connection into the hub. You pick a source (stream/source/sink-tap), toggle it on, then apply.

### Outputs panel
Each output row represents one potential destination sink. You pick a sink, toggle it on, then apply.

### Hub panel
The center panel shows whether `asyphon` exists and allows you to request creation/destruction of the hub sink. This change is also staged and only committed on **Apply**.

If the hub sink is missing, aSyphon will attempt to create it via pipewire-pulse when needed.

### Auto refresh
Auto refresh periodically re-reads the live PipeWire graph so newly created app streams and newly connected devices show up without restarting the UI. Disable it if you are making heavy changes externally (qpwgraph, Helvum, scripts) and you want the UI to stay stable while you work.

## Limitations

aSyphon is intentionally narrow in scope. Current constraints are practical rather than ideological, and most of them are explicitly on the roadmap.

- **Best with stereo (2ch)**: it works most predictably with common stereo streams and sinks. Multi-channel devices and unusual channel layouts can work, but are more sensitive to how ports are exposed and labeled.
- **Best-effort channel mapping**: mapping prefers explicit channel tags (FL/FR/…/AUX*) and falls back to port order when tagging is missing or inconsistent. If either side presents ports in a strange order (or mislabels channels), the resulting links can be surprising.
- **No persistent state between sessions**: aSyphon does not currently save configuration (no “preset” system) and does not attempt to restore links automatically when restarted.
- **Hub lifetime is tied to the app**: by design (currently), the `asyphon` sink only exists while aSyphon is running. When the app closes, the hub is removed (if aSyphon created it), and any routing involving it ends.

## Troubleshooting

- **No audio**
  - Confirm the intended input row is toggled on and you clicked **Apply**.
  - Confirm at least one output sink is toggled on and you clicked **Apply**.
  - Confirm the hub sink exists (`asyphon`) and that your routing is hub → output(s), not only input → hub.

- **An input disappeared**
  - Some applications recreate their streams; the old node vanishes and a new one appears.
  - Refresh (or wait for auto refresh), re-select the stream, then Apply again.

- **Weird channel layout**
  - Multi-channel devices can expose ports in unexpected ways.
  - aSyphon prefers explicit channel tags and otherwise falls back to port order. If the upstream ports are mislabeled, mapping can look odd.

- **Hub won’t create**
  - Ensure `pipewire` and `pipewire-pulse` are running.
  - Ensure `pw-link` and `pw-dump` are available in your PATH.

## Roadmap / TODO

Near-term work (not promises, but the direction):

- **More robust mapping**: better heuristics and improved handling when channel metadata is absent, partial, or inconsistent.
- **More channels compatibility**: broader coverage for multi-channel devices (including “odd” layouts) and better handling of AUX channels.
- **Session presets**: save/restore routing sets (inputs, outputs, hub behavior), so aSyphon can re-apply a known configuration quickly.

## Support / diagnostics

The Help / About dialog includes:

- Repository / Releases / Bug report buttons
- “Copy diagnostics” (version + platform + descriptor URL) suitable for issue reports

If you file a bug, include the diagnostics output and a short description of what you expected vs what happened.

## License

CC BY-NC-SA 4.0 (Attribution required; noncommercial only; derivatives must use the same license).
