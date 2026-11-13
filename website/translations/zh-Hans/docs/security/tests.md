---
title: 测试
description: InvenTag 如何测试：测试套件覆盖什么、无法证明什么、如何运行，以及 CI 在哪些 Python 版本上运行它。
sidebar_position: 2
---

# 测试

**适合谁阅读：** 正在判断该在多大程度上信任 InvenTag 的人，以及要修改代码的人。

**读完后你会了解：** 测试覆盖什么、不覆盖什么，以及如何自己运行它们。

## 运行什么，在哪里运行 {#what-runs-and-where}

测试套件共有 1,389 个测试（加上九个基准测试为 1,398 个）。没有一个调用真实的
AWS：需要 AWS 的测试使用 [moto](https://github.com/getmoto/moto)（它在内存中模拟 AWS）或模拟客户端，并使用假凭证。
测试离线运行，不产生费用。
九个性能基准测试不在常规运行之内，只有在你要求时才会启动。

CI 在每次推送到 `main` 或 `develop`、以及每个指向 `main` 的拉取请求时，都会在 Python 3.11、3.12、3.13、3.14 和 3.15 上运行测试套件，
外加 lint、集成和基础安全作业。

**没有任何测试针对真实的 AWS 账户运行。** 凡是结果取决于真实 AWS 行为的地方，
[功能状态](../getting-started/status.md)都会说明。

## 每项功能用什么测试 {#what-each-feature-is-tested-with}

每一行都是针对模拟的 AWS（moto）离线检查的，Google 相关的行则针对模拟的 Google 客户端。
moto 的 Resource Groups Tagging API 是 ARN 和标签的参照。

| 功能 | 测试 |
|---|---|
| 一个或多个账户中的资源，在报告和运行摘要中点名失败的账户 | `tests/integration/test_status_validation.py`, `tests/unit/test_cli_security.py` |
| Excel 和 Word 报告，稳定的工作表和行顺序，标签列 | `tests/integration/test_status_validation.py`, `tests/test_bom_converter.py` |
| 报告模板、标签策略检查、退出码 3 | `tests/integration/test_status_validation.py`, `tests/unit/templating/` |
| 每条路径上的过滤条件（`--account-regions`、`--account-services`、`--account-tags`） | `tests/integration/test_status_validation.py`, `tests/unit/test_global_services.py` |
| 每个服务真实的 ARN 和标签匹配，无重复 | `tests/unit/test_arn_and_tags.py` |
| 仅 `eu-west-1`、所有区域，以及包含 `us-east-1` 的列表下的全局服务 | `tests/unit/test_global_services.py` |
| 网络和安全工作表，`--risk-threshold`（退出码 4） | `tests/integration/test_status_validation.py` |
| `--enable-cost-analysis` 及其工作表 | `tests/integration/test_status_validation.py` |
| `--per-account-reports`、`--accounts-prompt`、`--credential-timeout`、`--disable-account-logging` | `tests/integration/test_status_validation.py` |
| `--bom-config` 警告、不发出 AWS 调用的 `--validate-config-only`、每个被拒绝的服务一条警告 | `tests/integration/test_status_validation.py` |
| 两次运行之间的变更报告、快照 | `tests/integration/test_status_validation.py`, `tests/unit/test_changelog_generator.py` |
| 只读防护、审计、`--validate-operations`、S3 上传、私有文件 | `tests/unit/test_cli_security.py`, `tests/unit/test_security_read_only_guard.py` |
| 机密的遮蔽，包括 Google 机密 | `tests/unit/test_security_redaction.py`, `tests/unit/test_google_output.py` |
| Google Sheets 和 Docs 输出（模拟的 Google 客户端） | `tests/unit/test_google_output.py` |

## 自己运行测试 {#run-the-tests-yourself}

```bash title="Terminal"
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

用 `pytest -m performance` 运行基准测试。搭建完整的开发环境：
[参与贡献 InvenTag](../development/CONTRIBUTING.md)。

## 还检查什么 {#what-else-is-checked}

- **文档网站**在 CI 中构建。遇到失效链接时构建会失败，并且会对构建出的页面运行无障碍检查。
- **依赖项**会被扫描已知漏洞。参见[安全](./index.md#how-dependencies-are-checked)和
  [软件物料清单](./sbom.md)。
