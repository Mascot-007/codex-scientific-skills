---
name: biacore-bme-repair
description: 诊断与修复 Biacore/GE/Cytiva .bme（及 .blr）评价文件在打开或分析时报 InvalidXmlSource / 浓度无法转换为
  Molar 的问题。适用于仪器电脑（西文码页）产出的文件在中/日文 Windows 上无法打开的场景——根因是评价项 XML 里的单字节 Latin-1 字符（µ
  ² °）被系统 ANSI 码页(如 cp936)解码后字节数大于字符数，在软件按字节数分配的字符缓冲尾部留下 NUL 空洞。含扫描、预判、修复（XML 字符实体化
  + 浓度单位 µM→nM 换算 + OLE 原位改写）、批量（fix_all.py 二合一）、校验工具。触发词：bme 打不开、Biacore 报错、InvalidXmlSource、XmlManagementException、浓度无法转换
  Molar、SPR 数据修复、批量修复 bme。
metadata:
  agent_created: true
---

# Biacore .bme 评价文件修复

> 上游仓库：https://github.com/Mascot-007/biacore-bme-repair
> 目录内脚本：`bme_tool.py`（检查/单文件修复/批量/校验/导出）、`fix_all.py`（批量二合一，推荐）、
> `fix_conc_nm.py`（仅浓度单位）、`net_check.ps1`（.NET 权威终检）。

## 适用症状

- 打开评价文件弹窗：`XmlManagementException: InvalidXmlSource`
- 异常日志（桌面 `Exception <日期>.txt`）里出现以下之一：
  - `'.', hexadecimal value 0x00, is an invalid character. Line 1, position N.` ← **最常见**
  - `The 'unit' start tag ... does not match the end tag of 'column'`
- 文件能打开，但分析向导报 `The concentration could not be converted to Molar.`（中文界面：浓度无法转换为 Molar）

## 一、先判断文件格式（不要猜）

`.bme` / `.blr` 是 **OLE 复合文档**（头 `D0 CF 11 E0 A1 B1 1A E1`），内部是命名流：

```
Evaluation/EvaluationItem0..N          <- 各分析项的 XML（软件按 XML 严格解析）
Evaluation/EvaluationItem*Binary       <- 拟合结果二进制（不要动）
_DataManager 1/FileTag                 <- 文件级浓度单位 ConcUnit=µM（换算失败的根源，见 5.5）
_DataManager 1/AppData/ApplicationTemplate  <- 显示用模版（带 ISO-8859-1 声明，保持原样）
_DataManager 1/AppData/ApplicationMethod    <- 方法脚本（不是 XML）
_DataManager 1/_Cycle N/_Window 1/_Curve M/\x03Keywords <- 每周期关键字（Key=..\tValue=..\tType=..）
_DataManager 1/_Cycle N/.../Segment 1|XYData <- 传感图二进制（不要动）
```

工具：`pip install olefile`。**`olefile.write_stream` 只允许等长覆盖**，变长必须自行改写。

## 二、根因（已实测确认）

1. 仪器电脑是**西文码页**，写文件时 `µ`=**0xB5**、`²`=**0xB2**、`°`=**0xB0**，**1 字节 = 1 字符**，在那边一切正常。
2. 软件 `Biacore.XmlManagement.XmlSection` 在**本机用系统 ANSI 码页解码**（中文 Windows = cp936），
   且解码目标是**按「字节数」分配的字符缓冲**。因此流中任何 `>=0x80` 的字节都会：
   - 被 GBK 与后随字节**并成 1 个字符** → 解码后**字符数 < 字节数**
   - 缓冲区尾部残留 `空格 + NUL` 空洞 → 解析器报 **0x00 无效字符**，
     **报错位置 = GBK 字符数 + 2**（实测：字符数 27501→位置 27503；27500→位置 27502）
3. 若 `0xB2` 后跟 `<`(0x3C) 这类**非法 GBK 尾字节**，解码器会把 `<` 一起吞掉，
   `</unit>` → `/unit>`，标签结构断裂 → `The 'unit' start tag ... does not match the end tag of 'column'`。
4. **结论：只要评价项流是纯 ASCII（1 字节 = 1 字符），就没有空洞，软件必能打开。**

