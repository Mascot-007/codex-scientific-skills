# 本机验证 2026-10-09

Prism 8.0.2.263 实际执行 3 号散点箱线图模板的 Open、Save、GoTo G 1、ExportPNG、ExportPDF、Save 命令。UTF-8 BOM 脚本和中文绝对路径可执行。日志为“完成！没有错误”。生成 working.pzfx、result.pzfx、figure.png、figure.pdf；PNG 经视觉检查与 PDF 3 号示例一致。

该测试仅验证样例模板打开、保存及导出；尚未测试用户数据导入、129 个模板兼容性或 GUI 任意编辑。图中的原始 P 值仍为模板示例，不代表用户结果。

Prism 8 导出的 PZFX 使用默认 XML namespace；inspect 先去除 namespace 再解析。38 号模板为无 namespace 的 Prism 10 XML，两者都须支持。

运行环境可使用已有 Python，无需新安装。旧 anaconda Python 在沙箱内对相对路径 resolve 曾报 WinError 5，推荐绝对路径及可用的运行时 Python。中文 Skill 验证用 python -X utf8，避免系统 GBK 解码。
