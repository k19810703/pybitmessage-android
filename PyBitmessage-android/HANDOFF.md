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
>
> **M4.3 进行中**：wake lock ✅ 已生效并在正式包上验证（EVIDENCE §1.34）；
> 待做：D5 完整验收（锁屏 30 分钟 + 期间收到消息）。

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

## 6.0 ✅ 收工快照（2026-11-23 21:05）—— **新 session 从这里开始**

### 今天（11-23）的完整成果

| # | 成果 | 证据 |
|---|---|---|
| 1 | **M4.5.1** allowBackup=false | EVIDENCE §1.40 |
| 2 | **M4.8.1** singleCleaner 不再崩 | §1.42（0 崩溃 + flush 正常） |
| 3 | **M4.8.2b** 下载停摆修复（anti-intersection 窗口限频） | §1.43 |
| 4 | **M6 一期** 抽屉菜单全中文 + 图标正常 | §1.47 |
| 5 | **M6 二期** Sent/Draft/Trash/AllMails 四页面数据 + 状态中文化（含 M3.9.4） | §1.48 |
| 6 | **M4.8.7** 中文消息静默丢弃修复（UTF-8 字节长度） | §1.49 |
| 7 | **7 条被丢弃消息全部恢复** | §1.50 |
| 8 | **端到端实测**：中文消息 23 秒送达 | §1.50（20:58 实测） |

### 平板最终状态

```
包    : ~/Documents/pybitmessage-apk/pybitmessage-0.1.2-20261123-m487.apk
       （sha256 814cbe2b...，run 45141802772，含全部 8 项修复，零热补丁）
收件箱: 11 条（含 20:58 端到端实测消息）
地址  : BM-2cXrmLDcoGry6Z4kRWqCthD7kuhRxkzaWx（+ BM-2cWGibweLdxrU...）
私钥备份: /tmp/bk_keys_487.dat（重启会丢；重要的话导入其他设备）
```

### Mac 清理状态（21:05 执行）

- pubnet_node.py 测试节点：**已停止**
- adb forward：**已清空**
- 无其他测试进程残留
- 测试数据 /tmp/pubnet、备份 /tmp/bk_*.dat 等：**保留未删**（重启自动清空；
  正式备份位置见上）

### 新 session 下一步（按优先级）

0. ~~**M4.2.1** 通知权限~~ → **代码已完成**（commit `01e8892`，EVIDENCE §1.51，CI run 45298351539）：
   运行时申请 + 新消息通知。**只差装机验收**（见 §6.0c）
1. **D5 验收**：锁屏 30 分钟 + 期间收到消息（前台服务 + WakeLock 已就位）
2. M4.8.3/4/5：SIGTERM 关闭挂死、networkConnections 计数失真、doingmsgpow 偶发卡顿
3. M5 交付：README-ANDROID、回归 D1–D7、最终包 + SHA256
4. M6 收尾：搜索框 "Search" 硬编码英文等小项
5. 平板横屏适配（KIVY_ORIENTATION=Portrait 写死）

### 消息收发状态总结（用户关心的问题的最终答案）

- **中文收发**：✅ 已修复并实测（23 秒送达）
- **发给 sjy**：一条已确认，一条在网（TTL 至 11-27，等他上线）
- **11-19 的两条**：已丢失（TTL 过期 + 旧地址私钥丢失）

---

## 6.0c 🔜 待装机验收：M4.2.1 通知权限 + 新消息通知（2026-11-24 08:45）

**代码**：`src/android_notify.py`（新增）+ `src/main.py` 挂接，commit `01e8892`。
**包**：`/tmp/pybitmessage-m421-2026-11-24.apk`（run 45298351539 artifact `pybitmessage-apk-55`，
已用 `scripts/resign-apk.sh` 个钥重签，sha256 `234559e9...cd7124`，可直接覆盖安装）。
**前置**：设备 USB 连上（`adb devices` 应见 `b45f8e87`）。装包前先备份 keys/messages。

**验收步骤**（S 类，每步截图）：

```bash
ADB=~/Documents/platform-tools/adb; PKG=at.bitmessage.pybitmessage
# 1) 装包 + 启动
$ADB -s b45f8e87 push /tmp/pybitmessage-m421.apk /data/local/tmp/bm.apk
$ADB -s b45f8e87 shell pm install -r -d /data/local/tmp/bm.apk
$ADB -s b45f8e87 logcat -c
$ADB -s b45f8e87 shell am start -n $PKG/org.kivy.android.PythonActivity
sleep 25
# 2) 期望日志
$ADB -s b45f8e87 logcat -d | grep -E "NOTIFY|KEEPALIVE|SERVICE startForeground"
#    → NOTIFY: POST_NOTIFICATIONS requested   （平板是 Android 13，会走 API 33 分支）
#    → NOTIFY: message hook started
# 3) 此时屏幕应弹「允许 PyBitmessage 发送通知？」→ 点允许
# 4) 下拉通知栏：应有前台服务通知「PyBitmessage 正在运行」
$ADB -s b45f8e87 exec-out screencap -p > /tmp/notif-perm.png
# 5) 从 Mac 节点发一条中文消息 → 通知栏出现「新消息 / 主题」
grep -i "NOTIFY: message from" <(logcat)
```

