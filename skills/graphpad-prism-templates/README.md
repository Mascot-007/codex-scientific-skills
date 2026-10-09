# Prism 模板自动化

检索 129 个本地模板并生成 Prism 原生脚本。

## 安装与调用

复制整个目录到你的 Codex skills 目录，或在 discovery SKILL.md 中路由到完整包。使用 `$graphpad-prism-templates`，同时提供数据/参考图及目标输出。

## 依赖和边界

合法授权 Prism、用户自行获得的模板；仓库不含模板或图册。

完整操作规则见 [SKILL.md](SKILL.md)。不包含用户实验数据、软件安装程序或凭据。

```powershell
python scripts/prism_job.py prepare --id 3 --template-root C:\Templates --out C:\Figures\prism-01
python scripts/prism_job.py run C:\Figures\prism-01\job.pzc --exe "C:\Program Files\GraphPad\Prism 8\prism.exe"
```
