"""Validate observable action records, not the truth of a model's interpretation.

The model still judges meaning. These gates require explicit temporal evidence
and continuity checks, and prevent missing/uncertain checks from becoming approval.
"""
CHANGES = ["part_motion", "whole_rotation", "whole_flip", "camera_change", "other", "unclear"]
VERDICTS = ["supported", "revise", "uncertain"]
TRACE_PROPERTIES = {
    "viewpoint": {"type": "string", "description": "上下左右等の基準。1文。"},
    "stationary_parts": {"type": "string", "description": "動かさない部分・背景。ない場合も明記。"},
    "change": {"enum": CHANGES},
    "before_frame": {"type": "string"},
    "during_frame": {"type": "string", "description": "途中の根拠画像。未確認なら空文字。"},
    "after_frame": {"type": "string"},
    "uncertainty": {"type": "string", "description": "未解決の別解釈・見えない操作。なければ空文字。"},
    "previous_action_id": {"type": "string", "description": "時系列で直前のactionのid。最初だけ空文字。"},
    "connection": {"enum": ["start", "continues", "reset", "unclear"]},
    "connection_note": {"type": "string", "description": "前工程の終了状態から開始状態へのつながり。場面切替や向き変更も記録。1文。"},
}
TRACE_SCHEMA = {"type": "object", "properties": TRACE_PROPERTIES,
                "required": list(TRACE_PROPERTIES)}
ACTION_CHECK_PROPERTIES = {
    "motion": {"enum": VERDICTS},
    "continuity": {"enum": VERDICTS},
    "observed_change": {"enum": CHANGES},
    "observed_action": {"type": "string", "description": "映像から独立に読み取った、対象・方向・前後変化。"},
    "connection_finding": {"type": "string", "description": "前工程とのつながり・省略・戻し操作の確認結果。"},
}
ACTION_CHECK_SCHEMA = {"type": "object", "properties": ACTION_CHECK_PROPERTIES,
                       "required": list(ACTION_CHECK_PROPERTIES)}


def validate_traces(units, records):
    known = {r["file"]: r["seconds"] for r in records}
    previous = ""
    concerns = []
    for unit in units:
        if unit["type"] != "action":
            continue
        identity = unit["id"]
        trace = unit.get("action_trace")
        if not isinstance(trace, dict):
            raise ValueError(f"{identity}: action_traceで向き・動かさない部分・前後画像・工程のつながりを記録してください。")
        for field in TRACE_PROPERTIES:
            if not isinstance(trace.get(field), str):
                raise ValueError(f"{identity}: action_trace.{field}を文字列で記録してください。")
        for field in ("viewpoint", "stationary_parts", "connection_note"):
            if not trace[field].strip():
                raise ValueError(f"{identity}: action_trace.{field}が空欄です。")
        if trace["change"] not in CHANGES or trace["connection"] not in {"start", "continues", "reset", "unclear"}:
            raise ValueError(f"{identity}: 操作分類または工程のつながりが不正です。")
        if trace["previous_action_id"] != previous or (trace["connection"] == "start") != (previous == ""):
            raise ValueError(f"{identity}: previous_action_idは時系列で直前のactionを指定し、最初だけconnection=startにしてください。")
        names = [trace["before_frame"], trace["after_frame"]]
        if trace["during_frame"]:
            names.insert(1, trace["during_frame"])
        if any(n not in unit["evidence_files"] or n not in known for n in names):
            raise ValueError(f"{identity}: 前後・途中の画像はこの項目のevidence_filesから選んでください。")
        times = [known[n] for n in names]
        if any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError(f"{identity}: 前→途中→後は異なる時刻の昇順で指定してください。")
        # Classifications are language-independent; do not depend only on Japanese keywords.
        if trace["change"] in {"whole_rotation", "whole_flip", "camera_change"} and unit["risk"] == "none":
            unit["risk"] = "orientation"
        reasons = []
        if trace["uncertainty"].strip():
            reasons.append(trace["uncertainty"].strip())
        if trace["change"] == "unclear":
            reasons.append("操作の解釈が未確定")
        if trace["connection"] == "unclear":
            reasons.append("前工程からの状態変化が未確認")
        if unit["risk"] in {"orientation", "layers", "fine_motion"} and not trace["during_frame"]:
            reasons.append("操作途中の根拠画像が未指定")
        if reasons:
            concerns.append({"id": identity, "start": times[0], "end": times[-1],
                             "reasons": reasons, "previous_action_id": previous})
        previous = identity
    return concerns


def validate_action_check(unit, check, records):
    if unit["type"] != "action":
        return
    detail = check.get("action_check")
    if not isinstance(detail, dict):
        raise ValueError(f"{unit['id']}: action_checkで動作と工程のつながりを個別に確認してください。")
    if any(detail.get(k) not in VERDICTS for k in ("motion", "continuity")) or detail.get("observed_change") not in CHANGES:
        raise ValueError("動作・つながり・操作分類の確認結果が不正です。")
    if any(not isinstance(detail.get(k), str) or not detail[k].strip()
           for k in ("observed_action", "connection_finding")):
        raise ValueError("映像で観察した操作と、前工程とのつながりの説明が必要です。")
    verdicts = [check["verdict"], detail["motion"], detail["continuity"]]
    if "revise" in verdicts:
        check["verdict"] = "revise"
    elif "uncertain" in verdicts or detail["observed_change"] == "unclear":
        check["verdict"] = "uncertain"
    if check["verdict"] != "supported":
        return
    times = sorted({r["seconds"] for r in records if r["file"] in check["evidence_files"]
                    and unit["start"] - 3 <= r["seconds"] <= unit["end"] + 3})
    trace = unit.get("action_trace", {})
    risky = unit["risk"] in {"orientation", "layers", "fine_motion"} or detail["observed_change"] in {
        "whole_rotation", "whole_flip", "camera_change"} or bool(trace.get("uncertainty")) or trace.get("connection") == "unclear"
    if len(times) < (3 if risky else 2):
        raise ValueError(f"{unit['id']}: supportedには操作区間の前後{'・途中' if risky else ''}を示す異なる時刻の根拠画像が必要です。")


def review_details(plan, records, limit=4):
    """Prioritize unresolved transitions and use chosen anchors, bounded to 12 images."""
    known = {r["file"]: r for r in records}
    concerns = {c["id"] for c in plan.get("action_concerns", [])}
    candidates = [u for u in plan["units"] if u["id"] in concerns or u["risk"] != "none"]
    candidates.sort(key=lambda u: (u["id"] not in concerns, u["start"]))
    result, seen = [], set()
    for unit in candidates[:limit]:
        trace = unit.get("action_trace", {})
        names = [trace.get(k) for k in ("before_frame", "during_frame", "after_frame")]
        if not any(names):
            available = sorted((r for r in records if unit["start"] <= r["seconds"] <= unit["end"]), key=lambda r:r["seconds"])
            names = [r["file"] for r in (available[0], available[len(available)//2], available[-1])] if available else []
        for name in names:
            if name in known and name not in seen:
                result.append((unit["id"], known[name]))
                seen.add(name)
    return result