**若被拒授权**：`has_permission()` 返回 False，日志 `NOTIFY: skipped, POST_NOTIFICATIONS not granted`；
App 不崩、收发照常，只是没有通知——**这是通过标准之一，不是失败**。
想重新弹窗需到系统设置里重置该应用的通知权限（Android 13 不会二次自动弹）。

---

## 6.0k ⏸ 2026-11-25 21:40：收工点（今日开发结束）

### 今天最后落定的：连接数为 0 是真 bug，已修并设备验证

| 项 | 结果 |
|---|---|
| 根因 | **TLS 升级卡死**：只要对端 advertise `NODE_SSL` 就必然尝试 2013 年的客户端 TLS 配置，握手永不完成 → `fullyEstablished` 永远 False → `networkConnections=0`（EVIDENCE §1.63） |
| 修复 | TLS 默认关闭（`BITMESSAGE_ENABLE_TLS=1` 可开）、TLS 握手 20s 超时、`process()` 跟进状态移交（commit `c54acea`） |
| 设备验证 | 平板 `networkConnections` **0 → 1→2**、`TCP established` **16**、`tls_init` **0**、自发消息 **`ackreceived`**、收件箱 16→17（EVIDENCE §1.64） |
| 发布页 | `v0.6.3.2` 资产已更新，sha256 `1f496353…186d`；本地 `~/Documents/pybitmessage-apk/pybitmessage-0.6.3.2-m4810-2026-11-25.apk` |

**发送失败**已定性为"连接数为 0 的下游后果"，不是独立故障。

### 用户明确的下一个需求：收件箱邮件可删除

已立项 **M7**（`MILESTONES.md` §6.9），拆成 4 步，**后端全都有、只缺界面**：

- `helper_inbox.trash()/undeleteMessage()/delete()` 已实现
- `api.py` 有 `trashMessage` / `trashInboxMessage` / `deleteAndVacuum`
- 缺的是：主界面 `inbox()` 的 SQL **没带 `msgid`**；回收站页只读
- 顺序：M7.1.1 带 msgid → M7.1.2 软删+确认 → M7.1.3 回收站恢复/彻底删 → M7.1.4 中文化+扫描
- **坑**：`msgid` 是 `blob`（bytes），Kivy 里别当 `str`；`mail_list.load_folder()` 的行同样缺 msgid

### 明天开工建议顺序

1. **M7.1.1–M7.1.4**（用户点名要的，后端已就绪，预计 5h）
2. **M4.8.11**：连接数 0↔2 抖动、出站半开 50+（maxout=8）、`numberOfMessagesProcessed` 长期 0（EVIDENCE §1.64）
3. **M6.5**：删 payment/credits 死代码
4. **G4（用户要求最后做）**：D5 锁屏 30 分钟、C3 电量

### 平板当前状态

```
包     : run 45620481903（含 TLS 修复 + 日志 + 抽屉分享），零热补丁
连接   : 0↔2 抖动（M4.8.11）
收件箱 : 17 条
备份   : /tmp/bk_m67/（keys 1992B、vault 60B、messages 11.5MB、knownnodes 203KB 均已校验非 0）
```

---

## 6.0j ⏸ 2026-11-25 17:00：暂停点（用户回家路上，无网络；**代码已改完，未验证**）

### 这一轮改了什么（commit `6663bc2`，已 push，CI 会出包）

1. **「分享日志」入口从主界面挪到抽屉菜单**（用户反馈：主界面那个 Screen 无法从菜单进入，
   入口放错了）。抽屉最下面新增「分享日志」，调用 `app.share_logs()`。
2. **新增 `src/diag.py`：针对用户最关心的两个问题做定向诊断**
   - **连接数为 0**：每次快照记录 established/outbound/inbound、**逐连接握手状态**
     （est/connected/verack sent/recv/state/idle/close_reason）、knownnodes 数量与
     rating>0 个数、maxoutbound 等关键设置、网络线程是否存活
   - **对端 error 包**：包一层 `bm_command_error`（保存/恢复 `payloadOffset`，不干扰原逻辑），
     把 `Too many connections from your IP` / `time is too far` 这类文本按对端计数入日志
   - **连接数变化即记录**（每 30s 检查，变化就打完整快照），便于还原时间线
   - **发送失败**：发送前 `describe_send()` 记录地址解析结果、**是否已持有对方公钥**、
     历史发送状态；发送后 `watch_sent()` 跟踪
     `awaitingpubkey → doingpubkeypow → doingmsgpow → msgsent → ackreceived` 并打时间戳，
     超时则明确写「这不是已发送，是卡住了」

### 尚未验证（下次设备可用时按顺序做）

1. 出包后装到平板（包名不变、本钥重签）：`gh run list` 取最新 run，`scripts/resign-apk.sh`，`pm install -r -d`
2. 抽屉 → 分享日志：应弹分享面板、zip 落到 `Download/PyBitmessage/`
3. **重点看 `logs/app-*.log` 里的 `[DIAG]` 段**：
   - `[DIAG] 连接 established=… outbound=… inbound=…` → 若 established=0，紧跟着的逐连接表
     和「对端 error 包」就能说明是被拒、DNS 不通、还是根本没发起
   - 发一条消息，看 `发送状态 … -> …` 的时间线与最终状态
4. 把「0 连接」的真实原因按上面证据定性（这轮用户的原始诉求）

### 本地已做过的验证

