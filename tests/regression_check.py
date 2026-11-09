# -*- coding: utf-8 -*-
"""
R6 Faz 0 — Regresyon Kontrol Betigi.

Tek dosyalik studiyu import ederek sentetik fixture oyunlari uzerinde
analiz boru hattini (scan_files -> index_labels -> analyze_file_menus ->
project_ctx/alias/CFG -> evaluate_choices) salt-okunur modda calistirir
ve oyuncu-kararlarinin ozetini JSON olarak uretir.

Kullanim:
    python tests/regression_check.py                 # aktif sonucu yaz ve ozetle
    python tests/regression_check.py --write         # baseli­ne olarak kaydet
    python tests/regression_check.py --baseline      # kayitli baseline ile karsilastir (MATCH/DIFF)
    python tests/regression_check.py --fixture fx01_classic_route
"""
import os
import sys
import json
import importlib.util
import argparse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH_DIR = os.path.dirname(HERE)          # renpy_walkthrough_studio.py konumu
STUDIO_PATH = os.path.join(SCRATCH_DIR, "renpy_walkthrough_studio.py")
FIXTURES_DIR = os.path.join(HERE, "fixtures")
BASELINE_DIR = os.path.join(HERE, "baselines")


def load_studio():
    """Studiyu modul olarak yukler (pip kurulumu/giris noktasi calismaz)."""
    spec = importlib.util.spec_from_file_location("renpy_walkthrough_studio", STUDIO_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["renpy_walkthrough_studio"] = mod
    sys.path.insert(0, SCRATCH_DIR)
    spec.loader.exec_module(mod)
    return mod


ANALYZE_OPTIONS = {
    "read_only": True,             # fixture'lara ASLA yazma
    "enable_cheat_menu": False,
    "remove_rpyc": False,
    "verify_with_renpy_lint": False,
    "deep_jump_scan": True,
    "highlight_negative": True,
}


def analyze_fixture(studio, fixture_dir, log=print):
    """Tek bir fixture'i analiz eder ve ozet sozlugu dondurur."""
    analyzer = studio.RenpyWalkthroughAnalyzer(
        fixture_dir, options=dict(ANALYZE_OPTIONS), log_callback=log
    )
    analyzer.scan_files(auto_extract=False, log_callback=log)
    analyzer.index_labels(log_callback=log)

    # Asama A: tum dosyalari analiz et (menus topla)
    all_menus = []
    file_summaries = []
    for fpath in list(analyzer.rpy_files):
        _, menus = analyzer.analyze_file_menus(fpath)
        all_menus.extend(menus)
    analyzer.all_menus = all_menus

    # Asama A baglamlari: project_ctx -> alias -> CFG -> runtime (analyze_and_patch ile ayni sira)
    try:
        analyzer.project_ctx = {"consumed_vars": analyzer.get_all_consumed_variables()}
        for m in all_menus:
            m.project_ctx = analyzer.project_ctx
    except Exception as e:
        log("[!] project_ctx atlandi: %s" % e)

    try:
        studio.STUDIO_CONFIG["min_alias_cooccur"] = 2
        analyzer.build_alias_map(log_callback=log)
    except Exception as e:
        log("[!] alias atlandi: %s" % e)

    if analyzer.options.get("enable_cfg_verdicts", True):
        try:
            cfg = analyzer.build_control_flow_graph()
            unl = cfg.get_unreachable_labels()
            analyzer.cfg_unreachable_labels = analyzer.filter_cfg_unreachable(
                set(unl) if isinstance(unl, (set, list, tuple)) else set()
            )
        except Exception as e:
            analyzer.cfg_unreachable_labels = set()
            log("[!] CFG atlandi: %s" % e)

    try:
        analyzer.load_runtime_observations(log_callback=log)
    except Exception:
        pass

    # Asama B: kararlar uret ve ozetle
    menus_out = []
    for m in all_menus:
        decisions = m.evaluate_choices(highlight_negative=True)
        entry = {
            "file": os.path.basename(getattr(m, "file_path", "")),
            "line": int(getattr(m, "line_num", -1)) + 1,
            "choices": {},
        }
        for ch, verdict in decisions.items():
            if isinstance(ch, str):
                continue
            entry["choices"][str(getattr(ch, "text", ""))] = {
                "verdict": str(verdict),
                "score": round(float(getattr(ch, "score", 0.0) or 0.0), 3),
                "jump": getattr(ch, "jump_target", None),
            }
        if entry["choices"]:
            menus_out.append(entry)

    alias_groups = {}
    for var, group in sorted(getattr(analyzer, "alias_group", {}).items()):
        alias_groups[var] = sorted(group)

    cfg_unreachable = sorted(getattr(analyzer, "cfg_unreachable_labels", set()) or [])

    return {
        "fixture": os.path.basename(os.path.normpath(fixture_dir)),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "menus": menus_out,
        "alias_groups": alias_groups,
        "cfg_unreachable": cfg_unreachable,
    }


def normalize(obj):
    """Zaman damgasini karsilastirma disinda birak."""
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items() if k not in ("generated",)}
    return obj


