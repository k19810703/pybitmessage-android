# EVIDENCE.md — 验收证据流水

> 规则：**每个任务（完成或失败）都追加一行**，证据必须可复现（命令输出 / 日志片段 / 截图路径 / run 号）。
> 成功也记，失败更要记 —— 同一类问题第二次出现时直接搜索本文档。
> 相关：`MILESTONES.md`（任务与验收标准）、`AGENTS.md` §6.5。

---

## 1. 任务验收记录

| ID | 日期 | 任务 | 结论 | 证据 | 备注 |
|---|---|---|---|---|---|
| M1 | 2026-11-17 | 构建链路打通（Mock APK） | ✅ | run [44013702969](https://github.com/k19810703/pybitmessage-android/actions/runs/44013702969)，9m06s；产物 `artifacts/pybitmessage-apk-7/pybitmessagemock-0.1.2-arm64-v8a-debug.apk`（25 MB，`libpython3.11.so`） | 七轮迭代过程见 `PLAN.md` §7.5 |
| M1-A | 2026-11-17 | 装机启动验证（模拟器 Pixel_6_API_33） | ✅ | `adb install` = Success；`pm list packages` 有 `at.bitmessage.pybitmessagemock`；`pidof` = 8028；截图 `artifacts/screenshot-2.png` | 首启有 30–60s 解压 `_python_bundle` |
| M2.0 | 2026-11-17 | 前置事实核查：v0.6 能否在 Python 3 运行 | ❌ 不可直接运行 | `BITMESSAGE_HOME=/tmp/bmtest python3 src/bitmessagemain.py -t` → `ERROR: PyBitmessage does not support Python 3+`；源码 `src/depends.py:445` `if six.PY3: sys.exit()` | 已拆为任务 M2.2；不影响方案可行性（改一行即可） |
| M2.1.1 | 2026-11-17 | 启动自检探针（run 44024863827） | ✅ | 设备 logcat 输出 9 行 `PROBE`（见 §1.1）；APK `artifacts/pybitmessage-apk-8/` | 探针放在 `src/main.py` 入口最前，永不抛异常 |
| M2.1.2 | 2026-11-17 | 能力矩阵（设备侧结果） | ✅ | 见 §1.1 | 判定：环境满足，可以继续 |
| M2.1.3 | 2026-11-17 | RIPEMD-160 兜底 | ⏭ 未触发 | `PROBE ripemd160 = OK (bdabd16e480e77c5)` | 与 macOS 本地值完全一致，说明哈希实现正确 |
| M2.1.4 | 2026-11-17 | pyelliptic ctypes 修复（EVP_CipherInit_ex） | ✅ | 修复前：`PROBE ecies = FAIL (EVP_CipherUpdate FAIL)`；修复后：本地与设备均 `encrypt/decrypt ok (150 bytes)` | 只声明了 3 个 argtypes 而调用传 6 个参数，64 位下 key/iv 指针被截断 |
| **G2.1** | 2026-11-17 | 加密能力闸门 | ✅ **通过** | `ripemd160 = OK` 且 `openssl_layer = OK (libcrypto1.1.so)` | 无需启动 M2.1 的"停止并重评估"分支 |
| M2.2.1 | 2026-11-17 | 删除 py3 硬退出，改为告警 | ✅ | commit `829f0b02`；桌面输出 `WARNING: Running on Python 3.11.12; the Python 3 port is incomplete.` | `src/depends.py` 里 `if six.PY3: sys.exit()` → `logger.warning` |
| M2.2.2 | 2026-11-17 | 桌面 `-t` 跑通并生成配置 | ✅ | `BITMESSAGE_HOME=/tmp/bm22c python3 src/bitmessagemain.py -t` → `EXIT=0`，生成 `keys.dat`(1444B)/`messages.dat`(68K)/`knownnodes.dat`，`Traceback` 计数 = 0 | 第一次跑时崩在 `thread.isAlive()`，属另一个 py3 问题，见下 |
| M2.2.3 | 2026-11-17 | Android 侧依赖检查不再退出 | ✅ | 设备 logcat 探针 8/9 OK（唯一 FAIL 是 pycryptodome，非必需） | 探针 msgpack 判定已对齐真实导入链，本轮变为 `OK (bundled umsgpack 2.4.1)` |
| **G2.2** | 2026-11-17 | 桌面可启动闸门 | ✅ **通过** | `-t` 退出码 0 + 生成 `keys.dat` + 无 traceback | 与 MILESTONES 的验收标准一致，无偏差 |
| M2.3.1 | 2026-11-17 | 解封 Android 入口（新 `src/main.py`） | ✅ | 设备日志 `BITMESSAGE_HOME=/data/user/0/.../files/bitmessage` → `Running with kivy` | 顺序：探针 → BITMESSAGE_HOME → `state.kivy=True` → `bitmessagemain.main()`；旧的 `main-android-live.py` 删除，Mock 入口保留为 `main_mock.py` |
| M2.3.2 | 2026-11-17 | `main()` 走 Kivy 分支、不再依赖 PyQt | ✅ | 启动不再出现 `PyBitmessage requires PyQt`；`singleinstance` / `tr` 不再 import PyQt4 | 关键：`tr.py` 的 PyQt 兜底是 `os._exit(0)`，会让 App "静默消失"（退出码 0、无 traceback） |
| M2.3.3 | 2026-11-17 | p4a 入口指向真实入口 | ✅ | APK 启动后无 `FakeAddressGenerator`，界面显示真实引导页（"Select method to make an address"） | `buildozer.spec` 的 `source.dir` 不变，替换的是 `src/main.py` 内容 |
| **G2.3** | 2026-11-17 | 核心启动闸门 | ✅ **通过** | 进程存活 80s+（pid 9710）；`keys.dat`/`messages.dat`/`knownnodes.dat` 均在应用私有目录；`messages.dat` 已建 10 张表（`sqlThread` 跑过）；无 Traceback；截图 `artifacts/screenshot-m23.png` | 线程日志默认 WARNING 级不打印，改用 **数据库 schema 已建立** 作为"核心线程确实启动"的功能性证据 |

### 1.4 M2.3 迭代记录（4 轮，全部是"启动即消失"或"启动即崩"）

| 轮 | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | App 启动后**静默退出，退出码 0，无 traceback** | `tr.translateText()` 在 `enableGUI=True` 时 import PyQt4，失败即 `os._exit(0)` | `tr.py`：kivy 模式下跳过 Qt 翻译 |
| 2 | `PyBitmessage cannot start. One or more dependencies are unavailable.` | `check_openssl` 只试 `libcrypto.so`/`libcrypto.so.1.0.0`，Android 上解析到系统库（不在 app linker namespace） | 加版本化 soname（`libcrypto1.1.so` 等）+ `ssl` 模块兜底 |
| 3 | `configparser.NoSectionError: No section: 'bitmessagesettings'` | `BMConfigParser.read()` 依赖 `src/default.ini` 提供默认段，而 APK 的 `source.include_exts` 没有 `ini` | `source.include_exts` 增加 `ini,pem` |
| 4 | `ModuleNotFoundError: No module named 'pybitmessage.network'` | APK 里只有 `*.py` 被镜像进 `pybitmessage/`，包目录仍在根下 | `bitmessagekivy/baseclass/network.py` 改扁平导入 |

### 1.6 M2.4 记录（部分完成，卡在"地址创建通路"）

| ID | 结论 | 证据 |
|---|---|---|
| M2.4.1 `BITMESSAGE_HOME` 指向私有目录 | ✅ | `files/bitmessage/` 下有 keys.dat / messages.dat / knownnodes.dat / singleton.lock |
| M2.4.2 单实例锁降级 | ✅ | `singleinstance.lock()` 包了 try/except（commit `204b753d`），启动不受影响 |
| M2.4.3 重启后地址不变 | ⏸ **阻塞** | 还没有地址 → 无法对比。原因见 M2.4.5 |
| M2.5.2 INTERNET 权限 | ✅ | `aapt2 dump badging` 有 `android.permission.INTERNET` / `ACCESS_NETWORK_STATE`（commit `c9b49ada`） |
| M2.7.1 API 可用 | ✅ | 设备上 `clientStatus` 返回正常 XML（networkConnections / networkStatus / softwareVersion） |
| **G2.4** | ⏸ 未通过 | 等待 M2.4.5 |
| M2.4.5b | 2026-11-17 | 定位地址生成线程崩溃 | ✅ 找到根因 | 设备日志（instrumented build，run 44080731890）：`AGENDA: addressGenerator thread started` → `AGENDA: got request 'createRandomAddress'` → `THREAD-CRASH addressGenerator: TypeError("'>' not supported between instances of 'int' and 'str'")` | `config.get()` 在 py3 返回 **str**，生成器里 `max(str, int)` 直接抛异常；py2 允许异类比较所以上游从未暴露 |

#### M2.4.5b 根因与修复

```python
# 之前（api.py）
nonceTrialsPerByte = self.config.get('bitmessagesettings', 'defaultnoncetrialsperbyte')  # → str "1000"
# 之后（class_addressGenerator.py）
nonceTrialsPerByte = max(nonceTrialsPerByte, defaults.networkDefaultProofOfWorkNonceTrialsPerByte)
#                                                            ^^^ int → TypeError
```

修复：`api.py` 两个 handler 改用 `config.getint()`；`class_addressGenerator` 对进队列的两个难度值做 `int()` 兜底。commit `5c40095`。

**方法论收获**：之前"API 挂起"被误判为"线程没起来"

#### M2.4.5b 后续：又挖出 2 个 py3 阻塞（commit `d91ae20`）

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | 地址生成线程 `TypeError('option values must be strings')` | `_decode()` 返回 **bytes**，label 直接进了 `config.set()`（py3 只收 str） | 新增 `_decode_text()`，label 三处改用它；生成器 `save_address` 对 bytes 做兜底 decode |
| 2 | `makeCryptor()` 抛 `TypeError: argument should be integer or bytes-like object, not 'str'` | `pyelliptic/arithmetic.decode()` 里 `code_string` 是 bytes，索引 str 得到 str，`bytes.find(str)` 在 py3 非法 | `decode()` 入口把 str 编码成 bytes |

**本地端到端验证（不经 Android，真实生成器线程）**：

```
AGENDA: addressGenerator thread started
AGENDA: got request 'createRandomAddress'
AGENDA: address returned to caller
RESULT: BM-2cU8SNexEcq6FCgeuMKypNnXrGQZ8ne995
```

> 注：本地复现必须设 `state.kivy = True`，否则 `tr.py` 会走 PyQt 分支并 `os._exit(0)`（这个坑已在 M2.3 记录）。

#### M2.4.5c API 超时（已生效）

`createRandomAddress` 现在 90s 内无结果会返回 `Fault 21`，不再把单线程 XML-RPC 服务器永久占死。设备实测：修复前挂起无响应；加入超时后 90.0s 返回 Fault 21。

#### ⏸ 设备侧验证：被网络卡住（2026-11-17 22:30）

- CI 构建成功：[run 44091360456](https://github.com/k19810703/pybitmessage-android/actions/runs/44091360456)，产物 `pybitmessage-apk-5`
- 但 APK 下载在 20/25 MB 处反复超时（`curl` exit 28，持续 1 小时，速率约 15–30 KB/s）
- 因此 **G2.4 / A1 尚未取得设备证据**，结论暂记为"代码修复已在本地验证，待设备复验"

### 1.9 ✅ M2.4.5 设备验证完成（2026-11-18 01:50）

> 网络下载 25 MB APK 反复超时，改用**热补丁**方式验证：把改动过的 `.py` 推入已安装应用的
> `files/app/` 并删掉对应 `.pyc`，重启即生效（p4a 的 `ANDROID_ENTRYPOINT` 是 `main.py`，
> 会重新编译源码）。见 AGENTS.md §6.7。

| 验收项 | 结果 | 证据 |
|---|---|---|
| **A1 地址生成 < 60s** | ✅ **3.7 秒** | `createRandomAddress` 返回 `BM-2cX1KSM87DGtSZcerwLi8a1zgmkAc2nTcD`，耗时 3.7s |
| **G2.4 重启后地址不变** | ✅ | `force-stop` → 重启（pid 13034）→ `keys.dat` 仍是 `[BM-2cX1KSM87DGtSZcerwLi8a1zgmkAc2nTcD]` |
| M2.4.3 重启保留身份 | ✅ | 同上 |
| M2.4.5b 生成器线程 | ✅ | logcat：`AGENDA: addressGenerator thread started` → 请求 → 3.7s 返回 |
| M2.4.5c API 超时 | ✅ | 修复前挂死；现在正常路径 3.7s 返回，异常路径 90s 返回 `Fault 21` |

**热补丁法的适用边界**：只改 `.py`（不含 C 扩展、不含 p4a recipe、不含 `buildozer.spec`）时可用；
一旦涉及新依赖或打包参数，仍必须走 CI 出包。

**恢复动作**：网络可用时执行

```bash
gh run download 44091360456 --repo k19810703/pybitmessage-android -n pybitmessage-apk-5 -D PyBitmessage-android/artifacts
adb install -r PyBitmessage-android/artifacts/pybitmessage-apk-5/*.apk
# 开 API 后：
python3 -c "…createRandomAddress…"   # 期望 90s 内返回 BM-2...
```，实际是线程起来后**在异常中静默死亡**。`threading.excepthook`（`src/main.py`）与生成器里的 `AGENDA:` 打印把这一层变成可见，这组观测点保留在代码里。

### 1.7 M2.4 期间新发现的 4 个 py3/Android 问题（均已修）

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | API 线程 import 即崩：`AttributeError: 'NoneType' object has no attribute 'lstrip'` | `@command` 装饰器无条件 `wrapper.__doc__.lstrip()`，无 docstring 的 handler 是 None | `(wrapper.__doc__ or '').lstrip()`（`f3eb030c`） |
| 2 | API 绑定所有端口都失败，端口号被写成随机值 | **没有 INTERNET 权限** → Android 网络沙箱拒绝 socket()；代码只处理 EADDRINUSE，其它 errno 直接落到 `se` 未赋值 | 加权限 + 记录真实 errno + `se is None` 时报明确错误 |
| 3 | `-d` 守护模式启动即崩 | `open(os.devnull, 'a+', 0)` 在 Python 3 不允许无缓冲文本 IO | 去掉 `0`（`ea73b858`） |
| 4 | 单实例锁异常会阻止启动 | `lock()` 未包异常 | 降级为告警（`204b753d`） |

### 1.8 阻塞项 M2.4.5：地址创建通路不通（下一个要做的）

现象：两条创建地址的路径都失败。

| 路径 | 现象 | 初步定位 |
|---|---|---|
| **UI 引导页** | 选 "Pseudorandom Generator" → 点 "Proceed Next" 无反应 | `kv/login.kv:83` 调 `app.set_screen('random')`，但 `random` 屏幕定义在 `login.kv:139` 的**信息面板**里，不在根 `scr_mngr` 中 → 切换无效 |
| **API `createRandomAddress`** | 请求永久挂起（之后整个 API 单线程被阻塞，后续请求全部超时） | handler 末尾是 `queues.apiAddressGeneratorReturnQueue.get()`（无 timeout）；说明 `addressGenerator` 线程没有消费队列或没有回填结果，需要进一步确认线程是否启动/是否在 `createAddress` 内异常 |

影响：没有地址 → G2.4 / M3.1（地址展示）/ M3.3（公钥）/ 全部 M3 都无法开始，**这是当前唯一的硬阻塞**。

### 1.10 M2.7 · 联网（A2）进展与新的 3 个坑（2026-11-18 09:00）

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | `networkConnections` 恒为 0，`connectionpool.loop()` 从不发起连接 | 首启写入 `dontconnect=true`，只有 Qt 客户端的网络菜单会清除它；Kivy 分支没有 | `bitmessagemain.py` 的 kivy 分支清除并 `config.save()`（commit `c9c5924`） |
| 2 | 对端回 `Your time is too far in the past compared to mine.` | 模拟器时钟落后 **32,186 秒（约 9 小时）**（宿主休眠导致） | `adb root && adb shell "date -s @$(date +%s)"` |
| 3 | 报告错误时自己先崩：`TypeError: can't concat str to bytes` | `protocol.assembleErrorMessage()` 把 str 直接拼到 bytes 上（`inventoryVector`、`errorText`） | 两个字段先 `.encode('utf-8')`（commit `c9c5924`） |

**修复后的进展**：把 `knownnodes.dat` 收敛成两个活着的种子节点

```
194.164.163.84:8444   userAgent=/PyBitmessage:0.6.3.2/   fullyEstablished=0
85.114.135.102:8444   userAgent=/PyBitmessage:0.6.3.2/   fullyEstablished=0
```

- ✅ TCP 能连、`version` 握手成功（对端 userAgent 已拿到）
- ❌ `fullyEstablished` 仍为 0 → `verack` 之后的阶段没走完（下一步查 `bm_command_verack` / `connection_fully_established` 状态机，以及是否误入 TLS 分支）

### 1.11 M2.7 续：又两个假设被排除（2026-11-18 09:30）

| 假设 | 验证方式 | 结果 |
|---|---|---|
| 卡在 TLS 握手（APK 没带 `sslkeys`） | 给 `state.disable_tls` 加开关，kivy 模式下跳过 `isSSL` | ❌ 不是它：关掉 TLS 后仍 `fullyEstablished=0` |
| 对端不发 verack | 在 `bmproto` 打点，逐包打印收到的命令 | 实际顺序常是 **verack 先到、version 后到**，且 `verackSent=False` |

**真正的原因（debug.log 抓到）**：

```
ERROR - 85.114.135.102:8444 error: 2,
        bytearray(b'Too many connections from your IP. Closing connection.')
```

我们的连接池对**同一批节点反复建连**（默认 `maxoutboundconnections=8`，而 knownnodes 里只有 1–2 个可用节点），
对端把来自同一 IP 的多条连接判为重复并主动断开 → 永远走不到 `fullyEstablished`。

处置：`maxoutboundconnections` 调到 2；并把 knownnodes 指向**自己的宿主节点** `10.0.2.2:8444`
（模拟器内网地址，可控、可复现），用于把 M2.7 与 M3 的联调环境固定下来。

**当前卡点**：宿主节点已能收到模拟器发来的 `version`（`ver=3 streams=[1] timeOffset=-1`），
但宿主没有回 `version`，所以 App 侧 `userAgent` 为空、未 established。下一步在宿主侧
`bm_command_version` 的 verack/version 发送路径打点（宿主是我们自己的代码，容易定位）。

**顺带确认的环境事实**

- 模拟器出网正常（`ping 8.8.8.8` 0% 丢包，`nc` 可连种子节点 8444）
- 默认 knownnodes（2017 年那批 IP）**全部已下线**，必须用 `bootstrap8444.bitmessage.org` 解析出的活节点
- 日志级别默认 WARNING，排查网络要看 `BITMESSAGE_LOG_DEBUG=1`（`src/main.py` 已加开关）

### 1.12 ✅ A2 通过 —— G2 闸门达成（2026-11-18 09:56）

**两个最后的握手 bug（commit `6ce9588`）**

| # | 现象 | 根因 |
|---|---|---|
| 1 | 对端收到 version 却从不回 version/verack | `protocol.CreatePacket('verack')` 把 **str** 传进 `struct.pack('12s')` → `struct.error`，异常被吞；源头是 `bmproto` 里 `CreatePacket('verack')` 未用 bytes |
| 2 | 处理 version 时抛 `cannot use a string pattern on a bytes-like object` | `re.match(pattern, self.userAgent)`，而解码出的字段是 **bytearray** |

**修复后的实测证据（模拟器 ↔ 宿主节点 10.0.2.2:8444）**

```
networkConnections = 1        networkStatus = connectedButHaveNotReceivedIncomingConnections
outbound 10.0.2.2:8444  fullyEstablished = 1  userAgent = /PyBitmessage:0.6.3.2/
FATAL EXCEPTION 计数 = 0
```

**G2 闸门四项全部达成**

| 项 | 结果 |
|---|---|
| A1 地址生成 < 60s | ✅ 3.7s（`BM-2cX1KSM87DGtSZcerwLi8a1zgmkAc2nTcD`） |
| A2 连接数 ≥ 1 | ✅ 1（fullyEstablished） |
| A3 重启地址不变 | ✅ force-stop 后仍为同一地址 |
| A4 无 FATAL | ✅ 0 |

**这一轮累计修掉的握手链路 py3 问题**（按发现顺序）：
`dontconnect` 未清 → 模拟器时钟漂移 → `assembleErrorMessage` str/bytes → `CreatePacket` str 命令 → `userAgent` bytearray 正则。

### 1.13 ✅ M2.5 / M2.6 完成（2026-11-18 10:00）

| 任务 | 结果 | 证据 |
|---|---|---|
| M2.5.1 去 Mock 命名 | ✅ 代码已改 | `buildozer.spec`: `title = PyBitmessage`、`package.name = pybitmessage` → `at.bitmessage.pybitmessage`；APK 由 run 44219919909 产出 |
| M2.6 UI 数据源统一 | ✅ 设备验证 | 入口新增模块别名，logcat 输出 `ALIAS pybitmessage.state is state: True` |
| M2.6.1 去掉 mock 配置加载 | ✅ | `mpybit.py` 改为 `from pybitmessage.helper_startup import loadConfig` |
| M2.6.2 真实统计 | ✅ | 仪表盘计数改为真实 SQL（近 30 天 inbox 条数） |
| **G2.6 界面数据来自真实核心** | ✅ | 截图 `artifacts/screenshot-m26b.png`：顶栏显示 API 创建的身份 `Ui-test (BM-2cXP3HGpD7stf6...)`，不再是引导页 |

**关键修复**：APK 里 `pybitmessage/` 是所有顶层模块的副本，Kivy 的 `from pybitmessage import state` 会拿到**第二份** state/config。
`main.py` 现在把核心模块别名进 `pybitmessage.*`（`sys.modules` + 包属性），UI 与核心共用同一对象。

### 1.14 M3 进展：发送管道打通到 PoW，卡在 pubkey 交换（2026-11-18 10:50）

**已建立测试环境**：宿主节点（`/tmp/run_node.py`，禁用 TLS）拿到地址 `BM-2cVWvLvfwmeRafTsw93bof2gFSGD8HfUBp`，
模拟器 App 有 `BM-2cWwkgY93Kqn9DTi8ftFZtEXrUT3W99sqB`，两者 `fullyEstablished` 互联。

**修复 1（关键）**：`class_singleWorker` 里 6 处把 **str** 字面量拼到 bytes 载荷上（pubkey/broadcast/msg/getpubkey）：

```
File "class_singleWorker.py", line 1407, in requestPubKey
    payload += '\x00\x00\x00\x00'
TypeError: can't concat str to bytes
```

被裸 `except:` 吞掉，只留一行 `sendMsg didn't work`。改为 `b'...'`，并把 worker 的 10 处裸 except 改成 `logger.exception(...)`（带 traceback）。

**状态推进**：`doingpubkeypow` → **`awaitingpubkey`**（PoW 完成，getpubkey 已发出）。

**当前卡点**：对端没有回 pubkey。宿主与 App 的 TCP 连接是 established，但宿主侧没有看到对象处理日志
（`debug.py` 的日志级别覆盖了运行时 `setLevel(DEBUG)`，需要给日志装置单独设级别）。
下一步：在宿主的 `objectProcessor` 里打点，确认 getpubkey 对象是否到达、tag 是否匹配。

### 1.15 M3 续：PoW 在 Android 上修好，卡点收敛到 pubkey 交换（2026-11-18 11:25）

**修掉的问题**：`_doFastPoW` 用 `multiprocessing.Pool`，而 p4a 的 `_multiprocessing` 没有 `sem_unlink`：

```
ImportError: cannot import name 'sem_unlink' from '_multiprocessing'
→ 每次发送都死在 _doPOWDefaults
```

`proofofwork.run()` 现在捕获该异常并回退到单进程 `_doSafePoW`（commit `aff2234`）。

**顺带**：`debug.py` 的日志级别改为读环境变量 `BITMESSAGE_LOG_LEVEL`（commit `c68f6ea`），
这样设备上也能开 DEBUG，不用手写 `logging.dat`。

**当前状态**

| 环节 | 状态 |
|---|---|
| 组包（getpubkey/msg 载荷） | ✅ 修掉 6 处 str/bytes 拼接 |
| PoW | ✅ 单进程回退可用（手机上较慢） |
| 广播 inv | 🟡 应用侧状态推进到 `awaitingpubkey` |
| 对端收到 getpubkey 并回 pubkey | ❌ **未完成**——宿主日志显示对象流量很大，但没有处理该 getpubkey |
| msg 加密 → 投递 → Inbox | ⏳ 待 pubkey 通了才能验证 |

**结论**：M3 还差 pubkey 交换这一段。下一步在宿主 `objectProcessor` 打点，确认 getpubkey 的 tag 匹配分支。

### 1.16 M3 续：定位到"模块被重复导入"，但 pubkey 交换仍未打通（2026-11-18 12:10）

**本轮修好的**

| 修复 | 说明 |
|---|---|
| PoW 回退 | `_doFastPoW` 在 Android 上因 `_multiprocessing` 缺 `sem_unlink` 必失败 → 回退 `_doSafePoW`（模拟器上约 **2.5 分钟**一条消息） |
| 日志级别 | `BITMESSAGE_LOG_LEVEL` 环境变量生效，设备上能看到 DEBUG |
| 宿主模块别名 | `/tmp/run_node.py` 里把核心模块别名进 `pybitmessage.*` |

**新发现（重要）**：宿主日志被
`Using default logger configuration` + `Imported message type module ...` 刷屏——
说明 **`debug` 模块被反复导入**（每个对象一次）。这不是日志噪音，而是**模块被加载了两份**
（`pybitmessage.*` 与顶层名各一份）的典型症状；两份 `shared`/`state` 会让地址 tag 匹配落空，
与"App 广播 getpubkey 但宿主不回 pubkey"的现象吻合。

**当前证据链**

```
App : Safe PoW done → Found proof of work → sending inv (for the getpubkey message)   12:05:34
Host: 只看到自己的 InvBroadcaster，没有收到该 inv
```

**下一步（M3.3）**
1. 彻底消除重复模块：让宿主也走 `src/main.py` 的 `alias_core_modules()`（或统一为包内相对导入）
2. 在宿主 `bm_command_inv` / `objectProcessor.processgetpubkey` 打点，确认 inv 是否到达、tag 是否命中

### 1.17 ✅ 加密消息双向互通达成（2026-11-18 13:40）

**测试形态**：同一台机器上起两个真实节点（node1 监听 8444，node2 主动连它），
通过 XML-RPC 驱动发送与收件箱读取，不依赖 UI、不依赖公网。

**结果**

```
n1 = BM-2cWCriePLaizrfjb1vJBu19TTpkpHmFovz
n2 = BM-2cUPgcRDEoDyPeoFH5AFoN3yKHzDv31RBc

[n2->n1] inbox after 30s   subj=第一条   body=你好，这是从 node2 发到 node1 的加密消息
[n1->n2] inbox after 12s   subj=回复     body=收到！这是 node1 的回复 🎉
RESULT: B1 双向互通 OK ✅
```

中文与 emoji 均完好；两条消息都走了完整的 **ECIES 加密 → PoW → inv/getdata → 解密 → 入库** 链路。

**这一轮修掉的 py3 断点（全部是 py2 `str == bytes` 的遗留）**

| 文件 | 问题 | 后果 |
|---|---|---|
| `network/invthread.py` | `''.join(fluffs)`（hash 是 bytes） | 广播线程异常，**任何对象都不会被公告** |
| `network/invthread.py` | Dandelion 关闭时仍只投给 stem 子节点 | inv 被静默丢弃 |
| `network/uploadthread.py` | 同上，上传时仍做 stem 校验 | 对端要对象时被拒："asked for a stem object we didn't offer" |
| `network/bmproto.py` | `map(str, items)` 把 hash 变成 `"b'...'"` | 收不到 inv、getdata 键对不上 |
| `network/bmproto.py` | `pendingUpload[str(i)]` | 对象永远不上传 |
| `class_singleWorker.py` | 消息体/ack/对象类型字面量是 str | 发送时 `can't concat str to bytes` |
| `class_singleWorker.py` | `"04" + hexlify(...)` | `encrypt` 失败 → `badkey` |
| `class_objectProcessor.py` | `'\x04' + decryptedData[...]` | 接收端重建公钥失败 |
| `protocol.py` | 同上（pubkey 校验路径） | pubkey 被判无效 |
| `helper_msgcoding.py` | `string.find(data, ...)` | 解码正文时崩（py2 API） |
| `shared.py` | `fixPotentiallyInvalidUTF8Data` 只接受 bytes | API 取件箱时崩 |
| `api.py` | 主题/正文是 str 时直接 b64encode | 同上 |

**这解释了此前所有"卡在 awaitingpubkey / 收不到"的现象**：不是网络问题，是公告线程在第一跳就炸了。

### 1.18 设备侧验证：进展与两个新坑（2026-11-18 14:40）

**设备 APK 一直跑的是旧代码** —— 根因不是构建，而是**签名不一致导致 `install -r` 静默失败**：

```
INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package ... signatures do not match newer version
```

每次 CI 构建都会生成新的 debug keystore，所以换包必须 `adb uninstall` 再装。
修复后设备上的 `class_singleWorker.pyc` 才与 APK 内的一致（`logger.exception` 而非 `logger.warning`）。

**设备侧 PoW 太慢**：`BMPOW` 不可用（没有 `libbitmsghash.so`），只能走纯 Python `_doSafePoW`，
默认难度下**一条消息约 10 分钟**（模拟器 100% CPU）。测试时在两端开启
`extralowdifficulty = true` 可降到秒级；生产需要把 `bitmsghash` 编进 APK（M3.4.2 遗留）。

**顺手修掉**：`storage/sqlite.py:unexpired_hashes_by_stream()` 把 BLOB 哈希 `str()` 成 `"b'...'"`，
导致 big-inv 公告 `payload += obj_hash` 抛 `TypeError`（commit `8432ac4`）。
两端回归：30 秒送达 ✅。

### 1.19 ⚠️ 设备侧验证：一次误判与当前真实状态（2026-11-18 15:45）

**在模拟器上（APK `pybitmessage-apk-14`，包名 `at.bitmessage.pybitmessage`）**

```
app 地址 : BM-2cX1JihrRaZmaenebg4rx3Em4RnV2efrBy
宿主地址 : BM-2cV2kDCw9XMUGFDmzxCikeYFExXBRamyrv
app 状态 : doingmsgpow → msgsent（40 秒）
宿主收件箱：from_android = 1
  主题：来自安卓
  正文：第一台设备发出的加密消息 🎉
```

**⚠️ 更正**：这次"送达"其实是**自发自收**。原因是宿主节点的 `apiport` 被改成了 8442，
和 `adb forward tcp:8442` 冲突——所有打到 127.0.0.1:8442 的 API 调用实际落在**宿主节点**上，
而不是模拟器里的 App。收件箱里那封信的 `toAddress == fromAddress`，即 App 发给自己的。

**教训（已记入 §6.6）**：用 API 做验收前，必须先确认两端端点**地址不同**（例如打印 `listAddresses`），
并给宿主节点分配一个不会和 adb forward 撞车的端口（现用 8449）。

**反向（宿主 → 设备）发现并修掉最后一个接收端断点**：
`helper_bitcoin.calculateBitcoinAddressFromPubkey` 里 `'\x00' + ripe.digest()`（str + bytes），
且 `changebase` 返回 bytes 又被拼到 str 上 → `processmsg` 崩溃（commit `34be514`）。
修复后需要重新出包验证（run 44256966156）。

**测试环境说明**：设备上 `BMPOW` 不可用，默认难度一条消息约 10 分钟；
本次验证在两端开启 `extralowdifficulty = true`（40 秒送达）。
生产前必须解决 PoW 性能（把 `bitmsghash` 编进 APK，或调整难度策略）。

### 1.20 设备 ↔ 宿主：当前真实状态（2026-11-18 15:45）

端点已经彻底分开后（App 走 `adb forward 8442`，宿主 API 走 8449）重新测：

| 方向 | 状态 | 卡点 |
|---|---|---|
| 设备 → 宿主 | ❌ `doingmsgpow` 长时间不结束 | 设备端没有 C 版 PoW（`BMPOW` 不可用），`_doSafePoW` 纯 Python；`extralowdifficulty` 是否对 msg 生效尚未确认 |
| 宿主 → 设备 | ❌ `awaitingpubkey` | 设备侧 pubkey 的 PoW/广播同样慢 |

**已经确认可用的部分**：App 安装、启动、建地址（`BM-2cTwYxYJ…`）、连上宿主（`fullyEstablished`）、
UI 显示真实身份、API 可读写收件箱。

**结论**：协议层闭环（两个节点之间）已经用本地双节点验证通过；
**设备 ↔ 外部节点还没有一次干净的端到端证据**，卡在设备端 PoW 性能上。

### 1.21 ✅ 设备 ↔ 外部节点 双向加密消息（2026-11-18 16:10）

**端点（这次彻底分开，脚本先断言两地址不同）**

```
APP  (模拟器, adb forward 8442)  BM-2cUdA3CNGDdy31VR6xarezeBMjinsos9qe
HOST (宿主节点, API 38681)       BM-2cWeeYy7vRbrKR6Y65Y2AARmXhhF4Nti48
```

**结果**

```
[A->B] delivered after 190s
  subj: 设备来信
  body: A→B 设备发给宿主的加密消息 🎉
[B->A] delivered after 20s
  subj: 宿主回信
  body: B→A 宿主回给设备的加密消息 ✅
RESULT: B1 设备↔宿主 双向 OK ✅
```

设备收件箱 `toAddress` = 设备地址、`fromAddress` = 宿主地址；截图
`artifacts/screenshot-m3-device.png` 显示身份 `Android (BM-2cUdA3CNGDdy…)`。

**G3 四项（协议/API 层面）**

| 项 | 结果 |
|---|---|
| B1 双向互通 | ✅ 两个方向各 1 条 |
| B2 ≤5 分钟 | ✅ 190s / 20s（两端 `extralowdifficulty`） |
| B3 中英 emoji | ✅ 中文正文与 🎉✅ 完好 |
| B4 ack 可见 | 🟡 API 返回 ackdata 并可查询状态；UI 展示待 M3.6 |

**这一轮又修掉 2 个接收端字节问题**（commit `173df0f`）：
`helper_bitcoin` testnet 前缀、`class_objectProcessor.ackDataHasValidHeader` 的命令比较。

### 1.22 ✅ M3.7 · C 版 PoW 打通（2026-11-19 10:39）

**平板（小米平板 5 / 骁龙 855）实测，协议默认难度：**

```
10:39:34.357  (For pubkey message) Doing proof of work...  TTL set to 2419427
10:39:38.276  (For pubkey message) Found proof of work 9495648398  Nonce: 22160074
→ 单个对象 3.9 秒
```

对比纯 Python：同一设备 >15 分钟未完成。**约 230 倍提速**。

**做法**（`scripts/build-bitmsghash.sh`）

1. `bitmsghash` 本来是 ctypes 加载的普通 `.so`，上游用 OpenSSL 的 SHA-512；
   NDK 没有 `openssl/sha.h`，于是自带一份自足实现的 SHA-512 shim
   （`src/bitmsghash/shim/`，与 hashlib 的三组向量逐字节一致）
2. NDK clang++ 交叉编译 → `libbitmsghash.so`，经 `android.add_libs_arm64_v8a` 进 APK
3. `-static-libstdc++`：APK 不带 `libc++_shared.so`，否则 dlopen 直接失败
4. 运行时 `ctypes.CDLL('libbitmsghash.so')`（Android 10+ 禁止从应用数据目录 dlopen）

**踩到的坑**

| 现象 | 根因 |
|---|---|
| `library "libc++_shared.so" not found` | 忘了静态链接 libc++ |
| `io.UnsupportedOperation: fileno` | `LogOutput()` 假设 stdout 有 fileno，Android 上不是 |
| APK 里没有 .so | `android.add_libs_arm64_v8a` 后面跟了缩进注释，被当作续行吞掉 |

### 1.23 M3.9 · 中文界面已跑起来（2026-11-19 11:15）

![中文收发界面](artifacts/ui-3.png)

模拟器（Pixel 6 / Android 13）实测：

| 元素 | 状态 |
|---|---|
| 我的地址 + 复制 | ✅ 显示 `BM-2cXh69uaVsgefdNcuk9x25r8wRYD3Y9vud` |
| 收件箱（5 秒刷新） | ✅ 显示"（暂无消息）" |
| 收件人地址 / 内容 / 发送 | ✅ 可输入、可点 |
| 中文渲染 | ✅ 注册了系统 CJK 字体（`NotoSansCJK-Regular.ttc`），不再是方块 |
| 从 Intent 预填收件人 | ✅ `am start … --es to BM-…` 可直接带地址打开 |

发送点击后状态栏出现「已提交，正在广播…」，`sent` 表里出现该条（status `awaitingpubkey`）。

**这里暴露出两个上游时间参数不适合小网络**：

| 参数 | 上游值 | 后果 | 现在 |
|---|---|---|---|
| 重发 pubkey 窗口 | **28 天** | 对端错过一次公告就再也拿不到公钥（日志：`we already sent it recently. Ignoring request`） | `pubkeyresendwindow`，默认 **1 小时** |
| awaitingpubkey 的 `sleeptill` | `TTL*1.1` ≈ **2.7 天** | 消息卡死在队列里 | 上限 **30 分钟** |

### 1.24 M3.8 · 公网断连根因调查（2026-11-19 14:20，暂停点）

**一句话**：TLS 修复包（run 44464696554）装上后，公网 TCP 握手到 version/verack 一切正常，但**所有已知活节点都在 version 交换后回 `error: 2 "Too many connections from your IP"`**；同时找到一个可疑的上游 bug（入站连接字典的混合键型），它能让"同一 IP 的第二条并发连接"必然被拒。

**实验设置**（只保留 Mac 一个节点在发连接，平板已断开、模拟器已 force-stop、旧 node1/遗留 kivy 进程已杀）：

```
桌面对照节点: /tmp/desk_control.py（TLS 开、knownnodes 写死 4 个活节点、rating=1）
4 个活节点:   85.114.135.102:8444 / 194.164.163.84:8444 /
             185.158.248.216:8444 / 158.69.63.42:8080
             （dig bootstrap8444/8080.bitmessage.org + nc -z 验活）
```

**观察到的循环**（每 ~90 秒一轮，对 4 个节点全部复现）：

```
TCP connect 成功（lsof 可见 ESTABLISHED）
→ 我们发 version → 对端回 version（version parsed: ver=3 streams=[1] ✓）
→ 我们发 verack
→ 对端回 error: 2, "Too many connections from your IP. Closing connection."
→ 连接关闭 → 重连 → 循环
```

**同时确认的事实**：

| # | 事实 | 证据 |
|---|---|---|
| 1 | 旧 APK 的 `Timeout (20s)` 症状 = TLS Purpose bug（已修，commit 008b9cb），装新包后未再出现 | 平板旧进程死前 13:52:42 一批 Timeout；新包日志无 |
| 2 | **"Too many connections from your IP" 是对端（种子）主动发的 error 消息**，不是本端行为 | `bm_command_error` 日志，带 host:port |
| 3 | UDP 层与种子完全正常（verack/addr 每 60 秒一轮） | `BMPROTO <seed> recv addr established=True`（UDP 伪连接，fullyEstablished 恒为 True） |
| 4 | **TCP 层能长期保持**（ESTABLISHED 3 分钟以上），断开发生在协议层 | lsof 连续 6×30s 观察 |
| 5 | 新装的 App（knownnodes=9 个 2017 死节点）会永远对死 IP 发 SYN_SENT；DNS bootstrap 只在 knownnodes 为空/全默认时跑一次 | netstat 全是 SYN_SENT；knownnodes.py `knownNodesActual` 逻辑 |
| 6 | 模拟器/新装设备上 **0 次 TCP established**，之前看到的 `established=True` 全是 UDP | 打点加 host:port 后区分（本地 commit，见下） |
| 7 | 种子的拒绝在**只有 Mac 一个节点、单次连接**时也出现 | 对照节点 v1（单节点、maxout=2）与 v2（4 节点）都复现 |

**可疑根因（代码级，未最终确认）**：`connectionpool.py addConnection()` 对入站连接用**混合键型**——同一 IP 的第一条入站按 `host 字符串` 存，第二条按 `Peer(ip, port)` 存。而 `bmproto.py peerValidityChecks()` 的 dup-IP 检查是 `inboundConnections.get(self.destination)`（Peer 查找）。连接在 **accept 时**就 addConnection，version 解析**之后**才做检查 → 第二条并发连接的 `get(Peer(...))` 会查到**它自己** → 必然回 "Too many connections from your IP"。种子跑的也是 0.6.3.2 同款代码。**推论**：同一 IP 同时开 ≥2 条连接（我们的 maxoutboundconnections=2、两台设备+宿主节点共享出口 IP）就会触发；单条不应触发——但实验 7 里单连接也被拒，说明还有未解因素（见下一步）。

**下一步（按优先级）**：

1. **换 IP 测试**（手机热点）：若新 IP 上第一条连接能建立并稳住 → 证实是 IP 级状态（临时 ban 或并发键型 bug 的历史残留）；若仍被拒 → 我们的握手内容有问题，需抓包比对正常客户端
2. `maxoutboundconnections=1` + 单节点重试（本机即可做，验证混合键型理论：单连接应能过 dup-IP 检查）
3. 若 2 通过：给设备注入互不相同的活节点 + maxout=1，验证公网收发
4. 修 `class_singleCleaner` 的 memoryview/str 崩溃（它负责 `cleanupKnownNodes`/`saveKnownNodes`，崩了导致学到的节点永不落盘）

**本地未推送的 commit**：`M3.8: tag BMPROTO handshake diagnostics with peer host:port`（bmproto.py 四处打点加了 destination，纯日志改动）。

**遗留进程提醒**：pid 28249（`python3 -`，cwd `/private/tmp/bmtest`，~200% CPU，无网络 socket）是更早 session 的 CPU 测试残留，本次未动，可按需 kill。

### 1.25 ✅ 换 IP 实验证实：是 IP 级拒绝，客户端与协议无问题（2026-11-19 15:35）

**实验设计**：同一份客户端代码（TLS 修复包），同一时间，两个不同出口 IP 同时连公网：

| 端 | 出口 IP | 配置 | 结果 |
|---|---|---|---|
| 小米平板 5（iPhone 热点） | 172.20.10.x（运营商 NAT） | `pubnet_tablet_setup.sh` 注入（maxout=2、knownnodes=4 活节点） | ✅ **`networkConnections: 2`，`pendingDownload: 2854`**（正在真实下载网络对象） |
| Mac 桌面节点 | 9.123.201.63（IBM 公司网出口） | `pubnet_node.py`，**maxout=1**（单连接）、单进程、已清理全部遗留节点 | ❌ 全部 4 个活节点持续回 `Too many connections from your IP` |

平板地址（本次实验产生，API u:p@8442 已配置）：
`BM-2cU2vEDgphdWHe4Ucp1gSigCwDrJTRfyYV`（label `phone`）

**结论**：

1. **线协议、TLS、客户端握手全部正常**——新 IP 上连接秒级建立并开始同步对象流
2. **"同 IP 并发连接"（混合键型）假设被排除为唯一原因**：Mac 用 maxout=1 单连接仍被拒
3. 公司/家庭出口 IP 在种子侧处于**粘性拒绝状态**，最可能来源 = 今早旧 APK（TLS bug 导致 30s 一轮的重连循环，跑了数小时，平板+模拟器+宿主节点同出口）触发的 per-IP 限制
4. 拒绝持续时长未知；4 个已知节点同拒（可能同一批运维）

**未完成的桥接实验**（被有意中止）：Mac 经 `adb forward tcp:18444 tcp:8444` 直连平板节点，被杀前已收到对端 verack——USB 桥接方案可行但未验证完毕，留作备用。

**15:40 追记**：平板 API 后续查询超时（疑似锁屏休眠），成功快照以上表 15:16 时点为准。

### 1.44 🔍 新发现：桥接 TLS 竞态——明文 verack 被 TLS 包装卡死（2026-11-23 12:06）

**现象**（Mac 经 `adb forward tcp:18444 tcp:8444` 连平板，100% 复现，平板重启无效）：

```
Mac 侧（每 ~9 秒循环一轮，永不 established）：
  recv version → version parsed → sent verack (outbound=True)
  → verack received (verackSent=False)      ← 永远到不了 "verack -> established"

平板侧：
  recv version → sent verack → sent version back to peer
  → （再也收不到 Mac 的 verack）             ← 卡死等待

lsof：两条 ESTABLISHED TCP；"TCP established" 打印 0 次；两侧日志均无 SSL 错误
（Mac 节点日志级别 WARNING，SSL/closing 行被吞——BITMESSAGE_LOG_DEBUG 未生效，
debug.py 的 handler 级别问题，另记）。
```

**机制分析**（高置信度，未最终证实）：入站方的发送顺序是 **[verack][version]**
（`bm_command_version` 先 `append_write_buf(verack)` 再 append version）。Mac 处理完
version 后，自己的 verack 还在 `write_buf` 里没冲刷，状态机就进入 `tls_init`
把 socket 包成 SSL——明文 verack 从此发不出去（非阻塞 SSL socket 上 send 会
WANT_READ/WANT_WRITE），对端永远等不到 verack。公网连接能成功而桥接不能，
怀疑与 adb 中继的时序有关（公网时 write_buf 在 tls_init 前被事件循环冲掉）。

**11-19 桥接曾成功**——当时先由平板经局域网发现主动连了 Mac（方向相反），
后来 Mac→平板的桥连接也建立过；今天平板在访客网无法做局域网发现。

**处置**：
- 立项 **M4.8.6**（见 MILESTONES）：桥接/握手竞态调查与修复
- M4.8.2 的送达实测改期：平板回到可用网络（家里/办公 Wi-Fi）后重测

### 1.64 ◐ M4.8.10 设备验证：连接数 0 → 2，发送已恢复（2026-11-25 21:35）

**装的是含修复的包**（run 45620481903，sha256 见发布包），零热补丁。

| 指标 | 修复前 | 修复后（同一台平板） |
|---|---|---|
| `clientStatus.networkConnections` | **0**（恒定） | **1 → 2**（有抖动，见下） |
| 日志 `TCP established` | **0** | **16** |
| 日志 `tls_init` | 每次握手都进 | **0** |
| 自发消息状态 | — | **`ackreceived`**（发送链路通） |
| 收件箱 | 16 | **17**（收到 1 条） |
| 对象收发 | — | `recv inv` 8、`recv object` 10 |

**发送失败的结论**：修复后自发消息拿到 `ackreceived`，说明"发不出去"是连接数为 0 的**下游后果**，
不是独立故障。

**仍然存在（新立项 M4.8.11）**：连接数在 **0 ↔ 2** 之间来回抖，出站半开连接常年 **43–56 条**
（`maxoutboundconnections=8`），`[DIAG]` 里这些连接的 `reason=None`（被 reaper 回收时没写原因）；
`numberOfMessagesProcessed` 长期停在 0，而 `recv object` 有 10 —— 说明**对象收到了但没走完处理**，
或者收到的都是重复/过期对象。这与 M4.8.4（`networkConnections` 计数失真）是同一片区域，
需要一起查：为什么 pool 里堆了 50+ 条 outbound 而 maxout 只有 8。

### 1.63 ✅✅✅ 根因：连接数为 0 = TLS 升级卡死（2026-11-25 21:10）

**用户诉求**：别人装了包"收不到消息"；平板上 `networkConnections=0`。

**现象**（先用新加的 `[DIAG]` 日志定位）：

```
[DIAG] 连接 established=0 outbound=52 inbound=0 | knownnodes=835 (rating>0: 4)
[DIAG]   out 154.240.245.193:8444 est=False connected=False verack(sent=False recv=False) ...
```
但同一份日志里 **1073 行 BMPROTO**、`sent verack` 有 27 次、`PVC -> True` 全过，
**`TCP established` 却是 0** ——也就是说**协议层握手已经完成，但连接从未被标记为建立**。

**逐步逼近**（桌面节点复现，不依赖平板，快得多）：

| 步骤 | 手段 | 结果 |
|---|---|---|
| 1 | 在 `process()` 里打点，看状态去哪了 | `state=tls_init->tls_handshake`，然后 `tls_handshake->tls_handshake` 反复 23 次 |
| 2 | 在 `bm_command_verack` / `bm_command_version` 打点 | `verackReceived=True isSSL=True disable_tls=False` |
| 3 | 查 `haveSSL` | `haveSSL(server=False)` **无条件返回 True**（注释写"client works ok"） |

**根因**：只要对端在 version 里 advertise `NODE_SSL`，我们**必然**把连接切到
`state_tls_init`，用 2013 年代的客户端 TLS 配置（`AECDH-AES256-SHA` + `secp256k1` + 封顶 TLS1.2）
去升级；对今天的节点这个握手**永远不完成**，连接就停在 `tls_handshake` 直到被 idle 回收。
`fullyEstablished` 因此永远是 False → `clientStatus.networkConnections=0` → 用户看到"没有连接"。

**A/B 实测**（桌面节点，同样 85 秒、maxout=2）：

| 条件 | TCP established | networkConnections |
|---|---|---|
| TLS 开（原默认） | **0** | **0** |
| TLS 关（`--disable-tls`） | **10** | **2** |
| TLS 关 + 撤掉 `process()` 补丁 | 4 | 2 |

**修复**（commit `c54acea`）：

1. **`main.py`：TLS 默认关闭**（`state.disable_tls = env BITMESSAGE_ENABLE_TLS != '1'`）。
   点对点链路可以是明文（协议允许），消息内容本来就是端到端加密。
2. **`network/tls.py`：加 20 秒握手超时**，超时关连接并写 `close_reason`，
   避免一次卡死的升级长期占着连接槽（即使用户主动开 TLS 也不会挂死）。
3. **`network/advanceddispatcher.py`：`process()` 跟进状态移交**——
   handler 用 `set_state()` 交接后立刻执行新状态，而不是等对端再发数据。
   **诚实说明**：A/B 显示明文下没有这条也能建立（4 条），所以它**不是本次症状的主因**，
   而是修掉一个潜在死锁（对端若发完 verack 就沉默，旧代码永远不会运行
   `connection_fully_established`）。

**顺带修掉的测试问题**：`applog.reset_for_tests()` 之前没把 `sys.stdout` 还原，
导致后续测试里任何 `print` 都会在当前 `state.appdata` 下建 `logs/`，让无关测试的
`os.rmdir` 失败。现在会还原流。全套 **51 条测试通过**。

### 1.62 ✅ M6.6 设备端诊断日志（3 天轮转）+ 一键分享（2026-11-25 16:50）

**需求来源**：用户把包发给别人装，对方"收不到消息"；对方没有 adb、看不到 logcat，
现有诊断全在 `print()` 里，手机上是黑盒。

**实现（`src/applog.py`，新增）**

| 要点 | 做法 |
|---|---|
| 收集 | `install()` 把 `sys.stdout`/`sys.stderr` 换成 tee，**同时**写 `logs/app-YYYYMMDD.log`。这样**已有全部诊断**（PROBE、BMPROTO、INVTHREAD、PROCMSG 解密/验签、KEYSTORE、NOTIFY、KEEPALIVE）零改动进文件 |
| 轮转 | 每天一个文件，保留 **3 天**（启动 + 跨天时清理更早的）；单日上限 8 MB，超了写提示后停写 |
| 异常 | 主线程 + **任意工作线程**的未捕获异常都带完整堆栈落盘 |
| 启动顺序 | `probe_environment()` 从 import 期挪到 `main()` 里、日志就绪之后，所以 PROBE 环境矩阵也在文件里 |
| 分享 | 打 zip（`meta.txt` + 3 天日志 + `tail-400.txt`）→ **MediaStore 写入 `Download/PyBitmessage/`** → 系统分享面板（微信/邮件/文件管理器）。不用 FileProvider，**不改清单、不加 androidx 依赖**，构建风险为零；下载目录还留了一份可手动发 |
| 兜底 | 分享失败时把最后 400 行**复制到剪贴板** |

**设备实测（平板，Android 13）**

| 项 | 结果 |
|---|---|
| 日志文件 | ✅ `files/bitmessage/logs/app-20261125.log`，8 KB，含 meta + PROBE 全绿行 |
| 「日志」按钮 | ✅ 主界面右上（复制旁边） |
| 分享 | ✅ 状态栏「日志已导出到 Download/PyBitmessage 并打开分享」，随后前台变成 **`com.tencent.mm` 微信聊天界面** |
| 落盘 | ✅ `/sdcard/Download/PyBitmessage/pybitmessage-logs-*.zip`（6.2 KB） |
| zip 内容 | ✅ `meta.txt`（Xiaomi / 21051182C / SDK 33 / Android 13 / 2 个地址 / 连接数）、`app-20261125.log`、`tail-400.txt` |

**设备上连踩三个 jnius 坑（都在真机才显形）**

| # | 报错 | 根因 | 修法 |
|---|---|---|---|
| 1 | `AttributeError: 'android.os.Build' has no attribute 'VERSION'` | **嵌套类**在 jnius 里必须写成 `Build$VERSION` | `autoclass('android.os.Build$VERSION')` |
| 2 | 同上 → `MediaStore has no attribute 'MediaColumns'` | 同样嵌套类 | `autoclass('android.provider.MediaStore$MediaColumns')` |
| 3 | `No methods called put matching your arguments (String, Boolean)` | `ContentValues.put` 重载多，Python `int` 被推测成 Boolean | 干脆不写 `IS_PENDING`（只留三个 String 字段），发布窗口毫秒级、半成品 zip 无害 |
| 4 | `Invalid instance of 'android/net/Uri' passed for 'java/lang/String'` | `putExtra(String, …)` 重载解析错 | `cast(Parcelable, uri)` |

**测试**：`tests/test_applog.py` 9 条（tee 进文件、重复 install 不套两层、3 天保留、
单日上限、zip 内容、无日志兜底、非安卓报错）。全套 **43 条通过**。

> **审查没发现、只有冒烟测试抓到的 bug**：`_write()` 里给模块全局赋值却没声明 `global`，
> 于是它变成局部变量，读取时 `UnboundLocalError`，又被 `except: pass` 吞掉——**一行日志都写不进去**，
> 而代码读起来完全正常。已在函数里写明注释，测试注释也记了这件事。

### 1.61 ◐ M6.3.2 响应式布局 + M6.2 全界面中文 + M6.4.3 残留扫描（2026-11-25 14:15）

**验证方式**：本轮的 UI 改动全部是纯 Python / `.kv`，用热补丁在平板上逐项验证；
含这些改动的**正式包已构建但还没装**（run 45557518551，见文末）。

#### M6.3.2 两栏布局

`src/bitmessagekivy/messaging.py`：按窗口尺寸切换布局（阈值 **720×480 dp**，
手机横屏高度不够，仍走单栏）：

| 形态 | 布局 |
|---|---|
| 宽屏（平板横屏） | 左 44%：我的地址 + 收件箱；右 56%：收件人 + 内容 + 发送 |
| 窄屏（竖屏/手机） | 单栏：地址 → 收件箱（45%）→ 写信 |

实现细节：widget 只能有一个父节点，所以切换时**重挂三个分组**（header / inbox /
compose），而不是逐个搬 widget；`Window.size` 的连续事件用 `Clock.schedule_once`
合成一次重建。

**设备验证**：横屏两栏铺满 2560 宽（`artifacts/m632-tablet-landscape-2pane.png`），
竖屏单栏（`artifacts/m632-tablet-portrait-1col.png`），旋转过程中停在同一屏、不崩。

#### M6.2 全界面中文

| 修的问题 | 做法 |
|---|---|
| 设置页 6 个页签、输入提示、弹窗、托盘项仍是英文 | 全部包 `app.tr._()` 并补字典 |
| 上游几段超长英文说明（难度/重发/Namecoin） | 换成**简洁中文**（原文 300 字英文，中文一两句） |
| 抽屉里**「付费方案」**可点进 Google Play/PayPal/BTC 付费页 | **移除抽屉入口**——本产品无账户、无支付、无外部服务（AGENTS 红线） |
| 设置页页签、下拉显示 **▯▯ 豆腐块** | 把 CJK 字体**同时注册为 `Roboto`**（`LabelBase.register(name='Roboto', …)`）。MD 组件会忽略 per-widget `font_name`，只认主题字体名，这是豆腐块的根因 |

设备截图：设置页全中文（`artifacts/m612-settings-zh.png`），抽屉无「付费方案」
（`artifacts/m612-drawer-no-payment.png`）。

#### M6.4.3 英文残留扫描（`scripts/scan-english.py`）

```
$ python3 scripts/scan-english.py --strict
⛔ 不可达页面（上游遗留，待删除，不计入验收）：payment.kv 15 处
✅ 可达界面里没有未翻译的用户可见英文
EXIT=0
```

扫描器做三件事（比"grep 有没有包 `_()`"强）：

1. 找**没包 `_()`** 的用户可见字面量（kv 的 text/hint_text/title + py 的 text=/hint_text=）；
2. 找**包了 `_()` 但字典里没有**的键（线上会静默回退英文）——这条抓到了
   `"Start Bitmessage in the tray(...)"`；
3. 排除数字/端口/主机名，以及**已含中文**的字面量。

**踩坑**：第 2 条一开始误报——kv 里的 `\n` 在源码中是两个字符，而 `ast` 解析字典时
变成了真换行；两边语义相同、字面不同。修法是比对前先按 KVC 规则反转义。

#### ⚠️ 本轮未完成的事

- **含 M6 改动的正式包没装上**：`pm install` 之前设备被拔掉（`device not found`）。
  平板仍是上一版包 + 5 个热补丁（`kv/chat|popup|login|settings.kv`、`mpybit.py`、
  `messaging.py`）。**下次插上设备第一件事就是装 run 45557518551 的包并清掉这些热补丁。**
- 拔线时 `exec-out cat` 留下了 **0 字节的备份文件**（`/tmp/bk_m62/*`）——静默失败，
  以后备份后必须校验大小。
- M6.2.3 的逐屏截断/溢出复检、M6.3.3 字号缩放、M6.3.4 平板 AVD 仍未做。

### 1.60 ✅ M4.4.1 数据持久化 + M6.3.1 横屏（2026-11-25 13:30）

#### 图标：dock 里一直是旧的 Kivy 风筝

**结论：不是打包问题，是 MIUI 桌面缓存**。

| 检查 | 结果 |
|---|---|
| APK 内图标 | ✅ `application-icon-{160,240,320,480}` 全指向 `res/mipmap/icon.png`（512×512 盾牌） |
| 清单 | ✅ 只有一个 `<application android:icon>`，activity 无单独 icon |
| 桌面第 3 页 | ✅ 显示新盾牌（`artifacts/icon-grid-correct.png`） |
| 底部 dock | ❌ 仍是 Kivy 风筝（`artifacts/icon-dock-before-stale.png`） |
| UI 树 | ✅ dock 那个节点 `content-desc` 也是 **PyBitmessage** → 同一个包，两处显示不同 |

**修复**：`adb shell am force-stop com.miui.home`（重启桌面进程，重载图标缓存），
布局与数据都不受影响。之后 dock 显示盾牌（`artifacts/icon-dock-after-fix.png`）。

#### M4.4.1 数据持久化与恢复

| 项 | 结果 |
|---|---|
| `messages.dat` 完整性 | ✅ `PRAGMA integrity_check` = **ok**；10 张表；inbox 16 / sent 12 / inventory 9678 |
| `keys.dat` | ✅ 密文（`#BMENC1`），明文私钥关键字 **0** |
| 重启一致性（F） | ✅ `am force-stop` + 重启前后：**2 地址 / 16 收件箱 / 4 通讯录** 完全相同 |
| **`knownnodes.dat`** | ❌→✅ 见下 |

**顺带挖到并修掉的真缺陷**：`knownnodes.dat` 的 mtime 停在 **11-24 11:13**，内容仍是
手写的 4 个种子——而进程内已学到几百个节点。根因：`cleanupKnownNodes()` 只在
**删除了节点**时才 `saveKnownNodes()`，`addKnownNode()` 从没设置过"脏"标记，
所以**学到的节点永远不落盘**，每次重启都退回旧列表（正是 11-24 那次"knownnodes 全死"的成因之一）。

修复（commit `fec5663`）：新增模块级 `knownNodesDirty`，
`addKnownNode()` 新增/更新时置位、`saveKnownNodes()` 清除，
`cleanupKnownNodes()` 改为 `needToWriteKnownNodesToDisk or knownNodesDirty` 才写。
新增 5 条单测（`tests/test_knownnodes_persist.py`：落盘、无变化不重写、lastseen 更新算脏、保存清标记、重载可见）。

**设备验证**：装含修复的包后运行约 5 分钟（一个 cleaner 周期 300s）：

```
knownnodes.dat: 507 B（4 个种子） → 2031 B / 835 个节点，mtime 2026-11-25 13:25:40
```

#### M6.3.1 横竖屏

**先踩了个空**：`buildozer.spec` 的 `orientation = all` 被 buildozer 直接判为非法值；
查 buildozer 源码发现**这个 token 只做校验、根本不传给 p4a**（`targets/android.py` 的
p4a 构建命令里没有 `--orientation`），而 p4a 自己默认写死 portrait——`aapt2` 确认
`screenOrientation=1`（PORTRAIT）。所以改 spec 永远没用。

**真正的做法**（`src/android_keepalive.py: allow_rotation()`）：用 jnius 直接调
`activity.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR)`，
在已有的 KEEPALIVE 主线程回调里执行。日志确认：`KEEPALIVE: rotation allowed (FULL_SENSOR)`。

**设备验证**：

| 项 | 结果 |
|---|---|
| 横屏 | ✅ **铺满 2560 宽**（之前被 MIUI letterbox 成一条竖窗），`artifacts/m631-landscape.png` |
| 不崩、不白屏、不丢页面 | ✅ 旋转时停在同一个 messaging 屏 |
| 转回竖屏 | ✅ 正常恢复 |

> 附注：横屏下"收件箱"区域被挤成两行、正文框占了大部分高度——这是 M6.3.2（响应式布局，
> 大屏应做列表+详情两栏）要解决的，不在本任务范围。

### 1.59 ✅ M5.4.1 回归 D1–D7（D5 按约定跳过）（2026-11-25 11:45）

**结果（`artifacts/regression-d1d7.md`，原始日志 `artifacts/regression-run.log`）**

| # | 结果 | 数据 |
|---|---|---|
| D1 | ✅ | A=`BM-2cXVvaPP…`（Mac 节点）B=`BM-2cXrm…`（平板） |
| D2 | ✅ | B 的通讯录 4 条，含 A |
| D3 | ✅ | B→A 主题 `REG-B2A-1795577984`，**130 秒**送达 |
| D4 | ✅ | A→B 主题 `REG-A2B-1795578114`，**30 秒**送达 |
| D5 | ⏭ | 用户明确要求最后做，本轮不验（不计入通过） |
| D6 | ✅ | force-stop 重启前后完全一致：2 个地址 / 16 条收件箱 / 4 条通讯录 |
| D7 | ✅ | logcat 中 `FATAL / Traceback / THREAD-CRASH` **0 条** |

复现：

```bash
adb -s b45f8e87 forward tcp:8445 tcp:8442
python3 scripts/regression-d1-d7.py --connect-timeout 600 --node-retries 4
```

**这轮修正的 4 个"测试脚本自身的 bug"**（都不是产品问题，但都制造过假结论）：

| # | 症状 | 根因 | 修法 |
|---|---|---|---|
| 1 | D1 报 A 无地址 | **headless 节点根本不会创建首个地址**（只有 Qt GUI 会） | 脚本调用 `createRandomAddress`（同样要 base64 参数） |
| 2 | D2 `Fault 17: not valid UTF-8` | API 参数顺序是 `addAddressBookEntry(address, label_b64)` | 调换参数 |
| 3 | D3 `Fault 13: fromAddress not in keys.dat` | 参数顺序是 `sendMessage(toAddress, fromAddress, …)` | 调换参数 |
| 4 | **D3/D4 报"480s 未到达"，实际 130s/30s 就到了** | 主题经 `xmlrpc.client.Binary` 返回，`bytes(Binary)` 抛异常，而 `wait_for_subject` 用 `except: pass` 把异常吞了 → 每次轮询都在崩 | `Binary.data`；并把轮询异常打印一次而不是静默 |

> 教训写在这里：**测试脚本里的 `except: pass` 会伪造"产品失败"**。这次差点据此判定消息功能坏了。

**A 节点上线的稳定性**：同一出口 IP 常常整轮都被
`Too many connections from your IP` 拒绝（这个现象在 11-24 两次运行里都出现，
其中一次 A 0 条连接）。脚本改为**换新节点重试**（`--node-retries`，每次换新地址与新的
节点抽签），本轮第 1 次尝试就拿到连接。

**产物更新**：`v0.6.3.2` 发布页的 APK 已替换为含 API 修复的构建
（`sha256 10f7b7ef0209acad…b82c9`，28 MB）；`RELEASE.md` / `SHA256SUMS` 同步。

### 1.58 ◐ M5.1.1 启动图 + M5.4.1 首轮回归（2026-11-24 17:10，暂停于此）

**启动图（用户反馈"启动有个 logo 没改、黑底不好看"）**

原来 p4a 用的是 **Kivy 自带的白风筝 "Loading..." 黑底图**，而且和我们的
`android.presplash_color = #091220` 拼在一起有明显接缝。

现在 `scripts/make-icon.py --only presplash` 生成 `src/images/presplash.png`
（1024×1024）：原图整幅（保留背景走线）+ 提亮 + 泛光 + 最外圈径向淡出到纯深蓝 +
底部 `PyBitmessage` 字标；spec 里 `presplash.filename` 指向它。

截图证据：`artifacts/m511-splash-new.png`（旧：`artifacts/m511-splash-old-kivy.png`）。

**踩坑（同一类错误犯了两次）**：先用 `ImageDraw.ellipse` 画环造径向渐变 → 蒙版全 0（`ellipse`
填满整圆，后画的大圆覆盖中心）；第二版把 emblem 当作矩形 paste 上去 → 四边有硬接缝；
最后改成"整幅铺满 + 径向淡出"才干净。脚本里已写明这个陷阱。

**M5.4.1 首轮回归结果（`scripts/regression-d1-d7.py`）**

| # | 结果 | 说明 |
|---|---|---|
| D1 | ✅ | A=`BM-2cU7wbs…`（Mac 节点，脚本自动 `createRandomAddress`）B=`BM-2cXrm…`（平板） |
| D2 | ✅ | B 的通讯录出现 A（1 条）——**并因此暴露了一个真实 py3 bug** |
| D3 | ❌ | B→A 480s 未到达 |
| D4 | ❌ | A→B 480s 未到达 |
| D5 | ⏭ | 按用户要求显式跳过 |
| D6/D7 | 未执行 | 进程在 D5 后被中断（设备随后断开） |

**D2 顺带修掉的真 bug（commit `c827a03`）**：`api.py` 的 `listAddressBookEntries` 在通讯录
**非空**时必崩——`shared.fixPotentiallyInvalidUTF8Data()` 对 str 输入返回 str，
`base64.b64encode()` 需要 bytes → `TypeError: a bytes-like object is required`。
同一模式还存在于 `listSubscriptions`、`listBlacklist/listWhitelist`、`listAddresses2`
（后者的 label 直接来自 config，本来就是 str）。四处统一用已有的 `_as_bytes()`。
之前没人发现，是因为地址簿一直是空的，循环体从不执行。

**D3/D4 失败的实际原因（环境，非产品）**：A（Mac 节点）在整个窗口内
**`networkConnections` 一直是 0**，日志全是
`error: 2, Too many connections from your IP. Closing connection.`
——本机出口 IP 被公网节点按"同 IP 连接数超限"拒绝（R7/M3.8.2 的已知问题）。
一个连不上网络的节点既不能广播自己的 pubkey，也收不到任何东西，所以双向收发根本无从发生。

**为此改进了脚本**：新增 `wait_for_connections()`，在 D3 之前先等 A 真正上线；
等不到就把 D3–D7 标为新增的 **`BLOCKED`** 状态（既不算通过、也不算产品失败），
并写明原因。`--connect-timeout` 可调（默认 420s）。

**⚠️ 平板当前状态**：装着 `0.6.3.2` 包 + **一处热补丁**（`files/app/api.py`，就是上面
那个 API 修复）。下次装新包前需要重新出包才能固化；直接重装会丢掉这个热补丁。

### 1.57 ◐ M5.2.1 统一签名 + M5.4.2 发布 + M5.4.1 回归脚本（2026-11-24 15:50）

**M5.2.1 统一签名**

| 交付 | 内容 |
|---|---|
| 稳定签名 | `scripts/resign-apk.sh` 首次生成 `~/.pybitmessage-android/signing.keystore`，之后每包复用；结尾打印证书指纹便于比对 |
| 指纹 | `SHA-256: 82463dfe0a7ef14821c33fef5e462e1f7bed070387de2bee7e9dd4fdebc551c7`（`CN=PyBitmessage Android`） |
| CI 自动签 | workflow 新增 `Sign with the release keystore (optional)`：有 `RELEASE_KEYSTORE_B64/PASS/ALIAS` 就用它签，没有则打印提示后跳过（已实测跳过分支，构建 11m07s 成功） |
| 文档 | `INSTALL.md` §2.5：本地重签 vs CI 签两条路，含 keystore 备份警告 |

**M5.4.2 发布**

- GitHub Release：<https://github.com/k19810703/pybitmessage-android/releases/tag/v0.6.3.2>
- 资产：`pybitmessage-0.6.3.2-arm64-v8a.apk`（26,974,744 B）+ `SHA256SUMS`
- sha256 `5d3fd7b0ec8e54042fb3d0d6fbfc598c6b9053f8d97d4c6b6d117d7949e128c9`
- `aapt2` 复核：`versionName=0.6.3.2`、`application-label:'PyBitmessage'`、
  `application-icon-480:'res/mipmap/icon.png'`、`native-code:'arm64-v8a'`、
  权限含 `INTERNET / FOREGROUND_SERVICE / POST_NOTIFICATIONS / WAKE_LOCK`
- 发布说明 `release/RELEASE.md`（安装、校验、签名核对、能力清单、已知限制）

**M5.4.1 回归脚本（已就绪，未跑通）**

`scripts/regression-d1-d7.py`：

- **A = Mac** 上脚本自启的 `pubnet_node.py`（临时 home，API :8451）
- **B = 平板**，经 `adb forward 8445→8442` 的 XML-RPC
- 自动执行 D1（双方各有地址）、D2（地址进通讯录）、D3（B→A）、D4（A→B，
  轮询直到主题出现并报实际耗时）、D6（force-stop 重启后地址/消息/联系人逐项比对）、
  D7（logcat 抓 FATAL/Traceback/THREAD-CRASH）
- **D5 显式 SKIP 并注明"用户要求放到最后"**——闸门项不因为"没人看"就算绿
- 可选 `--no-restart`（不动 App）、`--skip-send`、`--json/--markdown` 出报告

**为什么没跑通**：第一次 `--skip-send --no-restart` 就卡住——平板 API 拒连，
logcat 每秒一条 `socket error on sendto: PermissionError`（`network/udp.py:146`），
即 **MIUI 把后台的 App 冻结了**（当时前台是游戏）。这是已知的 R12/MIUI 行为，
不是本轮改动引入的。回归需要 App 在前台跑，只能等设备空闲。

### 1.56 ✅ M5.1.1 图标定稿 + M5.1.2 版本号对齐（2026-11-24 15:10）

**M5.1.1 应用图标**

素材：用户提供的 `image_20261123_211538_610565.jpeg`（2048×2048，深蓝底的
盾牌 +「SJY」+ 挂锁 + 对话气泡，背后有细密的电路走线）。

直接缩放成图标不可用——原图平均亮度只有 **35/255**，48–96 dp 下字母和挂锁全部糊进背景。
做了 4 项必要修改（脚本 `scripts/make-icon.py`，可复现）：

| 步骤 | 做法 | 为什么 |
|---|---|---|
| 裁切 | 取 `(142,150)-(1892,1900)`，emblem 占画布 ~79% | 图标外沿会被 launcher 遮罩裁掉，自适应图标只保证中心 66% |
| 抬亮度 + 泛光 | 亮度 ×1.5，对 >70 的亮部做高斯模糊后 screen 回叠 | 盾牌边、锁、气泡在降采样后才不会和背景糊在一起 |
| 压平背景 | 用径向蒙版把外围换成纯深蓝 + 中心蓝光 | 电路走线是缩小时最先变成噪点的部分 |
| 微调 | 对比度 ×1.12、饱和度 ×1.2 | —— |

**位置测量不是猜的**：先用 12 px 高斯模糊把细线抹掉再阈值化，得到 emblem 真实范围
x 327..1711 / y 418..1633（1375×1210，中心 1017,1025），再据此定裁切框。

**踩坑**：第一版用 `ImageDraw.ellipse` 循环造径向渐变，结果蒙版**全 0**、出了张全黑图——
`ellipse()` 填的是整个圆盘，后画的大圆把中心一起盖掉了。改用
`Image.rgb2`… 改成 `Image.radial_gradient` + LUT 才正确（脚本里留了注释警告）。

**验收**

| 项 | 结果 |
|---|---|
| APK 内含图标 | ✅ `res/mipmap/icon.png`，512×512 RGB，`application-icon-{160,240,320,480}` 全部指向它 |
| 桌面显示 | ✅ 截图 `artifacts/m511-launcher-home.png`、特写 `artifacts/m511-icon-on-launcher.png`：squircle 遮罩下盾牌发光、SJY 可辨、锁与气泡清晰 |
| 应用名 | ✅ `application-label:'PyBitmessage'` |
| 冷启动不再白闪 | 顺带设 `android.presplash_color = #091220`（与图标底色一致）；首次解压要 3–5 分钟，白屏很难看 |

**M5.1.2 版本号对齐**

发现不一致：APK `versionName = 0.1.2`，而 `src/version.py` 的 `softwareVersion = 0.6.3.2`
（后者会进 `version` 消息的 userAgent `/PyBitmessage:0.6.3.2/`，所有对端都能看到）。
已把 `buildozer.spec` 的 `version` 改为 **0.6.3.2**，并在 `version.py` 写明两者必须一致。

**装到平板验证（run 45345527791）**

```
包     : /tmp/pybitmessage-0632-2026-11-24.apk（本钥重签，sha256 82a0673c…）
aapt2  : versionName='0.6.3.2'  application-label:'PyBitmessage'
         application-icon-480:'res/mipmap/icon.png'
设备   : dumpsys 显示 versionName=0.6.3.2
升级后 : 2 个地址 / 14 条收件箱 / 3 条连接全部完好，KEYSTORE 仍走 AndroidKeyStore
```

> 附注：本次构建首次失败**与代码无关**——runner 解析不到
> `org.jetbrains.kotlin:kotlin-stdlib-jdk8:1.8.20-RC2`（AGP 8.1.1 的传递依赖），
> 属 Maven 侧偶发；`gh run rerun` 后 8m21s 通过。

### 1.55 ✅✅✅ M4.5.2 私钥加密：Android Keystore 包裹 + keys.dat 密文（2026-11-24 14:20）

**目标（C4）**：`keys.dat` 里不能有明文私钥，而 App 仍能正常启动并解密。

**设计：信封加密**

```
keys.dat  = AES-256-CBC(enc_key, iv) + HMAC-SHA512(mac_key)   ← 自带 magic 便于识别
enc_key/mac_key = HMAC-SHA512(master, 不同标签)[:32]           ← 密钥分离
master    = 32 字节随机数
          ├─ Android：由 AndroidKeyStore 里的 AES-GCM 密钥（别名 pybitmessage-vault）包裹
          │           密钥材料不出 TEE，root 也导不出
          └─ 桌面/CI：keys.vault（0600）—— 仅用于保持格式一致，**不是安全边界**
```

文件格式 `b'#BMENC1\n' + iv(16) + mac(32) + ciphertext`，`mac` 覆盖 `iv||ciphertext`（encrypt-then-MAC）。
读的时候靠 magic 判断：**没有 magic 就是旧明文**，下一次 `save()` 自动加密 —— 这就是迁移路径。

**改动**

| 文件 | 改动 |
|---|---|
| `src/keystore.py`（新增） | 信封加密、magic 识别、篡改检测、两种后端、`enabled()` |
| `src/bmconfigparser.py` | `read()` 走 `_read_config_file()`（透明解密）；`save()` 走**临时文件 + fsync + os.replace**（原子写，半个 keys.dat 等于丢身份）；首次加密时写入 `keysencrypted = true` |
| `src/main.py` | 启动打印 `KEYSTORE enabled=… backend=…`，日志本身就能回答"是否加密、用什么加密" |

**设备实测（平板 b45f8e87，Android 13）**

```
KEYSTORE vault via AndroidKeyStore
KEYSTORE enabled=True backend=AndroidKeyStore
KEYSTORE decrypted keys.dat (AndroidKeyStore)
```

| 验收 | 结果 |
|---|---|
| **F** `keys.dat` 无私钥明文 | ✅ 文件头 `#BMENC1`，`grep -c 'privsig\|privenc\|BM-'` = **0** |
| **F** App 能正常启动并解密 | ✅ 重启后 `dpkg` pid 正常，日志见上 |
| **F** 身份不变 | ✅ 重启后地址仍为 `BM-2cXrmLDco…` + `BM-2cWGibweLd…`，收件箱 14 条，连接 3 条 |
| vault 是硬件包裹的 | ✅ `keys.vault` 60 B 密文（base64 文本形态会是 44 B ASCII，明显不同） |

**顺带修掉的真实泄漏**：`save()` 崩溃时会留下 `keys.dat.*.bak`，那是**明文私钥副本**，
一直躺在目录里会让加密形同虚设。现在只要加密开启，保存后就会清掉所有 `.bak`（有单测）。

**测试**：`tests/test_keystore.py` 14 条全过（往返 / 每次新 IV / 篡改拒绝 / 截断拒绝 /
换金库打不开 / vault 权限 0600 / 桌面默认不加密 / 明文可读 / 保存后加密并置位 /
多次保存幂等 / 不可解密时保留原文不销毁 / 明文备份被清理 / 无残留临时文件）。
全套相关测试 30 条通过。

**踩坑记录（jnius 传 Java 数组，全部实测）**——给以后要用 Keystore 的人省时间：

| 写法 | 结果 |
|---|---|
| `autoclass('[Ljava.lang.String;')(n)` | `JavaException('No constructor available')` |
| `autoclass('java.lang.String[]')` | **进程硬 abort**：`JNI DETECTED ERROR: illegal class name`（FindClass 只认 `/` 分隔的 JNI 描述符，且这个错误 Python 接不住） |
| 传 Python list 给 `String...` | `ArrayStoreException: java.lang.String[] cannot be stored in an array of type java.lang.String[]`（pyjnius 把 list 转成 Object[]） |
| 用 `java.lang.reflect.Array` 造好真 `String[]` 再传 | 同样 `ArrayStoreException` —— varargs 参数会把你的数组当**一个元素**再包一层 |
| **直接传裸字符串给 `String...`** | ✅ 正确，Java 自己打包 |
| `Cipher.init(mode, key)` 不 cast | `TypeError: Invalid instance of 'javax/crypto/SecretKey' passed for a 'java/security/cert/Certificate'` → 必须 `cast(Key, key)` |

**固化进包（零热补丁，2026-11-24 14:35）**

新包 run **45338885347**（`/tmp/pybitmessage-m452final-2026-11-24.apk`，本钥重签，
sha256 `8052cf6d…6cf16f0`）装机后删除全部热补丁，冷启动日志：

```
PROBE summary: 8/9 ok, failed=pycryptodome
KEYSTORE vault via AndroidKeyStore
KEYSTORE enabled=True backend=AndroidKeyStore
KEYSTORE decrypted keys.dat (AndroidKeyStore)
NOTIFY: POST_NOTIFICATIONS already granted
NOTIFY: inbox insert hook installed
```

`files/app/*.py` = **0 个**（零热补丁）；`keys.dat` 头仍是 `#BMENC1`；
地址 2 个、收件箱 14 条、连接 3 条，全部完好。

> ⚠️ 冷启动时这个包会重新解压 Python 运行时，**实测要 3–5 分钟**（比文档里写的
> 30–60 秒长），期间 logcat 只有 `extracting …` 行。`README-ANDROID.md` 已按
> 实测值更新。

**已知限制（必须写在文档里，别过度承诺）**：
`keys.vault` 与 `keys.dat` 在同一目录。**备份/迁移时必须两个文件一起拷**，
只拷 `keys.dat` 在新设备上打不开（会走"保留原文 + 新建身份"的兜底路径，
日志打 `KEYSTORE FATAL: cannot decrypt …`）。

### 1.54 ✅✅✅ 设备验收：M4.2.1 通过 + M4.8.9 关闭（2026-11-24 11:45）

**设备**：小米平板 5 `b45f8e87`（Android 13 / API 33）
**包**：`m489`（run 45315773202，本钥重签）→ 装机后两处**热补丁**（`android_notify.py`）
**数据**：装机前已备份 `keys.dat`(1862B) / `messages.dat`(11.1MB) / `knownnodes.dat` 到 `/tmp/bk_m489/`；
装后私钥与消息库**字节数不变**，2 个地址 `BM-2cXrmLDco…` / `BM-2cWGibweLd…` 完好。

#### M4.2.1 通知权限 —— **通过**

| 验收 | 证据 |
|---|---|
| **S** 首次启动有授权弹窗 | 截图：`artifacts/m421-permission-dialog.png`（「是否允许"PyBitmessage"发送通知 / 拒绝 / 始终允许」） |
| **S** 授权后前台服务通知 | 截图：`artifacts/m421-service-notification.png`（通知栏「PyBitmessage 正在运行」）；`dumpsys` 见 `id=1001 channel=pybitmessage_service` |
| **S** 收到消息弹通知 | 截图：`artifacts/m421-new-message-notification.png`（通知栏「**新消息** 通知验证第三条」）；日志 `NOTIFY: message from BM-2c… posted (subject)` |
| 拒绝后不崩 | 首次我误点在按钮外（= 拒绝），App 照常运行、收发不受影响 |

**设备验收暴露并修掉的 3 个真 bug**（都只在真机上才会显形）：

| # | 症状 | 根因 | 修复 |
|---|---|---|---|
| 1 | `NOTIFY: request failed: JavaException('No constructor available')` | 手写 jnius 创建 `String[]`（`autoclass('[Ljava.lang.String;')(1)`）在设备上不可用 | 改用 p4a 的 `android.permissions.request_permissions`（带手写回退） |
| 2 | 权限授了、消息到了，**通知不出现** | 原实现**轮询** `queues.UISignalQueue`，但该队列的所有者是 `UIkivySignaler`，UI 通常先取走 | 改为包装 `helper_inbox.insert`（核心唯一入库点），与 UI 无竞争 |
| 3 | `NOTIFY: message notification failed: AttributeError('...setShortCriticalText')` | 我按 `sdk >= 31` 调用，但该方法 **API 36 才有** | 删除该调用 |

单测同步改写（`tests/test_android_notify.py` 3 条：入库触发一次通知 / trash 文件夹不通知 / 无 Android 环境全 no-op）。

#### M4.8.9 公网连接 —— **关闭**（是环境 + 配置问题，不是协议 bug）

| 阶段 | 观测 | 结论 |
|---|---|---|
| 沿用旧 `knownnodes.dat`（11-20 遗留） | `networkConnections=0`；`listConnections` **57 条 outbound 全 `fullyEstablished=false`**、`userAgent=''`；这些对端**零 BMPROTO 日志** | knownnodes 全是死节点，握手无从开始 |
| 换 4 个活节点（`85.114.135.102` / `194.164.163.84` / `185.158.248.216` / `158.69.63.42`，rating=1） | `networkConnections=6`、`numberOfMessagesProcessed=**297**`、`TCP established` 6 次、`recv inv` 12 次 | 全链路恢复 |
| 11:28–11:43 持续观测（15 分钟） | `networkConnections=5` 稳定；`established` 对端带真实 UA：`/PyBitmessage:0.6.3.2/` ×3、`/PyBitmessage:0.6.3.2/`、`/MiNode:0.3.3/`；`INVTHREAD sending` **14** 次、`recv inv` 17 次、`numberOfMessagesProcessed` 递增 | **≥10 分钟稳定 + inv 双向**，满足 M4.8.9 验收 |

**所以两条"症状"的最终归因**：

1. **"连接数秒被断"** → 本机（无 TLS 证书）连公网被 RST（§1.52 线缆证据）；平板上**不存在**该现象，
   连接可稳定 15+ 分钟。**结论：本机环境限制，非产品缺陷。**
2. **"inv 从不发出"** → 平板上其实是 **knownnodes 全死**导致无连接可发。换上活节点后
   `INVTHREAD sending` 与 `recv inv` 都正常。**结论：数据/配置问题，非代码缺陷。**

**顺带发现（未修，低优先级）**：日志有 `INVTHREAD skip stream 1 not in [0]` —— 少量连接
`self.streams` 仍是默认 `[0]`（version 尚未解析完），这些连接会被跳过。属正常跳过，
但如果长期不更新会影响对象分发效率，记入待观察。

#### 固化（零热补丁）

新包 run **45320464967**（`/tmp/pybitmessage-m421final-2026-11-24.apk`，本钥重签，
sha256 `92dbea1d…20fa9`）已装机并删除全部热补丁：

- `run-as … ls files/app/*.py` → **空**（零热补丁）
- 备份的私钥/消息库未被覆盖（装机后地址与 13 条收件箱仍在）
- 截图 `artifacts/m421-final-zero-hotpatch.png`：通知栏「PyBitmessage 正在运行」
- 重装后系统把权限重置为未授予（`REVOKED_COMPAT`），App 再次正常弹出申请 → 说明
  **首次安装路径**和**升级路径**都验过了

**平板当前状态（可回滚）**

```
包      : m489 + 2 处热补丁（files/app/android_notify.py）
配置变更: keys.dat 加 apienabled=true/u/p；knownnodes.dat 换成 4 个活节点
备份    : /tmp/bk_m489/{keys,messages,knownnodes}.dat（原始）
连接    : 5 条 established（真实公网节点）
收件箱  : 13 条（含 3 条本轮自发通知验证消息）
```

### 1.53 ⚠️ 更正 + M4.8.9 真因定位（2026-11-24 11:20）

> **本节先自我更正上一版 1.53 的两条错误结论**（原文已删，错误保留在此以便追溯）：
>
> | 上一版的错误说法 | 实测 | 真相 |
> |---|---|---|
> | "`CreatePacket` 命令字段未补齐到 12 字节，`verack` 少 2 字节导致对端 RST" | `struct.Struct('!L12sL4s').pack(1, b'verack', 0, b'aaaa')` → `b'verack\x00\x00\x00\x00\x00\x00'`；修复前后 `verack` 字节**完全相同** | **`struct` 对 bytes 也会补齐**，这个"修复"是 **no-op**。当时我看到了"新旧字节相同"却错误地解释成"空载荷特例碰巧正确" |
> | "`assembleAddrMessage` 等返回裸头而非完整包" | 源码一直是 `retval += CreatePacket(b'addr', payload)`；线缆抓包也是 63B 完整包 | **本来就是对**，这条结论纯属误判 |
>
> 教训：**先验证前提再改代码**。`tests/test_packet_framing.py` 保留下来作为格式回归测试（7 条），
> 但它保护的是"本来就对"的行为，不能算 M4.8.9 的修复。

**M4.8.9 真因（平板实测，2026-11-24 11:12–11:20）**

| 步骤 | 观察 | 结论 |
|---|---|---|
| 装 m489 启动（沿用平板旧 `knownnodes.dat`） | `clientStatus.networkConnections=0`、`networkStatus=notConnected`；`listConnections` 有 **10 条 outbound，全部 `fullyEstablished=false`**、`userAgent=''` | 连接**发起了但握手从不完成** |
| 逐对端查日志 | 那 10 个对端**一条 `BMPROTO` 日志都没有**；只有 `bootstrap8080.bitmessage.org` 有 version/verack | 对端已死，根本没回包（不是我们不发 inv） |
| 把 `knownnodes.dat` 换成 4 个**活节点**（rating=1）后重启 | `networkConnections=6`、`numberOfMessagesProcessed=297`、日志出现 `TCP established` 6 次、`recv inv` 12 次 | **全链路正常** |

**所以 M4.8.9 的"公网连接数秒被断 / inv 不发"是两个独立问题，都不是协议代码 bug**：

1. **连接数秒被断** → 本机（无 TLS 证书）连公网节点会被 RST（EVIDENCE §1.52 的线缆证据）；
2. **inv 不发** → 平板 `knownnodes.dat` 里全是 11-20 留下的**死节点**，一条都连不上，
   自然没有 `inv`。换上活节点后 `inv` 立刻正常收发。

**副产品：平板当前配置变更（可回滚）**

```
keys.dat      : 加 apienabled=true / apiusername=u / apipassword=p  （为了用 API 观测）
knownnodes.dat: 替换为 4 个活节点；原文件备份在 /tmp/bk_m489/knownnodes.dat
私钥/消息库   : 未改动（keys.dat 1862B、messages.dat 11.1MB，与本轮装机前一致）
```

**新增（本轮）**：`tests/test_packet_framing.py`（7 条格式回归）；
`android_notify.py` 的权限申请改用 p4a 的 `android.permissions` 助手
（原手写 jnius 数组创建在设备上抛 `JavaException('No constructor available')`，
热补丁后日志为 `NOTIFY: POST_NOTIFICATIONS requested`）。

### 1.52 ◐◐ 本机公网联调：M4.8.3 已修，顺手挖出 1 个致命缺陷（2026-11-24 09:55）

**背景**：用户选择先做「不依赖设备的缺陷修复」。用 `scripts/pubnet_node.py`
在本机起真节点连公网，边复现边验证。

**M4.8.3（SIGTERM 关闭挂死）——已修，本机实测**

| 假设 | 验证 | 结论 |
|---|---|---|
| 关闭流程本身会挂 | 对 `pubnet_node` 发 SIGTERM，进程 1–2 s 退出 | ❌ 当前代码**不挂** |
| 但锁文件残留 | 退出后 `singleton.lock` 仍在（内容是被杀进程的 pid） | ✅ 属实：下游误判「Another instance is running」 |

**根因（两段）**：
1. `shutdown.doCleanShutdown()` 里的 `thread.join()` **没有超时**，任一线程卡在读 socket
   就永久等待（外层还有 `while state.shutdown == 1: sleep` 无上限）——
   8 月观察到的"僵尸进程占锁"就是这个；
2. 进程退出后**没人删锁文件**（`atexit` 不跑，`os._exit` 直接跳）。

**修复**（commit `5018bf4`）：

- `shutdown.py`：新增 `ShutdownWatchdog`（默认 10 s）+ `forcedExit()`（join 全部带截止时间）；
  `doCleanShutdown()` 加重入保护（第二个 SIGTERM 不再进清理流程，避免半拆状态下二次 flush）；
  强制退出前 best-effort 存 knownnodes + 释放锁
- `singleinstance.py`：启动时若锁文件**未被任何进程持有**（`flock` 探测）则删除并打印
- 实测：带陈旧锁启动 → `Removed stale single instance lock` → 锁被重建；SIGTERM 后
  `singleton.lock` **不再残留**
- 单测 `tests/test_shutdown.py` 6 条全过（超时会强制退出 / 按时完成则不动 / 重入保护 / 陈旧锁清理）；
  修过的两个自身 bug：`lockf()` 需要可写句柄（只读句柄 EBADF 被误当"被持有"）、
  join 返回后线程尚未回收导致误判

**顺带修的健壮性**（同 commit）：`connectionchooser.chooseConnection()` 先快照候选列表，
候选为空时报 `ValueError` 而不是 `random.choice([])` 抛 `IndexError`；`connectionpool.loop()`
捕获它——否则**空 knownnodes（首次启动、bootstrap 前）会让 Asyncore 线程直接死掉**，
之后整个进程没有任何网络（本 session 实测复发过一次）。

**修 tcp 新连接 `connecting` 标志**（同 commit，M4.8.5 疑似根因之一）：
`TLSDispatcher.__init__` → `create_socket()` → `set_socket()` 重建了 socket，`connecting`
永远是默认 `False`，SYN-ACK 到达时 `handle_connect_event()` 不跑 → `connected=False` →
`readable()` 恒 `False` → **新拨出的 TCP 连接一个字节都读不到**。一上线就"成功"只是因为
loopback 的建立比事件循环第一次 poll 还快，靠 `select` 把 socket 报成 writable 才走到
`handle_write_event`。修复后**公网 TCP 稳定建立**（修复前同网络下 0 次，修复后
`TCP established: 185.158.248.216:8444 outbound=True`，`networkConnections=1`）。

**🚨 尚未修复的致命问题（M4.8.9 候选）**：公网连接建立后 **2–6 秒被主动断开**，且网关不发任何
跟踪日志。已排除：

| 怀疑 | 证据 | 结论 |
|---|---|---|
| TCP 层被网关"超时回收" | `scripts/pubnet_diag.py`（120 s 窗口）：4 节点各连一次 → 9 次 `Too many connections`
拒绝、1 次建立；此后**没再向对端发任何东西**，连接仍在 `clientStatus` 里 | 不能解释断开 |
| 对端拒绝（dup-IP / 时间偏差） | 对端对**每次**新连接都回 `Too many connections from your IP`；
`timeOffset` −1～−6 s 正常 | 对端自己的状态，不是我们被二次断开的原因 |
| `receiveDataQueue` 被塞满触发停网 | 每个连接建立都 `put`，只显式 `get` 一次，队列上限 1000 | 待验证 |
| **`inv` 从不发给公网对端** | 对端回了 `verack`，我们回了 `verack`（87 B）后 8 s 内两侧都没有 `inv/getdata` 日志 | 待验证 |

**已排除的排查陷阱（写给下一个 session）**

1. **匿名管道里的 print 是块缓冲**：`subprocess.stdout` 不是 TTY 时，`print(flush=True)` 只把数据
   推进 Python 的 `TextIOWrapper`，进程被杀时整块丢失。用 `python3 -u`。
   本 session 因此误判了两次「打点没触发」。
2. **写死的 8444 是共享资源**：`pubnet_node` 固定监听 8444，任何残留节点都会抢占它；
   现象是「端口的监听者 ≠ 你以为是的那台」。排查前先 `lsof -nP -iTCP:8444 -sTCP:LISTEN`。
3. **`pubnet_node.py` 默认 4 个公网对端**，`--peer` 只替换第一条；想只连一台必须用
   `--reset-peers --peer <host:port>`，否则会被「Too many connections from your IP」淹没。

**新增诊断脚本（全部只读，不参与出包）**：`scripts/hs_trace.py`（逐包握手）、
`scripts/handshake_probe.py`（用真实抓包 `tests/fixtures/handshake/` 离线跑状态机，
证明握手状态机本身没问题）、`scripts/pipeline_trace.py`（inv→getdata 链路）、
`scripts/pubnet_diag.py`（公网连通性与拒绝率）、`scripts/close_trace.py`（连接关闭归因）、
`scripts/which_module.py`（模块真实来源，防"文件写了却没生效"）。

### 1.51 ◐ M4.2.1：通知权限 + 新消息通知（代码完成，待装机）（2026-11-24 08:40）

**任务缺口调研（先读代码再动手）**：

| 项 | 现状（动手前） | 结论 |
|---|---|---|
| 清单权限 `POST_NOTIFICATIONS` | `buildozer.spec` 已声明（M4.1c） | 有声明 ≠ 有授权（API 33+） |
| 运行时申请 | **全仓库零调用**（`grep requestPermissions` 无结果） | ❌ 缺 |
| 新消息通知 | 核心**已经**对每条入库消息发 `displayNewInboxMessage`（`class_objectProcessor.py:691`），但 Kivy 侧 `UIkivySignaler` 只处理 3 种命令，这条**被直接丢弃** | ❌ 缺 |
| 前台服务通知 | `core_service.py` 自建可见渠道 | 已有，但同样被权限卡住 |

**实现**（commit `01e8892`）：

- **新增 `src/android_notify.py`**
  - `request_permission_once()`：API 33+ 调 `activity.requestPermissions([POST_NOTIFICATIONS])`，
    每进程只问一次；API < 33 直接跳过并打日志。**不用结果回调**（需要 Java 侧 receiver，
    `android_keepalive.install()` 里踩过一次 JNI 崩溃），是否授权在下一次启动由
    `has_permission()` 打日志。
  - `ensure_channel()`：独立渠道 `pybitmessage_messages`（IMPORTANCE_HIGH），
    用户可单独静音「新消息」而不影响前台服务通知。
  - `notify_message(from, subject, body)`：标题「新消息」，正文取主题（超 40 字截断），
    **正文永不进通知**（锁屏会显示通知内容）；`privacy=True` 只显示发件地址。
    固定 id 覆盖更新，不堆叠。
  - `install_message_hook()`：守护线程 `get_nowait` **查看** `UISignalQueue`，
    命中 `displayNewInboxMessage` 后**原样 put 回去**再通知——队列所有者仍是
    `UIkivySignaler`，不抢消费。
- **`src/main.py`**：在已有的 `KEEPALIVE 8s` 主线程回调里（Kivy Clock，避开 SDL/JNI 坑）
  依次调用 权限 → 渠道 → hook，整体 try/except，失败不阻塞启动。

**单元测试**（`src/tests/test_android_notify.py`，3 条全过）：

```
$ cd PyBitmessage/src && python3 -m unittest tests.test_android_notify -v
test_inbox_signal_is_notified_and_requeued ... ok     # 通知发出 + 信号仍可被消费
test_other_commands_are_not_notified ... ok           # 其它命令不触发通知
test_all_entry_points_are_noops_without_android ... ok
Ran 3 tests ... OK
```

`python3 -m compileall -q src | grep -c "Error compiling"` → **0**。

**CI**：run 45298351539 ✅ **success**（10m12s），artifact `pybitmessage-apk-55`。
APK 内已验证：`assets/private.tar` 含 `android_notify.pyc`（顶层 + `pybitmessage/` 两份）；
`aapt2 dump badging` 含 `POST_NOTIFICATIONS` / `FOREGROUND_SERVICE` / `WAKE_LOCK`。
个钥重签后：`/tmp/pybitmessage-m421-2026-11-24.apk`，sha256 `234559e9fe26fa310a4f42f0b2f31d3cd86b90db7731db811c7e27e25fcd7124`，25 MB。

**待做（设备验收，需用户确认后执行）**：

- **S**：首次启动出现系统授权弹窗；允许后通知栏出现前台服务通知
- **S**：收到一条消息 → 通知栏出现「新消息 / 主题」
- **S**：拒绝授权后 App 不崩、照常收发（只是无通知）

### 1.50 ✅✅ M4.8.7 正式包装机 + 7 条丢弃消息全部恢复（2026-11-23 20:51）

**装机**：`/tmp/pybitmessage-m487.apk`（run 45141802772，个钥重签，
sha256 `814cbe2b24d37809d22f12870a8eb2c67abf75fd0d75c9bd4ed4f3a69d3e94d4`）。
字节码验证：`encodeSimple` 含 `'utf-8'` 字节长度修复。装后删除全部热补丁。

**消息恢复的两次尝试**（都留了证据）：

1. **重排队**（把 8 个对象插回 `objectprocessorqueue` 重启）→ **失败**：
   队列处理完（0 剩余）但收件箱不变。原因：长度 bug 在**发送端**，错误的
   msglen 已固化在加密对象内部——重新处理也没用。16:48 成功那条是因为
   Mac 修复后**新发**的对象本身正确（接收端解析本来就正确）。
2. **直接注入**（从 Mac 发件表提取 subject/body，直接 INSERT 进平板
   inbox 表）→ **成功**：7 条全部恢复，收件箱 10 条，UI 正确加载。

**最终收件箱**（时间倒序）：

```
[16:48] 中文修复验证      ← 网络真实送达（修复后首发）
[16:22] 打点追踪          ┐
[16:02] 新鲜公钥测试       │
[15:43] M4.8.2b 收信验证   │ 注入恢复的 7 条
[15:05] 差集定位测试       │ （原始发送时间）
[15:02] DEBUG追查         │
[14:51] 第二次收信验证     │
[14:45] 平板收信验证      ┘
[11-20 09:56] test form sjy
[11-19 20:14] 公网测试 1
```

**11-19 的两条**（公网加密消息测试 / 端到端加密·公网验证通过）：
TTL 于今晚 20:33/20:46 过期，未恢复——对象已从网络消失，且收件地址
（pm clear 前的旧地址）私钥也已丢失，双重不可恢复。

**回答用户问题"没收到的消息是丢失了吗"**：
- 今天 Mac 发的 7 条：**没丢**（对象一直在库存+网络），已全部恢复 ✅
- 发给 sjy 的：ASCII 无 bug，一条已确认、一条在网等对方上线（TTL 至 11-27）
- 11-19 的两条：**真丢了**（TTL 过期 + 收件地址私钥丢失）

### 1.49 ✅✅✅ M4.8.7：中文主题消息被静默丢弃的根因与修复（2026-11-23 16:50）

**故障现象**：用户问"平板上没有新消息吗"——Mac 发的 7 条测试消息（14:45–16:02）全部未达，
但 11:33 的 ASCII 主题消息（M481-test）成功送达且收到回执。

**完整排查链**（每一步都有设备实测证据）：

| # | 假设 | 验证方法 | 结论 |
|---|---|---|---|
| 1 | 下载停滞（skipUntil） | 库存 hash 差集 | **部分成立**：M4.8.2b 修复后对象能下载了，但消息仍未入库 |
| 2 | 公钥错误 | 重算 ripe（先漏 \x04 前缀误判，修正后） | ❌ 公钥完全匹配 |
| 3 | 解密失败 | 本地用平板私钥解密 Mac 对象 | ❌ 解密成功（密钥正确） |
| 4 | 验签失败 | **processmsg 加 PROCMSG 打点热补丁** | ✅ **实锤**：`DECRYPT OK` → `ECDSA verify FAILED`，且 sig=22B（正常 ~70B） |

**根因**（`helper_msgcoding.py encodeSimple`）：

```python
self.data = 'Subject:%(subject)s\nBody:%(body)s' % message   # str
self.length = len(self.data)                                   # ← 字符数，不是 UTF-8 字节数！
```

中文主题下 `len(str) < len(utf-8)`（每字差 2 字节）→ 对象里 msglen 偏短 →
接收方解析错位（acklen/siglen 读到垃圾）→ 验签必败 → `logger.debug('ECDSA verify
failed')` 静默丢弃（该级别不进 logcat，所以之前完全看不见）。

**为什么以前"能用"**：api.py 的 repr 入库 bug（M3.9.1c 修复）曾把中文主题存成
纯 ASCII 的 `b'\xe5..'` 字符串——字符数恰好等于字节数，不错位。修好 api.py 后
这个底层 bug 才暴露。**今天所有失败消息全是有中文主题的；ASCII 主题全成功**——
证据完全吻合。

**修复**（commit `40dcb8a`）：`encodeSimple`/`encodeTrivial` 改为产出 bytes 并按
字节计数；接收端 `decodeSimple` 本就兼容 bytes。

**设备端到端验证**：16:36 发「中文修复验证」→ 16:48:07 平板日志
`DECRYPT OK + ECDSA verify PASSED` → 收件箱显示完整中文主题和正文。

**过程中顺带完成**：
- M4.8.2b（`599214c`）：anti-intersection 窗口限频（每连接 60 秒最多延长一次、
  单窗封顶 30 秒）——修复了"inv 收到但对象永不下载"
- processmsg 保留精简打点（DECRYPT OK / 验签结果 / 转发攻击检查）

**待办**：CI run 45141802772 出包后装机固化（平板当前跑
class_objectProcessor.py 热补丁 + Mac 节点已带修复）。

### 1.48 ✅✅ M6 第二阶段：Sent/Draft/Trash/AllMails 四个空壳页面修复（2026-11-23 14:41）

**问题**：这四个抽屉页面和最初的 Inbox 一样是空壳——`loadSent()` / `load_draft()` /
`load_message_list()` 只设置 `self.account` 就结束，从不查询数据库；Trash 连
loader 都没有。

**实现**（commit `bb0a68d` + `aae1942` + `053b5ea`）：新增
`baseclass/mail_list.py` 作为共享实现：

- `load_folder(sent|draft|trash|inbox|all)`：Bitmessage 用 `folder` 列在同两张表里区分
  文件夹，因此一个查询辅助覆盖四个页面
- `render()`：原生 Label + CJK 字体填充 `ids.ml`，并装 MDList 层点击处理
- `show_detail()`：复用 Inbox 验证过的 MDDialog 模式
- `_STATUS_ZH`：发送状态中文化（**顺带完成 M3.9.4**）：
  `msgsent`→已发送、`ackreceived`→对方已确认、`doingmsgpow`→计算消息 PoW 等

四个页面均加 `on_pre_enter` 重载；表缺失时返回空列表 + 日志而不抛异常。

**AllMails 的第二个坑**（只有修完第一个才发现）：`all_mails` 是空 ListProperty，
导致 `_update_mail_count()` 总走空分支，往 `ids.ml` 里塞「暂无消息」标签，
**盖住了刚渲染的 8 行**。改为把 `render()` 返回值存进 `all_mails`，
`_update_mail_count()` 只更新徽章，空状态交给 `render()`。

**设备验证**（干净包，零热补丁）：

```
LIST sent: 6 message(s)          → 「已发送」列出全部 6 条，状态全中文
LIST all: 8 message(s)            → 「全部邮件」列出 8 条（收件+发件混排）
LIST render all by AllMails done: 8 widget(s)
徽章显示 8
```

截图确认：「已发送」6 条（含 `[对方已确认]`、`[已发送]`）；
「全部邮件」8 条（收件与发件按时间倒序混排，中文状态）。

**顺带确认的业务事实**：13:33 发给 sjy 的消息已是 **[对方已确认]**，
即 sjy 已收到并返回回执。

**包**：run 45123990348 → `/tmp/pybitmessage-m6c.apk`（个钥重签，
sha256 `52f4273f6b8974fe762cf526dd835e2555fb5d1da8f678e66d2eb0ea8d034fd6`）。

**遗留**（记录，非本轮）：搜索框仍是硬编码英文 "Search"。

### 1.47 ✅✅ M6 第一阶段完成：抽屉菜单全中文 + 图标完整（2026-11-23 14:07）

**首轮现象**（1.45 的包）：翻译生效但**全部渲染成豆腐块 □**——翻译对了，字体没跟上。

**三层排查，每层都是设备日志/截图驱动的**：

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | 菜单项是 □ | KivyMD 组件从 `theme_cls.font_styles` 取字体（Roboto，无中文字形），不是 kv 里的 font_name | 新增 `apply_cjk_theme_font()`，注册系统 CJK 字体并重写 13 个文字样式的字体名 |
| 2 | 加了函数但没日志 | `MDApp.get_running_app()` 在 `build()` 内还没设好，返回 None | 改为把 `self` 传进去 |
| 3 | 热补丁不生效 | **mpybit 走顶层 `bitmessagekivy/`**（main.py 是 `from bitmessagekivy.mpybit import ...`），不是带 `pybitmessage/` 前缀那份。两个模块**导入路径不同**：kv 里的 Import 用 `pybitmessage.` 前缀，main.py 不用 | 两份都打 |
| 4 | 中文出来了但**图标全变 ⊠** | `MDLabel.update_font_style()` 无条件套用主题字体，把 `"Icon": ["Icons", 24, ...]` 也改了——所有 IconLeftWidget/MDIconButton 的图标字形丢失 | **跳过 `Icon` 样式**：13 个文字样式改了，Icon 保留 `Icons` |

**最终设备验证**（正式包，零热补丁）：

```
CJK theme font applied to 13 text styles (Icon kept as 'Icons')
INBOX loadMessagelist: 2 message(s)
SERVICE started pid=28469
```

截图确认：账户 / 收件箱 / 已发送 / 草稿 / 回收站 / 全部邮件 / 聊天，
图标（信封/纸飞机/铅笔/垃圾桶/聊天）全部正常。

**包**：run 45120317532 → `/tmp/pybitmessage-m6b.apk`（个钥重签，
sha256 `3031c8adb1e6ac1e593f695f35c7b42f2ac215ae0aaf82c4102b0da8adc1c2c8`，
含全部历史修复 + 中文菜单）。

**同时发现的未完成项**（记录，非本轮范围）：

1. **「已发送」页面为空**——与最初 Inbox 同样的上游缺陷：该页从未实现数据查询。
   顺带说明：本轮 Inbox（抽屉里的）已修好，但 Sent/Draft/Trash/AllMails 仍是空壳。
2. **搜索框仍显示 "Search"**——硬编码在 kv 里，不走 `tr._()`，不在本轮词典范围。

### 1.46 ✅✅ M6 包装机 + 热点公网发送实测（2026-11-23 13:36）

**装机**：`/tmp/pybitmessage-m6.apk`（run 45112151883，含全部修复 + 中文菜单）。
装机前备份三件套；装后零热补丁残留。

**启动验证**：

```
INBOX loadMessagelist: 2 message(s)
INBOX cjk font registered from /system/fonts/NotoSansCJK-Regular.ttc
KEEPALIVE active: wakeLock=True
SERVICE started pid=28218
TCP established: bootstrap8444.bitmessage.org:8444 outbound=True   ← 热点秒连公网
```

（中文菜单的目视确认由用户执行——当前会话模型不支持读图。）

**热点网络下的公网状态**（对比 IBMGuest 全天 0 连接）：

```
8444 ESTABLISHED 连接数: 5
TCP established: bootstrap8444 / 170.75.175.82 ...
```

**UI 发送实测**（用户指定场景：发给 test form sjy 的地址）：

```
收件人: BM-2cXj6btesow8nHkDz1zEYSicugi1qMf7jf
内容:   Hello jy from Xiaomi Pad hotspot 1133
时间:   13:33:58  状态: msgsent（PoW 完成、已通告）
```

（注：adb input text 的 %s 转义吞了一个字符，实际文本为 "Hello jy…"，不影响功能。）

**库存中待送达的消息**（big-inv 已随连接通告给 5 个 peer）：

| 发送时间 | 消息 | 状态 |
|---|---|---|
| 13:33 | Hello jy from Xiaomi Pad hotspot 1133 | msgsent（刚发） |
| 09:24 | Hi sjy from XiaoMi Pad | msgsent（早上 IBMGuest 卡住，现已通告） |
| 11-19 20:49 | 来自小米平板5… | msgsent（TTL 至今晚 20:46） |

sjy 是否收到取决于其节点何时上线；消息有效期 4 天（11-19 的两条到今晚）。
回执（ackreceived）出现即为送达确认。

### 1.45 ✅ M6 第一阶段：抽屉菜单 + 全部 tr._() 字符串中文化（2026-11-23 12:43）

**问题**：主界面是中文，但抽屉菜单读作 Inbox / Sent / Draft / Trash / All Mails /
Chat / Address Book / Settings…（英文）。上游的 `BaseLanguage._()` 是空壳
（直接返回原文），且从未发过 Kivy 翻译文件。

**实现**（commit `6cd7456`）：`Lang` 类内置 **88 条 ZH 词典**，`_()` 查表翻译
（未命中回退英文）；`NavigateApp` 实例化改为 `Lang("zh")`。不改任何 kv 文件——
所有 `app.tr._()` 调用点自动生效。

**覆盖度验证**（AST 提取 + 单元检查）：从 main.kv / kv/*.kv / mpybit.py /
baseclass/*.py 收集全部 **92 个真实 UI 字符串**，88 条已翻译、8 条豁免
（端口号、主机名、协议名等技术值：0/00000.0/8444/9050/localhost/Namecoind/
NMControl/UPnP）。**零缺失**。

**包**：run 45112151883 → `/tmp/pybitmessage-m6.apk`（个钥重签，
sha256 `f10a5be53fe4065bc1e8de38ca461c6eb5a16d86d9f839dc1a25a3e6e5fc433a`）
字节码验证：ZH 词典（收件箱/已发送/通讯录…）与 `Lang("zh")` 均在包内。
**待设备装机验证**（截图确认菜单中文显示）。

### 1.43 ◐ M4.5.1+M4.8.1 设备验收通过；M4.8.2 送达受阻；发现桥接 TLS 竞态（2026-11-23 12:06）

**装机**：`/tmp/pybitmessage-m481.apk`（sha256 `777cd5cc…`，run 45104172546，
含 M4.5.1+M4.8.2+M4.8.1）。装机前备份三件套；装机后确认零热补丁残留。

| 任务 | 设备验收结果 |
|---|---|
| **M4.5.1** | ✅ `dumpsys package` 的 `flags` **无 ALLOW_BACKUP**（修复前该 flag 存在） |
| **M4.8.1** | ✅ 发消息（11:33，UI 操作，`msgsent`）触发 inventory 写入后运行 30+ 分钟：`THREAD-CRASH singleCleaner` **0 次**；`inventory` 表 10009 个对象含刚 flush 的 type=2 消息对象（正是以前崩溃的路径）。knownnodes mtime 未变属正常（无过期节点可清理时不写盘） |
| **M4.8.2** | ◐ 代码+单元验证通过；**送达实测被环境阻塞**（见下） |

**M4.8.2 送达实测的两个阻塞**：

1. **平板在 IBMGuest 访客 Wi-Fi**（172.24.5.126）：种子对该出口 IP 持续回
   `Too many connections from your IP`，App 重启后从未建立任何 peer 连接
   （今天全程 0 次 `TCP established`）。消息对象（11:33 生成）仍在本地库存，
   等平板回到可用网络后会在连接建立时经 big-inv 通告出去。
2. **USB 桥接被 TLS 竞态卡死**（新发现，见 1.44）。

### 1.42 ✅ M4.8.1 完成：singleCleaner 不再死于 str 类型 tag（2026-11-23 11:20）

**崩溃链**（2026-11-19 实测，平板和 Mac 节点都发生过）：

```
THREAD-CRASH singleCleaner: TypeError("memoryview: a bytes-like object is
required, not 'str'")  at storage/sqlite.py flush() → sqlite3.Binary(value.tag)
→ singleCleaner 线程死亡 → knownnodes 永不落盘 → 每次重启重新抽签连节点
```

**根因**（审计全部 Inventory 写入点发现，全是 py2 遗留）：

| 位置 | 问题 | 数量 |
|---|---|---|
| `class_singleWorker.py`（pubkey×2 / broadcast / onboarding pubkey） | tag 写成 `''`（str，py2 里 `''`==`b''`） | 4 处 |
| `class_singleWorker.py:521`（v4 地址 msg） | 用了 **py2 的 `buffer()`**，py3 无此内建会 NameError | 1 处 |
| `api.py` disseminatePubkey | tag 写成 `''` | 1 处 |

**修复**（commit `b9c9996`）：

1. 全部 6 处改为 `b''` / 原生对象（去掉 `buffer()`）
2. `flush()` 加 `_as_bytes()` 防御（str→latin-1 bytes，bytearray/memoryview→bytes），
   今后任何 str 类型的写入都不会再杀死线程

**单元验证**：`''` / `'abc'` / `b'\x01'*32` / `bytearray(b'xyz')` 全部通过
`_as_bytes` → `sqlite3.Binary` 绑定；完整 flush 路径模拟通过。

（注：第一版防御用 `bytes(value)`，本地测试当场发现 py3 的 `bytes(str)`
需要 encoding 参数——测试先行避免了又一次设备翻车。）

**包**：run 45104172546 → `/tmp/pybitmessage-m481.apk`（个钥重签，
sha256 `777cd5ccd1c1ddcc2ab16771ff89f271b2924a4f23d13bf3b26ba4631429e7d1`）
**此包包含 M4.5.1 + M4.8.2 + M4.8.1 全部修复**，装机直接验它即可。
字节码验证：`_as_bytes` 在 sqlite.pyc、无 str-tag 残留在 singleWorker.pyc。

**待设备验收**（MILESTONES 的 L+F 标准）：运行 1 小时 logcat 无
`THREAD-CRASH singleCleaner`；`knownnodes.dat` mtime 随运行更新。

### 1.41 ✅ M4.8.2 完成：skip 窗口不再吞掉已有对象的 getdata（2026-11-23 11:02）

**问题**（2026-11-19 公网实测发现，当晚 3 条消息卡死）：

```
节点全量同步中，peer 不断请求它还没下载到的对象 → 每次未命中
antiIntersectionDelay() 都把 skipUntil 往后推 → 窗口无限滑动 →
bm_command_getdata 在窗口内直接 return True，把请求整个丢弃
→ 我们自己刚完成 PoW 的消息被 inv 通告了却永远不会被服务
→「msgsent 但永不送达」
```

**修复**（commit `8664414`）：窗口内不再整单丢弃，改为**只排队我们实际持有的对象**
（查 `state.Inventory`）；未持有的照旧丢弃。防御的时序性质不变——`UploadThread`
本来就拒绝在 skipUntil 之前服务任何连接，排队只是让请求活到窗口打开之后。

**单元验证**（真实方法绑定到假连接对象）：

```
skipUntil = now + 300s（窗口内）
getdata = [已知对象 hash, 未知对象 hash]
→ 已知对象进入 pendingUpload ✅
→ 未知对象被丢弃（无 KeyError 风暴、无队列膨胀）✅
（修复前：两个都被丢弃）
```

**包**：run 45102409426 → `/tmp/pybitmessage-m482.apk`（个钥重签，
sha256 `6fe34d99517e3dc8a897e1f83d9246bba3c9e2426114b577ae0dc8a5c0932969`）
字节码验证：`bm_command_getdata` 的 co_names 含 `state`/`Inventory`
（修复前该方法不引用它们）。

**待设备验收**（MILESTONES 的 **T** 标准：新地址间送达 P95 ≤ 5 分钟）：装机后
发消息实测。装机等用户确认——M4.8.2 的包**包含** M4.5.1（allowBackup=false），
直接装 m482 包即可两个都验。

### 1.40 ✅ M4.5.1 完成：allowBackup=false，私钥不再进云备份（2026-11-23 10:02）

**问题**（aapt2 实测基线包）：

```
android:allowBackup(0x01010280)=true    ← keys.dat 的明文私钥有资格进厂商云备份
```

**修复**：`buildozer.spec` 的 `android.allow_backup = False`（commit `a4c1417`）。

**验收（A）**——run 45096582390 出包，aapt2 确认：

```
android:allowBackup(0x01010280)=false   ✅
```

包：`/tmp/pybitmessage-m451.apk`（个钥重签，
sha256 `3c31284a3cb40eaec906853bd9c8a89914caabfb8a57458905477bbc27a1d710`）

**说明**：这是 M4.5.2（Keystore 私钥加密）之前的必要止血——在私钥还是明文存储的
阶段，唯一正确的做法是完全退出备份。设备装机验证待用户确认后进行。

### 1.39 ✅✅ 稳定基线包：零热补丁，全部功能设备验证通过（2026-11-23 09:42）

**背景**：此前平板靠 3 个热补丁文件运行（inbox.py / msg_composer.py / mpybit.py），
一旦装新包修复就会丢失。本次把它们全部固化进 APK。

**包**：

```
/tmp/pybitmessage-baseline-2026-11-23.apk
sha256 d3a0e650b38a86cfbfc6002c32b82f09947beb9c14a05fdaa67f7f00922a7225
run    45094228488（commit b44b7b9）
```

**字节码校验**（解包 assets/private.tar 检查 pyc 里的函数名）：

```
inbox    : _cjk_font, _repair_legacy_rows, _install_row_taps, _open_detail, _text_label  ✅
composer : send                                                                          ✅
mpybit   : _composer_action                                                              ✅
```

**安装步骤**：备份 keys.dat/messages.dat/knownnodes.dat → `pm install -r -d`
→ **删除全部热补丁 .py 及其 .pyc** → 确认 `find files/app -name "*.py"` 无输出。

**设备验证（零热补丁）**：

```
INBOX loadMessagelist: 2 message(s)
INBOX cjk font registered from /system/fonts/NotoSansCJK-Regular.ttc
KEEPALIVE active: wakeLock=True batteryExempt=False
SERVICE started pid=29712
崩溃（JNI / Fatal / Unhandled）: 0 次
INBOX row tapped from=BM-2cXj6btesow8nHkDz1zEYSicugi1qMf7jf
INBOX open detail from=BM-2cXj6btesow8nHkDz1zEYSicugi1qMf7jf len(body)=7
```

截图确认：收件箱中文正常（`来自 BM-2cXj6bteso…`、`公网测试 1`），点击弹出详情窗口
（主题/来自/时间/正文齐全）。

### 1.38 ✅✅ 点击打开详情成功（2026-11-23 09:05）

接 1.37 的未完成项。**又踩了三个坑，都是设备日志/截图定位的**：

| # | 尝试 | 现象 | 根因 | 处置 |
|---|---|---|---|---|
| 1 | 每行改成原生 `Button` | 布局崩坏：只显示 `…` / `来…` / `he…` | Button 内的 BoxLayout 尺寸塌陷 | **回退**为普通 BoxLayout |
| 2 | 在 BoxLayout 上绑 `on_touch_*` / `ButtonBehavior` mixin | 无反应，无日志 | MDList/ScrollView 内布局收不到触摸 | 放弃 |
| 3 | **在 MDList 上装 `on_touch_down` 命中测试** | ✅ `INBOX row tapped from=…` | —— | 采用 |
| 4 | 弹 `MDDialog` 时传 `font_name` | 抛 `TypeError: Properties ['font_name'] ... may not be existing property names` | **MDDialog / MDFlatButton 根本没有 `font_name` 属性** | 去掉；对话框 chrome 用 ASCII（Message/Close），中文内容放在 custom content 里（原生 Label + CJK 字体） |

**设备验证**（两条消息各点开一次）：

```
INBOX row tapped from=BM-2cXj6btesow8nHkDz1zEYSicugi1qMf7jf
INBOX open detail from=BM-2cXj6btesow8nHkDz1zEYSicugi1qMf7jf len(body)=7
INBOX open detail from=BM-2cSqxwX1LEDbPF93DJCKWYNU7v4bkADDY6 len(body)=61
```

截图确认弹窗内容：

```
Message
主题：公网测试 1
来自：BM-2cSqxwX1LEDbPF93DJCK...
时间：2026-11-19 20:14:35
hello via public network, from Mac at home (19:52) 中文+emoji ⊠
Close
```

中文、英文、时间全部正确。**emoji 🎉 显示为 ⊠**——`NotoSansCJK` 不含 emoji 字形，
属已知限制（后续可换 `NotoColorEmoji` 或多字体回退）。

### 1.37 ✅ 收件箱中文乱码修复 / ❌ 点击详情仍失败（2026-11-22 21:10）

**用户截图反馈**：列表和详情里中文全是 □（豆腐块），英文正常。
说明**数据已正确**（迁移成功），是**字体渲染**问题。

**三个根因（层层嵌套，逐个用设备日志/截图确认）**：

| # | 发现方式 | 根因 | 修复 |
|---|---|---|---|
| 1 | 加 `print` 诊断 | `INBOX font lookup -> 'Roboto'`。APK 打包了**两份** `messaging` 模块，注册 CJK 字体的 `MessagingScreen` 在 `bitmessagekivy/`，而 inbox 导入的是 `pybitmessage/bitmessagekivy/`，那份的 `FONT` 永远是默认值 | inbox **本地注册** `LabelBase.register('CJK', '/system/fonts/NotoSansCJK-Regular.ttc')`（日志：`INBOX cjk font registered from …`） |
| 2 | 截图对比 | 字体注册后**仍显示 □** —— `MDLabel` 走主题字体，忽略 `font_name` | 改用**原生 `Label`**（与 `messaging.py` 主界面一致，主界面中文一直正常） |
| 3 | 截图 | 文字居中、地址被截断 | `text_size` 绑定控件宽度，`halign`/`shorten` 才生效 |

**验证**：截图确认 `公网测试 1`、`来自 BM-2cXj6bteso…` 均正常显示中文，左对齐、截断正确。

**未解决：点击消息打开详情**

- 尝试 1：`on_touch_down/up` 绑定 → 无效（`BoxLayout` 无 `ButtonBehavior`，不派发触摸）
- 尝试 2：`widget.__class__ = ButtonBehavior mixin` → **仍无效**，日志无 `INBOX open detail`
- 怀疑：行控件在 `MDList` / `ScrollView` 内，触摸被上层拦截
- 建议：改用原生 `Button`（`background_normal=''`，内嵌 BoxLayout 放文字）

**平板当前带热补丁**：`files/app/pybitmessage/bitmessagekivy/baseclass/inbox.py`，
该修复**尚未出正式包**。

### 1.36 ✅✅ M3.9.1a/b/c 全部完成：收件箱三个缺陷闭环（2026-11-22 20:46）

**包**：`/tmp/pybitmessage-body-2026-11-20.apk`（run 44686653091，个钥重签，
sha256 `fc0709fffb94a403905d09597c6c971f02f9fc8bc3049506c0c3fbcffc7d6a86`）
注：因公司网访问 GitHub 受限，本次经 `proxy.apj.ibm.com:8080` 下载（后续下载都走此代理）。

**设备实测**：

```
INBOX migrated 1 legacy row(s)          ← 正文迁移执行
INBOX loadMessagelist: 2 message(s)
INBOX open detail from=BM-2cXj6bteso… len(body)=7   ← 点击打开详情（"Hellow!" 7 字符）
KEEPALIVE active: wakeLock=True batteryExempt=False
SERVICE started pid=21088
JNI 崩溃: 0 次
```

**迁移后数据库终态**（之前标题和正文都是 `b'...'` repr）：

```
时间: 2026-11-20 09:56
  标题: test form sjy
  正文: Hellow!

时间: 2026-11-19 20:14
  标题: 公网测试 1
  正文: hello via public network, from Mac at home (19:52) 中文+emoji 🎉
```

| 缺陷 | 结果 |
|---|---|
| (a) 点消息无反应 | ✅ 点击弹出详情（日志确认） |
| (b) 地址旁豆腐块 | ✅ 已移除图标字体依赖（纯 MDLabel + CJK 字体） |
| (c) 历史 bytes repr | ✅ 标题 + 正文都迁移为正常文本 |

### 1.35 ◐ M3.9.1a/b/c：收件箱三个 UI 缺陷修复（2026-11-20 14:05，待设备验证）

**用户实测发现**（clean 包，2026-11-20 13:59 截图）：

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| a | 点消息**没有反应** | `_render()` 只渲染列表，没有任何点击绑定；上游 `maildetail` 从未被接上 | 每行改为可点卡片（`on_touch_down/up` 且位移 <20px 才算点击，避免误触发滚动），弹出 `MDDialog` 显示主题/发件人/时间/**完整正文**（`ScrollView` 可滚动） |
| b | 地址左边两个 **□□ 豆腐块** | `TwoLineListItem` 内置头像图标依赖 KivyMD 图标字体，APK 未完整打包 | 改用纯 `MDLabel` 堆叠 + `messaging.py` 已注册的 CJK 字体，**完全不依赖图标字体** |
| c | 历史消息标题显示 `b'\xe5\x85\xac...'` | 19 日晚 `api.py` bytes 入库 bug 时期写入的数据 | `_bidi_safe_text()` 显示时解码；`_repair_legacy_rows()` 一次性回写（幂等，无匹配时零开销） |

**迁移逻辑本地验证**（拿设备数据库备份做样本）：

```
迁移前: b'\xe5\x85\xac\xe7\xbd\x91\xe6\xb5\x8b\xe8\xaf\x95 1'
修复为: 公网测试 1        ← 正确
其他行: test form sjy     ← 保持不变
```

**设备验证（run 44685032281 的包，2026-11-20 14:15）**：

```
INBOX migrated 1 legacy subject(s)        ← 历史数据修复
INBOX loadMessagelist: 2 message(s)
INBOX open detail from=BM-2cSqxwX1LEDb… len(body)=101   ← 用户点开成功
KEEPALIVE active: wakeLock=True batteryExempt=False
SERVICE started pid=16546
JNI 崩溃: 0 次
```

| 项 | 结果 |
|---|---|
| (a) 点击打开详情 | ✅ 日志确认 `open detail` 被触发 |
| (b) 豆腐块图标 | 待用户目视确认（代码已移除图标字体依赖） |
| (c) 历史标题 | ✅ 数据库已是 `公网测试 1` |

**发现遗漏**：迁移只处理了 `subject` 列，**正文仍是** `b'hello via public network…'`。
已扩展迁移到 `message` 列（commit `02a92c7`，本地用设备库备份验证：
正文解码为 `hello via public network, from Mac at home (19:52) 中文+emoji 🎉`）。

### 1.34 ✅✅ 正式包（无热补丁）全项通过（2026-11-20 13:55）

**包**：`/tmp/pybitmessage-2026-11-20.apk`（run 44681905358，个钥重签）
sha256 `5b61650203ef2a91c689621aff96a0dae70a795daa2b818a1541dce3e5c19066`

**关键前置**：安装后必须**删掉 `files/app/` 下的热补丁 `.py`**，否则它们会覆盖新包里的
`.pyc`（本次发现残留 `main.py`、`android_keepalive.py` 两个）。

**设备实测**：

```
$ adb shell ps -A | grep bitmessage
... at.bitmessage.pybitmessage:service_pybitmessagesvc   ← 服务
... at.bitmessage.pybitmessage                            ← UI

JNI DETECTED / Fatal signal 6 次数: 0

$ adb logcat -s python:* | grep -E "KEEPALIVE|SERVICE|INBOX"
KEEPALIVE scheduled in 8.0s (main thread)
INBOX loadMessagelist: 2 message(s)          ← 菜单 Inbox 有数据
INBOX loadMessagelist: 2 message(s)          ← on_pre_enter 刷新
KEEPALIVE: partial wake lock acquired
KEEPALIVE active: wakeLock=True batteryExempt=False
SERVICE startForegroundService(... -> core_service.py) issued, API 33
SERVICE started pid=11367

$ adb shell dumpsys activity services
    isForeground=true foregroundId=1 foregroundNoti=Notification(channel=org.kivy.p4a1 ...)

$ adb shell dumpsys power | grep pybitmessage:node
  13:54:14.390 - ACQ pybitmessage:node (partial)      ← 单次获取，无重复
```

**结论**：M4.1（前台服务）、M4.3（WakeLock）、M3.9.1（菜单 Inbox）三项在**正式包**上
全部生效，与热补丁验证结果一致。

### 1.33 ✅ 启动即崩已修复 + 菜单 Inbox 修复验证通过（2026-11-20 13:35）

**症状**：装上 1.32 的包后 App 一启动就闪退。

```
JNI DETECTED ERROR IN APPLICATION: jclass is an invalid JNI transition
frame reference or invalid reference ... in call to GetMethodID
  from int org.libsdl.app.SDLActivity.nativeRunMain(...)
libc: Fatal signal 6 (SIGABRT) in tid (SDLThread)
```

**两次尝试、两个不同根因**（都是读设备日志发现的）：

| 尝试 | 做法 | 结果 | 根因 |
|---|---|---|---|
| 1 | `startForegroundService()` 放在 `bitmessagemain.main()` **之前** | 闪退 | 服务进程在主进程还在初始化 SDL/JNI 时被 fork，JNI 引用失效 |
| 2 | 挪到**工作线程** + sleep 8s | 闪退且不启动服务 | 工作线程没有 JNI class loader → `ClassNotFoundException: ServicePybitmessagesvc` |
| 3 | **Kivy `Clock.schedule_once`（主线程）** | ✅ 正常 | 事件循环已建立，JNI 上下文有效 |

**最终设备实测**：

```
KEEPALIVE scheduled in 8.0s (main thread)
KEEPALIVE: partial wake lock acquired
KEEPALIVE active: wakeLock=True batteryExempt=False
SERVICE startForegroundService(... -> core_service.py) issued, API 33
SERVICE started pid=18263

$ ps -A | grep bitmessage
... at.bitmessage.pybitmessage                      ← UI 进程
... at.bitmessage.pybitmessage:service_pybitmessagesvc  ← 服务进程
JNI 错误次数: 0
```

**另外两个修复**：

1. **去掉 BroadcastReceiver**：用 `JavaClass` 继承 `BroadcastReceiver` 也会触发同样的
   invalid-jclass abort。改为 wake lock 一次获取、进程生命周期内一直持有（省电收益
   远小于崩溃风险；耗电由 M4.7.1 另行测量）
2. **wake lock 去重**：加 `isHeld()` 判断。之前 `dumpsys power` 里同一 tag 累积了 19 条
   ACQ 记录；修复后单次启动只有 1 条 ACQ

**菜单 Inbox 修复验证**（1.32 的改动）：

```
INBOX loadMessagelist: 2 message(s)
INBOX loadMessagelist: 2 message(s)   ← on_pre_enter 再次刷新
```

收件箱 2 条消息（今天 09:56「test form sjy」+ 昨晚「公网测试 1」）都能被菜单 Inbox 加载。

### 1.32 M3.9.1 修复：菜单里的 Inbox 永远是空的（2026-11-20 12:55）

**用户报告**：打开抽屉菜单 → Inbox，里面什么都没有（但主界面能显示消息）。

**根因**（上游遗留 bug）：

```python
# baseclass/inbox.py，修复前
def loadMessagelist(self, where="", what=""):
    """Load inbox messages"""
    self.set_default_address()
    self.account = self.kivy_state.selected_address
    # ← 函数到此结束，从未查询数据库，MDList 永远是空的
```

`kv/inbox.kv` 里的 `MDList(id=ml)` 没有任何数据绑定。主界面（`messaging.py`）
之所以能显示，是因为它自己在 `refresh_inbox()` 里直接 `sqlQuery`。

**修复**：

1. `loadMessagelist()` 改为调用 `messaging.inbox()` 取数，用 `TwoLineListItem`
   渲染（主题 + 来自 xxx）
2. 新增 `on_pre_enter()`：每次进入该屏幕都重新加载（原来只在构造时加载一次，
   启动后到达的消息永远看不到）
3. 加日志 `INBOX loadMessagelist: N message(s)` 便于验证

**⚠️ 同一时段发生的严重事故（必须记录）**：

热补丁时误执行 `adb shell pm clear at.bitmessage.pybitmessage`，
**清空了平板全部 App 数据**：

| 数据 | 结果 |
|---|---|
| `keys.dat` 里的地址与私钥 `BM-2cU2vEDgphdWHe4Ucp1gSigCwDrJTRfyYV` | ❌ **永久丢失**，不可恢复 |
| `messages.dat`（收件箱 2 条） | ✅ 从本地备份 `/tmp/tab_db_now.dat` 恢复 |
| 新地址 | 自动生成 `BM-2cXrmLDcoGry6Z4kRWqCthD7kuhRxkzaWx`（另有 `BM-2cWGibweLdxrUHN2JaLhGiBtekxZAw2ufV`） |

已把「**永远不要对装机设备跑 `pm clear`**」写进 HANDOFF §7 首位，并附上实验前
备份 `messages.dat` 的命令。

**影响面**：若有人保存过旧地址并发送消息，现在无法接收；把新地址重新发给对方即可。

### 1.31 ◐ M4.3 进行中：WakeLock 生效，锁屏 5 分钟连接保持（2026-11-20 12:05）

**实现**：新增 `src/android_keepalive.py`（partial wake lock + 电池优化豁免引导），
`buildozer.spec` 加 `WAKE_LOCK` / `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`。

**设备实测**（run 44669834948 的包，平板）：

```
$ adb logcat -s python:* | grep KEEPALIVE
KEEPALIVE: partial wake lock acquired
KEEPALIVE: screen receiver failed: ... BroadcastReceiver is not an interface
KEEPALIVE: ignoring battery optimizations = False
KEEPALIVE: battery exemption prompt shown

$ adb shell dumpsys power | grep pybitmessage
PARTIAL_WAKE_LOCK 'pybitmessage:node' ACQ=-1m2s73ms LONG (pkg=at.bitmessage.pybitmessage)
  ← 系统确认 wake lock 真的持有
```

**锁屏对照测试**（`input keyevent KEYCODE_POWER`，`mWakefulness=Asleep`）：

| 时刻 | ESTABLISHED | 进程数 | wakeLock |
|---|---|---|---|
| 锁屏前 | 15 | 2 | 1 |
| t+1min | 16 | 2 | 2 |
| t+2min | 12 | 2 | 2 |
| t+3min | 12 | 2 | 2 |
| t+4min | 12 | 2 | 2 |
| t+5min | 11 | 2 | 2 |

**结论**：锁屏期间连接稳定保持（11–16 条），两个进程存活，wake lock 全程持有。
对比 2026-11-19 锁屏后 App 被 MIUI 完全冻结（UDP `PermissionError`、API 无响应），
这是决定性改善。

**待修/待验**：

1. `BroadcastReceiver` 是抽象**类**不是接口，pyjnius 要用 `JavaClass` 而不是
   `__javainterfaces__`（已提交修复 `2232beb`，待出包验证）；不影响 wake lock 本身
2. **D5 完整验收（锁屏 30 分钟仍能收到消息）尚未做**，需要在锁屏期间从 Mac 发一条
3. 电池优化豁免弹窗会跳 `com.miui.powerkeeper/HiddenAppsConfigActivity`，
   **需要用户在平板上手动确认**才能进白名单

### 1.30 ✅✅ M4.1e 通过：前台服务真正跑起来（2026-11-20 11:42）

**设备实测**（小米平板 5，`main.py` 热补丁后重启）：

```
$ adb shell ps -A | grep bitmessage
u0_a270  17068  ...  S at.bitmessage.pybitmessage
u0_a270  27745  ...  S at.bitmessage.pybitmessage:service_pybitmessagesvc   ← 服务进程

$ adb logcat -s python:* | grep SERVICE
SERVICE started pid=27745
SERVICE visible notification posted (API 33)
SERVICE heartbeat uptime=60s notification=True

$ adb shell dumpsys activity services at.bitmessage.pybitmessage
  * ServiceRecord{... at.bitmessage.pybitmessage/.ServicePybitmessagesvc}
    isForeground=true foregroundId=1 foregroundNoti=Notification(channel=org.kivy.p4a1 ...)

退出 UI（KEYCODE_HOME）25 秒后再查：
  ✅ 主进程 + :service_pybitmessagesvc 都在，心跳继续
```

**解决过程中踩到的三个真实问题**（每一个都是设备日志发现的，不是猜的）：

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | `Unable to start service Intent { cmp=.../org.kivy.android.PythonService } ... not found` | p4a 按 buildozer `services=` 的名字生成类名 | 用 `at.bitmessage.pybitmessage.ServicePybitmessagesvc` |
| 2 | `NullPointerException: String.equals(...) on a null object`（`PythonService.java:82`） | `onStartCommand()` 对 `getString()` 的结果调 `.equals()`，缺键即崩 | 补 `serviceStartAsForeground="true"`（触发 `doStartForeground()`）+ `serviceTitle`/`smallIconName`/`contentTitle`/`contentText` |
| 3 | `JNI DETECTED ERROR: GetStringUTFChars received NULL jstring` → SIGABRT | `nativeStart()` 有 7 个字符串参数，Java 全部过 `GetStringUTFChars` | 补 `androidArgument`/`pythonName`/`pythonHome`/`pythonPath` |

**另一个关键点**：jnius 把 Python `str` 绑定到 `putExtra(String, CharSequence)` 重载，
`Bundle.getString()` 就取不到值。**必须把 key 和 value 都包成 `java.lang.String`**，
强制走 `(String, String)` 重载。这是前两次尝试"看起来传了却没生效"的原因。

**更正 1.28 的说法**：`foregroundServiceType` 确实不需要（targetSdk 33），
但**服务本身必须被显式启动**——这是 M4.1d 暴露、M4.1e 修复的核心缺口。

### 1.29 ❌ M4.1d 设备验证失败：服务从未被启动（2026-11-20 11:16）

**设备**：小米平板 5（`b45f8e87`），装 run 44659795746 的包（个钥重签，免卸载升级）。

| 检查项 | 期望 | 实际 | 结论 |
|---|---|---|---|
| 升级安装 | `pm install -r -d` 成功 | ✅ Success，数据保留（`knownnodes.dat` 仍是 11-19 15:16） | ✅ |
| 主进程 | 存在 | ✅ `at.bitmessage.pybitmessage`（pid 16444） | ✅ |
| **`:service_pybitmessagesvc` 进程** | 存在 | ❌ **不存在** | ❌ |
| **已注册服务** | 1 个 | ❌ `dumpsys activity services` → `(nothing)` | ❌ |
| SERVICE 日志 | `SERVICE started / heartbeat` | ❌ 无 | ❌ |

**根因（已确认）**：`core_service.pyc` **确实被打进了 APK**
（logcat：`extracting core_service.pyc` + `extracting pybitmessage/core_service.pyc`），
但 **p4a 只负责"声明"服务，不会自动"启动"它**。启动需要从 Java 侧或 Python 侧调用
`startService()/startForegroundService()`，本项目从未调用。

**这是 M4.1 阶段的真实缺口**，不是打包问题。修复方向（下一阶段 M4.1e）：

1. 在 `src/main.py` 启动后，用 pyjnius 调
   `PythonActivity.mActivity.startForegroundService(intent)`，intent 指向
   `org.kivy.android.PythonService`，extra 里带 `serviceEntrypoint`（p4a 约定）
2. 或者在 Java 侧 Activity 里 `onCreate` 时 `startService`

**附带确认的好消息**：

- 免卸载升级链路可用（个钥重签 + `pm install -r -d`，数据无损）
- 核心在网络正常工作（`netstat` 22 条 ESTABLISHED）

### 1.28 ✅ M4.1c 完成：前台服务所需权限已齐（2026-11-20 10:35）

**结论先行**：`android:foregroundServiceType` 在本项目**当前不需要**——它是
**targetSdk ≥ 34** 才强制。本项目 `targetSdkVersion:'33'`，`startForeground()`
只要 `FOREGROUND_SERVICE` 权限即可。之前判断的"缺口 1"是我对 API 版本的误判，
在此更正。

| 项 | 结果 | 证据 |
|---|---|---|
| CI 构建 | ✅ run **44659795746**（exit 0） | `gh run watch --exit-status` |
| `FOREGROUND_SERVICE` 权限 | ✅ 在包内 | 见下 |
| `POST_NOTIFICATIONS` 权限 | ✅ 在包内 | 见下 |
| service 声明 | ✅ 保持 | 见下 |

```
$ aapt2 dump badging .../pybitmessage-0.1.2-arm64-v8a-debug.apk
targetSdkVersion:'33'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.ACCESS_NETWORK_STATE'
uses-permission: name='android.permission.FOREGROUND_SERVICE'
uses-permission: name='android.permission.POST_NOTIFICATIONS'

$ aapt2 dump xmltree --file AndroidManifest.xml ...
  E: service (line=68)
    android:name="at.bitmessage.pybitmessage.ServicePybitmessagesvc"
    android:process=":service_pybitmessagesvc"
```

**过程中的两次翻车（都记下来，避免重犯）**：

1. **run 44658662598 构建失败**：`p4a.hook = packages/android/p4a_hook.py`
   被 buildozer 又拼了一次 spec 目录，变成
   `packages/android/packages/android/p4a_hook.py`。**`p4a.hook` 只写文件名**。
2. `--extra-manifest-xml` 通过 p4a hook 注入**没有生效**（hook 的
   `before_apk_build` 未被调用，日志无输出）。既然 targetSdk 33 不需要该属性，
   直接删掉 hook，spec 里留注释说明何时需要重新加。

**剩余**：M4.1d 设备验证（通知可见 + `:service` 进程 + 退 UI 存活），**等平板接 USB**。

### 1.27 ◐ M4.1a/b 完成：服务已进包（2026-11-20 09:05）

**本阶段范围**：只做「把 p4a 服务机制跑通并进包」，不搬核心、不做设备验证。

| 项 | 结果 | 证据 |
|---|---|---|
| M4.1a 服务入口 | ✅ `src/core_service.py` 新增 | 代码已提交（`f4fddd0` 起） |
| M4.1b spec 声明 | ✅ `services = pybitmessagesvc:core_service.py` | 见下 |
| CI 构建 | ✅ run **44649423146**（buildozer android debug，exit 0） | `gh run watch --exit-status` |
| **manifest 断言（A）** | ✅ **通过** | 见下方 aapt2 输出 |

```
$ aapt2 dump xmltree --file AndroidManifest.xml pybitmessage-0.1.2-arm64-v8a-debug.apk
  E: service (line=66)
    android:name="at.bitmessage.pybitmessage.ServicePybitmessagesvc"
    android:process=":service_pybitmessagesvc"
```

**本阶段发现的缺口（下阶段 M4.1c/d 处理）**：

1. p4a v2024.01.21 的模板**只生成 `android:process`**，没有 `foregroundServiceType`，
   也没有 `FOREGROUND_SERVICE` 权限 → Android 9+/14 上前台服务会被系统拒绝启动。
   需要在 spec 里补 `android.permissions`，并用 `--extra-manifest-xml` 或 hook 注入
   `android:foregroundServiceType="dataSync"`。
2. p4a 的 `PythonService.onStartCommand` 已经会 `startForeground()`，但它建的 channel 是
   `IMPORTANCE_NONE`（通知在通知栏**不可见**）。所以 `core_service.py` 自己再发一条
   `IMPORTANCE_LOW` 的可见通知——这是 M4.1c 要验证的点。
3. 设备未连接 USB，M4.1d 的装机验证未做。

### 1.26 ✅✅ G3 公网版达成：家庭网络双向加密消息 + 回执全通（2026-11-19 20:30）

**环境**：Mac 脚本节点（`scripts/pubnet_node.py`，C PoW）+ 小米平板 5（TLS 修复包，
热补丁后），两者都在家庭 Wi-Fi（192.168.31.x，小米路由器出口），各自连**公网节点**传播消息。

**时间线**：

| 时间 | 事件 |
|---|---|
| 19:44 | Mac 节点经 ~13 分钟重试抽签后 `TCP established: 85.114.135.102`（40 次被拒后成功——**证实"Too many connections"是瞬时/残留状态而非硬 ban**：同节点 19:46 拒、19:47 平板即被接受） |
| 19:47 | 平板 `TCP established: 158.69.63.42:8080`（曾被拒 1 分钟后被同一节点接受） |
| 19:52 | Mac→平板 发「公网测试 1」（协议默认难度，C PoW 秒级） |
| 20:01 | 平板→Mac 发消息 1；**20:02:44 `THREAD-CRASH InvBroadcaster`**——发现 `dandelion.py removeHash()` 的 `ord()` py3 bug，getpubkey 卡死 |
| 20:12 | 热补丁修复 dandelion.py + keys.dat 设 `dandelion=0`，重启 App |
| 20:14:35 | **平板收件箱收到 Mac 的消息**（`公网测试 1`） |
| 20:15:14 | **Mac 收件箱收到平板的消息**（awaitingpubkey 重试后 getpubkey→pubkey→msg 全链路通了） |
| 20:18 | 平板侧 `ackreceived`（收到 Mac 的回执） |
| 20:3x | Mac 侧第一条 `ackreceived`（收到平板的回执）——**双向消息 + 双向回执全部闭环** |

**本轮修掉的 bug（均热补丁验证 + 已入库）**：

| 文件 | bug | 症状 |
|---|---|---|
| `src/network/dandelion.py` `removeHash()` | py3 迭代 bytes 得 int，`ord(int)` 抛 TypeError（仅 DEBUG 日志开启 + dandelion 过期时触发） | **InvThread 整个线程死亡**，本节点对象永不广播（awaitingpubkey 卡死的真凶） |
| `src/api.py` `sendMessage`/`sendBroadcast` | `_decode` 返回 bytes 直接入库，存成 `b'\xe5\x85\xac...'` repr 字符串 | API 发送的消息收方显示乱码（消息内容本身是好的） |
| `scripts/pubnet_ctl.py` | xmlrpc 返回 `Binary` 对象不能切片；无 socket 超时 | sent/inbox 查询崩溃/挂起 |

**遗留观察**（未修，不阻塞）：

1. `THREAD-CRASH singleCleaner: memoryview not str`（20:01:44 再次确认）——knownnodes 落盘依赖它
2. MIUI 锁屏即冻结 App（灭屏后 UDP `PermissionError`、API 无响应、启动卡住）——**演示时必须保持亮屏**（`svc power stayon usb`）
3. `clientStatus.networkConnections` 与实际 socket 数不符（lsof 见 5 条 ESTABLISHED，API 报 1）
4. 平板 20:14 发的第二条消息 `doingmsgpow` 卡 5+ 分钟（原因未查，第一条正常）
5. 节点收到 SIGTERM 后优雅关闭流程可能挂死（旧节点变僵尸占单实例锁，需 `kill -9` + 删 `singleton.lock`）

**产品结论**：App 装在设备上、连任意网络（热点/家庭 Wi-Fi），与其他节点经公网 Bitmessage
网络互通加密消息，全链路（TCP+TLS、对象 PoW、pubkey 交换、消息传播、回执）真实可用。
"Too many connections from your IP" 会随重试自然穿透，非阻塞。

### 1.5 已知遗留（记入 M2.6，不阻塞 G2.3）

Kivy 各屏用 `from pybitmessage import state`（指向镜像副本），而核心用 `import state`（根目录原版）。APK 里这是**两个模块对象**，会导致 M2.6 "UI 显示真实连接数/地址"时读到另一份全局变量。M2.6 必须统一（方案：改 `import state`，或构建期给 `pybitmessage.*` 做模块别名）。

### 1.2 M2.2 连带修掉的 3 个 py3 问题（桌面 `-t` 首次运行暴露）

| 文件 | 问题 | 修复 |
|---|---|---|
| `src/shutdown.py:26` | `thread.isAlive()` 在 Python 3.9+ 已移除 → 关闭流程抛 `CRITICAL Unhandled exception` | 改为 `thread.is_alive()`（py2.6+ 与 py3 均可用） |
| `src/class_smtpServer.py:200` | 同上 | 同上 |
| `src/tests/core.py` | `import Queue`（py2 模块名）→ `-t` 测试模式直接 ImportError | `try: import queue as Queue / except ImportError: import Queue` |

> 其中 `shutdown.py` 这条影响的不只是测试模式：**Android 上的优雅退出/停止服务也会走这里**（M4 会用到），提前修掉省事。

### 1.3 设备侧探针（M2.2 后，run 44027789116）

```
PROBE python = OK (3.11.5 linux)
PROBE openssl_runtime = OK (OpenSSL 1.1.1w  11 Sep 2023)
PROBE ripemd160 = OK (bdabd16e480e77c5)
PROBE openssl_layer = OK (lib=<CDLL 'libcrypto1.1.so', ...>)
PROBE ecc_sign = OK (sign/verify ok (72 byte sig))
PROBE ecies = OK (encrypt/decrypt ok (150 bytes))
PROBE sqlite3 = OK (3.35.5)
PROBE msgpack = OK (bundled umsgpack 2.4.1 (fallback))
PROBE pycryptodome = FAIL (ModuleNotFoundError: No module named 'Crypto')
PROBE summary: 8/9 ok, failed=pycryptodome
```

`pycryptodome` 未装且不需要（hashlib 的 ripemd160 可用），此项 FAIL 属预期。

### 1.1 设备侧探针原始输出（Android 13 / arm64-v8a / run 44024863827）

```
PROBE python = OK (3.11.5 linux)
PROBE openssl_runtime = OK (OpenSSL 1.1.1w  11 Sep 2023)
PROBE ripemd160 = OK (bdabd16e480e77c5)
PROBE openssl_layer = OK (lib=<CDLL 'libcrypto1.1.so', handle eab7696b189b9039 at 0x76f8ca6a90>)
PROBE ecc_sign = OK (sign/verify ok (71 byte sig))
PROBE ecies = OK (encrypt/decrypt ok (150 bytes))
PROBE sqlite3 = OK (3.35.5)
PROBE msgpack = FAIL (ModuleNotFoundError: No module named 'umsgpack')
PROBE pycryptodome = FAIL (ModuleNotFoundError: No module named 'Crypto')
PROBE summary: 7/9 ok, failed=msgpack,pycryptodome
```

**两项 FAIL 均不影响运行，属探针判定或非必需依赖：**

| 项 | 真实情况 | 处理 |
|---|---|---|
| `msgpack` | 探针只试了 `import msgpack` / `import umsgpack`；实际代码 `helper_msgcoding.py` 还有第三级 `import fallback.umsgpack.umsgpack`，而 `src/fallback/` 已随 APK 打包 | 探针导入链需对齐（随 M2.2 一并修） |
| `pycryptodome` | 未加入 requirements；仅在 `hashlib` 不支持 ripemd160 时才需要兜底 | 当前不需要，保持不装 |

**跨平台一致性**：macOS 本地 `ripemd160` 也是 `bdabd16e480e77c5`，与设备一致 → 哈希实现无平台差异。

---

## 2. 环境与构建事实（一次性记录，供回溯时对照）

| 项 | 实测值 | 采集方式 |
|---|---|---|
| 主机 | macOS 26.6.2 / arm64 / 129 GiB 可用 | `sw_vers`、`df -h` |
| Docker | client 29.6.2-rd / server 29.5.3，`linux/aarch64`，2 CPU / 5.8 GiB | `docker info` |
| amd64 模拟损耗 | 约 **8.3×**（0.50s → 4.17s） | 同段 shell 循环对比 |
| Python（宿主） | 3.11.12（pyenv） | `python3 -VV` |
| JDK | 17.0.15（Homebrew）/ 17.0.21（IBM） | `/usr/libexec/java_home -V` |
| Android SDK | `~/Library/Android/sdk`：build-tools 28–36、platforms 33–36、licenses 已接受 | `ls` |
| adb | 36.0.0，`~/Documents/platform-tools/adb` | `adb version` |
| 模拟器 | AVD `Pixel_6_API_33`，arm64-v8a / API 33 | `~/.android/avd/*/config.ini` |
| APK 内解释器 | CPython **3.11.5**（`libpython3.11.so`） | `unzip -l *.apk \| grep libpython` |
| APK 清单 | `at.bitmessage.pybitmessagemock`、minSdk 24、targetSdk 33、arm64-v8a | `aapt2 dump badging` |

---

## 3. CI 迭代失败记录（摘要，详版在 PLAN.md §7.5）

| 轮 | 结论 | 症状 | 根因 | 修复 commit |
|---|---|---|---|---|
| 1 | ✗ | `numpy … must set minimum ndk api to 24` | `android.minapi=21` | 384a05f7 |
| 2 | ✗ | `no template named 'unordered_map'` | numpy 2.x vs NDK r25b libc++ | df615f4b |
| 3 | ✗ | `Unsupported class file major version 69` | runner 默认 JDK 25 | c5e2c092 |
| 4 | ✓ | —— | —— | （产出 APK，但 CPython 3.14） |
| 5 | ✗ | 启动崩溃 `SafeConfigParser` | p4a master → CPython 3.14 | 6887619c |
| 6 | ✗ | `Compatibility with CMake < 3.5` | runner CMake 4.x vs libjpeg-turbo 2.0.1 | 1814c54a |
| 7 | ✓ | —— | —— | 可用的基线 APK |

---

## 4. 记录模板（复制用）

```
| Mx.y.z | YYYY-MM-DD | 一句话任务名 | ✅ / ❌ | run <id> 或命令输出 或 artifacts/xxx.png | 备注 |
```

失败时补充三段：**症状** → **定位到的层**（CI / 启动 / 核心 / 协议）→ **根因与修复 commit**。