`python3 -m unittest` 51 条通过；`compileall` 0 错误；`scripts/scan-english.py --strict` 通过
（新增菜单项「分享日志」已进字典）。

---

## 6.0i ⏸ 2026-11-25 14:20：M6 推进中（接设备后第一件事是装包）

### 一口气要做的事（设备一插上）

```bash
ADB=~/Documents/platform-tools/adb
PKG=at.bitmessage.pybitmessage
# 1) 备份并校验大小（拔线会让 exec-out cat 留下 0 字节文件）
$ADB -s b45f8e87 exec-out run-as $PKG cat files/bitmessage/keys.dat > /tmp/keys.bak
ls -l /tmp/keys.bak     # 必须非 0！
# 2) 装含 M6 的包（已构建、已重签）
$ADB -s b45f8e87 push /tmp/pybitmessage-m62-2026-11-25.apk /data/local/tmp/bm.apk
$ADB -s b45f8e87 shell pm install -r -d /data/local/tmp/bm.apk
# 3) 清掉 5 个热补丁（整个 bitmessagekivy 覆盖层直接删）
$ADB -s b45f8e87 shell "run-as $PKG rm -rf files/app/bitmessagekivy"
# 4) 验证：两栏横屏 / 设置页全中文 / 抽屉无「付费方案」
```

### 本轮（M6）已完成并验证的

| 任务 | 状态 |
|---|---|
| M6.3.2 响应式两栏 | ✅ 热补丁验证（平板横屏两栏、竖屏单栏） |
| M6.2.1 全界面中文 | ✅ 可达界面 0 处英文；顺带移除「付费方案」入口 |
| M6.2.3 豆腐块 | ✅ 根因是 MD 组件忽略 `font_name`；把 CJK 注册成 `Roboto` 解决（截断复检未做） |
| M6.4.3 残留扫描 | ✅ `scripts/scan-english.py --strict` 退出码 0 |
| M6.5（新） | ⬜ 删除 payment/credits 死代码（入口已移除，文件还在） |

### 平板当前真实状态（**注意**）

```
包      : 上一版（run 45551686340），**不含** M6 的 UI 改动
热补丁  : 5 个 —— bitmessagekivy/{messaging.py, mpybit.py, kv/chat.kv,
          kv/popup.kv, kv/login.kv, kv/settings.kv}（实际 6 个文件）
数据    : 未动（本轮没装包，只是热补丁）
待装包  : /tmp/pybitmessage-m62-2026-11-25.apk（run 45557518551）
```

### 其余待办（优先级）

1. **装 M6 包 + 清热补丁**（上面那段）
2. M6.5 删除 payment/credits 死代码（15 处英文，纯清理）
3. M6.2.3 逐屏截断复检、M6.3.3 字号缩放、M6.3.4 平板 AVD
4. **G4 闸门（用户要求最后做）**：D5 锁屏 30 分钟、C3 电量 ≤8%/h（M4.7.1）
5. M4.8.4 计数失真、M4.8.5 `doingmsgpow` 偶发卡顿

---

## 6.0h ✅ 2026-11-25 11:50：M5 收口（新 session 从这里开始）

### M5 完成情况

| 任务 | 状态 |
|---|---|
| M5.1.1 图标 + 启动图 | ✅ 设备验证（启动图已替换 Kivy 风筝） |
| M5.1.2 版本号对齐 | ✅ `versionName = softwareVersion = 0.6.3.2` |
| M5.2.1 统一签名 | ✅ 指纹 `82463dfe…c551c7`；CI 可选自动签 |
| M5.3.1 / M5.3.2 文档 | ✅ `README-ANDROID.md` + `INSTALL.md` §2.5 |
| M5.4.1 回归 D1–D7 | ✅ **D1/D2/D3/D4/D6/D7 全绿**（D5 按用户要求跳过） |
| M5.4.2 最终包 | ✅ 发布页 v0.6.3.2，sha256 `10f7b7ef…b82c9` |

**回归数据**：B→A 130s、A→B 30s、重启前后 2 地址/16 消息/4 联系人一致、0 FATAL。
报告：`artifacts/regression-d1d7.md`、原始日志 `artifacts/regression-run.log`。

### 平板当前状态（零热补丁）

```
包     : run 45393594862 的包（本钥重签后 /tmp/pybitmessage-0632-fix-2026-11-25.apk）
         = 发布页 v0.6.3.2 的资产（sha256 10f7b7ef…）
热补丁 : 无
地址   : BM-2cXrmLDcoGry6Z4kRWqCthD7kuhRxkzaWx（phone）
         BM-2cWGibweLdxrUHN2JaLhGiBtekxZAw2ufV（HD）
收件箱 : 16 条    通讯录: 4 条（含本轮回归用的两个 Mac 节点地址，可删）
备份   : /tmp/bk_reg2/{keys.dat,keys.vault,messages.dat}
```

### 剩下的事（按优先级）

1. **D5 锁屏 30 分钟验收**（G4/C1，唯一没验的闸门项）—— 用户要求最后做
2. **M4.7.1 电量策略 + 1 小时 ≤8%**（G4/C3）
3. **M4.4.1 数据持久化校验**（G4/C2，D6 已覆盖一半）
4. M4.8.4 `networkConnections` 计数失真、M4.8.5 `doingmsgpow` 偶发卡顿（低/中）
5. M6 剩余：横屏（`orientation = portrait` 写死）、全界面中文化、翻译基建

