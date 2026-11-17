# 里程碑计划 v2：PyBitmessage 安卓加密通讯 APK

> v2 · 2026-11-17 · 本版重点：**任务细分 + 每条任务的可执行验收标准**
> 前置文档：`PLAN.md`（方案与构建环境）
> 代码库：`PyBitmessage/`（本仓库子目录）@ v0.6 状态；仓库 <https://github.com/k19810703/pybitmessage-android>；工作分支 `android-port`

---

## 0. 本版变更：粒度重估结论

上一版（v1）的里程碑方向没问题，但**单个任务过大**，有三处必须拆：

| v1 的任务 | 实际隐含的工作 | 问题 | 本版处理 |
|---|---|---|---|
| M2-5「加密能力实测」 | ①探测 RIPEMD160 ②探测 libcrypto ③两条不同的修复路径 | 一条任务跨 3 个独立目标、结果不确定，无法估时 | 拆成 M2.1.1–M2.1.4（含 2 个条件任务） |
| M3「发消息」 | getpubkey → 等 pubkey → 组包 → 签名 → PoW → 入队 → 广播 | 一条 bullet 里 7 个阶段，失败时无法定位 | 拆成 M3.4–M3.6 三个任务 |
| M3「收消息」 | 对象过滤 → 解密 → 验签 → 入库 → UI 刷新 | 同上 | 拆成 M3.7 + M3.8 |
| M4「前台服务」 | 服务声明 + 通知渠道 + 通知权限 + 保活 | 混了 4 件事，且权限是 Android 13 的坑 | 拆成 M4.1–M4.3 |
| M5「文档」 | 安装 / 首次配置 / 故障排查 | 一条无法验收 | 拆成 M5.3 的两个子项 |

### 本版粒度原则

1. **单任务 ≤ 1 人日**，多数控制在 **2–4 小时**；
2. 每个任务有**唯一 ID**（`M2.3`）与**前置依赖**；
3. 每个任务都有**可执行、可复现、非主观**的验收标准（见 §3 模板）；
4. 每个子里程碑有 **Gate（出口条件）**，不达标不进入下一阶段；
5. 不确定的任务（如加密库能否加载）**先探测再决定**，不预先写死实现。

---

## 1. 需求与 Definition of Done

> **做一个 APK：装了这个 APK 的设备之间可以互相发加密消息。** 侧载安装、无自建服务器、基于现有 PyBitmessage。

| # | DoD | 验证 |
|---|---|---|
| D1 | 两台设备各生成 `BM-2...` 地址 | 截图 + `keys.dat` |
| D2 | 互换地址后可加入通讯录 | 双端截图 |
| D3 | A→B 一条消息到达并可读 | 双端截图 + 时间戳 |
| D4 | B→A 回复到达 | 同上 |
| D5 | 锁屏 30 分钟后仍能收消息 | logcat + 收件时间 |
| D6 | 重启 App 后地址/消息/联系人都在 | 重启截图 |
| D7 | 全程无 FATAL | logcat 过滤 |

**不做**：图片/文件/语音、群聊、多设备同步、应用商店、iOS、前向保密。

---

## 2. 当前基线

