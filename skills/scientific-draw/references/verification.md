# 实测 2026-10-09

- Illustrator 2023 COM 版本 27.0.0；PowerPoint 版本 16.0。
- 机制示例：同一 SVG 18 个 atoms、7 段文字；PPT 18 个原生对象，7 个文本框。PPTX XML 有 11 个 custom geometry，0 个 p:pic 图片。AI 13 个路径、1 个 compound，7 个文本框。两分支文字内容与源缓存逐项比对相同。
- 两应用均导出 PNG/PDF，图像经过视觉检查。AI 字体家族 Arial 在本机有粗体误选现象，适配器已显式选择 ArialMT/Arial-BoldMT 等字体，并重新实际绘制验证。
- 复合路径 fixture：白色外形的内部镂空透出蓝色底色；两应用保持一致，贝塞尔曲线正常，2 段文字保留。
- 本地 VTracer：纯色圆形和矩形图片生成 SVG，并回填 live text，准备后的缓存为 4 atoms、1 段文字。这里只测试 tracing/merge/parse，未对该 tracing 样例再执行双应用渲染。
- 自动 OCR、复杂照片、中文字体、旋转文字、超大图和用户已有文档的编辑尚未实测；此入口默认新建文档，不能宣称任意已有文档修改已经验证。
- Illustrator ExtendScript 不提供稳定 JSON.stringify；桥接使用 URI 编码返回值，缓存读取用原后端本地 JSON 解析方式。
- 测试输出位于 <LOCAL_PROJECT_DIRECTORY>