### 演示口径（现在可以这么说）

两台设备装同一 APK、各自连公网节点，**双向加密消息 + 回执全链路可用**，
中文主题/正文正常，送达量级 **30 秒 – 2 分钟**；重启不丢地址与消息；
私钥在盘上是密文（AndroidKeyStore 包裹）。**锁屏长待机未验收**，演示请亮屏。

---

## 6.0g ⏸ 2026-11-24 17:15：暂停点（等设备就绪后从这里继续）

### 一句话状态

M5 只剩 **M5.4.1 回归**没跑完。D1/D2 已通过（并顺带修掉一个 API 的真实 py3 bug），
D3/D4 被**本机出口 IP 拿不到公网连接**卡住（`Too many connections from your IP`），
D6/D7 因设备中途断开未执行。

### 平板当前状态

```
包      : 0.6.3.2（图标 + 启动图 + 私钥加密 + 通知 都在里面）
热补丁  : files/app/api.py  ← 唯一一处，是 1.58 里的 API 修复
          重新装包会丢，需要「先出包再装」才能固化
地址    : BM-2cXrmLDcoGry6Z4kRWqCthD7kuhRxkzaWx（phone）
          BM-2cWGibweLdxrUHN2JaLhGiBtekxZAw2ufV（HD）
收件箱  : 14 条
备份    : /tmp/bk_splash/{keys.dat,keys.vault,messages.dat}
```

### 下次继续时的步骤

1. **先出包固化 API 修复**（`api.py` 已提交在 `c827a03`，直接 push 触发 CI 即可），
   再装到平板 → 零热补丁
2. 设备在前台、网络能联通公网节点后，跑完整回归：

   ```bash
   adb -s b45f8e87 forward tcp:8445 tcp:8442
   python3 scripts/regression-d1-d7.py --json /tmp/d1d7.json --markdown /tmp/d1d7.md
   ```

   脚本会自动起 Mac 节点（A）、必要时给它 `createRandomAddress`、等它真正上线，
   再跑 D3/D4/D6/D7；等不到连接就把 D3–D7 标 `BLOCKED` 并写明原因。
3. **如果 A 仍然连不上**（同一个出口 IP 问题）：换把手机热点给 Mac 用（换公网出口），
   或用第二台真实设备当 A——D3/D4 必须两台不同设备才有意义
4. D5（锁屏 30 分钟）按用户要求最后做

### 顺带待办

- 发布页 `v0.6.3.2` 的资产是**修复 API 之前**的包；重出包后需要替换资产并更新
  `SHA256SUMS`、`RELEASE.md` 里的 sha
- p4a 产出的是 `res/drawable/presplash.jpg`（JPEG，有轻微色带），可接受但非无损

---

## 6.0f ✅ 2026-11-24 11:50：M4.2.1 设备验收通过、M4.8.9 关闭（新 session 从这里开始）

### 平板当前状态（干净，零热补丁）

```
包     : /tmp/pybitmessage-m421final-2026-11-24.apk
        run 45320464967 · 本钥重签 · sha256 92dbea1d…20fa9 · 25 MB
热补丁 : 无（files/app 下无任何 .py）
地址   : BM-2cXrmLDcoGry6Z4kRWqCthD7kuhRxkzaWx（label=phone）
         BM-2cWGibweLdxrUHN2JaLhGiBtekxZAw2ufV（label=HD）
收件箱 : 14 条
连接   : 2–5 条 established（真实公网对端，UA=/PyBitmessage:0.6.3.2/ 等）
配置   : keys.dat 已开 API（u:p@8442，adb forward 8445）；knownnodes 为 4 个活节点
备份   : /tmp/bk_m489/{keys,messages,knownnodes}.dat（本轮装机前的原始文件）
```

### 本轮完成的两个任务

| 任务 | 结果 | 证据 |
|---|---|---|
| **M4.2.1** 通知权限 + 新消息通知 | ✅ **设备验收通过** | EVIDENCE §1.54，截图 3 张（授权弹窗 / 服务通知 / **新消息+中文主题**） |
| **M4.8.9** 公网连接被断 + inv 不发 | ✅ **关闭**（环境 + 配置，非代码） | EVIDENCE §1.54：换活节点后 6→5 条稳定 ≥10 分钟、`INVTHREAD sending` 14 次、`recv inv` 17 次 |

### 设备验收才暴露的 3 个真 bug（都已修 + 已出包）

1. jnius 手写 `String[]` → `JavaException('No constructor available')`
   → 改用 p4a `android.permissions` 助手
2. 轮询 `UISignalQueue` 与 `UIkivySignaler` 抢消费 → 通知永远不出现
   → 改为包装 `helper_inbox.insert`
3. `Notification.Builder.setShortCriticalText()` 在 API 33 不存在（我按 sdk≥31 判据写错）
   → 删除

### 📋 待办全清单（2026-11-24 13:56 盘点）

> 依据：`MILESTONES.md` 各任务行的状态标记 + 今日设备实测。**按"是否阻塞产品可用"排序**，
> 不是按里程碑编号。

#### 🔴 P0 · 阻塞「能长期用」（G4 闸门，还差 4 项）