| 项 | 状态 |
|---|---|
| 构建 | GitHub Actions 约 9 分钟出包（[run 44013702969](https://github.com/k19810703/pybitmessage-android/actions/runs/44013702969)） |
| 已固定参数 | `minapi=24`、`archs=arm64-v8a`、`p4a.branch=v2024.01.21`（CPython 3.11.5）、JDK17、CMake 3.31 |
| 现有 APK | `pybitmessagemock-0.1.2-arm64-v8a-debug.apk`：能装、能启动、界面正常，但跑的是 Mock 线程、无 `INTERNET` 权限 |

---

## 3. 验收标准模板（所有任务只用这 5 种）

| 代号 | 类型 | 形式 | 示例 |
|---|---|---|---|
| **L** | logcat 断言 | 出现/不出现某字符串 | `adb logcat -d \| grep "PROBE ripemd160=OK"` |
| **F** | 文件系统断言 | `run-as` 读应用私有目录 | `adb shell run-as <pkg> cat files/keys.dat \| grep BM-` |
| **A** | API 断言 | `adb forward` + `curl` 调本地 API | `curl ... clientStatus` 返回 `networkConnections>=1` |
| **S** | 截图断言 | 界面上有/没有某元素 | 地址列表出现 `BM-2...` |
| **T** | 计时断言 | 某操作耗时在阈值内 | 地址生成 < 60s；发消息 PoW < 120s |

> 一个任务至少 1 条验收；跨端任务（M3.10）必须 S+L 组合。**不接受"看起来正常了"这种验收。**

---

## 4. 里程碑总览（细分后）

| 阶段 | 子里程碑 | 任务数 | 预估 | 达成 |
|---|---|---|---|---|
| **M2** 真实核心 | 2.1 能力探测 / 2.2 py3 解禁 / 2.3 入口 / 2.4 存储 / 2.5 打包 / 2.6 数据源 / 2.7 网络 | 13 | 5–7 天 | A1–A4 |
| **M3** 收发闭环 | 3.1 地址 / 3.2 联系人 / 3.3 公钥 / 3.4 发送 / 3.5 接收 / 3.6 联调 | 10 | 6–7 天 | B1–B4 |
| **M4** 后台持久 | 4.1 服务 / 4.2 权限 / 4.3 保活 / 4.4 持久化 / 4.5 私钥 | 7 | 5–6 天 | C1–C4 |
| **M5** 交付 | 5.1 品牌 / 5.2 签名 / 5.3 文档 / 5.4 回归 | 6 | 2 天 | D1–D7 |
| **M6** UI 中文化与平板 | 6.1 翻译基建 / 6.2 全界面中文 / 6.3 平板适配 / 6.4 验收 | 13 | 6–8 天 | G6 |

```
M2.1 ─┬─► M2.2 ─► M2.3 ─► M2.4 ─► M2.5 ─► M2.6 ─► M2.7 ─► G2
      └─►（条件分支：加密修复）
G2 ─► M3.1 ─► M3.2 ─► M3.3 ─► M3.4 ─► M3.5 ─► M3.6 ─► G3
G3 ─► M4.1 ─► M4.2 ─► M4.3 ─► M4.4 ─► M4.5 ─► G4 ─► M5 ─► 交付
M6.1（可与 M3 并行）─► M6.2 ─► M6.3 ─► M6.4 ─► G6（在 M5 之前完成）
```

---

## 5. M2 · 真实核心接入（13 个任务，5–7 天）

### M2.1 能力探测（先探路，0.5–2 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M2.1.1 ✅ | 启动自检：打印解释器版本、`hashlib.new('ripemd160')`、`pyelliptic.openssl.OpenSSL`、`msgpack` 是否可用 | `src/bitmessagemain.py` 加 `_probe_env()`，在 `main()` 最前面调用 | 2h | **L**：logcat 出现四行 `PROBE ...`，每行末尾是 `OK` 或 `FAIL` |
| M2.1.2 ✅ | 出探测包 → 装机 → 收集结果，形成"能力矩阵" | 无代码改动 | 2h | **L**：`adb logcat -d \| grep PROBE` 四条结果贴进 `PLAN.md` |
| M2.1.3 ⏭ | （条件，仅当 ripemd160=FAIL）RIPEMD-160 兜底 | 加 `pycryptodome` 到 requirements，或内置纯 Python 实现 | 4–8h | **L**：`PROBE ripemd160=OK`；**F**：能算出与已知向量一致的 RIPE |
| M2.1.4 ✅ | 修复 pyelliptic ctypes 签名（`EVP_CipherInit_ex` 只声明 3 个参数，实际 6 个 → 64 位下指针截断） | `src/pyelliptic/openssl.py`：`argtypes` 补全为 6 项 | 1h（比预估快，实测直接定位） | **L**：`PROBE ecies = OK (encrypt/decrypt ok)`；ECIES 与对称加密均能 roundtrip |

> **Gate G2.1（已通过 2026-11-17）**：`ripemd160` 与 `openssl` 两项必须 OK。任一为 FAIL 且 2 天内修不掉，**停止后续开发，重新评估方案**（这是整个项目的技术前提）。

### M2.2 解除 Python 3 启动拦截（0.5 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M2.2.1 ✅ | 去掉 `if six.PY3: sys.exit()`，改为仅告警 | `src/depends.py` | 1h | **L**：桌面 `BITMESSAGE_HOME=/tmp/bm python3 src/bitmessagemain.py -t` 退出码 0 |
| M2.2.2 ✅ | 桌面端跑通 `-t`，生成 `keys.dat` | 无（验证） | 1h | **F**：`/tmp/bm/keys.dat` 存在且含 `[bitmessagesettings]` |
| M2.2.3 ✅ | 补 `check_openssl` / `check_sqlite` 在 Android 上的容错 | `src/depends.py` | 1h | **L**：Android 上不再因依赖检查 `sys.exit` |

> **Gate G2.2（已通过 2026-11-17）**：桌面 Python 3.11 能启动到"生成配置"。这是"核心能在 3.11 跑"的第一个证据。

### M2.3 启动入口接线（0.5–1 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M2.3.1 ✅ | 解封 Android 入口 | `src/main-android-live.py`：删 `print+sys.exit`，设 `state.kivy=True` 后调 `main_()` | 2h | **L**：APK 启动后出现 `Running with kivy` 类似日志 |
| M2.3.2 ✅ | 让 `main()` 接受 kivy 而非 PyQt | `src/bitmessagemain.py`：`check_pyqt` 判断加 `and not state.kivy`；UI 分发加 `elif state.kivy:` | 2h | **L**：不再出现 `PyBitmessage requires PyQt` |
| M2.3.3 ✅ | 把 p4a 入口从 Mock 换成真实入口 | `packages/android/buildozer.spec` / `source.dir`，或把 `src/main.py` 内容替换为 `main-android-live` | 1h | **L**：启动日志里没有 `FakeAddressGenerator`，出现 `SQL thread` / `Inventory` |

> **Gate G2.3（已通过 2026-11-17）**：APK 启动后核心线程确实运行（以 `messages.dat` 已建 10 张表为证），进程存活 80s+、无 traceback。线程日志默认 WARNING 级不打印，故用数据库 schema 作为功能性证据。

> **M2.3 实际改动比计划多 3 处**（都属"启动即崩"必要修复，已记入 `EVIDENCE.md` §1.4）：
> `tr.py` 的 `os._exit(0)`、`check_openssl` 在 Android 找不到 libcrypto、`default.ini` 未打进 APK。
>
> 遗留到 M2.6：Kivy 用 `from pybitmessage import state` 与核心 `import state` 在 APK 里是两个模块对象，必须统一。

### M2.4 存储路径与单实例（0.5 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M2.4.1 ✅ | 启动时把 `BITMESSAGE_HOME` 指到应用私有目录 | 入口处 `os.environ['BITMESSAGE_HOME'] = app_storage_path()`（p4a `android.storage`） | 2h | **F**：`adb shell run-as at.bitmessage.pybitmessage ls files/keys.dat` 存在 |
| M2.4.2 ✅ | 单实例锁在 Android 可用 | `src/singleinstance.py` 失败时降级（try/except 不阻塞启动） | 1h | **L**：连续启动两次不崩；无 `flock` 异常 |
| M2.4.3 ⏸ | 重启保留身份 | 无（验证） | 1h | **F**：`am force-stop` 后重启，`keys.dat` 里的地址不变（对比前后 hash） |

> **Gate G2.4**：地址持久化成立（D6 的一半提前验证）。

### M2.4.5 地址创建通路（**当前阻塞项**，0.5–1 天）

UI 与 API 两条路都创建不了地址，没有地址就没有后续一切。

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M2.4.5a | 修 UI 引导页跳转 | `src/bitmessagekivy/kv/login.kv`：`set_screen('random')` 指向根 `scr_mngr` 里真实存在的屏幕（或把 random 屏移入根管理器） | 2h | **S**：点 Proceed Next 能进入随机地址表单 |
| M2.4.5b | 查清 `addressGenerator` 线程为何不消费队列 | 在 `class_addressGenerator.run()` 入口加日志；必要时用 `sys.excepthook`/`threading.excepthook` 抓守护线程异常 | 3h | **L**：logcat 出现 `addressGenerator: got request` 且 API 调用在 60s 内返回 |
| M2.4.5c | API 调用加超时，避免单线程服务器被永久阻塞 | `src/api.py`：`apiAddressGeneratorReturnQueue.get(timeout=...)` 并返回明确错误 | 1h | **A**：失败时返回 Fault 而不是挂死 |

> **Gate G2.4**：`keys.dat` 在私有目录，重启后地址不变 —— 依赖 M2.4.5 先造出地址。

### M2.5 打包参数（0.5 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M2.5.1 | 去 Mock 命名 | `title=PyBitmessage`、`package.name=pybitmessage` | 0.5h | **A**：`aapt2 dump badging` 显示 `package: name='at.bitmessage.pybitmessage'` |
| M2.5.2 ✅ | 加联网权限 | `android.permissions = INTERNET, ACCESS_NETWORK_STATE` | 0.5h | **A**：`aapt2 dump badging \| grep uses-permission` 含 INTERNET（已达成，见 EVIDENCE §1.6） |
| M2.5.3 | 依赖补齐 | requirements 加 `msgpack`（可选）、`pycryptodome`（若 M2.1.3 需要） | 1h | **L**：启动无 `ImportError` |

> **Gate G2.5**：包名、权限、依赖三项在 `aapt2 dump` 与 logcat 中都能对上。

### M2.6 UI 数据源切换（1 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M2.6.1 | 换掉 mock 配置加载 | `src/bitmessagekivy/mpybit.py`：`mockbm.helper_startup` → 真实 `helper_startup` | 2h | **S**：地址列表显示的地址与 `keys.dat` 一致 |
| M2.6.2 | 换掉 mock 网络统计 | 引用 `mockbm.network` 的地方改 `network.stats` | 2h | **S**：网络页显示真实连接数（与 API 一致） |
| M2.6.3 | mock 仅保留给测试 | `src/mockbm/` 加注释；`tests-kivy.py` 仍可用 | 1h | **L**：`python3 tests-kivy.py` 仍能跑（不阻塞主流程） |

> **Gate G2.6**：界面数据全部来自真实核心，mock 只在测试路径。

### M2.7 P2P 联网验证（1 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M2.7.1 | 打开 API 便于自动化验收 | `keys.dat` 里 `apienabled=true`、`apivariant=json`、apiuser/pass | 1h | **A**：`adb forward tcp:8442 tcp:8442` 后 `curl` 能拿到 `clientStatus` |
| M2.7.2 | 验证出网连接 | 无（验证） | 2h | **A**：`networkConnections >= 1`，`networkStatus != notConnected` |
| M2.7.3 | 验证能收到对象（inv/getdata 通路） | 无（验证） | 2h | **A**：`pendingDownload` 有变化 / logcat 有 `inv` 处理 |

> **Gate G2（阶段出口）**：A1–A4 全绿
> - A1 启动 60 秒内出现可用地址（**S**）
> - A2 连接数 ≥ 1（**A**）
> - A3 `keys.dat` 在私有目录且重启不变（**F**）
> - A4 logcat 无 FATAL（**L**）

---

## 6. M3 · 收发闭环（10 个任务，6–7 天）

### M3.1 地址展示与交换（1 天）

| ID | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| M3.1.1 | 地址列表显示真实地址 + 复制按钮 | 3h | **S**：点击复制后 `adb shell cmd clipboard` 或粘贴到输入框内容 == `keys.dat` 地址 |
| M3.1.2 | 地址二维码生成与展示（`qrcode` 生成 PNG） | 3h | **S**：二维码可被另一台设备扫出同一地址字符串 |

> **Gate G3.1**：能把自己的地址完整、无误地交给对方（这是 D2 的前提）。

### M3.2 联系人（0.5 天）

| ID | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| M3.2.1 | 粘贴 `BM-2...` → 校验 → 写入地址簿 | 3h | **F**：`keys.dat` 的 `[addressbook]` 出现该地址；**S**：联系人列表可见 |

### M3.3 公钥交换（1 天）

| ID | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| M3.3.1 | 发送 `getpubkey` 并处理回包 | 4h | **L**：logcat 出现收到 pubkey 的日志；**F**：`keys.dat` 的 `[pubkeys]` 出现条目 |
| M3.3.2 | 首次通信等待提示（UI） | 2h | **S**：发送前若缺 pubkey，界面显示"正在获取对方公钥" |

### M3.4 发送管道（2 天）

| ID | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| M3.4.1 | 组包 + 签名（消息编码 SIMPLE） | 4h | 单元级：本地构造的对象能被 `decodeObjectParameters` 正确解析 |
| M3.4.2 | PoW 计算与进度反馈 | 4h | **L**：`Found proof of work`；**S**：界面显示"计算中→已发送"；**T**：< 120 秒 |
| M3.4.3 | 入队广播（inv 通告） | 4h | **A**：发送后 `numberOfMessagesProcessed` 或 sent 列表 +1 |

### M3.5 接收管道（1.5 天）

| ID | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| M3.5.1 | 对象过滤（tag/ripe）+ 解密 + 验签 | 4h | **L**：`decrypted message` 日志；验签失败有明确告警 |
| M3.5.2 | 入库 + Inbox 刷新 | 3h | **F**：`messages.dat` 有记录；**S**：Inbox 出现消息 |
| M3.5.3 | ack 回执处理 | 3h | **S**：发送方出现"已送达"标记 |

### M3.6 联调（1 天）

| ID | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| M3.6.1 | 双端互通：地址交换 → 双向各 1 条 | 4h | **S+L**：两台设备截图 + 两端 logcat 对得上时间戳（B1） |
| M3.6.2 | 中文/英文/emoji 编码验证 | 2h | **S**：三类文本均不乱码（B3） |

> **Gate G3（阶段出口）**：B1–B4
> - B1 双向各收到 1 条（S+L）
> - B2 端到端 ≤ 5 分钟（T）
> - B3 三类文本正确（S）
> - B4 ack 可见（S）

---

## 7. M4 · 后台与持久化（7 个任务，5–6 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M4.1.1 | 声明前台服务并常驻通知 | `buildozer.spec services=`、新增 `service.py` | 4h | **L**：通知栏出现；`adb shell ps -A \| grep bitmessage` 在退出 UI 后仍有进程 |
| M4.1.2 | 通知渠道（Android 8+） | `service.py` 用 `NotificationChannel` | 2h | **S**：通知正常显示、不报渠道错误 |
| M4.2.1 | 通知权限（Android 13+） | `POST_NOTIFICATIONS` 运行时申请 | 3h | **S**：首次启动有授权弹窗；拒绝后 App 不崩 |
| M4.3.1 | WakeLock + Doze 白名单引导 | `PowerManager` via pyjnius | 4h | **L**：锁屏后连接数仍 ≥1（**A**）；引导页可跳系统设置 |
| M4.4.1 | 数据持久化与恢复 | 校验 `keys.dat`/`messages.dat` 完整性 | 4h | **F**：`am force-stop` 后重启，D1/D6 仍成立 |
| M4.5.1 | 禁用云备份 | `android:allowBackup=false`（manifest 或 spec） | 1h | **A**：`aapt2 dump badging` 无 `allowBackup=true` |
| M4.5.2 | 私钥加密（Keystore 派生密钥） | 新增 `keystore.py`，启动时解密 `keys.dat` | 8h | **F**：`keys.dat` 中无私钥明文；App 能正常启动并解密 |
| M4.6.1 | 崩溃自恢复 | 服务重启 + 启动自检 | 3h | **L**：`am kill` 后 1 分钟内进程恢复 |
| M4.7.1 | 电量策略（仅 Wi-Fi/充电同步） | 设置项 + 网络策略 | 4h | **T**：1 小时后台耗电 ≤ 8%（C3） |

> **Gate G4（阶段出口）**：C1–C4
> - C1 锁屏 30 分钟仍能收消息（S）
> - C2 强杀重启数据完整（F）
> - C3 1 小时 ≤ 8% 电（T）
> - C4 私钥非明文（F）

---

## 8. M5 · 交付（6 个任务，2 天）

| ID | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| M5.1.1 | 应用名/图标/启动图定稿 | 2h | **S**：桌面图标与应用名正确（不再是 "PyBitmessage Mock"） |
| M5.1.2 | 版本号与 `softwareVersion` 对齐 | 1h | **A**：`aapt2 dump badging` 的 versionName 与 `src/version.py` 一致 |
| M5.2.1 | （可选）release keystore 与统一签名 | 2h | **L**：`apksigner verify` 通过；覆盖安装不丢数据 |
| M5.3.1 | `README-ANDROID.md`：安装/首配/互换地址 | 3h | **S**：他人按文档 10 分钟完成 D1–D3 |
| M5.3.2 | 故障排查章节（连不上/收不到/耗电） | 2h | 文档覆盖 3 类常见问题 |
| M5.4.1 | 回归 D1–D7 全跑一遍 | 4h | **全绿** |
| M5.4.2 | 产出最终 APK + SHA256 | 1h | `shasum -a 256` 与发布说明一致 |

> **Gate G5（项目出口）**：D1–D7 全绿；一台"干净"手机按文档完成互通。

---

## 8.5 M6 · UI 中文化与平板适配（6–8 天，产品需求，不阻塞协议）

> 需求来源（用户 2026-11-17）：**界面必须是中文；需要适配平板。**
> 现状：Kivy UI **完全没有翻译机制** —— `BaseLanguage._()` 是 `return text` 的空实现，
> `Lang("en")` 只是占位；`src/translations/` 里那 19 个 `.ts/.qm` 是 **Qt 版**的翻译，Kivy 用不上。
> 因此这不是"改个语言设置"，而是要新建一层本地化 + 一套响应式布局。

### M6.1 翻译基础设施（1–1.5 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M6.1.1 | 实现 Kivy 侧翻译函数 | `src/bitmessagekivy/base_navigation.py`：`BaseLanguage._()` 查字典，未命中回退原文；`Lang` 支持加载语言包 | 4h | **S**：切换语言后同一界面文案变化；**L**：未命中键会打 debug 日志 |
| M6.1.2 | 从 Qt 翻译生成 Kivy 语言包 | 新增 `tools/ts2json.py`：解析 `src/translations/bitmessage_zh_cn.ts` → `src/bitmessagekivy/lang/zh_CN.json`；构建期生成 | 4h | **F**：JSON 条目数 ≥ `.ts` 中 `type="unfinished"` 之外的条目数；抽样 20 条与 `.ts` 逐字一致 |
| M6.1.3 | 语言选择与持久化 | 设置页加"语言"项，写入 `keys.dat` 的 `userlocale`；启动时读取，缺省 `zh_CN`（本产品定位） | 4h | **F**：`keys.dat` 出现 `userlocale = zh_CN`；**S**：重启后仍中文 |
| M6.1.4 | 系统语言跟随（可选） | 用 `locale`/Android `LocaleList` 决定默认语言 | 2h | **S**：系统设为英文时界面英文，设为中文时中文 |

> **Gate G6.1**：随便挑一个界面，能在中文/英文之间切换，且重启后保持。

### M6.2 全界面中文化（2 天）

| ID | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| M6.2.1 | 逐屏替换硬编码英文为 `app.tr._()`（登录/我的地址/收件箱/发送/设置/网络状态/二维码/地址簿/草稿/已发送/回收站） | 8h | **S**：12 个屏逐屏截图，无英文残留 |
| M6.2.2 | 补齐 Kivy 独有文案（Qt `.ts` 里没有的条目，约 80–150 条） | 4h | **F**：`zh_CN.json` 覆盖 kv/py 中所有 `_()` 调用（脚本比对，缺一即失败） |
| M6.2.3 | 中文排版检查 | 4h | **S**：无文字截断、无按钮溢出、行高正常（中文字宽约为英文 1.6 倍，需复检 `MAX_LABEL_LENGTH` 等写死值） |

> **Gate G6.2**：中文界面上完成一次「创建地址 → 看地址列表 → 进收件箱 → 打开设置」全流程，无英文、无截断。

### M6.3 平板适配（2–2.5 天）

| ID | 任务 | 改动 | 预估 | 验收标准 |
|---|---|---|---|---|
| M6.3.1 | 支持横竖屏 | `packages/android/buildozer.spec`：`orientation = sensor`；处理旋转时 Kivy 重排 |2h | **S**：旋转不崩、不白屏、不丢当前页 |
| M6.3.2 | 响应式布局 | `src/bitmessagekivy/kv/*.kv`：固定 `dp()` 宽高改 `size_hint`/`minimum_width`；大屏走两栏（列表 + 详情） | 8h | **S**：手机竖屏、平板横屏、平板竖屏三种布局均无重叠 |
| M6.3.3 | 字号与资源 | 图标/启动图补齐多分辨率；正文用 `sp`，随系统字体缩放 | 4h | **S**：系统字体放大到 130% 仍不截断 |
| M6.3.4 | 平板测试环境 | 新建 AVD（Pixel Tablet / 10" API 33），加入回归矩阵 | 2h | **S**：在平板上跑通 M6.4 全流程 |

> **Gate G6.3**：同一份 APK 在「手机竖屏 + 平板横屏 + 平板竖屏」下都能正常浏览与操作。

### M6.4 验收（0.5–1 天）

| ID | 任务 | 验收标准 |
|---|---|---|
| M6.4.1 | 中文全流程回归 | **S**：D1–D4（建地址、互换、互发、双向收到）全程中文界面截图 |
| M6.4.2 | 四象限截图 | **S**：手机竖 / 手机横 / 平板竖 / 平板横 各 1 张主界面 + 1 张收件箱 |
| M6.4.3 | 英文残留扫描 | **F**：脚本扫描 kv/py 中未包 `_()` 的用户可见字符串，结果为空 |

> **Gate G6（阶段出口）**：中文界面 + 手机/平板 × 竖/横 全通过，无英文残留、无截断。

### 排期与顺序建议

- **M6.1 可与 M3 并行**（纯 UI 层，不碰核心），约 1.5 天；
- **M6.2 建议在 M3 之后**：需要真实地址/消息内容才能检验文案与排版；
- **M6.3 与 M6.4 放在 M5 之前**，因为交付验收（G5）要在中文 + 平板上跑一遍。

预计 **+6–8 个工作日**，总排期由 17–18 天变成 **24–26 天**。

### 风险

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| Qt `.ts` 文案与 Kivy 界面文案对不上（Kivy 是后来加的界面） | 高 | 部分条目缺失 | M6.2.2 单独补齐；脚本比对覆盖率 |
| 中文字宽导致按钮/列表截断 | 高 | 界面难看 | M6.2.3 专项检查 + 去掉写死的 `MAX_LABEL_LENGTH` |
| Kivy `dp` 在大屏上不自动缩放 | 高 | 平板上一行字占满屏 | M6.3.2 全部改 `size_hint` + 关键页两栏 |
| 横屏旋转触发 Kivy 重建导致状态丢失 | 中 | 页面跳回首页 | M6.3.1 保存/恢复当前 screen |

---

## 9. 排期（按工作日，1 人）

| 天 | 内容 |
|---|---|
| D1 | M2.1.1–M2.1.2（探测包 → 能力矩阵） |
| D2 | M2.1.3/M2.1.4（按探测结果走条件分支） |
| D3 | M2.2 + M2.3（解禁 + 入口） |
| D4 | M2.4 + M2.5（存储 + 打包） |
| D5 | M2.6 + M2.7（数据源 + 联网）→ **G2** |
| D6–D7 | M3.1–M3.3（地址、联系人、公钥） |
| D8–D9 | M3.4–M3.5（发送/接收管道） |
| D10 | M3.6 联调 → **G3** |
| D11–D13 | M4.1–M4.3（服务、权限、保活） |
| D14–D15 | M4.4–M4.5（持久化、私钥） |
| D16 | M4.6–M4.7（自恢复、电量）→ **G4** |
| D17–D18 | M5 全部 → **交付** |

**合计 17–18 个工作日**（约 3.5 周），与 v1 的 3–4 周一致，但现在每 2–4 小时就有一个可验收的产出。

> **含 M6（中文化 + 平板）后的总排期：24–26 个工作日（约 5 周）**
>
> - M6.1 翻译基建（1.5 天）可与 M3 并行，不占用关键路径
> - M6.2 全界面中文化（2 天）、M6.3 平板适配（2–2.5 天）排在 M4 之后
> - M6.4 与 M5.4 合并做一次"中文 + 平板"回归，不重复劳动

---

## 10. 风险登记（按里程碑归属）

| ID | 风险 | 归属 | 概率 | 影响 | 对策 |
|---|---|---|---|---|---|
| R1 | `libcrypto.so` 在 Android 加载失败 | M2.1 | 高 | 方案成本翻倍 | M2.1.1 先探测；备选换 pycryptodome 底层 |
| R2 | `ripemd160` 被 OpenSSL 3 禁用 | M2.1 | 高 | 无法生成地址 | 加 pycryptodome 或内置实现 |
| R3 | 核心在 py3 下 bytes/str 错误 | M2.3–M2.6 | 中 | 修不完 | 逐个修，优先 `protocol.py`/`addresses.py` |
| R4 | 首次通信要等 pubkey 广播 | M3.3 | 高 | 用户以为坏了 | UI 明确提示 + 重试按钮 |
| R5 | PoW 手机耗时过长 | M3.4 | 中 | 体验差 | 测量后调低 `nonce_trials_per_byte` |
| R6 | 厂商 ROM 杀后台 | M4.1 | 高 | 收不到消息 | 前台服务 + 白名单引导 |
| R7 | 无私钥加密导致泄露 | M4.5 | 中 | 身份被盗 | Keystore + 禁备份 |
| R8 | 模拟器网络与真机不一致 | M3.6 | 中 | 联调失败 | 至少一台真机参与 |

---

## 11. 每轮迭代 SOP（15 分钟一轮）

```bash
# 1) 改代码并推送（触发 CI）
git -C PyBitmessage add -A && git -C PyBitmessage commit -m "M2.3.2: ..." && git -C PyBitmessage push fork android-port

# 2) 等 CI + 下载
gh run watch --repo k19810703/pybitmessage-android
gh run download --repo k19810703/pybitmessage-android -D PyBitmessage-android/artifacts

# 3) 装机 + 验收（按任务的 L/F/A/S/T 标准逐条打勾）
~/Documents/platform-tools/adb install -r PyBitmessage-android/artifacts/*/*.apk
~/Documents/platform-tools/adb logcat -c && ~/Documents/platform-tools/adb logcat | grep -i python
```

**每个任务完成后在本文档对应表格里勾选，并附一行证据**（截图路径 / 日志片段 / curl 输出）。

---

## 12. 待确认（影响 M3/M4）

- [ ] 目标设备型号 / Android 版本 / ABI
- [ ] 是否有第二台设备（真机优先）用于互通测试
- [ ] 是否接受常驻通知
- [ ] 是否只需安卓之间互通（不要求与桌面端兼容）
