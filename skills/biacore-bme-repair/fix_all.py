# -*- coding: utf-8 -*-
"""Biacore .bme 批量两步修复（打不开 + 不能分析，一次搞定）

用法:
    python fix_all.py <src_dir> <out_dir>

步骤1  评价项 XML 字符实体化  -> 解决 InvalidXmlSource（"打不开"）
步骤2  FileTag 单位 uM->nM + 各 Cycle 浓度值 x1000 -> 解决
       "The concentration could not be converted to Molar."（"不能分析"）

要点:
* 同一批文件里，**即使能打开的文件也需要步骤2** —— 它们的 FileTag 同样是
  `ConcUnit=µM`，在中文系统上向导一律换算失败。所以本工具对目录下**所有** .bme
  都做步骤2，只有评价项是纯 ASCII 的才跳过步骤1。
* 统一处理常规流（≥ MiniStreamCutoffSize）与迷你流两种存储；改写只发生在
  该流自身的扇区配额内，不动 FAT / 迷你 FAT / 其他流。
* 输出到独立目录、保持原文件名；**原目录一个字节都不动**。

校验（每个文件）:
  - olefile.parsing_issues 为空
  - 流清单与原始一致；除评价项/FileTag/Keywords 外无任何流被改
  - Segment/Binary/XYData 等二进制流 md5 与原始完全相同
  - 每个评价项：纯 ASCII、gbk 字符数==字节数、NUL=0
  - FileTag == b'ConcUnit=nM'
  - 浓度换算：new == round(old*1000)，且 old*1e-6 == new*1e-9（Molar 语义不变）

权威终检（须另做，见 SKILL.md 第四节）:
    python bme_tool.py dump <out.bme> <tmp_dir>   # 逐文件
    powershell -File net_check.ps1 <tmp_dir>
"""
import os
import re
import sys
import glob
import struct
import hashlib
import shutil

import olefile

ENTITIES = [
    (b'\xb5M', b'&#181;M'),   # µM   (U+00B5)
    (b'\xb2<', b'&#178;<'),   # Chi² (U+00B2)
    (b'\xb0C', b'&#176;C'),   # °C   (U+00B0)
]
SELFCLOSE = re.compile(rb'<([A-Za-z0-9_]+)></\1>')
ALLOWED = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}
NOSTREAM = 0xFFFFFFFF
CONC_RE = rb'(Key=Sample_1_Conc\tValue=)([^\t]*)(\tType=SampleConc)'