| 任务 | 内容 | 预估 | 说明 |
|---|---|---|---|
| **D5 / C1** | 锁屏 30 分钟 + 期间收到消息 | 1h 验收 | **代码已就位**（前台服务 M4.1e + WakeLock M4.3），只差实测。唯一一项完全没验过的 Gate 项 |
| **M4.5.2 / C4** | 私钥加密（Keystore 派生密钥） | 8h | **剩下唯一有实质代码量的任务**。当前 `keys.dat` 私钥明文，`keysencrypted = False` |
| **M4.7.1 / C3** | 电量策略 + 1 小时 ≤8% | 4h | WakeLock 常驻的代价必须量出来，否则用户装了就掉电 |
| **M4.4.1 / C2** | 数据持久化与恢复 | 4h | `am force-stop` 后重启 D1/D6 仍成立（含 knownnodes 落盘） |

#### 🟠 P1 · 交付必需（M5，7 个任务全未做）

| 任务 | 内容 | 预估 |
|---|---|---|
| M5.3.1 | `README-ANDROID.md`：安装 / 首配 / 互换地址 | 3h |
| M5.3.2 | 故障排查章节（连不上 / 收不到 / 耗电） | 2h |
| M5.4.1 | 回归 D1–D7 全跑 | 4h |
| M5.4.2 | 最终 APK + SHA256 | 1h |
| M5.1.1 | 图标 / 应用名定稿 | 2h |
| M5.1.2 | 版本号与 `softwareVersion` 对齐 | 1h |
| M5.2.1 | release keystore（可选） | 2h |

> **注**：M5.3.1 是给别人装机的唯一入口。今天我自己踩的坑（knownnodes 全死、
> API 未开、签名不兼容）都会原样发生在新用户身上，必须写进文档。

#### 🟡 P2 · 产品明确要求但未满足（M6）

| 任务 | 现状 | 预估 |
|---|---|---|
| **M6.3.1 横屏** | `buildozer.spec` 写死 `orientation = portrait` | 2h |
| **M6.3.2 响应式布局** | 固定 `dp()` 宽高多，平板横屏会很难看 | 8h |
| M6.3.3 字号/资源 | 未做 | 4h |
| M6.3.4 平板 AVD | 未建 | 2h |
| M6.1.1–4 翻译基建 | **未做**：当前中文是 `mpybit.py` 里一个 88 条的硬编码字典，`_()` 只查这一张表，没有 `lang/` 目录、没有语言切换 | 12h |
| M6.2.1–3 全界面中文 | 抽屉 + 四个邮件页已完成；仍有硬编码英文（如搜索框 `hint_text: 'Search'`） | 16h |
| M6.4.x 验收 | 未做 | 4h |

#### 🟢 P3 · 已知缺陷（不阻塞，但会咬人）

| 任务 | 症状 | 优先级 |
|---|---|---|
| **M4.8.5** | `doingmsgpow` 偶发卡 5 分钟（第 2 条消息） | 中 |
| **M4.8.4** | `networkConnections` 计数失真——今天实测 `listConnections` 报 **57 条 outbound**，明显偏多 | 低 |
| **新观察项** | `INVTHREAD skip stream 1 not in [0]`：少量连接 version 未解析完就跳过 | 低 |
| **M4.8.6** | 桥接 / 握手 TLS 竞态（只影响 adb 桥测试路径） | 低 |

#### ⚪ 建议的下一步（一次只做一件）

1. **D5 锁屏 30 分钟验收** —— 1 小时、零代码、闭合 G4 最大不确定性
2. **M5.3.1 + M5.3.2 文档** —— 把今天踩的坑变成别人的说明书
3. **M4.5.2 私钥加密** —— 唯一的硬骨头，8h，做完 C4 也过了

### 下一步（按优先级）

1. **M4.8.9 遗留观察项**：日志有 `INVTHREAD skip stream 1 not in [0]`（少量连接 version 未解析完就被跳过）
2. **D5 锁屏 30 分钟验收**（G4 最后一项，用户说最后做）
3. M4.8.4 `networkConnections` 计数失真（本次见 `outbound total=57`，明显偏多）
4. M5 交付（README-ANDROID / 回归 D1–D7 / 最终包 + SHA256）
5. M6 收尾（搜索框硬编码英文、横屏适配）

---

## 6.0e ✅ 2026-11-24 11:05：M4.8.9 定性完成（RST 来自对端）+ 3 个真实修复

**结果**：线缆抓包证明「公网连接建立后数秒被断开」是**对端主动 RST**，不是我们的 bug
（EVIDENCE §1.53）。但顺着这条线索修掉了 3 个真问题，并补了 7 条回归测试。

| 修复 | 文件 | 测试 |
|---|---|---|
| `CreatePacket` 命令字段补齐到 12 字节 | `protocol.py` | `tests/test_packet_framing.py` |
| `assembleAddrMessage`/`assembleVersionMessage`/`assembleErrorMessage` 返回**完整包**（原来返回裸头） | `protocol.py` | 同上 |
| `tcp.handle_read` 遇到「可读但 0 字节」的陈旧唤醒不再误关连接 | `tcp.py`（`STALE_READ_GRACE=15s`） | 只在 `!fullyEstablished` 分支生效 |

**测试**：`tests.test_packet_framing + test_shutdown + test_android_notify` = **15 条全过**。

