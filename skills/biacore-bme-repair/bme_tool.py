# -*- coding: utf-8 -*-
"""Biacore .bme 检查/修复工具（配合 biacore-bme-repair skill 使用）

用法:
  python bme_tool.py scan    <file.bme>                 # 逐个评价项流列出非 ASCII 字节及上下文
  python bme_tool.py check   <file.bme>                 # 判定是否会被判为损坏 + ConcUnit 在 GBK 下解析成什么
  python bme_tool.py fix     <in.bme> <out.bme>         # 生成修复副本（字符实体化 + OLE 原位改写）
  python bme_tool.py fixdir  <src_dir> <out_dir>        # 批量：目录下所有 .bme 生成修复副本（无需修的原样复制）
  python bme_tool.py verify  <file.bme> [orig.bme]      # 校验：纯 ASCII / NUL / 流差异 / 二进制完整性
  python bme_tool.py dump    <file.bme> <out_dir>       # 导出评价项流为 .bin（供 net_check.ps1 做权威终检）

原理: 软件 Biacore.XmlManagement.XmlSection 用系统 ANSI 码页(cp936)把评价项 XML 解码进
      「按字节数分配的字符缓冲」。流中任何 >=0x80 的字节都会被 GBK 合并成 1 个字符，
      解码后字符数 < 字节数，缓冲区尾部留下 "空格+NUL" 空洞 -> InvalidXmlSource。
      报错位置 = GBK 字符数 + 2（对照两份日志实测吻合）。
      修复 = 把 µ ² ° 改成 XML 字符实体 &#181; &#178; &#176;：
      字节变纯 ASCII（无空洞，能打开），解析结果仍是真的 µM / Chi² / °C
      （匹配软件内部单位表 U+00B5 + M，向导才能换算 Molar）。

判据（无需打开软件即可预判）:
      cp936 解码后 字符数 == 字节数  -> 无空洞 -> 能打开
      cp936 解码后 字符数 <  字节数  -> 有空洞 -> 必报 InvalidXmlSource
"""
import os
import re
import sys
import glob
import shutil
import struct
import hashlib
import xml.etree.ElementTree as ET

import olefile

ENTITIES = [
    (b'\xb5M', b'&#181;M'),   # µM (U+00B5)
    (b'\xb2<', b'&#178;<'),   # Chi² / RU² (U+00B2)
    (b'\xb0C', b'&#176;C'),   # °C (U+00B0)
]
SELFCLOSE = re.compile(rb'<([A-Za-z0-9_]+)></\1>')
ALLOWED = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}
XML_STREAM_PREFIX = 'Evaluation/EvaluationItem'


def cp936_view(d):
    """模拟软件读取：按 cp936 解码。返回 (文本, 字符数, 空洞?)"""
    try:
        t = d.decode('cp936')
    except UnicodeDecodeError:
        t = d.decode('cp936', 'replace')
    return t, len(t), len(t) < len(d)


def concunit_codepoints(text):
    """从 cp936 视角的文本里取第一个 <ConcUnit> 的**解析后**值（软件看到的就是这个）。

    必须走 XML 解析（实体会被展开），否则会把 `&#181;M` 误判成非 µM。
    """
    try:
        root = ET.fromstring(text)
        for el in root.iter('ConcUnit'):
            v = el.text or ''
            return ' '.join('U+%04X' % ord(c) for c in v), v
    except Exception:
        pass
    m = re.search(r'<ConcUnit>(.*?)</ConcUnit>', text, re.S)   # 退化路径
    if not m:
        return None
    expand = re.sub(r'&#(\d+);', lambda mm: chr(int(mm.group(1))), m.group(1))
    return ' '.join('U+%04X' % ord(c) for c in expand), expand


