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

## 6.1 ✅ 稳定基线已建立（2026-11-23 09:42）—— **从这里继续**

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
| 1 | **M4.8.1 singleCleaner 崩溃** | knownnodes 不落盘，重启后重新找节点（下一个任务） |
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
