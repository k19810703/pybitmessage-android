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