def main():
    ap = argparse.ArgumentParser(description="R6 Faz 0 regresyon kontrolu (salt-okunur analiz)")
    ap.add_argument("--fixture", help="Yalnizca bu fixture'i analiz et")
    ap.add_argument("--write", action="store_true", help="Yeni baseline olarak kaydet")
    ap.add_argument("--baseline", action="store_true", help="Baseline ile karsilastir")
    args = ap.parse_args()

    studio = load_studio()

    fixture_names = args.fixture and [args.fixture] or (
        sorted(os.listdir(FIXTURES_DIR))
        if os.path.isdir(FIXTURES_DIR) else []
    )
    os.makedirs(BASELINE_DIR, exist_ok=True)

    all_ok = True
    for name in fixture_names:
        fdir = os.path.join(FIXTURES_DIR, name)
        if not os.path.isdir(fdir):
            print("[?] Fixture yok: %s" % name)
            continue
        summary = analyze_fixture(studio, fdir)

        best = sum(
            1
            for m in summary["menus"]
            for c in m["choices"].values()
            if c["verdict"].upper() in ("GREEN", "BEST")
        )
        worst = sum(
            1
            for m in summary["menus"]
            for c in m["choices"].values()
            if c["verdict"].upper() in ("RED", "WORST")
        )
        print("\n=== %s: menus=%d green=%d red=%d alias_groups=%d cfg_unreachable=%d ===" % (
            name,
            len(summary["menus"]), best, worst,
            len(summary["alias_groups"]), len(summary["cfg_unreachable"]),
        ))

        baseline_path = os.path.join(BASELINE_DIR, name + ".json")
        if args.write:
            with open(baseline_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)
            print("    -> baseline kaydedildi: %s" % baseline_path)
        elif args.baseline:
            if not os.path.exists(baseline_path):
                print("    [!] Baseline yok (%s) — once --write ile uret." % baseline_path)
                all_ok = False
                continue
            with open(baseline_path, "r", encoding="utf-8") as f:
                old = json.load(f)
            if normalize(old) == normalize(summary):
                print("    [MATCH] Baseline ile birebir uyumlu.")
            else:
                print("    [DIFF] Baseline farklilasiyor:")
                old_m = {m["file"] + ":" + str(m["line"]): m for m in old.get("menus", [])}
                new_m = {m["file"] + ":" + str(m["line"]): m for m in summary["menus"]}
                for key in sorted(set(old_m) | set(new_m)):
                    if old_m.get(key) != new_m.get(key):
                        print("        ~ menu %s" % key)
                        oc = old_m.get(key, {}).get("choices", {})
                        nc = new_m.get(key, {}).get("choices", {})
                        for ckey in sorted(set(oc) | set(nc)):
                            if oc.get(ckey) != nc.get(ckey):
                                print("            - %s: %s -> %s" % (
                                    ckey[:60],
                                    (oc.get(ckey) or {}).get("verdict"),
                                    (nc.get(ckey) or {}).get("verdict"),
                                ))
                if normalize(old).get("alias_groups") != normalize(summary).get("alias_groups"):
                    print("        ~ alias degiskence farki")
                if normalize(old).get("cfg_unreachable") != normalize(summary).get("cfg_unreachable"):
                    print("        ~ cfg_unreachable farki")
                all_ok = False

        # Ozet JSON'u da yaz (inceleme icin)
        with open(os.path.join(BASELINE_DIR, name + ".latest.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