# ---------------------------------------------------------------- 公共
class OleImage:
    """极简 OLE 定位器：扇区/FAT/目录项/链"""

    def __init__(self, path):
        self.path = path
        self.data = bytearray(open(path, 'rb').read())
        d = self.data
        self.sector_size = 1 << struct.unpack_from('<H', d, 0x1E)[0]
        num_fat = struct.unpack_from('<I', d, 0x2C)[0]
        self.dir_start = struct.unpack_from('<I', d, 0x30)[0]
        fat_secs = [s for s in struct.unpack_from('<109I', d, 0x4C)[:num_fat] if s != 0xFFFFFFFF]
        self.fat = []
        for s in fat_secs:
            self.fat += list(struct.unpack_from('<%dI' % (self.sector_size // 4), d, self.off(s)))

    def off(self, sector):
        return (sector + 1) * self.sector_size

    def chain(self, start):
        out, s = [], start
        while s < 0xFFFFFFFA and len(out) < 100000:
            out.append(s)
            s = self.fat[s]
        return out

    def entries(self):
        for ds in self.chain(self.dir_start):
            for i in range(self.sector_size // 128):
                e = self.off(ds) + i * 128
                nlen = struct.unpack_from('<H', self.data, e + 64)[0]
                if nlen < 2:
                    continue
                name = bytes(self.data[e:e + nlen - 2]).decode('utf-16-le', 'replace')
                yield name, e, struct.unpack_from('<I', self.data, e + 116)[0], \
                    struct.unpack_from('<Q', self.data, e + 120)[0]

    def find(self, name):
        """name 可传 'Evaluation/EvaluationItem4' 或叶子名 'EvaluationItem4'（目录项只存叶子名）"""
        leaf = name.split('/')[-1]
        hit = None
        for nm, off, start, size in self.entries():
            if nm == leaf:
                hit = (off, start, size)
                if size >= 4096:      # 优先取常规流（> mini 阈值的那个）
                    return hit
        if hit:
            return hit
        raise KeyError(name)

    def streams(self):
        return ['/'.join(s) for s in olefile.OleFileIO(self.path).listdir()]

    def read(self, name):
        return olefile.OleFileIO(self.path).openstream(name.split('/')).read()

    def rewrite(self, name, content):
        off, start, size = self.find(name)
        ch = self.chain(start)
        alloc = len(ch) * self.sector_size
        if len(content) > alloc:
            raise ValueError('%s 超出扇区配额 %d > %d（需先腾出空间或扩 FAT）'
                             % (name, len(content), alloc))
        buf = content + b'\x00' * (alloc - len(content))
        for k, s in enumerate(ch):
            p = self.off(s)
            self.data[p:p + self.sector_size] = buf[k * self.sector_size:(k + 1) * self.sector_size]
        struct.pack_into('<Q', self.data, off + 120, len(content))
        return len(ch), alloc

    def save(self, path):
        open(path, 'wb').write(bytes(self.data))


def xml_streams(ole_img):
    return [n for n in ole_img.streams()
            if n.startswith(XML_STREAM_PREFIX) and not n.endswith('Binary')]


def build_ascii(old, allow_selfclose=True):
    new = old
    stat = {}
    for a, b in ENTITIES:
        n = new.count(a)
        stat[a.decode('latin-1')] = n
        new = new.replace(a, b)
    n_sc = 0
    if allow_selfclose:
        new, n_sc = SELFCLOSE.subn(lambda m: b'<' + m.group(1) + b'/>', new)
    bad = sorted({x for x in new if x not in ALLOWED})
    if bad:
        raise ValueError('仍含非法字节: %s' % [hex(x) for x in bad])
    return new, stat, n_sc


def needs_repair(path):
    """返回需要修复的流名列表"""
    img = OleImage(path)
    return [n for n in xml_streams(img) if not img.read(n).isascii()]


# ---------------------------------------------------------------- 命令
def cmd_scan(path):
    img = OleImage(path)
    for n in xml_streams(img):
        d = img.read(n)
        hx = [(i, hex(b), d[i + 1] if i + 1 < len(d) else -1) for i, b in enumerate(d) if b >= 0x80]
        flag = '  <== 会被软件判为损坏' if hx else ''
        print('%-34s %7d bytes  非ASCII=%d%s' % (n, len(d), len(hx), flag))
        for i, b, nxt in hx[:8]:
            ctx = d[max(0, i - 26):i + 20]
            print('    @%-6d %s 后随 %r  ...%s...' % (
                i, b, chr(nxt) if 32 <= nxt < 127 else hex(nxt),
                ''.join(chr(c) if 32 <= c < 127 else '.' for c in ctx)))


def cmd_check(path):
    """不做任何修改，预判该文件能否被软件打开"""
    img = OleImage(path)
    print('文件: %s' % path)
    bad_total = 0
    for n in xml_streams(img):
        d = img.read(n)
        text, chars, hole = cp936_view(d)
        nonascii = sum(1 for b in d if b >= 0x80)
        verdict = 'OK' if not hole else '会报错(有空洞)'
        cu = concunit_codepoints(text)
        print('  %-34s bytes=%-7d 非ASCII=%-3d gbk字符=%-7d %s' % (
            n.split('/')[-1], len(d), nonascii, chars, verdict))
        if cu:
            cps, raw = cu
            print('        <ConcUnit> 在 GBK 下 = %r  %s%s' % (
                raw, cps, '   <== 不是 U+00B5(µ)，向导会报"浓度无法转换 Molar"' if cps != 'U+00B5 U+004D' else '   ✓ 正确'))
            if cps != 'U+00B5 U+004D' and nonascii:
                bad_total += 1
        elif nonascii:
            bad_total += 1
    print('结论: %s' % ('需修复（存在非 ASCII 评价项）' if bad_total else '无需修复'))
    return bad_total == 0


def cmd_fix(src, dst, quiet=False):
    shutil.copy2(src, dst)
    img = OleImage(dst)
    print('源: %s\n目标: %s' % (src, dst))
    for n in xml_streams(img):
        old = img.read(n)
        if old.isascii():
            print('  %-34s 已是纯 ASCII，跳过' % n)
            continue
        new, stat, n_sc = build_ascii(old)
        nsec, alloc = img.rewrite(n, new)
        print('  %-34s %d -> %d bytes (配额 %d, 链 %d 扇区)' % (n, len(old), len(new), alloc, nsec))
        print('      实体替换 %s，空元素自闭合 %d 处' % (stat, n_sc))
    img.save(dst)
    print('已写出:', dst, os.path.getsize(dst), 'bytes')
    return cmd_verify(dst, src)


def cmd_verify(path, ref=None):
    ole = olefile.OleFileIO(path)
    print('\n=== 校验 %s ===' % path)
    print('olefile 解析问题:', getattr(ole, 'parsing_issues', 'n/a'))
    ok = True
    for n in xml_streams(OleImage(path)):
        d = ole.openstream(n.split('/')).read()
        bad = sum(1 for b in d if b >= 0x80)
        nul = d.count(b'\x00')
        _, chars, hole = cp936_view(d)
        st = 'OK' if not bad and not nul and not hole else 'BAD'
        if st == 'BAD':
            ok = False
        print('  %-4s %-34s %7d bytes 非ASCII=%d NUL=%d gbk字符=%d' % (st, n, len(d), bad, nul, chars))
    if ref:
        o0 = olefile.OleFileIO(ref)
        s0 = {'/'.join(x): x for x in o0.listdir()}
        s1 = {'/'.join(x): x for x in ole.listdir()}
        if set(s0) != set(s1):
            print('!! 流清单与原始文件不同'); ok = False
        else:
            changed = [k for k in s0
                       if o0.openstream(s0[k]).read() != ole.openstream(s1[k]).read()]
            expect = {n for n in changed if n.startswith(XML_STREAM_PREFIX)}
            print('  变化的流:', changed)
            if not set(changed) <= expect:
                print('!! 出现了预期外的改动'); ok = False
            seg = [k for k in s0 if any(t in k for t in ('Segment', 'Binary', 'XYData'))]
            badseg = [k for k in seg
                      if hashlib.md5(o0.openstream(s0[k]).read()).digest()
                      != hashlib.md5(ole.openstream(s1[k]).read()).digest()]
            print('  二进制/传感图流 (%d 个) 完整性: %s' % (len(seg), '一致 ✓' if not badseg else '异常 %s' % badseg))
            if badseg:
                ok = False
        o0.close()
    ole.close()
    print('结论:', 'PASS' if ok else '仍需处理')
    return ok


def cmd_fixdir(src_dir, out_dir):
    files = sorted(glob.glob(os.path.join(src_dir, '*.bme')))
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for f in files:
        name = os.path.basename(f)
        dst = os.path.join(out_dir, name)
        try:
            if not needs_repair(f):
                shutil.copy2(f, dst)
                results.append((name, 'COPY', '评价项已是纯 ASCII，原样复制'))
                print('-- %s 无需修复，原样复制' % name)
                continue
            ok = cmd_fix(f, dst)
            results.append((name, 'PASS' if ok else 'CHECK', ''))
        except Exception as e:
            results.append((name, 'FAIL', str(e)))
            print('== %s !! 失败: %s' % (name, e))
    print('\n' + '=' * 70)
    for name, st, info in results:
        print('  [%-5s] %s %s' % (st, name, info))
    print('全部通过' if all(r[1] in ('PASS', 'COPY') for r in results)
          else '存在未通过项，请检查上面的 !! 行')
    return results


def cmd_dump(path, out_dir):
    """导出评价项流为 .bin，供 net_check.ps1 用 .NET 做权威终检"""
    os.makedirs(out_dir, exist_ok=True)
    img = OleImage(path)
    tag = os.path.basename(path)
    for n in xml_streams(img):
        dst = os.path.join(out_dir, '%s__%s.bin' % (tag, n.split('/')[-1]))
        open(dst, 'wb').write(img.read(n))
        print('%s  %7d bytes' % (dst, os.path.getsize(dst)))
    return True


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    mode, target = sys.argv[1], sys.argv[2]
    if mode == 'scan':
        cmd_scan(target)
    elif mode == 'check':
        sys.exit(0 if cmd_check(target) else 2)
    elif mode == 'fix':
        if len(sys.argv) < 4:
            sys.exit('用法: fix <in.bme> <out.bme>')
        sys.exit(0 if cmd_fix(target, sys.argv[3]) else 2)
    elif mode == 'fixdir':
        if len(sys.argv) < 4:
            sys.exit('用法: fixdir <src_dir> <out_dir>')
        cmd_fixdir(target, sys.argv[3])
    elif mode == 'verify':
        sys.exit(0 if cmd_verify(target, sys.argv[3] if len(sys.argv) > 3 else None) else 2)
    elif mode == 'dump':
        if len(sys.argv) < 4:
            sys.exit('用法: dump <file.bme> <out_dir>')
        cmd_dump(target, sys.argv[3])
    else:
        print(__doc__)
