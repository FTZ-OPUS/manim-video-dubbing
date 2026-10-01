# 环境准备

本技能只依赖两样外部工具，其余全在 Python 内。开始前逐项自检。

## ffmpeg / ffprobe（必需）

检测：`which ffmpeg ffprobe`（Windows: `where ffmpeg`）

| 平台 | 安装 |
|---|---|
| macOS (Homebrew) | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Windows | `winget install Gyan.FFmpeg` 或从 https://www.gyan.dev/ffmpeg/builds/ 下载后加入 PATH |

已知坑：某些精简版 ffmpeg 无 `drawtext` 滤镜（缺 freetype）——本技能不使用 drawtext，不影响。

## Python + edge-tts（必需）

- Python 3.9+，任意 venv 均可：`pip install edge-tts`
- 验证：`python -c "import edge_tts; print('ok')"`
- edge-tts 需联网（调用微软接口）；生成 30 段约 1~2 分钟
- 音色（config 中 `voice` 字段）：默认 `zh-CN-XiaoyiNeural`（轻快活泼女声）；备选 `zh-CN-XiaoxiaoNeural`（温柔亲和）。仅支持中文解说。

## 已知环境问题

- pip 安装大体积包（onnxruntime 系）在 16GB 内存机器上可能被 OOM kill（exit 137）——本技能不需要这类包
- 无音轨视频是理想输入；有原声时先与用户确认保留/替换
- 渲染中间产物 `partial_movie_files` 若存在可用于时间轴二次对账，但常被清理，不作依赖