**最新包**：`/tmp/pybitmessage-m489-2026-11-24.apk`（run 45315773202，个钥重签，
sha256 `a0e547f3…877491`）—— **包含了 M4.2.1 / M4.8.3 / M4.8.9 全部修复，装这一个即可**。

**下一步（M4.8.9 的验收）**：本机没有 TLS 证书（`src/sslkeys` 不入库），公网节点直接 RST，
所以「公网 ≥10 分钟稳定 + 发出 `inv`」这条验收**只能在 ①带证书的节点 或 ②平板 上做**。
平板之前有公网收发历史证据，装 `m489` 后按 `scripts/PUBNET-TEST.md` 复测即可。

## 6.0d 🚨 2026-11-24 上午：M4.2.1 + M4.8.3 已出包，同时挖出一个致命网络缺陷

**本轮到手的包**（都可用 `scripts/resign-apk.sh` 个钥覆盖升级）：

| 包 | 内容 | 来源 |
|---|---|---|
| `/tmp/pybitmessage-m421-2026-11-24.apk` | M4.2.1 通知权限 + 新消息通知 | run 45298351539（`pybitmessage-apk-55`），sha256 `234559e9…cd7124` |
| `/tmp/pybitmessage-m486-2026-11-24.apk` | 上面全部 + M4.8.3 关闭超时/陈旧锁 + 选点空列表防护 + **TCP `connecting` 修复** | run 45308520550（`pybitmessage-apk-56`），sha256 `436d8045…9868` |

**只装一个就直接装 `m486`**（包含 m421 的全部内容）。

**M4.8.3 已完成**（本机实测 + 6 条单测，EVIDENCE §1.52）：SIGTERM 后锁文件不再残留；
关闭流程有 10 s 硬上限；陈旧锁启动时自动清理。

**TCP `connecting` 修复**：公网 TCP 连接从"0 次建立"变成"稳定建立"
（`TCP established: 185.158.248.216:8444`，`networkConnections=1`）。

**🚨 但暴露了新问题 M4.8.9（高优先级，未修）**：公网连接建立后 **2–6 秒被主动断开**，
网关无任何日志；`verack` 之后双方都不发 `inv`。排查结论与已排除项见 EVIDENCE §1.52，
任务卡见 `MILESTONES.md` §7.0。**下一个 session 优先从这里接着干。**

**排查陷阱（务必先读）**：管道里 print 是块缓冲 → 用 `python3 -u`；8444 是共享端口 →
先 `lsof -nP -iTCP:8444 -sTCP:LISTEN`；`pubnet_node.py` 默认 4 个公网对端，只连一台要
`--reset-peers --peer host:port`。EVIDENCE §1.52 里还列了 6 个新增诊断脚本。

## 6.0b ⏸ 历史暂停点（16:52，已被上节取代）

### 刚完成（未固化进包，等装机）

**M4.8.7（commit `40dcb8a`）**：中文主题消息被静默丢弃——`encodeSimple` 按字符数
而非 UTF-8 字节数计 msg 长度，接收方解析错位导致验签失败。**已设备验证**：
16:48:07 中文消息 `DECRYPT OK + ECDSA verify PASSED`，收件箱正确显示。
**M4.8.2b（commit `599214c`）**：anti-intersection 窗口限频，修复下载永久停摆。

**平板当前状态**：跑 m482b 包 + 2 个热补丁（class_objectProcessor.py 两份副本，
含 PROCMSG 打点）。Mac 节点已带全部修复在跑。

**下一步**：
1. CI run **45141802772**（M4.8.7 包）→ 下载重签 → 装机（删热补丁）→ 验证
   中文消息收发 + sjy 方向回执
2. 记录 M4.8.7 完成到 MILESTONES

### 排查方法论（本次 5 层穿透，供后续参考）

1. 库存 hash 差集 → 对象是否下载
2. ripe 重算（注意 \x04 前缀！）→ 公钥是否匹配
3. 本地解密 → 密钥是否正确
4. **processmsg 打点热补丁** → 精确到"验签失败 + sig=22B"
5. 长度比对：字符数 43 vs UTF-8 55 → msglen 偏短实锤

---

## 6.1 ✅ 稳定基线已建立（2026-11-23 09:42）—— 已被 6.0 取代

### 平板现状：**零热补丁，全部修复已固化进包**

```
包      : /tmp/pybitmessage-baseline-2026-11-23.apk
sha256  : d3a0e650b38a86cfbfc6002c32b82f09947beb9c14a05fdaa67f7f00922a7225
run     : 45094228488（commit b44b7b9）
热补丁  : 无（files/app 下已无任何 .py）
```

**设备验证通过**（EVIDENCE §1.39）：启动无崩溃、收件箱中文正常、
点击打开详情、前台服务 + WakeLock 正常、**发送消息实测成功**
（发给 `BM-2cXj6btesow8nHkDz1zEYSicugi1qMf7jf`，状态 `msgsent`）。

### 已完成的能力清单

| 能力 | 状态 |
|---|---|
| 构建 / 地址 / 存储 / 公网连接 | ✅ |
| 双向加密消息 + 回执 | ✅ |
| 中文界面（主界面 + 抽屉 Inbox） | ✅ |
| 收件箱点击看详情（含完整正文） | ✅ |
| 发送消息（中文主界面） | ✅ 实测 |
| Composer（英文页）发送崩溃 | ✅ 已修 |
| 前台服务 + WakeLock | ✅ |
| 历史 bytes repr 数据迁移 | ✅ |

