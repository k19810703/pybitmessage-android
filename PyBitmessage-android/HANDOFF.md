# 交接单 · 2026-11-20 09:10

> 目的：新 session 从这份文档直接接着干，不用回翻对话。
> 除非特别说明，命令都在仓库根 `for_shizong/` 下执行，adb 用
> `~/Documents/platform-tools/adb`。
> 详细调查证据见 `EVIDENCE.md` §1.24–§1.26。

---

## 0. 当前阶段（每次只做一个阶段，做完就更新这里）

**正在做：M4.1 前台服务**（MILESTONES §7.1，拆成 a/b/c/d 四步）

| 步骤 | 内容 | 状态 |
|---|---|---|
| M4.1a | `src/core_service.py` 服务入口 | ✅ **完成**（CI 已出包） |
| M4.1b | `buildozer.spec` 声明 `services=` | ✅ **完成，aapt2 已验证**：manifest 含 `ServicePybitmessagesvc` + `android:process=":service_pybitmessagesvc"` |
| M4.1c | 前台服务所需的权限（`FOREGROUND_SERVICE` / `POST_NOTIFICATIONS`） | ✅ **完成**，run 44659795746，aapt2 已确认 |
| M4.1d | 设备验证 | ❌ 失败：服务从未启动（EVIDENCE §1.29） |
| **M4.1e** | **启动时拉起服务** | ✅ **通过**（EVIDENCE §1.30）：`:service_pybitmessagesvc` 进程在、`isForeground=true`、退后台仍存活 |

> **M4.1 阶段完成**（a/b/c/e ✅，d 失败由 e 修复）

**M4.1e 的三个坑（下一阶段遇到同类问题直接看这里）**：

1. **服务类名**：p4a 按 `services = 名字:入口` 生成 `<包名>.Service<首字母大写名字>`
   → `at.bitmessage.pybitmessage.ServicePybitmessagesvc`，**不是** `org.kivy.android.PythonService`
2. **`serviceStartAsForeground="true"` 必传**：`PythonService.java:82` 对它调 `.equals()`，
   缺了就 NullPointerException
3. **jnius 的 `putExtra` 重载陷阱**：Python `str` 会绑到 `(String, CharSequence)`，
   `Bundle.getString()` 取不到。**key 和 value 都要包成 `java.lang.String`**
4. 另外 `nativeStart()` 的 7 个参数（含 `androidArgument`/`pythonName`/`pythonHome`/`pythonPath`）
   任何一个为 null 都会 JNI abort

**设计取舍（勿混淆）**：M4.1 只解决「进程不被杀」。**不要**把 Bitmessage 核心搬进
service 进程——两个进程会争单实例锁和同一份数据文件，这件事留到 M4.3 之后单独评估。

---

## 1. 一句话状态

**M2 完成、G3 公网版达成（2026-11-19 20:30）：Mac 脚本节点 ↔ 平板 App 经公网双向加密消息 + 双向回执全部闭环。当前推进 M4（后台与持久化），第一站 M4.1 前台服务。**

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

## 3. 公网消息：已闭环（2026-11-19 20:30，EVIDENCE §1.26）

**达成**：Mac 节点 ↔ 平板 App（同一家庭 Wi-Fi，各自连公网节点）双向加密消息 + 双向 ack
全部送达。`Too many connections from your IP` 是**瞬时状态**（节点侧残留半死连接时的
dup-IP 检查），重试抽签几分钟内自然穿透（同节点 19:46 拒、19:47 即接受），**非阻塞**。

**本轮修复**（已入 git，热补丁已在设备验证；正式包需 CI 出包）：

| 文件 | 修复 |
|---|---|
| `src/network/dandelion.py` | `removeHash()` 的 `ord()` py3 bug——**InvThread 死亡、对象永不广播的真凶** |
| `src/api.py` | `sendMessage`/`sendBroadcast` 用 `_decode_text`（修 bytes repr 乱码） |
| `scripts/pubnet_ctl.py` | Binary 切片 + socket 超时 |
| `scripts/pubnet_tablet_setup.sh` | adb 引号 |

**注意**：平板当前跑的是**热补丁版**（dandelion.py、api.py 直接推进 `files/app/`），
下次出包装机自然替换；热补丁方法见 AGENTS §6.7。平板 keys.dat 现为 `dandelion = 0`。

**仍未修的观察项 → 已全部收编为 MILESTONES §7.0 的 M4.8.x 任务**（2026-11-20）：

| 观察项 | 任务 ID |
|---|---|
| `singleCleaner` memoryview 崩溃（knownnodes 不落盘） | **M4.8.1** |
| `skipUntil` 吞 getdata（消息发出去永不送达） | **M4.8.2** |
| SIGTERM 优雅关闭挂死 + 陈旧单实例锁 | **M4.8.3** |
| `networkConnections` 计数失真 | **M4.8.4** |
| 平板 `doingmsgpow` 偶发卡 5 分钟 | **M4.8.5** |
| MIUI 锁屏冻结 App（**演示必须亮屏**：`svc power stayon usb`） | M4.1 + M4.3 + 风险 R12 |

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

1. **推送本轮修复 + CI 出包 + 装机复验**（dandelion/api 修复的正式包替代热补丁）
2. 平板 UI 实测中文收发（API 路径已证明；UI 路径拍照留证）
3. 修 `class_singleCleaner` 的 memoryview/str 崩溃（knownnodes 落盘依赖它）
4. MIUI 保活（锁屏冻结问题，M4 范畴；演示先用 `svc power stayon usb`）
5. 查 doingmsgpow 卡 5 分钟的问题
6. 平板横屏适配（`KIVY_ORIENTATION=Portrait` 写死）；UI 补发送进度中文化

**演示口径**：两台设备（任意网络）↔ 互发加密消息已全链路可用；同 Wi-Fi 直连低难度
（秒级）和公网（分钟级）两条路都验证过。
