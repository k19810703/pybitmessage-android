# 交接单 · 2026-11-19 15:45

> 目的：新 session 从这份文档直接接着干，不用回翻对话。
> 除非特别说明，命令都在仓库根 `for_shizong/` 下执行，adb 用
> `~/Documents/platform-tools/adb`。
> 详细调查证据见 `EVIDENCE.md` §1.24/§1.25。

---

## 1. 一句话状态

**公网连接问题已定性：客户端与协议完全正常（平板换热点 IP 后 2 条连接秒建、正常同步对象流）；被拒的是公司出口 IP（今早旧 APK 重连循环轰炸种子的残留，粘性 per-IP 限制）。待办：换 IP（晚上家里）完成双向消息闭环。**

---

## 2. 已经跑通并留下证据的

| # | 能力 | 证据 |
|---|---|---|
| 1 | APK 构建（CI，约 10 分钟） | run 44450937098 / 44446383246 等 |
| 2 | 安装启动、建地址、重启不丢 | `EVIDENCE.md` §1.12 |
| 3 | 连接建立（`fullyEstablished`） | 同上 |
| 4 | **协议层双向加密消息**（两个本地节点，中文+emoji） | §1.17（n2→n1 30s、n1→n2 12s） |
| 5 | 设备 ↔ 宿主节点双向消息（低难度） | §1.21（190s / 20s） |
| 6 | **C 版 PoW**：全难度 **3.9 秒/对象**（平板实测） | §1.22（纯 Python 是 >15 分钟） |
| 7 | **中文收发界面**：我的地址/复制、收件箱（5s 刷新）、收件人、内容、发送 | §1.23 + `artifacts/ui-3.png` |
| 8 | Intent 预填收件人（`--es to BM-…`） | 同上 |

**关键实现**

- `src/bitmessagekivy/messaging.py`：整个演示界面（一个 Screen，纯 Python 构建）
- `src/bitmsghash/shim/`：自带 SHA-512 实现，让 `libbitmsghash.so` 不依赖 NDK 缺失的 openssl 头
- `scripts/build-bitmsghash.sh`：NDK 交叉编译（**必须 `-static-libstdc++`**）
- `android.add_libs_arm64_v8a = libs/arm64-v8a/*.so`（注释不能缩进，否则被当成续行）
- `proofofwork.init()`：Android 上用 `ctypes.CDLL('libbitmsghash.so')`（Android 10+ 禁止从 data 目录 dlopen）

---

## 3. 公网连接：已定性，剩消息闭环（2026-11-19 15:35）

**实验结论**（EVIDENCE.md §1.25）：

| 端 | 出口 IP | 结果 |
|---|---|---|
| 平板（iPhone 热点） | 运营商 NAT | ✅ 2 连接 + 2854 对象下载中 |
| Mac（公司网 9.123.201.63） | IBM 出口 | ❌ 全部种子拒 `Too many connections from your IP`（maxout=1 也拒） |

- **客户端/协议/TLS 无问题**；被拒的是 IP（今早旧 APK 30s/轮 × 数小时的轰炸残留）
- "同 IP 并发连接"混合键型假设**已被排除为唯一原因**（单连接也被拒）
- 拒绝时长未知；测试工具链全部就绪（见 §4 脚本）

**下一步（晚上家里，全新出口 IP）**：

1. Mac 和平板都连家里网络 → 跑 `scripts/PUBNET-TEST.md` 的 runbook
2. Mac：`./scripts/pubnet_node.py` + `wait-conn`（家里 IP 干净应秒连）+ `create mac-test`
3. 平板：已配置完毕（API u:p@8442、maxout=2、knownnodes=4 活节点、地址 `BM-2cU2vEDgphdWHe4Ucp1gSigCwDrJTRfyYV`），重连 USB 后 `adb forward tcp:8445 tcp:8442` 直接查状态即可；App 卡住就 force-stop 重启等 90s
4. 双向消息（`pubnet_ctl.py send` / 平板 UI），预期 5-15 分钟
5. **注意**：如果家里 IP 也被拒 → 说明拒绝按"客户端指纹"而非 IP（那就真要抓包了）；但热点实验已证明新 IP 可连，大概率是 IP 维度

**备用方案**（家里 IP 万一也不行）：Mac 经 `adb forward tcp:18444 tcp:8444` 直连平板节点（USB 桥，已见 verack 回包未验证完）；或两台设备各连不同热点直接对发。

---

## 4. 环境清单（写文档时的真实状态）

### 仓库

```
branch : android-port
HEAD   : 91ffe30（测试工具链）+ 本次文档提交；均未推送
remote : git@github.com:k19810703/pybitmessage-android.git
最新CI : run 44464696554（TLS 修复包，11m07s，✅）
```

### 设备（2026-11-19 15:45 快照）