class Bme:
    """极简 OLE 读写器：常规流 + 迷你流统一寻址（按目录树全路径定位）"""

    def __init__(self, path):
        self.path = path
        self.data = bytearray(open(path, 'rb').read())
        d = self.data
        self.SECTOR = 1 << struct.unpack_from('<H', d, 0x1E)[0]
        self.MINI = 1 << struct.unpack_from('<H', d, 0x20)[0]
        self.CUTOFF = struct.unpack_from('<I', d, 0x38)[0]
        num_fat = struct.unpack_from('<I', d, 0x2C)[0]
        dir_start = struct.unpack_from('<I', d, 0x30)[0]
        minifat_start = struct.unpack_from('<I', d, 0x3C)[0]
        fat_secs = [s for s in struct.unpack_from('<109I', d, 0x4C)[:num_fat] if s != 0xFFFFFFFF]
        self.fat = []
        for s in fat_secs:
            self.fat += list(struct.unpack_from('<%dI' % (self.SECTOR // 4), d, self.off(s)))
        self.dir_entries = []
        for sec in self.chain(dir_start, self.fat):
            for i in range(self.SECTOR // 128):
                e = self.off(sec) + i * 128
                nlen = struct.unpack_from('<H', d, e + 64)[0]
                self.dir_entries.append({
                    'off': e,
                    'name': bytes(d[e:e + nlen - 2]).decode('utf-16-le', 'replace') if nlen >= 2 else '',
                    'type': d[e + 66],
                    'left': struct.unpack_from('<I', d, e + 68)[0],
                    'right': struct.unpack_from('<I', d, e + 72)[0],
                    'child': struct.unpack_from('<I', d, e + 76)[0],
                    'start': struct.unpack_from('<I', d, e + 116)[0],
                    'size': struct.unpack_from('<Q', d, e + 120)[0],
                })
        self.bypath = {}
        root = self.dir_entries[0]
        if root['child'] != NOSTREAM:
            self._walk(root['child'], [])
        self.minifat = []
        for s in self.chain(minifat_start, self.fat):
            self.minifat += list(struct.unpack_from('<%dI' % (self.SECTOR // 4), d, self.off(s)))
        self.mini_chain = self.chain(root['start'], self.fat)
        self.mini_per_sector = self.SECTOR // self.MINI

    def off(self, sector):
        return (sector + 1) * self.SECTOR

    def chain(self, start, table):
        out, s = [], start
        while s < 0xFFFFFFFA and len(out) < 1000000:
            out.append(s)
            s = table[s]
        return out

    def _walk(self, idx, prefix):
        """目录树遍历（left/right/child）——**不能**按叶子名匹配，可能撞上同名孤儿条目"""
        seen, stack = set(), [idx]
        while stack:
            i = stack.pop()
            if i in seen or i == NOSTREAM or i >= len(self.dir_entries):
                continue
            seen.add(i)
            e = self.dir_entries[i]
            if e['type'] in (1, 2):
                self.bypath[tuple(prefix + [e['name']])] = e
                if e['type'] == 1 and e['child'] != NOSTREAM:
                    self._walk(e['child'], prefix + [e['name']])
            stack.append(e['left'])
            stack.append(e['right'])

    def _mini_file_off(self, ms):
        # 迷你扇区号 -> 文件偏移，必须经 ministream 自身的常规扇区 FAT 链映射
        sec = self.mini_chain[ms // self.mini_per_sector]
        return self.off(sec) + (ms % self.mini_per_sector) * self.MINI

    def _positions(self, e):
        if e['size'] < self.CUTOFF:
            ch = self.chain(e['start'], self.minifat)
            return [(self._mini_file_off(s), self.MINI) for s in ch], len(ch) * self.MINI
        ch = self.chain(e['start'], self.fat)
        return [(self.off(s), self.SECTOR) for s in ch], len(ch) * self.SECTOR

    def read(self, e):
        pos, _ = self._positions(e)
        out = bytearray()
        for foff, chunk in pos:
            out += self.data[foff:foff + chunk]
        return bytes(out[:e['size']])

    def write(self, e, content):
        pos, alloc = self._positions(e)
        if len(content) > alloc:
            raise ValueError('超出扇区配额 %s: %d > %d' % (e['name'], len(content), alloc))
        buf = bytes(content) + b'\x00' * (alloc - len(content))
        k = 0
        for foff, chunk in pos:
            self.data[foff:foff + chunk] = buf[k:k + chunk]
            k += chunk
        struct.pack_into('<Q', self.data, e['off'] + 120, len(content))
        e['size'] = len(content)
        return alloc

    def save(self, path):
        open(path, 'wb').write(bytes(self.data))

    def by_clean_path(self):
        """流名可能带不可见 \\x03 前缀（如 \\x03Keywords），统一剥离后再索引"""
        return {tuple(x.lstrip('\x03') for x in p): e for p, e in self.bypath.items()}


def build_ascii(old):
    """µ ² ° -> XML 字符实体；再把空元素 <X></X> 压成 <X/> 省字节（语义等价）"""
    new, stat = old, {}
    for a, b in ENTITIES:
        stat[a.decode('latin-1')] = new.count(a)
        new = new.replace(a, b)
    new, n_sc = SELFCLOSE.subn(lambda m: b'<' + m.group(1) + b'/>', new)   # 必须用 lambda！
    bad = sorted({x for x in new if x not in ALLOWED})
    if bad:
        raise ValueError('仍含非法字节: %s' % [hex(x) for x in bad])
    return new, stat, n_sc


def process(src, dst):
    rep = {'file': os.path.basename(src), 'ok': True, 'eval': [], 'conc': [],
           'filetag': None, 'notes': []}
    shutil.copy2(src, dst)
    b = Bme(dst)
    clean = b.by_clean_path()

    # ---- 步骤1：评价项 XML 字符串实体化 ----
    for path, e in sorted(clean.items()):
        if len(path) != 2 or path[0] != 'Evaluation' or e['type'] != 2:
            continue
        if not path[1].startswith('EvaluationItem') or path[1].endswith('Binary'):
            continue
        old = b.read(e)
        if old.isascii():
            continue
        try:
            new, stat, n_sc = build_ascii(old)
            alloc = b.write(e, new)
        except Exception as ex:
            rep['ok'] = False
            rep['notes'].append('评价项 %s: %s' % (path[1], ex))
            continue
        rep['eval'].append({'name': path[1], 'old': len(old), 'new': len(new),
                            'alloc': alloc, 'ent': stat, 'selfclose': n_sc})
        print('  [评价项] %-22s %6d -> %6d B  %s 自闭合%d' % (
            path[1], len(old), len(new), stat, n_sc))

    # ---- 步骤2a：FileTag 单位 µM -> nM ----
    #     幂等保护: 已经是 nM 说明步骤2 执行过，若再乘一次 1000 会毁掉浓度值
    conc_ok = False
    ft = clean.get(('_DataManager 1', 'FileTag'))
    if ft is None:
        rep['ok'] = False
        rep['notes'].append('找不到 FileTag')
    else:
        ftd = b.read(ft)
        if ftd == b'ConcUnit=\xb5M':
            b.write(ft, b'ConcUnit=nM')          # 恰好等长 11 B
            rep['filetag'] = {'old': repr(ftd), 'new': 'ConcUnit=nM'}
            conc_ok = True
            print('  [单位]   FileTag: ConcUnit=uM -> ConcUnit=nM (等长)')
        elif ftd == b'ConcUnit=nM':
            rep['filetag'] = {'old': repr(ftd), 'new': 'ConcUnit=nM', 'already': True}
            rep['notes'].append('单位已是 nM，跳过步骤2（避免浓度被重复 x1000）')
        else:
            rep['ok'] = False
            rep['notes'].append('FileTag 非预期: %r' % ftd)

    # ---- 步骤2b：Keywords 浓度值 x1000 ----
    for path, e in (sorted(clean.items()) if conc_ok else []):
        if len(path) != 5 or path[-1] != 'Keywords' or not path[1].startswith('_Cycle '):
            continue
        d0 = b.read(e)
        m = re.search(CONC_RE, d0)
        if not m:
            continue
        old = m.group(2).decode()
        if old in ('', '0'):
            continue
        val = float(old) * 1000.0
        newv = str(int(round(val)))
        if abs(float(newv) - val) > 1e-9:
            rep['ok'] = False
            rep['notes'].append('非精确整数换算: %s -> %s' % (old, newv))
            continue
        newd = d0[:m.start(2)] + newv.encode() + d0[m.end(2):]
        try:
            alloc = b.write(e, newd)
        except ValueError as ex:
            rep['ok'] = False
            rep['notes'].append('%s: %s' % ('/'.join(path), ex))
            continue
        rep['conc'].append({'cycle': int(path[1].split()[1]), 'curve': path[3],
                            'old': old, 'new': newv, 'alloc': alloc})
    print('  [浓度]   Keywords 改写 %d 条（每 Cycle 4 条曲线）' % len(rep['conc']))

    b.save(dst)

    # ---- 校验 ----
    o0, o1 = olefile.OleFileIO(src), olefile.OleFileIO(dst)
    if o1.parsing_issues:
        rep['ok'] = False
        rep['notes'].append('olefile.parsing_issues=%s' % o1.parsing_issues)
    s0 = {'/'.join(x).replace('\x03', ''): x for x in o0.listdir()}
    s1 = {'/'.join(x).replace('\x03', ''): x for x in o1.listdir()}
    if set(s0) != set(s1):
        rep['ok'] = False
        rep['notes'].append('流清单不一致')
    changed = sorted(k for k in s0 if o0.openstream(s0[k]).read() != o1.openstream(s1[k]).read())
    unexpected = [k for k in changed
                  if not (k.startswith('Evaluation/EvaluationItem')
                          or k == '_DataManager 1/FileTag'
                          or (k.endswith('/Keywords') and '_Cycle' in k))]
    if unexpected:
        rep['ok'] = False
        rep['notes'].append('预期外改动: %s' % unexpected)
    seg = [k for k in s0 if any(t in k for t in ('Segment', 'Binary', 'XYData'))]
    badseg = [k for k in seg
              if hashlib.md5(o0.openstream(s0[k]).read()).digest()
              != hashlib.md5(o1.openstream(s1[k]).read()).digest()]
    if badseg:
        rep['ok'] = False
        rep['notes'].append('二进制流被改: %s' % badseg)
    for k in sorted(s0):
        if not k.startswith('Evaluation/EvaluationItem') or k.endswith('Binary'):
            continue
        d = o1.openstream(s1[k]).read()
        ch = len(d.decode('cp936', 'replace'))
        if not d.isascii() or ch != len(d) or b'\x00' in d:
            rep['ok'] = False
            rep['notes'].append('评价项未达标 %s: ascii=%s chars=%d bytes=%d'
                                % (k, d.isascii(), ch, len(d)))
    if o1.openstream(s1['_DataManager 1/FileTag']).read() != b'ConcUnit=nM':
        rep['ok'] = False
        rep['notes'].append('FileTag 终检失败')
    rep['changed'] = len(changed)
    rep['seg'] = '%d/%d' % (len(seg) - len(badseg), len(seg))
    o0.close()
    o1.close()
    return rep


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src_dir, out_dir = sys.argv[1], sys.argv[2]
    files = sorted(glob.glob(os.path.join(src_dir, '*.bme')))
    os.makedirs(out_dir, exist_ok=True)
    print('源目录: %s\n输出到: %s\n共 %d 个 .bme\n' % (src_dir, out_dir, len(files)))
    reps = []
    for f in files:
        print('=' * 78)
        print(os.path.basename(f))
        try:
            reps.append(process(f, os.path.join(out_dir, os.path.basename(f))))
        except Exception as ex:
            import traceback
            traceback.print_exc()
            reps.append({'file': os.path.basename(f), 'ok': False, 'eval': [], 'conc': [],
                         'filetag': None, 'notes': ['异常: %s' % ex],
                         'changed': 0, 'seg': '-'})
        print('  => %s' % ('PASS' if reps[-1]['ok'] else 'FAIL ' + str(reps[-1]['notes'])))

    print('\n' + '=' * 78)
    print('%-6s %-38s %-9s %-7s %-8s %s' % ('结果', '文件', '评价项', '浓度条数', '流变更', '备注'))
    for r in reps:
        n_ent = sum(sum(v for v in s['ent'].values()) for s in r['eval'])
        print('%-6s %-38s %-9s %-7d %-8s %s' % (
            'PASS' if r['ok'] else 'FAIL', r['file'],
            '%d流/%d实体' % (len(r['eval']), n_ent), len(r['conc']),
            r.get('changed', '-'), r['notes'] if r['notes'] else '无'))
    print('\n' + ('全部通过 ✅' if all(r['ok'] for r in reps) else '⚠ 存在失败项，请检查'))
    print('提醒: 还需按 SKILL.md 第四节做 .NET 权威终检（bme_tool.py dump + net_check.ps1）')
    sys.exit(0 if all(r['ok'] for r in reps) else 2)


if __name__ == '__main__':
    main()
