# 交接单 · 2026-11-19 13:45

> 目的：新 session 从这份文档直接接着干，不用回翻对话。
> 除非特别说明，命令都在仓库根 `for_shizong/` 下执行，adb 用
> `~/Documents/platform-tools/adb`。

---

## 1. 一句话状态

**协议、加密、C 版 PoW、中文界面全部打通；唯一卡点是"公网传输层"——两台设备连公网种子后连接会被断开，消息停在 `awaitingpubkey`。**

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

## 3. 当前卡点（下一步要解决的唯一问题）

**现象**

```
平板   : streams:[1] → ~10s 后 "closing, Timeout (20s)" → 重连 → 循环
模拟器 : version parsed → ~2s 后 "closing, None" → 重连 → 循环
结果   : 发送状态卡在 awaitingpubkey，收件箱 0
```

**已排除**

| 假设 | 结论 |
|---|---|
| TCP 不通 | ❌ 排除：`nc -w 4 <seed> 8444` 从平板 exit=0 |
| TLS 升级失败 | ✅ **已修**（`network/tls.py` 的 Purpose 搞反了，commit `008b9cb`） |
| 出站连接数过多被踢 | 已把 `maxoutboundconnections` 设为 1，仍有断连 |
| 低难度被拒 | 已恢复协议默认难度（C PoW 够快） |

**仍存疑（按优先级）**

1. 种子太少：`dig bootstrap8444.bitmessage.org` 只有 3 个 IP，1 个不可达，任意一个抖动整条链就断
2. 被对端临时 ban（早期日志出现过 `Too many connections from your IP`）
3. 握手后我们发的某个字段对端不认（`closing, None` 没有错误文本，像是对方直接关 TCP）

**下一步动作（建议顺序）**

1. 在 `bm_command_error` 打点，确认是对端踢我们还是我们自己关的
2. 用 Mac 上的桌面节点连同样的种子做对照（桌面之前能稳住 → 能区分"网络问题"还是"手机端握手问题"）
3. 扩充节点池：不只靠 DNS 种子，从 addr 交换里收集 10+ 活节点

---

## 4. 环境清单（写文档时的真实状态）

### 仓库

```
branch : android-port
HEAD   : 008b9cb  (M3.8: fix the TLS role mix-up...)
remote : git@github.com:k19810703/pybitmessage-android.git
```

### 设备

| 设备 | 序列号 | 系统 | 分辨率 | 当前 App 地址 | API 转发 |
|---|---|---|---|---|---|
| 小米平板 5 | `b45f8e87` | HyperOS V816 / Android 13 | 2560×1600 @360dpi | `BM-2cXKRdK3kTb9mkHLsqisMMx1RFiN5L18qy` | `adb -s b45f8e87 forward tcp:8445 tcp:8442` |
| 模拟器 Pixel 6 | `emulator-5554` | Android 13 (SDK 33) | 1080×2400 | `BM-2cXFwKXTCiusUrf54LPHNvpFxNQDuYVXGy` | `adb -s emulator-5554 forward tcp:8442 tcp:8442` |

> 地址随重装变化，用 `listAddresses` 查最新值。

### 两台设备当前配置（已写入各自 keys.dat）

```
apienabled = true / apivariant = xml / apiusername = u / apipassword = p
dandelion = 0
maxoutboundconnections = 1
extralowdifficulty = false        # 协议默认难度
knownnodes.dat = 85.114.135.102:8444 / 194.164.163.84:8444
```

### 本机辅助脚本（**不在仓库里，/tmp 会被清掉，新 session 需要时按 §6 重建**）

| 路径 | 作用 |
|---|---|
| `/tmp/node_common.py` | headless 节点公共启动逻辑（含 `__main__` 保护，避免 multiprocessing 重跑） |
| `/tmp/run_node.py` | 宿主节点 1（`BITMESSAGE_HOME=/tmp/node1`，监听 8444） |
| `/tmp/run_node2.py` | 宿主节点 2（连 127.0.0.1:8444，用于本地双节点验证） |
| `/tmp/enable_api.sh` | 给设备上的 App 注入 `apienabled` 等配置 |
| `/tmp/bmapi.py` | XML-RPC 小封装 |

### 仓库里的脚本（会持久保留）

| 路径 | 作用 |
|---|---|
| `scripts/build-bitmsghash.sh` | 交叉编译 `libbitmsghash.so` |
| `scripts/enable-low-pow.sh` | 开关 `extralowdifficulty` |
| `scripts/resign-apk.sh` | 用个人钥匙重签，实现免卸载升级 |

---

## 5. 关键代码改动索引（都已在 git 里）

| 文件 | 改动 |
|---|---|
| `src/bitmessagekivy/messaging.py` | **新增**：中文收发界面 |
| `src/bitmessagekivy/mpybit.py` | 注册并默认进入 messaging 屏 |
| `src/main.py` | TLS 默认开启（`BITMESSAGE_DISABLE_TLS=1` 关闭）；不再默认低难度 |
| `src/network/tls.py` | **修 bug**：`ssl.Purpose` 客户端/服务端反了 |
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

### 重建本地双节点（用于验证协议层，不依赖公网）

```bash
# /tmp/node_common.py 的内容见 git 历史或按 AGENTS §6.7 的思路重建：
# 关键点：state.kivy=True、state.disable_tls=True、daemon=true、
#        alias_core_modules()、if __name__ == '__main__' 保护、
#        config.set('network','dandelion','0')、maxoutboundconnections=1
cd /tmp && (BITMESSAGE_LOG_LEVEL=INFO python3 -u /tmp/run_node.py > /tmp/node1.out 2>&1 &)
```

---

## 7. 已知坑（都会浪费时间，先看这里）

| 现象 | 原因 | 对策 |
|---|---|---|
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 每次 CI 构建签名不同 | 先卸载，或 `scripts/resign-apk.sh` 重签 |
| MIUI 报 `INSTALL_FAILED_USER_RESTRICTED` | HyperOS 拦 `adb install` | `adb push` + `pm install -r -d` |
| API 打到 8442 却操作到别的节点 | 宿主节点也占了 8442 | 宿主 API 必须换端口（当前 38681/8449 都出现过），设备用 8445 |
| 平板 App 有时没有 API、也没日志 | 疑似启动早期卡住 | `am force-stop` 后重新 `am start`，等 90s 再查 |
| `THREAD-CRASH singleCleaner: memoryview ... not 'str'` | `class_singleCleaner` 还有 py3 字节问题（未修） | 不影响收发，但应修 |
| 平板连种子 10 秒后被断 | 见 §3 | 待查 |
| 对端回 `Your time is too far in the past` | 模拟器时钟漂移 | `adb root && adb shell "date -s @$(date +%s)"` |
| 所有节点连不上 | 默认 knownnodes 是 2017 年的死节点 | 写入活种子（85.114.135.102 / 194.164.163.84） |

---

## 8. 建议的下一步（按价值排序）

1. **查清公网断连**（§3）——这是"公网可用"唯一的拦路虎
2. 修 `class_singleCleaner` 的 memoryview/str 崩溃
3. 平板横屏适配（`p4a_env_vars.txt` 里 `KIVY_ORIENTATION=Portrait` 写死，平板上是竖屏 letterbox）
4. UI 补发送进度（把 `doingpubkeypow/awaitingpubkey/msgsent` 映射成中文）

**如果演示时间紧**：两台设备连同一 Wi-Fi，直接互连（不依赖公网种子），这条路已经验证能通，`extralowdifficulty=true` 时秒级。
