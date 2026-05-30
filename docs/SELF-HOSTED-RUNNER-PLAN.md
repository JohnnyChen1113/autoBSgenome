# Self-hosted Runner 部署计划

Created: 2026-04-12
Status: 待执行（本月云端额度用完后）

## 为什么需要

GitHub Actions 免费额度 2,000 min/月（按用户算，所有仓库共享）。当前 batch-build 每 30 分钟跑一批，每天消耗 ~3,700 分钟，不到一天就用完。Self-hosted runner 在自己的机器上执行 workflow，**不消耗云端分钟数**。

## 前提条件

- 一台长期在线的机器（实验室服务器推荐，Mac 也行）
- Docker 已安装（构建 BSgenome 需要 R Docker 镜像）
- 网络能访问 GitHub

## 设置步骤

### 1. 获取 Registration Token

去仓库 Settings → Actions → Runners → New self-hosted runner

或用 CLI：
```bash
gh api repos/JohnnyChen1113/autoBSgenome/actions/runners/registration-token --method POST --jq '.token'
```

### 2. 下载并配置 Runner

**Linux (实验室服务器)：**
```bash
mkdir ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64-2.322.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.322.0/actions-runner-linux-x64-2.322.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.322.0.tar.gz

./config.sh --url https://github.com/JohnnyChen1113/autoBSgenome --token <TOKEN>
# Name: 随便取，如 lab-server
# Labels: 默认即可（self-hosted, Linux, X64）
# Work folder: 默认 _work
```

**macOS (Apple Silicon)：**
```bash
mkdir ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-osx-arm64-2.322.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.322.0/actions-runner-osx-arm64-2.322.0.tar.gz
tar xzf ./actions-runner-osx-arm64-2.322.0.tar.gz

./config.sh --url https://github.com/JohnnyChen1113/autoBSgenome --token <TOKEN>
```

### 3. 安装为系统服务（后台常驻）

```bash
# Linux
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status

# macOS
./svc.sh install
./svc.sh start
```

### 4. 安装 Docker（如果没有）

```bash
# Linux (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# macOS
brew install --cask docker
# 打开 Docker Desktop
```

### 5. 修改 Workflow 使用 self-hosted

修改 `.github/workflows/batch-build.yml`：
```yaml
jobs:
  build-batch:
    runs-on: self-hosted   # 原来是 ubuntu-latest
```

修改 `.github/workflows/build-bsgenome.yml`：
```yaml
jobs:
  build:
    runs-on: self-hosted   # 原来是 ubuntu-latest
```

### 6. 验证

```bash
# 检查 runner 状态
gh api repos/JohnnyChen1113/autoBSgenome/actions/runners --jq '.runners[] | "\(.name) \(.status)"'

# 手动触发一次测试
gh workflow run batch-build.yml --repo JohnnyChen1113/autoBSgenome

# 查看运行结果
gh run list --repo JohnnyChen1113/autoBSgenome --workflow batch-build.yml --limit 3
```

## 可以提速

Self-hosted runner 没有分钟数限制，可以：
- cron 改成 `*/15 * * * *`（每 15 分钟）
- batch_size 改成 20-30
- 预计 3-4 天跑完所有 ~2,660 个 pending

## 管理命令

```bash
# 启动/停止/重启
sudo ./svc.sh start
sudo ./svc.sh stop
sudo ./svc.sh status

# 卸载
sudo ./svc.sh uninstall

# 从 GitHub 移除
./config.sh remove --token <TOKEN>
```

## 安全注意

- Self-hosted runner 会在你的机器上执行任意代码（来自 workflow 文件）
- 因为是你自己的 private repo，风险很低
- 不要给 public repo 用 self-hosted runner（别人的 PR 可以执行代码）
