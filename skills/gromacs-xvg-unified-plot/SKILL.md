---
name: gromacs-xvg-unified-plot
description: Batch plot GROMACS .xvg analysis outputs including RMSD, RMSF, radius
  of gyration, hydrogen bonds, energy and SASA with consistent publication figure
  styling.
metadata:
  title: GROMACS xvg 统一风格批量绘图
  summary: 将 GROMACS 分析输出的 .xvg 文件批量绘制成统一风格的出版级图片（阴影+主线签名风格）
  read_when:
  - 用户要求绘制 GROMACS .xvg 分析结果
  - 分子动力学模拟结果可视化（RMSD/RMSF/Rg/氢键/能量/SASA 等）
  agent_created: true
---

# GROMACS xvg 统一风格批量绘图

## 适用场景

用户给一批 `gmx` 分析输出的 .xvg 文件，要求统一风格绘图。先做数据侦察，再逐张绘制并让用户确认风格，全部产出放入新建的 `MD_Figures/` 文件夹（图 + 代码 + 共享风格模块）。

## 环境

- Python（用户 venv）：matplotlib + pandas + numpy
- 读数据：`np.loadtxt(file, comments=['@', '#'])`
- 侦察命令：`grep -vE '^[@#&]' file.xvg | awk '{...}'` 看范围/均值/末帧

## 共享风格模块（md_style.py）

建议的默认风格，所有图引用同一模块保证统一：

- 配色：主色 `#1A237E`（深靛蓝），对比色 `#F46036`（橙）/`#8E24AA`（紫）/`#2ca02c`（绿）
- 签名效果：粗阴影（lw 4.0, alpha 0.3）+ 细主线（lw 1.5）
- figsize (10, 5.5)，dpi 300；轴标签 15 号 / 刻度标签 13 号 Arial
- 四边内向主刻度（length 6, width 1.5）+ 次级刻度（AutoMinorLocator）
- 图例：无边框，图外右上 `bbox_to_anchor=(1.02, 0.85)`
- `compress_y(ax, y, factor=1.5, bottom=0)`：Y 轴放宽压扁波动突出稳定（bottom=None 时围绕均值对称，用于键长/能量/温度等不接近 0 的量）
- 时间单位统一 ps→ns（除以 1000）；**先检查文件头 xaxis label 的单位，不同文件可能不同**

## 按数据类型选表达方式（关键决策规则）

| 数据类型 | 表达方式 | 例子 |
|---|---|---|
| 连续时间序列 | 原始数据粗阴影 + 平滑主线（rolling window=50） | contacts, SASA, Rg |
| 离散整数计数 | **阴影画在平滑线上并加粗到 lw=8**（光晕）；raw 阴影会糊成实心块/竖条 | 氢键数、给受体对 |
| 深尖峰时间序列 | 同上光晕方案，尖峰不再拉扯画面 | mindist, pressure |
| 离散类别标签 | 小散点（s=4, alpha 0.55），图例 markerscale=4 | cluster_id |
| 少数 bin 分布（<10） | 棒棒糖图（ax.stem），比单柱高级 | 粗分布 |
| 取整数据分布 | 高斯 KDE（带宽 > 取整间隔）+ 填充，归一化峰值=1 | 键长直方图 |
| 多序列对比 | 每条线各自配色 + 各自同色阴影 | Rg 四分量、RMSD 双线 |
| 多链 RMSF | 检测残基号回退断点 → 链连续化 → 链间灰色虚线分隔 | rmsf.xvg |

## 数据质量检查（必做）

1. **PBC 伪影**：Rg/RMSD 出现瞬时跳到 2-4 倍基线又恢复的尖峰 = 蛋白跨周期性边界。不要仅凭尖峰判断伪影或自动删除/插值。核实轨迹、PBC处理和拟合设置；如用户同意过滤，保留原始数据、展示处理前后差异并记录阈值。不同文件的伪影帧往往一致，可交叉验证。
2. **直方图溢出**：`gmx distance -oh` 默认范围可能不含实际值，100% 堆在末 bin。画之前检查非零 bin 数量，溢出则用原始序列重算。
3. **时长不一致**：同一批文件可能 250 ns 与 500 ns 混杂，逐文件核对末帧时间并告知用户。
4. **单点文件**：只有 1 行数据的文件无法画剖面，报告数值即可。
5. **Cα vs 全原子 RMSF 倒置**（Cα > 全原子）说明拟合基团不一致，提醒用户核实 `-fit` 参数。

## 可按用户需求调整的默认审美

- 图内**不放数值文字标注**，均值/峰值只用橙色虚线（保持画面干净）
- 稳定性图 Y 轴一律放宽压扁波动
- 曲线尽量在图中垂直居中
- 逐张展示确认风格后再画下一张；确认过的规则立即固化进 md_style.py

## 参考实现

本公开包为指令型 Skill，不包含私人项目的 21 个分析脚本或实验数据。使用时根据数据生成项目局部脚本和共享 md_style.py。

