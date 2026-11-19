# 交接单 · 2026-11-19 14:25

> 目的：新 session 从这份文档直接接着干，不用回翻对话。
> 除非特别说明，命令都在仓库根 `for_shizong/` 下执行，adb 用
> `~/Documents/platform-tools/adb`。
> 详细调查证据见 `EVIDENCE.md` §1.24。

---

## 1. 一句话状态

**协议、加密、C-PoW、中文 UI、TLS 全部打通；当前唯一卡点收窄为：所有公网种子在 version 交换后回 `error: 2 "Too many connections from your IP"`（对端主动拒绝），TCP 层本身能通。已定位到一个上游 addConnection 混合键型 bug 作为头号嫌疑。**

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

## 3. 当前卡点（公网连接被种子拒绝）

**现象**（桌面对照节点 `/tmp/desk_control.py`，只保留 Mac 一个节点在发连接）：

```
TCP connect 成功 → version 交换正常（ver=3 streams=[1]）→ 我们发 verack
→ 对端回 error: 2, "Too many connections from your IP. Closing connection."
→ 断开 → ~90s 后重连 → 循环
对 4 个活节点全部复现：85.114.135.102 / 194.164.163.84 /
                       185.158.248.216:8444 / 158.69.63.42:8080
```

**已确认的事实**（详见 EVIDENCE.md §1.24）：

1. 旧 APK 的 `Timeout (20s)` 症状 = TLS Purpose bug，**已修**（commit `008b9cb`，run 44464696554），新包未再出现
2. "Too many connections from your IP" 是**对端（种子）发的 error 消息**，不是本端关闭
3. **UDP 层与种子完全正常**（verack/addr 每 60s 一轮）——之前日志里的 `established=True` 全是 UDP 伪连接，不是 TCP
4. **TCP 层能长期保持**（ESTABLISHED 3 分钟+），断开发生在协议层
5. 新装 App 的 knownnodes 只有 9 个 2017 死节点 → 出站永远 SYN_SENT；DNS bootstrap 每进程只跑一次（`knownNodesActual` 逻辑）
6. **头号嫌疑（代码级）**：`connectionpool.py addConnection()` 入站连接用混合键型——同一 IP 第一条按 `host 字符串` 存、第二条按 `Peer` 存；而 `peerValidityChecks()` 的 dup-IP 检查用 Peer 查找，且连接 accept 时就入池、version 解析后才检查 → **同一 IP 的第二条并发连接会查到它自己而被拒**。种子跑的同款 0.6.3.2 代码。两台设备 + 宿主节点共享出口 IP、maxoutboundconnections=2 都会触发
7. 疑点未消：实验里**单连接**也被拒（对照节点 v1/v2 都复现），可能是 IP 级临时 ban（上午旧 APK 重连循环轰炸了种子几小时）

**下一步动作（建议顺序）**：

1. **换 IP 测试**（手机热点给平板或 Mac）：新 IP 上第一条连接若能建立并稳住 → IP 级状态问题；若仍被拒 → 我们握手内容有问题，抓包比对
2. 本机 `maxoutboundconnections=1` + 单节点重试（验证混合键型理论：单连接应能过检查）
3. 通过后：设备注入互不相同的活节点 + maxout=1 → 验证公网收发闭环
4. 修 `class_singleCleaner` 的 memoryview/str 崩溃（崩了导致学到的节点永不落盘）

---

## 4. 环境清单（写文档时的真实状态）

### 仓库

```
branch : android-port
HEAD   : 24aca55 + 本地未推送 commit（M3.8 打点加 host:port，纯日志改动）
remote : git@github.com:k19810703/pybitmessage-android.git
最新CI : run 44464696554（TLS 修复包，11m07s，✅）
```

### 设备（2026-11-19 14:20 快照）

| 设备 | 状态 | 说明 |
|---|---|---|
| 小米平板 5（`b45f8e87`） | **用户已断开** | 已装 TLS 修复包（个钥重签，`scripts/resign-apk.sh`）。**数据已重置**：地址变了（未记录，开机后用 `listAddresses` 查），**API 未配置**（fresh keys.dat，需重新注入 apienabled 等，注意写到 `[bitmessagesettings]` 段、不能与已有键重复，configparser 严格模式会崩） |
| 模拟器 Pixel 6 | **已关闭**（`adb emu kill`） | TLS 修复包（CI 原签）。地址 `BM-2cUZuPZeG4Sa6vknoq9HY64AmJrRQR4CJT`，API 已配好（u:p@8442），maxoutboundconnections=2 |

> 重新装包参考：`/tmp/apk-tls/pybitmessage-apk-25/pybitmessage-0.1.2-arm64-v8a-debug.apk`（个钥签，/tmp 可能被清，重下 run 44464696554）。
> 平板换包用 `pm install -r -d`；以后都走个钥签，可免卸载升级。

### 本机进程（已全部清理）

- 桌面对照节点 `/tmp/desk_control.py` — **已 kill**（脚本保留在 /tmp，可能被清；核心逻辑：BITMESSAGE_HOME=/tmp/deskctl、TLS 开、knownnodes 写死活节点 rating=1、API 8451、`Main.daemonize = lambda self: None` 后跑 `bitmessagemain.main()`）
- 旧 node1（/tmp/run_node.py）、两个周二遗留 kivy 进程 — **已 kill**
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
| 公网种子回 "Too many connections from your IP" | 见 §3：疑似 addConnection 混合键型 bug + 同 IP 并发连接 + 上午轰炸残留 | §3 下一步 1/2 |
| 对端回 `Your time is too far in the past` | 模拟器时钟漂移 | `adb root && adb shell "date -s @$(date +%s)"` |
| 所有节点连不上 | 默认 knownnodes 是 2017 年的死节点 | 写入活节点（见 §3 列表）；注意 DNS bootstrap 每进程只跑一次 |
| 日志里 `recv addr established=True` | **是 UDP 伪连接，不是 TCP 建立** | 判断 TCP 要看 `TCP established: host:port` 打点 |

---

## 8. 建议的下一步（按价值排序）

1. **公网连接**（§3 下一步 1/2）：换 IP（手机热点）测试 + `maxoutboundconnections=1` 单连接测试
2. 修 `class_singleCleaner` 的 memoryview/str 崩溃（knownnodes 落盘依赖它）
3. 推送本地 commit（M3.8 打点）并按需出包
4. 平板横屏适配（`p4a_env_vars.txt` 里 `KIVY_ORIENTATION=Portrait` 写死，平板上是竖屏 letterbox）
5. UI 补发送进度（把 `doingpubkeypow/awaitingpubkey/msgsent` 映射成中文）

**如果演示时间紧**：两台设备连同一 Wi-Fi，直接互连（不依赖公网种子），这条路已经验证能通，`extralowdifficulty=true` 时秒级。
