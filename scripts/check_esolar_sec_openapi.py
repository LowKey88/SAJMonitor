#!/usr/bin/env python3
"""Internal SAJ eSolar SEC OpenAPI probe.

Purpose: test whether the developer OpenAPI credentials can access the eSolar
SEC/load-monitoring data before patching the Home Assistant SAJ Monitor
integration.

Secrets are never printed. Provide credentials via environment variables:
  SAJ_APP_ID, SAJ_APP_SECRET, SAJ_PLANT_ID
Optional:
  SAJ_R6_SN      (R6/inverter SN for comparison)
  SAJ_SEC_SN     (defaults to GB Home eSolar SEC SN)
  SAJ_BASE_URL   (defaults to intl developer API)

Example:
  SAJ_APP_ID=... SAJ_APP_SECRET=... SAJ_PLANT_ID=... \
    SAJ_R6_SN=... python3 scripts/check_esolar_sec_openapi.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_BASE_URL = "https://intl-developer.saj-electric.com"
DEFAULT_SEC_SN = "M5370G2025000024"

TOKEN_URL = "/prod-api/open/api/access_token"
DEVICE_INFO_URL = "/prod-api/open/api/device/batInfo"
REALTIME_DATA_URL = "/prod-api/open/api/device/realtimeDataCommon"
HISTORY_DATA_URL = "/prod-api/open/api/device/historyDataCommon"
SEC_DATA_URL = "/prod-api/open/api/device/secData"
PLANT_STATS_URL = "/prod-api/open/api/plant/getPlantStatisticsData"

SENSITIVE_KEYS = {
    "access_token", "accessToken", "token", "appSecret", "app_secret", "secret",
    "authorization", "Authorization",
}


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in SENSITIVE_KEYS or "token" in k.lower() or "secret" in k.lower():
                out[k] = "[REDACTED]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def request_json(method: str, base_url: str, path: str, *, params: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"code": "NON_JSON", "msg": raw[:500]}


def get_token(base_url: str, app_id: str, app_secret: str) -> str:
    data = request_json(
        "GET", base_url, TOKEN_URL,
        params={"appId": app_id, "appSecret": app_secret},
        headers={"content-language": "en_US"},
    )
    token = data.get("data", {}).get("access_token")
    if not token:
        raise RuntimeError(f"Token failed: {json.dumps(redact(data), ensure_ascii=False)}")
    return token


def summarize(label: str, data: Dict[str, Any]) -> Dict[str, Any]:
    # Keep enough evidence for internal debugging without huge dumps/secrets.
    result: Dict[str, Any] = {
        "label": label,
        "code": data.get("code"),
        "msg": data.get("msg"),
        "has_data": "data" in data,
    }
    payload = data.get("data")
    if isinstance(payload, dict):
        result["data_keys"] = sorted(payload.keys())[:50]
        if "dataList" in payload and isinstance(payload["dataList"], list):
            result["dataList_len"] = len(payload["dataList"])
            modules = []
            for m in payload["dataList"][:5]:
                if isinstance(m, dict):
                    modules.append({
                        "moduleSn": m.get("moduleSn"),
                        "data_len": len(m.get("data") or []) if isinstance(m.get("data"), list) else None,
                        "total_keys": sorted((m.get("total") or {}).keys())[:30] if isinstance(m.get("total"), dict) else None,
                        "latest_keys": sorted((m.get("data") or [{}])[-1].keys())[:50]
                            if isinstance(m.get("data"), list) and m.get("data") else None,
                    })
            result["modules"] = modules
        # Copy common live fields if present.
        interesting = [
            "dataTime", "invTime", "sysGridPowerWatt", "totalGridPowerWatt",
            "gridDirection", "pvPower", "totalPvPower", "totalLoadWatt",
            "sysTotalLoadWatt", "todayPvEnergy", "todayLoadEnergy",
            "todaySellEnergy", "todayBuyEnergy",
        ]
        result["interesting"] = {k: payload.get(k) for k in interesting if k in payload}
    elif isinstance(payload, list):
        result["data_len"] = len(payload)
        if payload:
            result["first_keys"] = sorted(payload[0].keys())[:50] if isinstance(payload[0], dict) else None
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe SAJ eSolar SEC OpenAPI access safely")
    ap.add_argument("--base-url", default=os.getenv("SAJ_BASE_URL", DEFAULT_BASE_URL))
    ap.add_argument("--app-id", default=os.getenv("SAJ_APP_ID"))
    ap.add_argument("--app-secret", default=os.getenv("SAJ_APP_SECRET"))
    ap.add_argument("--plant-id", default=os.getenv("SAJ_PLANT_ID"))
    ap.add_argument("--r6-sn", default=os.getenv("SAJ_R6_SN"))
    ap.add_argument("--sec-sn", default=os.getenv("SAJ_SEC_SN", DEFAULT_SEC_SN))
    ap.add_argument("--minutes", type=int, default=30, help="history/secData lookback window")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON summary")
    args = ap.parse_args()

    missing = [name for name, value in {
        "SAJ_APP_ID/--app-id": args.app_id,
        "SAJ_APP_SECRET/--app-secret": args.app_secret,
        "SAJ_PLANT_ID/--plant-id": args.plant_id,
    }.items() if not value]
    if missing:
        print("Missing required values: " + ", ".join(missing), file=sys.stderr)
        return 2

    token = get_token(args.base_url, args.app_id, args.app_secret)
    headers = {"accessToken": token, "content-language": "en_US"}
    now = dt.datetime.now()
    start = now - dt.timedelta(minutes=args.minutes)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    checks = []

    # Plant stats proves credentials/plant are alive.
    checks.append(summarize("plant_stats", request_json(
        "GET", args.base_url, PLANT_STATS_URL,
        params={"plantId": args.plant_id, "clientDate": now.strftime("%Y-%m-%d %H:%M:%S")},
        headers={**headers, "Content-Type": "application/json"},
    )))

    # secData by plant is the key load-monitoring endpoint used by current integration.
    checks.append(summarize("secData_plant_today", request_json(
        "GET", args.base_url, SEC_DATA_URL,
        params={
            "plantId": args.plant_id,
            "startTime": today_midnight.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timeUnit": 0,
        },
        headers=headers,
    )))

    # SEC SN probes determine whether module direct access has been enabled.
    for path, label, params in [
        (DEVICE_INFO_URL, "sec_device_info", {"deviceSn": args.sec_sn}),
        (REALTIME_DATA_URL, "sec_realtime", {"deviceSn": args.sec_sn}),
        (HISTORY_DATA_URL, "sec_history", {
            "deviceSn": args.sec_sn,
            "plantId": args.plant_id,
            "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": now.strftime("%Y-%m-%d %H:%M:%S"),
        }),
    ]:
        checks.append(summarize(label, request_json("GET", args.base_url, path, params=params, headers=headers)))

    if args.r6_sn:
        checks.append(summarize("r6_realtime_compare", request_json(
            "GET", args.base_url, REALTIME_DATA_URL,
            params={"deviceSn": args.r6_sn}, headers=headers,
        )))

    ok_secdata = any(c["label"] == "secData_plant_today" and c.get("code") == 200 and c.get("has_data") for c in checks)
    ok_sec_direct = any(c["label"].startswith("sec_") and c.get("code") == 200 and c.get("has_data") for c in checks)

    summary = {
        "tested_at": now.isoformat(timespec="seconds"),
        "plant_id": args.plant_id,
        "sec_sn": args.sec_sn,
        "r6_sn_provided": bool(args.r6_sn),
        "secData_plant_access_ok": ok_secdata,
        "sec_direct_sn_access_ok": ok_sec_direct,
        "checks": checks,
    }

    if args.json:
        print(json.dumps(redact(summary), indent=2, ensure_ascii=False))
    else:
        print(f"SAJ eSolar SEC OpenAPI probe @ {summary['tested_at']}")
        print(f"plant_id={args.plant_id} sec_sn={args.sec_sn} r6_sn_provided={bool(args.r6_sn)}")
        print(f"secData plant access: {'OK' if ok_secdata else 'NOT OK'}")
        print(f"SEC direct SN access: {'OK' if ok_sec_direct else 'NOT OK'}")
        print("\nChecks:")
        for c in checks:
            print(f"- {c['label']}: code={c.get('code')} msg={c.get('msg')!r} has_data={c.get('has_data')}")
            if c.get("dataList_len") is not None:
                print(f"  dataList_len={c.get('dataList_len')} modules={json.dumps(c.get('modules'), ensure_ascii=False)}")
            if c.get("interesting"):
                print(f"  interesting={json.dumps(c.get('interesting'), ensure_ascii=False)}")
    return 0 if (ok_secdata or ok_sec_direct) else 1


if __name__ == "__main__":
    raise SystemExit(main())
