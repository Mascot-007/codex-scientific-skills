# Prism 8 原生脚本与验证

已核实本机 `SampleScripts/Repeatedly Import Data.pzc` 包含 `GoTo D 1`、`ClearTable` 和 `Import`。官方 Prism 8 文档确认脚本支持打开、导入、保存与图像导出：
https://www.graphpad.com/guides/prism/8/user-guide/using_scripts.htm
https://www.graphpad.com/support/faq/list-of-all-script-commands-for-graphpad-prism/
https://www.graphpad.com/guides/prism/latest/user-guide/script_example_4__open_a_template_and_import_data.htm

Windows 启动方式为 prism.exe @"job.pzc"；使用 subprocess 的参数列表，不用 shell 拼接。GUI 需要的授权由执行环境处理。

基本脚本：
```
Open "template.pzf"
Save "working.pzfx"
GoTo D 1
ClearTable
Import "mapped.tsv"
RecalcAll
GoTo G 1
ExportPNG "figure.png"
ExportPDF "figure.pdf"
Save "result.pzfx"
```

上例中的完整路径由辅助脚本生成。编号从 1 开始。ClearTable 的具体标题/格式行为、Import 的首行标题/X列规则需用该模板的工作副本验证，不能仅检查行列总数。装饰坐标表不应全部清空。模板保存的分析会自动重新计算，但模板可能还含不适用的分析；必须审查。

prepare 默认不导入数据，只生成试导出。run 只负责启动，不证明脚本完成。Prism 可能复用已有进程，退出码不能用作完成信号。等待输出时最多 60 秒一次，同时检查错误对话框；不要终止用户其他 Prism 进程。

PNG/PDF 导出后必须打开检查轴标题、图例、标签、统计标注、误差棒和样例残留。项目文件重新解析检查用户数据；必要时在 Prism 重新打开。不在没有实时 UI 能力时承诺任意菜单自动化。
