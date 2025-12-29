# pw_dump.py
from __future__ import annotations

from typing import Any, Dict, List

from models import AudioNode
from pw_channels import channel_from_port_props
from pw_cli import pw_dump_json
from pw_types import PwGraph, PwLink, PwPort


def props_from_obj(obj: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for src in (obj.get("props") or {}, (obj.get("info") or {}).get("props") or {}):
        if not isinstance(src, dict):
            continue
        for k, v in src.items():
            try:
                ks = str(k)
            except Exception:
                continue
            try:
                vs = "" if v is None else str(v)
            except Exception:
                vs = ""
            out[ks] = vs
    return out


def node_media_class(pr: Dict[str, str]) -> str:
    return pr.get("media.class", "") or ""


def node_name(pr: Dict[str, str]) -> str:
    return pr.get("node.name", "") or ""


def node_desc(pr: Dict[str, str]) -> str:
    return pr.get("node.description") or pr.get("node.nick") or pr.get("node.name") or ""


def port_name(pr: Dict[str, str]) -> str:
    return pr.get("port.name", "") or ""


def port_direction(pr: Dict[str, str], info: Dict[str, Any]) -> str:
    d = (pr.get("port.direction") or "").strip().lower()
    if d in ("in", "out"):
        return d
    d2 = (info.get("direction") or "").strip().lower() if isinstance(info, dict) else ""
    if d2 in ("in", "out"):
        return d2
    return ""


def dump_graph() -> PwGraph:
    data = pw_dump_json()

    nodes: Dict[int, AudioNode] = {}
    ports: Dict[int, PwPort] = {}
    links: List[PwLink] = []

    for obj in data:
        if not isinstance(obj, dict):
            continue
        t = str(obj.get("type") or "")
        if not t.endswith(":Node"):
            continue
        oid = int(obj.get("id"))
        pr = props_from_obj(obj)
        nodes[oid] = AudioNode(
            id=oid,
            name=node_name(pr),
            description=node_desc(pr),
            media_class=node_media_class(pr),
            props=pr,
        )

    for obj in data:
        if not isinstance(obj, dict):
            continue
        t = str(obj.get("type") or "")
        if not t.endswith(":Port"):
            continue
        oid = int(obj.get("id"))
        pr = props_from_obj(obj)
        info = obj.get("info") or {}

        try:
            nid = int(pr.get("node.id", "0"))
        except Exception:
            nid = 0

        n = nodes.get(nid)
        nname = n.name if n else ""

        pname = port_name(pr)
        direc = port_direction(pr, info)
        ch = channel_from_port_props(pr)
        full = f"{nname}:{pname}" if nname and pname else ""

        ports[oid] = PwPort(
            id=oid,
            node_id=nid,
            node_name=nname,
            port_name=pname,
            direction=direc,
            channel=ch,
            full_name=full,
        )

    for obj in data:
        if not isinstance(obj, dict):
            continue
        t = str(obj.get("type") or "")
        if not t.endswith(":Link"):
            continue
        oid = int(obj.get("id"))
        pr = props_from_obj(obj)

        out_pid = pr.get("link.output.port") or pr.get("link.output.port.id")
        in_pid = pr.get("link.input.port") or pr.get("link.input.port.id")
        if not out_pid or not in_pid:
            continue
        try:
            out_i = int(out_pid)
            in_i = int(in_pid)
        except Exception:
            continue

        links.append(PwLink(id=oid, out_port_id=out_i, in_port_id=in_i))

    return PwGraph(nodes=nodes, ports=ports, links=links)
