# -*- coding: utf-8 -*-
"""步骤2（单文件）：FileTag 单位 uM -> nM + 各 Cycle 浓度值 x1000

适用症状
    文件能正常打开，但在 Kinetics/Affinity 向导里报
    `The concentration could not be converted to Molar.`
    （中文界面：浓度无法转换为 Molar）

用法
    python fix_conc_nm.py <in.bme> <out.bme>

原理（详见 README「原理」与 docs/root-cause.md）
    软件 `ConcentrationConverter.RecalcConc` 用精确字符串比对内部单位词表
        M / mM / nM / uM(U+00B5) / g/l / ug/ml / ng/ml / mg/ml
    FileTag 流里的 `ConcUnit=µM`，其 µ(0xB5) 在 cp936 下被解成「碌」，
    `碌M` 不在词表 -> 换算失败（浓度为 0 的 Cycle 不参与换算，所以不报错）。
    而 cp936 里**没有任何字节对能解出 U+00B5**，所以单位只能整体换成纯 ASCII 的 nM，
    数值同步 ×1000 —— 软件内部本来就全部换算成 Molar 再拟合，KD 不受影响。

实现要点
    被改的 FileTag / Keywords 都是**迷你流**；改写只发生在该流自己的迷你扇区配额内，
    不动 FAT / 迷你 FAT / 其他流；**原文件不动**（copy 后改副本）。
    依赖同目录的 fix_all.py（复用其中的 Bme 读写器）。
"""
import re
import sys
import shutil

import olefile

from fix_all import Bme, CONC_RE


def convert(src, dst):
    shutil.copy2(src, dst)
    b = Bme(dst)
    clean = b.by_clean_path()

    # ---- 1) FileTag: ConcUnit=µM -> ConcUnit=nM（恰好等长 11 字节） ----
    ft = clean.get(('_DataManager 1', 'FileTag'))
    if ft is None:
        raise KeyError('找不到 _DataManager 1/FileTag 流')
    ftd = b.read(ft)
    if ftd == b'ConcUnit=\xb5M':
        b.write(ft, b'ConcUnit=nM')
        print('FileTag: ConcUnit=uM -> ConcUnit=nM (等长 %d B)' % len(ftd))
    elif ftd == b'ConcUnit=nM':
        # 幂等保护：步骤2 已执行过，再乘一次 1000 会毁掉浓度值
        print('FileTag 已是 ConcUnit=nM —— 步骤2 已执行过，跳过（避免浓度被重复 x1000）')
        b.save(dst)
        return 0
    else:
        raise ValueError('FileTag 非预期内容: %r（可能单位不是 µM）' % ftd)

    # ---- 2) 各 Cycle Keywords 的 Sample_1_Conc 数值 x1000 ----
    changed = []
    for path, e in sorted(clean.items()):
        if len(path) != 5 or path[-1] != 'Keywords' or not path[1].startswith('_Cycle '):
            continue
        d0 = b.read(e)
        m = re.search(CONC_RE, d0)
        if not m:
            continue
        old = m.group(2).decode()
        if old in ('', '0'):
            continue                                  # 空白对照/零浓度不换算
        val = float(old) * 1000.0
        newv = str(int(round(val)))
        if abs(float(newv) - val) > 1e-9:
            raise ValueError('%s: %s -> %s 不是精确整数换算，单位可能不是 µM'
                             % ('/'.join(path), old, newv))
        b.write(e, d0[:m.start(2)] + newv.encode() + d0[m.end(2):])
        changed.append((int(path[1].split()[1]), path[3], old, newv))

    for cyc, curve, old, newv in sorted(changed):
        print('  Cycle %-2d Curve %s  %s uM -> %s nM' % (cyc, curve, old, newv))
    print('Keywords 改写 %d 条（每 Cycle 4 条曲线）' % len(changed))

    b.save(dst)
    return len(changed)


def verify(src, dst):
    o0, o1 = olefile.OleFileIO(src), olefile.OleFileIO(dst)
    ok = not o1.parsing_issues
    if not ok:
        print('!! olefile 解析问题:', o1.parsing_issues)
    s0 = {'/'.join(x).replace('\x03', ''): x for x in o0.listdir()}
    s1 = {'/'.join(x).replace('\x03', ''): x for x in o1.listdir()}
    if set(s0) != set(s1):
        print('!! 流清单与原始文件不同')
        ok = False
    changed = sorted(k for k in s0
                     if o0.openstream(s0[k]).read() != o1.openstream(s1[k]).read())
    unexpected = [k for k in changed
                  if k != '_DataManager 1/FileTag'
                  and not (k.endswith('/Keywords') and '_Cycle' in k)]
    if unexpected:
        print('!! 预期外的改动:', unexpected)
        ok = False
    if o1.openstream(s1['_DataManager 1/FileTag']).read() != b'ConcUnit=nM':
        print('!! FileTag 终检失败')
        ok = False
    import hashlib
    seg = [k for k in s0 if any(t in k for t in ('Segment', 'Binary', 'XYData'))]
    bad = [k for k in seg
           if hashlib.md5(o0.openstream(s0[k]).read()).digest()
           != hashlib.md5(o1.openstream(s1[k]).read()).digest()]
    print('变更流 %d 个；二进制/传感图流 %d 个完整性: %s'
          % (len(changed), len(seg), '一致 ✓' if not bad else '异常 %s' % bad))
    if bad:
        ok = False
    o0.close()
    o1.close()
    print('结论:', 'PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    n = convert(sys.argv[1], sys.argv[2])
    sys.exit(0 if (n >= 0 and verify(sys.argv[1], sys.argv[2])) else 2)