### ⚡ 一句话判据（无需打开软件即可预判）

> **cp936 解码后「字符数 == 字节数」→ 能打开；「字符数 < 字节数」→ 必报 InvalidXmlSource。**

这个判据比“看非 ASCII 字节”更本质，且可用 `check` 模式直接算：

```bash
python bme_tool.py check  <file.bme>     # 逐流给出 bytes / gbk字符 / 有空洞? / ConcUnit 解析值
python bme_tool.py scan   <file.bme>     # 需要看坏字节上下文时用
```

`ConcUnit` 在 GBK 下解出的码点若是 **`U+791B`（"碌"）**，即等价于 `B5 4D`，也就是原始坏编码
（用户日志 `Arguments:` 字段里回显的就是这个字，可直接用来对照）。

### 单位词表（软件内部，位于安装目录的 `Biacore.T200.SharedModules.dll`）

```
M   mM   nM   µM(U+00B5)   g/l   µg/ml   ng/ml   mg/ml
```
- **没有** ASCII 备选写法 `uM` → 写 `uM` 文件能打开但向导报“浓度无法转换 Molar”（**实测过**）
- **cp936 里没有任何字节对能解码成 U+00B5**（只有 `A6CC` → U+03BC μ，且软件表里没有它）
  ⇒ 想给向导一个合法单位，**只能**在 XML 里用字符实体 `&#181;`

## 三、修复方法

把评价项流里的特殊字符改写成 **XML 字符实体**：

| 原字节 | 改写为 | 含义 |
|---|---|---|
| `B5 4D` (`µM`) | `&#181;M` | U+00B5 |
| `B2 3C` (`²<`) | `&#178;<` | U+00B2 |
| `B0 43` (`°C`) | `&#176;C` | U+00B0 |

效果：**字节全为 ASCII**（消除空洞 → 能打开），而 **XML 解析结果仍是真正的 µM / Chi² / °C**
（精确匹配软件单位表 → 向导能换算）。这是唯一同时满足两条件的写法。

### 一条命令搞定

```bash
python bme_tool.py fix     <in.bme> <out.bme>            # 单文件 → 修复副本（原文件不动）
python bme_tool.py fixdir  <src_dir> <out_dir>          # 批量整个目录，无需修的文件原样复制
python bme_tool.py verify  <out.bme> <in.bme>           # 校验（fix 内部已自动调用）
```

### ⭐ 两个问题一起修（推荐：同批次文件批量）

```bash
python fix_all.py  <src_dir> <out_dir>      # 步骤1 评价项实体化 + 步骤2 单位/浓度换算，一步到位
```

**重要**：同一批文件里，**即使能打开的文件也必须做步骤2** —— 它们的 `FileTag` 同样
是 `ConcUnit=µM`，在中文系统上向导一律换算失败（只是用户还没分析到那一步）。
所以只做步骤1（`bme_tool.py fixdir`）产出的副本，仍然是“能打开但不能分析”的半成品。
`fix_all.py` 会判断评价项是否已是纯 ASCII，是则跳过步骤1、只做步骤2。

### 字节预算

实体使流变长（每个 +5 字节），**必须仍在原扇区链配额内**（否则要扩 FAT，风险陡增）。
不够时把空元素 `<X></X>` 改写成 `<X/>`（XML 语义完全等价、用户不可见）。
😱 **Python 陷阱**：bytes 模式替换**必须用 lambda**，`rb'<\1/>'` 里的 `\1` 会被当成八进制转义写成 **0x01 字节**，静默破坏 XML：

```python
SELFCLOSE.sub(lambda m: b'<' + m.group(1) + b'/>', data)   # 正确
SELFCLOSE.sub(rb'<\1/>', data)                             # 错误！产生 0x01
```

### OLE 原位改写（不扩文件、不动 FAT）

```python
# 1) 解析头/FAT/目录，拿到目标流的扇区链与配额
# 2) 按链顺序写入新内容，剩余部分补 0x00
# 3) 把该流目录项偏移 +120 处的 8 字节长度改为新长度
struct.pack_into('<Q', data, entry_off + 120, len(new_content))
```

