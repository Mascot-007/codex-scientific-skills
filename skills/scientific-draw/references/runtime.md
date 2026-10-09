# 执行与支持范围

```powershell
& 'D:\public\Codex\environments\scientific-draw\Scripts\python.exe' 'D:\public\Codex\skills\scientific-draw\scripts\draw.py' --svg 'D:\project\master.svg' --application both --out 'D:\project\figure-01'
```

脚本提供 `--application ai|ppt|both`、`--svg`、`--out`，新目录保护避免覆盖。`--prepare-only` 仅解析并验证几何，不连接桌面；安装测试使用新的输出目录。缓存参数为 20-50 对象一批，不逐点复制粘贴。

SVG 支持 rect/circle/ellipse/line/polyline/polygon/path/text、仿射 transform、solid fill/stroke、Bezier 和 nonzero 复合路径。PPT 不接受未规范化的 evenodd 复合填充；出错时明确保留错误，不拆镂空。字体优先 Arial/Arial-BoldMT 或已安装中文字体；复杂排版需分成独立 text 元素。

脚本导出 `master.svg`、`text-manifest.json`、`geometry-cache/`、`verification.json`、`figure.ai`、`figure.pptx`、`illustrator.png/pdf`、`powerpoint.png/pdf`（取决于分支）。PPTX 中为 OOXML native custom geometry，而非作为单个 SVG 图片插入。PPT 实际 COM 打开并导出；Illustrator 调用 DoJavaScript 按缓存绘制。

依赖 python-pptx/fonttools/pywin32/pillow/vtracer。安装使用 process TEMP/TMP=D:/public/Codex/temp 和 PIP_CACHE_DIR=D:/public/Codex/cache/pip。不得自行安装到用户 C 盘。此 Skill 不保证任意第三方 SVG、复杂照片、渐变/网格或原图字体完全一致。