| 设备 | 状态 | 说明 |
|---|---|---|
| 小米平板 5（`b45f8e87`） | **配置完毕，等晚上家里网络** | TLS 修复包（个钥签）+ API 已配（u:p@8442）+ maxout=2 + knownnodes=4 活节点；地址 `BM-2cU2vEDgphdWHe4Ucp1gSigCwDrJTRfyYV`（label `phone`）。热点实验已证明公网可连（2 连接 + 2854 对象）。回家切 Wi-Fi 后 App 自动重连；查状态需 USB 重连 + `adb forward tcp:8445 tcp:8442`；App 卡住就 force-stop 重启等 90s |
| 模拟器 Pixel 6 | 已关闭（`adb emu kill`） | 不再需要：Mac 脚本节点替代了它的角色 |

### 公网测试工具链（全部提交在 `scripts/`，已实测）

| 脚本 | 作用 |
|---|---|
| `scripts/pubnet_node.py` | Mac 无头节点（TLS 开、活节点 knownnodes、API 8451、默认 maxout=1） |
| `scripts/pubnet_ctl.py` | API 客户端：status/wait-conn/addresses/create/send/inbox/sent（`--port 8445` 操控平板） |
| `scripts/pubnet_tablet_setup.sh` | 平板一键配置（含引号修复，实测通过；平板已配置过，勿重复跑除非重置） |
| `scripts/build-bitmsghash-native.sh` | 本机 C PoW（已编译好 `src/bitmsghash/bitmsghash.so`；.gitignore 不入库，换机器要重跑） |
| `scripts/PUBNET-TEST.md` | 完整 runbook（含晚上家里的流程） |

### 本机进程（已全部清理）

- pubnet 节点、冒烟测试节点 — **已 kill**
- 旧 node1（/tmp/run_node.py）、周二遗留 kivy 进程 — **已 kill**
- ⚠️ pid 28249（`python3 -`，cwd `/private/tmp/bmtest`，~200% CPU，无网络）是更早 session 的测试残留，未动，可 kill

### 仓库里的脚本（持久保留）

| 路径 | 作用 |
|---|---|
| `scripts/build-bitmsghash.sh` | 交叉编译 `libbitmsghash.so` |
| `scripts/enable-low-pow.sh` | 开关 `extralowdifficulty` |
| `scripts/resign-apk.sh` | 个钥重签，免卸载升级（keystore 在 `~/.pybitmessage-android/`） |

---

## 5. 关键代码改动索引（都已在 git 里）

| 文件 | 改动 |
|---|---|
| `src/bitmessagekivy/messaging.py` | **新增**：中文收发界面 |
| `src/bitmessagekivy/mpybit.py` | 注册并默认进入 messaging 屏 |
| `src/main.py` | TLS 默认开启（`BITMESSAGE_DISABLE_TLS=1` 关闭）；不再默认低难度 |
| `src/network/tls.py` | **修 bug**：`ssl.Purpose` 客户端/服务端反了 |
| `src/network/bmproto.py` | **打点**：BMPROTO 握手日志带 peer host:port（本地未推送 commit，区分 UDP/TCP 连接的关键） |
| `src/proofofwork.py` | Android 从 APK lib 目录加载 `libbitmsghash.so`；`LogOutput` 容忍无 `fileno` |
| `src/bitmsghash/shim/**` | **新增**：自足 SHA-512（与 hashlib 三组向量一致） |
| `src/class_objectProcessor.py` | pubkey 重发窗口可配（`pubkeyresendwindow`，默认 1h，上游是 28 天） |
| `src/class_singleWorker.py` | `awaitingpubkey` 重试上限 30 分钟（上游是 TTL×1.1 ≈ 2.7 天） |
| `packages/android/buildozer.spec` | `android.add_libs_arm64_v8a` |
| `.github/workflows/android-apk.yml` | 构建前编译 C PoW 库 |

**累计修掉的 py3 兼容问题约 20 处**（str/bytes、`string.find`、`str.rstrip('\x00')` 等），明细见 `EVIDENCE.md` §1.12–§1.22。

---

## 6. 新 session 怎么快速重建环境

```bash
# 0) 设备
~/Documents/platform-tools/adb devices -l          # 期望看到 b45f8e87 / emulator-5554

# 1) 装最新 APK（平板用 pm install，adb install 会被 MIUI 拦）
gh run list --repo k19810703/pybitmessage-android --limit 1
gh run download --repo k19810703/pybitmessage-android \
  -n pybitmessage-apk-<N> -D /tmp/apk
adb -s emulator-5554 install /tmp/apk/*.apk
adb -s b45f8e87 push /tmp/apk/*.apk /data/local/tmp/bm.apk
adb -s b45f8e87 shell pm install -r -d /data/local/tmp/bm.apk

# 2) 开 API + 端口转发
adb -s emulator-5554 forward tcp:8442 tcp:8442
adb -s b45f8e87 forward tcp:8445 tcp:8442

# 3) 查地址/连接
python3 - <<'PY'
import base64, xmlrpc.client
class T(xmlrpc.client.Transport):
    def send_headers(self, c, h):
        h.append(('Authorization', 'Basic ' + base64.b64encode(b'u:p').decode())); super().send_headers(c, h)
for name, port in (('tablet', 8445), ('emulator', 8442)):
    n = xmlrpc.client.ServerProxy('http://127.0.0.1:%d/' % port, transport=T(), allow_none=True)
    print(name, n.listAddresses()['addresses'], n.clientStatus()['networkConnections'])
PY
```