## 四、校验必做项（`verify` 已实现 1/4/5）

1. 新流 `bytes.isascii()`；`cp936 解码字符数 == 字节数`、NUL 数 = 0
2. **.NET 权威终检**（与软件同一条读取路径，唯一有说服力的证据）：
   ```bash
   python bme_tool.py dump <file.bme> <tmp_dir>      # 导出评价项流为 .bin
   powershell -File net_check.ps1 -Dir <tmp_dir>     # cp936 解码 + XmlDocument.LoadXml
   ```
   通过标准：`字符数 == 字节数`、`NUL=0`、`LoadXml` OK、`ConcUnit` 码点 = `U+00B5 U+004D`
3. **结构等价性**：`xml.etree` 解析「旧流按 latin-1 解码」与「新流按 ascii 解码」，逐节点比对必须完全一致
4. 除评价项外**所有流 md5 不变**（尤其 `*Binary`、`Segment`、`XYData`）
5. `olefile.OleFileIO(out).parsing_issues == []`

## 五、批量修复（同批次文件往往全都有病）

同一次实验拷回来的一批 `.bme`，只要评价项里有 µ，在中文 Windows 上**全都会报错**；
用户通常只在打开某个文件时才发现。而且**每一个**的 `FileTag` 都是 `ConcUnit=µM`，
分析时还都会撞上浓度换算失败。

👉 **直接跑二合一的批量工具**（推荐，一次解决两个问题）：

```bash
python fix_all.py "C:\data\SPR" "C:\data\SPR-fixed"
```

输出到**独立目录**、保持原文件名，不要覆盖原数据目录。
仅当只需要解决“打不开”时才用 `bme_tool.py fixdir`。

### 实测案例（8 个同批 SPR 文件，`fix_all.py` 一次跑通；文件名已匿名化）

| 文件 | 评价项 | 浓度换算 | 备注 |
|---|---|---|---|
| file-A | 1 流 / 8 实体 | 28 条（Cycle 6–12） | 浓度序列 1.37→1000 µM |
| file-B | 1 流 / 10 实体 | 40 条 | 含 15.625 / 31.25 / 62.5 µM 等小数 |
| file-C | 1 流 / 12 实体 | 40 条 | |
| file-D | **0（本就纯 ASCII）** | 40 条 | 只做步骤2 |
| file-E | 1 流 / 10 实体 | 32 条 | |
| file-F | 1 流 / 10 实体 | 32 条 | |
| file-G | 1 流 / 14 实体 | 40 条 | |
| file-H | 1 流 / 10 实体 | 40 条 | |

校验全绿：每个评价项 `gbk字符数==字节数`、NUL=0、`LoadXml` OK、`ConcUnit`=`U+00B5 U+004D`；
`Segment/Binary/XYData` 等二进制流 md5 与原始逐一相同（合计 400+ 个流）；
每个 Cycle 的 `Molar` 值与原 µM 语义完全一致（如 15.625 µM ≡ 15625 nM ≡ 1.5625e-5 M）。

### 小数浓度也要 ×1000

`15.625`、`31.25`、`62.5`、`0.05`、`0.46` 这类小数 ×1000 后**都是精确整数**
（15625 / 31250 / 62500 / 50 / 460），所以数值改写永远是“变短或变长几个字节”、
不会出现精度丢失。改写前必须断言 `abs(float(new) - float(old)*1000) < 1e-9`，
不成立就报错停下（说明单位不是 µM，需重新判断）。

## 五点五、文件能打开，但向导报 "The concentration could not be converted to Molar."

这是**另一层问题**：评价项修好后，Kinetics/Affinity 向导仍拒绝 Cycle 6..N（浓度 0 的 Cycle 不报）。

### 机制（从软件 DLL 反汇编实锤，KineticsAffinity.dll + SharedModules.dll）

- 浓度**数值**在各 Cycle `_Curve N/Keywords`：`Key=Sample_1_Conc\tValue=0.05\tType=SampleConc`（纯 ASCII，`Double.TryParse` 通过）
- 浓度**单位**来自 `_DataManager 1/FileTag` 流（11 字节 `ConcUnit=µM`），
  经 `FileTagItemCollection.ParseStream` 按 `\n` split、`Key=`/`Value=` 解析
