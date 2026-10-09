# 参考图片重绘

1. 原 PNG/JPG/WebP 保留，记录宽高、文字内容/边界/基线/字号/字重/颜色/旋转/层次。可人工记录或用已安装 OCR；不把 OCR 结果未经校对用于科学符号。
2. 清除文字后的图片作为独立文件。若使用图像编辑工具，检查形状、连线、尺寸、颜色未意外改变。不用 VTracer 追踪文字；文字轮廓化与 live text 叠加不能算恢复。
3. `trace.py --image cleaned.png --manifest text.json --text-removed --out master.svg`，在相同画布合并文本。纯图形也要提供空 text_elements 清单，明确所有文字已检查。
4. 检查 master.svg 的文字与源图的位置，运行 draw.py。不要从成图反推出实验数据。箭头、标签、比例和每项关键细节逐一对照。

文字清单格式：`{"schema_version":"1.0","text_elements":[{"id":"label1","content":"Protein A","x":150,"y":80,"coordinate_space":"svg","font_size":18,"font_family":"Arial","font_weight":"normal","fill":"#203344","text_anchor":"start","alignment_baseline":"alphabetic","rotation":0}]}`。

文字清单的坐标与 cleaned.png 原始像素坐标一致。底层图形 trace 输出中不应残留 glyph 路径。手工图形清理或图像编辑后由人工/视觉核对清单；脚本开关只是已核对的声明，不证明去字质量。
