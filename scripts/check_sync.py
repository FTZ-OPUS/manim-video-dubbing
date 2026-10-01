#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成片硬标准验收器。

用法:
    python check_sync.py <成片.mp4> <源视频.mp4>

检查项:
  1. 成片时长与源视频一致（±0.5s）
  2. 全程等间隔响度扫描：-70dB 以下视为静音窗
     - 孤立 1~2 窗且落在段间 → 正常呼吸空隙
     - 连续多窗或 -90dB 级 → 文案欠填充/排程事故，必须修复
退出码: 0 = PASS，1 = FAIL
"""
import subprocess, sys
from pathlib import Path


def find_tool(name):
    p = __import__("shutil").which(name)
    if p:
        return p
    for cand in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        c = Path(cand) / name
        if c.exists():
            return str(c)
    raise SystemExit(f"未找到 {name}，请安装 ffmpeg")


def dur_of(fp, path):
    r = subprocess.run([fp, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


def mean_vol(ff, path, t, dur=2.0):
    r = subprocess.run([ff, "-hide_banner", "-ss", str(t), "-t", str(dur),
                        "-i", str(path), "-map", "0:a", "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].replace("dB", "").strip())
    return -99.0


def main():
    ff = find_tool("ffmpeg")
    fp = find_tool("ffprobe")
    final, source = Path(sys.argv[1]), Path(sys.argv[2])
    total = dur_of(fp, final)
    src = dur_of(fp, source)
    print("== 时长 ==")
    print("  成片 %.2fs / 源 %.2fs" % (total, src))
    dur_ok = abs(total - src) < 0.5
    print("  时长校验: %s" % ("PASS" if dur_ok else "FAIL"))

    print("== 响度扫描 ==")
    step = max(3.0, total / 40)
    silent, ok = [], 0
    t = 1.0
    while t < total - 2.0:
        v = mean_vol(ff, final, t, min(2.0, step))
        if v < -70:
            silent.append((round(t, 1), v))
        elif v < -20 > -70 or v >= -20:
            ok += 1
        t += step
    if silent:
        print("  静音窗 %d 个:" % len(silent))
        for t, v in silent:
            print("    t=%6.1fs  %6.1f dB" % (t, v))
        print("  判读：孤立 1 窗且位于段间 = 呼吸空隙（可接受）；"
              "连续多窗 = 文案欠填充或排程事故，须修复")
    else:
        print("  无静音窗，全程有声 PASS")

    verdict = dur_ok and len(silent) <= 1
    print("== 总判定: %s ==" % ("PASS" if verdict else "FAIL"))
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()