- `ConcentrationConverter.RecalcConc` 用 **VB `Operators.CompareString` 精确比对**单位与内部词表
  `M / mM / nM / µM(U+00B5) / g/l / µg/ml / ng/ml / mg/ml`，按 `old*1e-6` 之类的表达式经
  `ExpressionEvaluator` 换算到 Molar；**没有任何模糊匹配/回退**
- µ 的 0xB5 在中文系统被解成"碌"→ `碌M` 不在词表 → 换算失败。
  **死结：cp936 没有任何字节对能解出 U+00B5**，所以 FileTag 里的 µ 在中文系统上怎么写都没用
  （写 UTF-8 / C1 控制字节 / A6CC 都不行）

### 修复（`fix_conc_nm.py` / `fix_all.py` 的步骤2，已实测交付）

把单位整体换成词表里**纯 ASCII 的 nM**，数值同步 ×1000：

1. `FileTag`: `ConcUnit=\xB5M` → `ConcUnit=nM`（**恰好等长 11 字节**，单字节替换）
2. 每个 Cycle 的 Keywords 流：`Sample_1_Conc` 的 `Value` ×1000（0.05→50 … 1000→1000000，
   全是精确整数），在**该流自己的迷你扇区配额内**重写（约 500 B 的流占 8 个迷你扇区=512 B，
   有 8~12 B 松弛，最长 +3 B 足够）
3. 对拟合零影响：软件内部本来就全换算成 Molar；向导里浓度列会显示 nM

### 关键技术点（.bme 的流名与迷你流）

- ⚠️ **流名带不可见 `\x03` 前缀**（如 `\x03Keywords`、`\x03Attributes`），控制台打印看不见，
  按裸名匹配会全部落空——匹配前先 `name.lstrip('\x03')`
- ⚠️ **迷你流寻址**：迷你扇区号 → 文件偏移必须经「ministream 自身的常规扇区 FAT 链」映射：
  `file_off = off(mini_chain[ms // (SECTOR//64)]) + (ms % (SECTOR//64)) * 64`；
  直接 `base + ms*64` 是错的
- ⚠️ **同名目录项陷阱**：目录里可能残留同名孤儿条目，按叶子名 `find` 会撞车——
  必须解析目录树（left/right/child，偏移 68/72/76）按**全路径**定位
- 改写迷你流 = 写入自己的迷你扇区链 + 补零 + 更新目录项 +120 处的 8 字节 size；
  不动迷你 FAT、不动其他流

### OLE 读取换算自检

修完后用词表复核一遍：`unit in 词表` 且 `Molar = value * 因子`（nM→1e-9），
逐 Cycle 打印应与原始 µM 数值语义一致（如 Cycle 6: 0.05 µM ≡ 50 nM ≡ 5e-8 M）。

## 六、注意（别踩坑）

- **不要**把 µ 改成 ASCII 的 `u`/`M`：能打开，但向导报“浓度无法转换为 Molar”
- **不要**改成 GBK 的 `A6CC`：字符数又少 1 → 空洞重现；且软件表里只有 U+00B5
- FileTag 里的 `0xB5`：**打开问题**不用动它（它不是 InvalidXmlSource 的原因）；
  但**向导换算失败**时必须按 5.5 的方案换成 nM 并同步数值
- `AppData/ApplicationTemplate`（1800+ 非 ASCII，带 `encoding="ISO-8859-1"` 声明）保持原样
- ⚠️ **曾走过的弯路（别重犯）**：只看“`B5 4D` 是不是合法 GBK 字节对”会得出错误结论——
  它确实是合法对，但**照样**造成“字节数>字符数”，照样报错。判据必须是「字符数 == 字节数」。
  同理，只改 µ 为 `u`（纯 ASCII）能让文件打开，却会让向导报浓度换算失败；
  必须用**字符实体**才能同时满足两个条件。
- 中间产物（如 `-fixed.bme`…）确认最终版可用后，**征得用户同意**再移入回收站，不要直接删。
- 从仪器拷数据时**只拷原始 run 数据、不在仪器端做分析**，可完全避开此问题。
