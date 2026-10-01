#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manim 视频配音流水线（可移植版）：分段 TTS → 级联排程 → ffmpeg 合成 → 验收。

用法:
    python dub_pipeline.py config.json

config.json 结构:
{
  "project_dir": "/abs/path/to/project",   // 含源视频的项目目录
  "video": "assets/source.mp4",            // 相对 project_dir 的视频路径
  "out_name": "成片名.mp4",
  "voice": "zh-CN-XiaoyiNeural",           // 可选，默认晓伊
  "sections": [
    {"name": "01_片头", "start": 0.0, "end": 6.5, "text": "解说文案"},
    ...
  ]
}

依赖: edge-tts (pip install edge-tts)、ffmpeg/ffprobe（自动探测 PATH 与常见安装位置）。
"""
import asyncio, json, os, shutil, subprocess, sys
from pathlib import Path

CFG = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
D = Path(CFG["project_dir"]).resolve()
AUDIO = D / "work" / "audio"
OUT_DIR = D / "out"
SRC = D / CFG["video"]
FINAL = OUT_DIR / CFG["out_name"]
VOICE = CFG.get("voice", "zh-CN-XiaoyiNeural")
LEAD, GAP = 0.3, 0.25
SECTIONS = CFG["sections"]
TOTAL = SECTIONS[-1]["end"]


def find_tool(name):
    p = shutil.which(name)
    if p:
        return p
    for cand in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        c = Path(cand) / name
        if c.exists():
            return str(c)
    raise SystemExit(f"未找到 {name}。请安装 ffmpeg（见 references/environment-setup.md）并确保在 PATH 中。")


FF = find_tool("ffmpeg")
FP = find_tool("ffprobe")


def dur_of(path):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


async def tts(text, rate, path):
    try:
        import edge_tts
    except ImportError:
        raise SystemExit("缺少 edge-tts：请先 pip install edge-tts")
    c = edge_tts.Communicate(text, VOICE, rate=rate)
    await c.save(str(path))


async def gen_all():
    AUDIO.mkdir(parents=True, exist_ok=True)
    durs = []
    for i, sec in enumerate(SECTIONS):
        target = (sec["end"] - sec["start"]) - 0.7
        path = AUDIO / ("s%02d.mp3" % (i + 1))
        rate = 4
        for _ in range(6):
            await tts(sec["text"], "+%d%%" % rate, path)
            d = dur_of(path)
            if d <= target:
                break
            rate += 4
        durs.append(d)
        flag = "OK" if d <= target else "LONG"
        print("TTS %2d/%d %-28s 段%5.1fs 音%6.2fs +%d%% %s"
              % (i + 1, len(SECTIONS), sec["name"],
                 sec["end"] - sec["start"], d, rate, flag), flush=True)
    return durs


def main(durs):
    sched, prev_end = [], -9.0
    for i, sec in enumerate(SECTIONS):
        start = max(sec["start"] + LEAD, prev_end + GAP)
        sched.append((sec, start, durs[i]))
        prev_end = start + durs[i]
    print("\n== 排程 ==")
    for sec, st, d in sched:
        print("  %-28s 画面%6.1f-%6.1f  音%7.2f-%7.2f"
              % (sec["name"], sec["start"], sec["end"], st, st + d))
    for a, b in zip(sched, sched[1:]):
        if b[1] < a[1] + a[2] - 1e-6:
            raise SystemExit("音频重叠: %s vs %s" % (a[0]["name"], b[0]["name"]))
    last = sched[-1]
    if last[1] + last[2] > TOTAL:
        print("警告: 尾部超出 %.2fs" % (last[1] + last[2] - TOTAL))

    inputs, chains, labels = [], [], ""
    for i, (sec, st, d) in enumerate(sched):
        inputs += ["-i", str(AUDIO / ("s%02d.mp3" % (i + 1)))]
        ms = int(round(st * 1000))
        chains.append("[%d:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                      "adelay=%d|%d[a%d]" % (i, ms, ms, i))
        labels += "[a%d]" % i
    fc = ";".join(chains) + ";%samix=inputs=%d:normalize=0[mix]" % (labels, len(sched))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-y", *inputs,
           "-i", str(SRC), "-filter_complex", fc,
           "-map", "%d:v" % len(sched), "-map", "[mix]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(TOTAL), str(FINAL)]
    subprocess.run(cmd, check=True)

    od = dur_of(FINAL)
    sz = FINAL.stat().st_size / 1e6
    print("\n== 成片 ==\n  %s\n  时长 %.2fs (源 %.1fs)  大小 %.1fMB"
          % (FINAL, od, TOTAL, sz))
    print("  时长校验: %s" % ("PASS" if abs(od - TOTAL) < 0.5 else "FAIL"))

    table = OUT_DIR / "段落表.txt"
    with open(table, "w", encoding="utf-8") as f:
        f.write("段名\t画面起\t画面止\t音频起\t音频止\t文案\n")
        for sec, st, d in sched:
            f.write("%s\t%.1f\t%.1f\t%.2f\t%.2f\t%s\n"
                    % (sec["name"], sec["start"], sec["end"], st, st + d, sec["text"]))
    print("  段落表: %s" % table)
    print("\n下一步：运行 scripts/check_sync.py 做硬标准验收，再做阶段五自我复核。")


async def run():
    durs = await gen_all()
    main(durs)

asyncio.run(run())
