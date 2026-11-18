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