### 重建桌面对照节点（公网连接实验）

```bash
# /tmp/desk_control.py 可能被清，按此重建（关键点都在）：
#   - BITMESSAGE_HOME=/tmp/deskctl（先 mkdir）
#   - state.kivy=True、state.disable_tls=False（与 APK 一致）
#   - knownnodes.dat 写活节点 + rating=1（chooser 立即选中）：
#     85.114.135.102:8444 / 194.164.163.84:8444 /
#     185.158.248.216:8444 / 158.69.63.42:8080
#   - config: daemon=true、apiport=8451（避开 adb forward 的 8442）、
#     maxoutboundconnections=2、dandelion=0
#   - bitmessagemain.Main.daemonize = lambda self: None（防 fork 后丢日志）
#   - bitmessagemain.main()
# 运行：nohup python3 -u /tmp/desk_control.py > /tmp/deskctl.out 2>&1 &
# 看：grep BMPROTO /tmp/deskctl.out（打点已带 host:port，本地未推送 commit）
```

### 重建本地双节点（用于验证协议层，不依赖公网）

```bash
# /tmp/node_common.py 的内容见 git 历史或按 AGENTS §6.7 的思路重建：
# 关键点：state.kivy=True、state.disable_tls=True、daemon=true、
#        alias_core_modules()、if __name__ == '__main__' 保护、
#        config.set('network','dandelion','0')、maxoutboundconnections=1
cd /tmp && (BITMESSAGE_LOG_LEVEL=INFO python3 -u /tmp/run_node.py > /tmp/node1.out 2>&1 &)
```

### 给设备注入 API 配置（注意！）

```bash
# 1) API 键在 [bitmessagesettings] 段，不是 [api] 段
# 2) 原 keys.dat 已有 apiinterface/apiport，重复注入会 DuplicateOptionError 崩启动
#    → 注入前先去重（本 session 踩过，见 EVIDENCE.md §1.24）
# 3) 路径是 files/bitmessage/keys.dat（不是 files/keys.dat）
```

---

## 7. 已知坑（都会浪费时间，先看这里）

| 现象 | 原因 | 对策 |
|---|---|---|
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 每次 CI 构建签名不同 | 先卸载，或 `scripts/resign-apk.sh` 重签（个钥在 `~/.pybitmessage-android/`，12:34 前装的包是 CI 原签，升级需先卸载一次） |
| MIUI 报 `INSTALL_FAILED_USER_RESTRICTED` | HyperOS 拦 `adb install` | `adb push` + `pm install -r -d` |
| API 打到 8442 却操作到别的节点 | 宿主节点也占了 8442 | 宿主 API 必须换端口（8451/38681 都用过），设备用 8445 |
| 平板 App 有时没有 API、也没日志 | 疑似启动早期卡住 | `am force-stop` 后重新 `am start`，等 90s 再查 |
| `THREAD-CRASH singleCleaner: memoryview ... not 'str'` | `class_singleCleaner` 还有 py3 字节问题（未修） | 不影响收发，但导致 knownnodes 永不落盘，应修 |
| 启动崩 `DuplicateOptionError ... keys.dat` | 注入的 API 键与已有键重复（configparser 严格模式） | 注入前去重，键放 `[bitmessagesettings]` 段 |
| 公网种子回 "Too many connections from your IP" | **已定性（EVIDENCE §1.25）**：出口 IP 粘性拒绝，今早轰炸残留；客户端无问题（热点 IP 秒连） | 换 IP；或等解封（时长未知） |
| 对端回 `Your time is too far in the past` | 模拟器时钟漂移 | `adb root && adb shell "date -s @$(date +%s)"` |
| 所有节点连不上 | 默认 knownnodes 是 2017 年的死节点 | 写入活节点（见 §3 列表）；注意 DNS bootstrap 每进程只跑一次 |
| 日志里 `recv addr established=True` | **是 UDP 伪连接，不是 TCP 建立** | 判断 TCP 要看 `TCP established: host:port` 打点 |

---

## 8. 建议的下一步（按价值排序）

1. **晚上家里（新 IP）跑 `scripts/PUBNET-TEST.md`**：Mac 节点连接 + 平板状态确认 + 双向消息闭环（G3 公网版）
2. 消息闭环通过后：推送本地 commits、更新 MILESTONES/EVIDENCE、考虑给设备默认注入活节点（避免 fresh install 的 2017 死节点 SYN_SENT 问题进产品）
3. 修 `class_singleCleaner` 的 memoryview/str 崩溃（knownnodes 落盘依赖它）
4. 平板横屏适配（`p4a_env_vars.txt` 里 `KIVY_ORIENTATION=Portrait` 写死，平板上是竖屏 letterbox）
5. UI 补发送进度（把 `doingpubkeypow/awaitingpubkey/msgsent` 映射成中文）

**如果演示时间紧**：两台设备连同一 Wi-Fi，直接互连（不依赖公网种子），这条路已经验证能通，`extralowdifficulty=true` 时秒级；或两台设备各连不同手机热点走公网（热点实验已证明可行）。
