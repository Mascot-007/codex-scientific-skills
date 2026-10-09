# Biacore .bme 权威终检：用 .NET 的 cp936 + XmlDocument 复现软件的读取路径
#
# 用法:
#   1) python bme_tool.py dump <file.bme> <tmp_dir>      # 导出评价项流（每个流一个 .bin）
#   2) powershell -File net_check.ps1 <tmp_dir>          # 逐个判定
#
# 判定标准（实测得出）:
#   cp936 解码后 字符数 == 字节数 且 NUL=0  -> 无空洞，软件能打开
#   字符数 < 字节数                          -> 缓冲区尾部留 "空格+NUL"，报 0x00 无效字符
#   <ConcUnit> 码点必须是 U+00B5 U+004D (µM)，否则向导报 "The concentration could not be converted to Molar."
#
param(
    [Parameter(Mandatory = $true)][string]$Dir,
    [string]$Out = "$Dir\net_check.txt"
)

$gbk = [System.Text.Encoding]::GetEncoding(936)
$lines = New-Object System.Collections.Generic.List[string]
$files = Get-ChildItem -Path $Dir -Filter '*.bin' | Sort-Object Name

foreach ($f in $files) {
    $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
    $text  = $gbk.GetString($bytes)
    $chars = $text.Length
    $nul   = 0
    foreach ($ch in $text.ToCharArray()) { if ([int]$ch -eq 0) { $nul++ } }

    $hole = if ($chars -eq $bytes.Length) { '无空洞' } else { '有空洞(会报错!)' }
    $parse = 'OK'
    $conc = ''
    try {
        $doc = New-Object System.Xml.XmlDocument
        $doc.LoadXml($text)
        $nodes = $doc.SelectNodes('//ConcUnit')
        if ($nodes.Count -gt 0) {
            $v = $nodes[0].InnerText
            $codes = @()
            foreach ($ch in $v.ToCharArray()) { $codes += ('U+{0:X4}' -f [int]$ch) }
            $conc = ($codes -join ' ')
        }
    } catch {
        $parse = 'FAIL: ' + $_.Exception.Message
    }

    $lines.Add(('{0,-50} bytes={1,6}  gbk字符={2,6}  {3}  NUL={4}  XML={5}' -f `
        $f.Name, $bytes.Length, $chars, $hole, $nul, $parse))
    if ($conc) {
        $mark = if ($conc -eq 'U+00B5 U+004D') { '  <- µM 正确' } else { '  <- 非 µM，向导会报"浓度无法转换 Molar"' }
        $lines.Add(('       ConcUnit: ' + $conc + $mark))
    }
}

$lines | Out-File -FilePath $Out -Encoding UTF8
Write-Output ("done: " + $files.Count + " files -> " + $Out)
