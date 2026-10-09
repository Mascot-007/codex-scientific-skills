# Biacore 文件修复

修复特定跨编码环境下 .bme/.blr XML 和浓度单位问题。

## 安装与调用

复制整个目录到你的 Codex skills 目录，或在 discovery SKILL.md 中路由到完整包。使用 `$biacore-bme-repair`，同时提供数据/参考图及目标输出。

## 依赖和边界

Python、olefile；仅针对说明中的已确认故障，必须保留备份。

完整操作规则见 [SKILL.md](SKILL.md)。不包含用户实验数据、软件安装程序或凭据。
