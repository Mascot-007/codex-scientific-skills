# Codex Scientific Skills

Mascot-007 的自建科研 Skill 合集：文件修复、分子模拟分析、虚拟筛选及可编辑科研绘图。

## Skill 索引

| Skill | 用途 |
|---|---|
| [biacore-bme-repair](skills/biacore-bme-repair/README.md) | 修复特定跨编码环境下 .bme/.blr XML 和浓度单位问题。 |
| [gromacs-xvg-unified-plot](skills/gromacs-xvg-unified-plot/README.md) | 检查并绘制 RMSD、RMSF、Rg、氢键、SASA 等 XVG 数据。 |
| [schrodinger-glide-workflow](skills/schrodinger-glide-workflow/README.md) | 配体准备、手性核查、并行对接和结果整理。 |
| [graphpad-prism-templates](skills/graphpad-prism-templates/README.md) | 检索 129 个本地模板并生成 Prism 原生脚本。 |
| [scientific-draw](skills/scientific-draw/README.md) | 机制图、实验流程图、图形摘要和本地矢量重绘；保留路径和 live text。 |

## 安装

克隆或下载仓库，将所需 `skills/<name>` 完整文件夹复制到 Codex skills 目录，下一轮对话使用 `$<name>` 调用。也可将完整包保存在其他磁盘，仅在 Codex skills 目录写一个路由入口。

```powershell
git clone https://github.com/Mascot-007/codex-scientific-skills.git D:\Codex\codex-scientific-skills
```

每个 Skill 的依赖、操作步骤、示例和限制见独立 README / SKILL.md。安装 Python 包时使用自己的独立环境；若 C 盘空间紧张，显式将环境、TEMP/TMP、pip cache 放到其他盘。商业软件必须自行安装和合法授权。

## 已验证和未验证

- scientific-draw：作者的 Windows / Illustrator 2023（27.0.0）/ PowerPoint（16.0）实测原生路径、文字、复合路径镂空及 PNG/PDF 导出；不保证任意照片或复杂 SVG。
- Prism：3号模板在 Prism8试导出成功；129个模板未全部验证。模板需用户自行合法取得。
- GROMACS 为指令型 Skill；不包含私人项目脚本和数据。平滑、过滤与单位变换需记录，不得把美化当作科学结论。
- 软件版本、COM权限和文件结构影响运行结果。脚本生成成功仍需检查实际文件及图像。

## 来源与许可

原创说明和代码使用 MIT（见 LICENSE），第三方代码遵循其原许可证。scientific-draw 的部分后端来自 [yrui-cmd/cell_su7](https://github.com/yrui-cmd/cell_su7)，保留 MIT 署名。直接导入的第三方 Skill 未冒充本合集原创内容。Prism 第三方图册、模板及其预览没有随仓库分发。

作者其他仓库：[Biacore 修复](https://github.com/Mascot-007/biacore-bme-repair)、[Glide 工作流](https://github.com/Mascot-007/schrodinger-glide-workflow)。