### 下一步（按优先级）

| 顺序 | 任务 | 说明 |
|---|---|---|
| ~~1~~ | ~~M4.5.1 禁用云备份~~ | ✅ 已完成（EVIDENCE §1.40），待装机：`/tmp/pybitmessage-m451.apk` |
| ~~1~~ | ~~M4.8.2 skipUntil~~ | ◐ 代码已修+单元验证（EVIDENCE §1.41），**待装机实测送达**；包 `/tmp/pybitmessage-m482.apk`（含 M4.5.1） |
| ~~1~~ | ~~M4.8.1 singleCleaner~~ | ◐ 代码已修+单元验证（EVIDENCE §1.42）**待装机**：最新包 `/tmp/pybitmessage-m481.apk` （含 M4.5.1+M4.8.2+M4.8.1，装它验全部） |
| 3 | **M6 界面中文化** | 菜单 Sent/Draft/Trash/Settings 等仍是英文 |
| 5 | M4.2.1 通知权限 | 新消息通知 |
| 6 | D5 锁屏 30 分钟验收 → M5 交付 | 用户说最后做 |

### 已知小问题（不阻塞）

- emoji 🎉 显示为 ⊠（NotoSansCJK 无 emoji 字形）
- 抽屉菜单项、Composer 页面仍是英文
- 新消息无系统通知

### 环境笔记

- **GitHub 需走代理**：`export HTTPS_PROXY=http://proxy.apj.ibm.com:8080`，
  然后 `gh api repos/k19810703/pybitmessage-android/actions/artifacts/<id>/zip > x.zip` 下载
- 热补丁路径必须带 `pybitmessage/` 前缀：`files/app/pybitmessage/bitmessagekivy/…`
- 数据备份：`/tmp/bk_{keys,msgs,kn}_base.dat`

---

## 6.2 ⏸ 历史暂停点（2026-11-22 21:10，已被 6.1 取代）

### 平板现状（重要：带热补丁）

平板当前跑的是 **run 44686653091 的包**，外加**一个热补丁文件**：

```
files/app/pybitmessage/bitmessagekivy/baseclass/inbox.py   ← 热补丁，尚未出包
```

**如果不重新出包，这个热补丁会一直生效**；一旦装新包，必须重新打补丁或等新包包含修复。

### 本阶段成果

| 项 | 状态 |
|---|---|
| 收件箱**中文乱码（豆腐块）** | ✅ **已修复并截图验证**（`公网测试 1`、`来自 BM-2c…` 正常） |
| 历史 bytes repr（标题+正文） | ✅ 已迁移（`公网测试 1` / `hello via public network… 中文+emoji 🎉`） |
| 收件箱列表左对齐、超长截断 | ✅ 正常 |
| **点击消息打开详情** | ❌ **仍未生效**（见下方待办） |

### 中文乱码的三个根因（已修，勿重踩）

1. **APK 里有两份 `messaging` 模块**（`bitmessagekivy/` 和 `pybitmessage/bitmessagekivy/`）。
   注册中文字体的 `MessagingScreen` 在另一份里，所以 `from ...messaging import FONT`
   拿到的永远是 `'Roboto'`。→ inbox 现在**自己注册** `/system/fonts/NotoSansCJK-Regular.ttc`
2. **`MDLabel` 会忽略 `font_name`**（用主题字体）。→ 改用**原生 `Label`**
   （主界面一直用的是原生 Label，所以它一直正常）
3. **`text_size` 必须跟随控件宽度**，否则 `halign`/`shorten` 不生效。

### 下一步（按优先级）

**1. 修「点击消息打开详情」**（唯一未完成项）

现状：`BoxLayout` 没有 `ButtonBehavior` 收不到触摸；已尝试 `widget.__class__` 改成
`ButtonBehavior` mixin，但**点击仍未触发**（日志无 `INBOX open detail`）。

建议方案 A（把握最高）：把每行换成原生 **`Button`**：

```python
btn = Button(background_normal='', background_color=(1,1,1,1),
             size_hint_y=None, height=dp(72))
btn.add_widget(inner_boxlayout)   # Button 可容纳子控件
btn.bind(on_release=lambda *_: self._open_detail(...))
```

验证：点击后 `adb logcat -s python:* | grep "INBOX open detail"` 应出现。

**2. 把当前代码出正式包**（包含中文字体修复，去掉对热补丁的依赖）

**3. 其余任务**：M4.2 通知权限、M4.4–M4.7、M4.8.x、D5 锁屏验收、M5、M6

### 环境笔记

- **GitHub 需走代理**：`export HTTPS_PROXY=http://proxy.apj.ibm.com:8080`，
  然后 `gh api repos/k19810703/pybitmessage-android/actions/artifacts/<id>/zip` 可直接下载
- **热补丁路径必须是** `files/app/pybitmessage/bitmessagekivy/...`（带 `pybitmessage/` 前缀），
  打到 `files/app/bitmessagekivy/...` **不生效**（本次踩过）
- 平板数据备份：`/tmp/bk_keys_body.dat`（2 个地址）、`/tmp/bk_msgs_body.dat`

---

## 6.3 当前进度快照（2026-11-20 14:20，用户移动中暂停）

