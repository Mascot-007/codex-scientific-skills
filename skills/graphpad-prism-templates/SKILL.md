---
name: graphpad-prism-templates
description: 使用 GraphPad Prism 和合法获得的本地 1-129 号模板选择图型、导入数据、保存可编辑项目并导出图像。
---

# Prism 模板绘图

模板原件和参考 PDF 由用户自行合法取得，本仓库只包含编号索引和原创自动化脚本，不分发第三方模板或图册预览。读取 references/catalog.md，按编号/文件名定位；给用户展示候选图时读取用户本地 PDF，不把商业图册上传到其他服务。

先核对实验结论、数据结构、配对、样本单位和误差棒。用 scripts/prism_job.py prepare --id N --template-root <本地模板目录> --out <新输出目录> 生成只打开副本并导出的试验脚本；run <job.pzc> --exe <本机 Prism.exe> 启动原生脚本。

先检查保存的 PZFX 数据表结构，再准备与子列、X列及标题规则匹配的 TSV。使用 --data <mapped.tsv> --table N --graph N --shape-verified。不得在未经映射检查时使用 shape-verified。多表模板需要逐表导入，辅助定位表不应盲目清空。

模板统计与示例数据不能当作用户结果；移除或重算 P值、HR、置信区间、星号。分析依据实验设计，不能由外观推断。38号原模板记录 Prism10；仅3号已在 Prism8试导出，其他兼容性未逐一验证。

原件不修改，输出目录必须不存在。运行完检查项目数据、导出 PNG/PDF 和日志，重新打开项目确认可编辑。脚本启动不证明绘图成功；许可/版本/错误对话框需要检查。没有实时 UI 能力时不能承诺任意菜单自动化。高级样式不兼容时说明损失，让用户选择兼容模板。

详见 references/automation.md 和 README.md。安装和项目路径由当前用户指定，不依赖作者电脑的用户名。
