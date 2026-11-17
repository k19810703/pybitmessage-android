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