### 已装到平板的包

```
/tmp/pybitmessage-ui-2026-11-20.apk    ← 当前平板上的就是这个
sha256 c4156aedfc2811df9f637ed4dad1912c7064488e307a92506cc26d10a566ee4c
run    44685032281
```

**平板实测通过**：启动无崩溃、`isForeground=true`、wake lock 持有、
菜单 Inbox 能列消息、**点开消息弹详情**（日志 `INBOX open detail ... len(body)=101`）、
历史标题已修复为 `公网测试 1`。

### 下一步（2026-11-22 20:50 更新）

**M3.9.1a/b/c 已全部完成并设备验证**（EVIDENCE §1.36）。平板当前跑的是
run 44686653091 的包（`/tmp/pybitmessage-body-2026-11-20.apk`）。

**网络注意**：公司网访问 GitHub 需走代理 `proxy.apj.ibm.com:8080`
（`export HTTPS_PROXY=http://proxy.apj.ibm.com:8080`），gh api 下载 artifact 可用。

**剩余任务**（按优先级）：
1. M4.2 通知权限运行时申请（Android 13+）
2. M4.4–M4.7（持久化校验、禁备份、私钥加密、崩溃自恢复、电量）
3. M4.8.x 缺陷收编（singleCleaner 崩溃、skipUntil 等）
4. D5 锁屏 30 分钟验收（用户说最后做）
5. M5 交付、M6 全界面中文化

### 仍未做的

| 项 | 状态 |
|---|---|
| 豆腐块图标目视确认 | 代码已移除图标字体依赖，需用户看一眼确认 |
| D5 锁屏 30 分钟验收 | 用户说最后做 |
| M4.2 通知权限运行时申请 | 未做 |
| M4.4/M4.5/M4.6/M4.7、M4.8.x | 未做 |
| M5 交付、M6 中文化 | 未做 |

### 数据备份位置（都还在）

```
/tmp/bk_keys_ui.dat    当前地址私钥（2 个地址）
/tmp/bk_msgs_ui.dat    安装前消息库
/tmp/bk_kn_ui.dat      knownnodes
```

---

## 6.4 待验包（2026-11-20 13:42，**已准备好，未安装**）

```
本地路径: /tmp/pybitmessage-2026-11-20.apk   （个钥重签，可覆盖升级）
SHA256  : 5b61650203ef2a91c689621aff96a0dae70a795daa2b818a1541dce3e5c19066
CI 来源 : run 44681905358
```

**包含的全部修复**：

| 修复 | 说明 |
|---|---|
| dandelion/api/protocol 三个 py3 崩溃 | 2026-11-19 公网测试发现 |
| 前台服务（M4.1） | 服务进程 + 可见通知 + 权限齐全 |
| WakeLock（M4.3） | 锁屏后连接保持；**去掉了 BroadcastReceiver**（会 JNI 崩溃） |
| 启动崩溃修复 | Android 相关初始化改为 Kivy Clock 主线程延迟 8s 执行 |
| 菜单 Inbox 修复（M3.9.1） | 原来从不查询数据库，现在能显示消息 |

**验证命令（先问用户，再执行）**：

```bash
ADB=~/Documents/platform-tools/adb
$ADB -s b45f8e87 push /tmp/pybitmessage-2026-11-20.apk /data/local/tmp/bm.apk
$ADB -s b45f8e87 shell pm install -r -d /data/local/tmp/bm.apk
$ADB -s b45f8e87 shell am force-stop at.bitmessage.pybitmessage   # 让热补丁失效
$ADB -s b45f8e87 logcat -c
$ADB -s b45f8e87 shell am start -n at.bitmessage.pybitmessage/org.kivy.android.PythonActivity
sleep 70
$ADB -s b45f8e87 shell "ps -A | grep bitmessage"          # 期望 2 个进程
$ADB -s b45f8e87 logcat -d -s python:* | grep -E "KEEPALIVE|SERVICE|INBOX"
$ADB -s b45f8e87 logcat -d | grep -c "JNI DETECTED"       # 期望 0
```

---

## 6.5 协作规则（用户明确要求，必须遵守）

**任何涉及物理设备（平板 `b45f8e87`）的操作，必须先向用户确认，不要自行安装/卸载/清数据/重启 App。**

具体包括但不限于：

- `pm install` / `adb install` / `adb push <apk>`
- `pm uninstall` / `am force-stop` / `am start`
- **`pm clear`（绝对禁止，会清掉私钥）**
- 热补丁推送（`push` 到 `files/app/`）

允许不询问就做的：只读查询（`ps`、`logcat`、`cat`、`dumpsys`、`screencap`）。
CI 出包、本地编译、改代码、写文档都不需要确认。

---

## 7. 已知坑（都会浪费时间，先看这里）

| 现象 | 原因 | 对策 |
|---|---|---|
| **🚨 地址/私钥突然没了、收件箱空了** | 误跑 `adb shell pm clear at.bitmessage.pybitmessage` —— **会连 `keys.dat` 一起清掉，私钥不可恢复**（2026-11-20 真实发生过一次） | **永远不要对装机设备跑 `pm clear`**；要"干净重来"只在模拟器上做。做实验前先 `adb exec-out run-as <pkg> cat files/bitmessage/messages.dat > /tmp/backup.dat` 备份 |
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
