# AGENTS.md — 项目入口（人与 AI 代理共用）

> 项目：把 PyBitmessage（v0.6）做成 **可在安卓侧载安装、设备间加密通讯** 的 APK。
> 本文件是**入口索引**：先读这里，再按 §1 的指引读具体文档。
> 版本：v1 · 2026-11-17 · 变更时请更新 §9 的变更记录。

---

## 0. 一页速览

| 项 | 值 |
|---|---|
| 目标 | 一个 APK，装了的设备互相能发加密消息（无自建服务器，不上架） |
| 当前阶段 | **G2 闸门已通过（A1–A4 全绿）；M2 剩余：包名/品牌（M2.5）与 UI 数据源统一（M2.6）** |
| 已完成 | M1 构建链路；M2.1–M2.4 全部通过（**G2.1/G2.2/G2.3/G2.4**）；**G2 达成**：地址 3.7s、已连上 1 个节点（fullyEstablished） |
| 仓库 | **<https://github.com/k19810703/pybitmessage-android>**（public，默认分支 `android-port`） |
| 仓库结构 | `PyBitmessage/`（代码）/ `PyBitmessage-android/`（文档）/ `artifacts/`（gitignore） |
| 最近成功构建 | [run 44091360456](https://github.com/k19810703/pybitmessage-android/actions/runs/44091360456)（含地址生成修复），11 分 27 秒 |
| 基线 APK | `PyBitmessage-android/artifacts/pybitmessage-apk-16/pybitmessagemock-0.1.2-arm64-v8a-debug.apk`（API 可用、含 INTERNET） |
| 包名（现状） | `at.bitmessage.pybitmessagemock`（Mock 壳） |
| 包名（M2.5.1 之后） | `at.bitmessage.pybitmessage` —— 本文所有 `run-as`/`am start` 命令以**当前包名**为准，改造后需替换 |
| 产品需求（待做） | **界面必须中文**、**适配平板** → 见 `MILESTONES.md` M6（Kivy 侧目前零翻译机制） |
| 唯一任务来源 | **`PyBitmessage-android/MILESTONES.md`**（任务 ID、验收标准、Gate） |

---

## 1. 需要参考的文件在哪（权威性从高到低）

| 文件 | 作用 | 说明 |
|---|---|---|
| `PyBitmessage-android/MILESTONES.md` | **任务与验收的唯一事实来源** | 36 个任务（M2.1.1 … M5.4.2），每条带预估与 L/F/A/S/T 验收 |
| `PyBitmessage-android/EVIDENCE.md` | 验收证据流水 | 每个任务完成/失败都追加一条，含命令输出、截图路径 |
| `PyBitmessage-android/PLAN.md` | 方案、环境体检、CI 踩坑 | §5 本机/容器环境；**§7.5 七轮 CI 失败-修复记录** |
| `PyBitmessage/`（代码） | 被改造的代码本体 | 就是本仓库的子目录，不再是独立 clone |
| `.github/workflows/android-apk.yml`（仓库根） | CI 定义 | 在 `PyBitmessage/` 里跑 buildozer；JDK17、CMake 3.31、p4a 缓存都在这里 |
| `PyBitmessage/packages/android/buildozer.spec` | 打包参数 | minapi/archs/p4a.branch/权限/requirements |
| `PyBitmessage-android/artifacts/` | 构建产物与截图 | 目录名带 run 号，如 `pybitmessage-apk-7/` ↔ run 44013702969 |

**外部地址**

- 仓库（CI 在这里跑）：<https://github.com/k19810703/pybitmessage-android> · Actions 页面：`/actions`
- 上游（只读参考）：<https://github.com/Bitmessage/PyBitmessage>
- 协议规范：<https://wiki.bitmessage.org/index.php/Protocol_specification>

**冲突时的取舍**：实测结果 > 代码 > `EVIDENCE.md` > `MILESTONES.md` > `PLAN.md` > 本文件。发现不一致，先实测，再改文档。

---

## 2. 计划（概览，细节只在 MILESTONES.md）

```
M1 构建链路        ✅ 完成
M2 真实核心接入     13 任务 / 5–7 天    ← 当前
M3 收发闭环         10 任务 / 6–7 天
M4 后台与持久化      9 任务 / 5–6 天
M5 交付             7 任务 / 2 天
M6 UI 中文化+平板    13 任务 / 6–8 天   ← 产品需求，可与 M3 并行
```

| 阶段 | 子里程碑 | 出口 Gate |
|---|---|---|
| M2 | 2.1 能力探测 · 2.2 py3 解禁 · 2.3 入口 · 2.4 存储 · 2.5 打包 · 2.6 数据源 · 2.7 联网 | **G2.1** 加密可用；**G2** 地址可生成 + 连接 ≥1 |
| M3 | 3.1 地址 · 3.2 联系人 · 3.3 公钥 · 3.4 发送 · 3.5 接收 · 3.6 联调 | **G3** 双向各收到 1 条 |
| M4 | 4.1 服务 · 4.2 权限 · 4.3 保活 · 4.4 持久化 · 4.5 私钥 | **G4** 锁屏 30 分钟能收 |
| M5 | 5.1 品牌 · 5.2 签名 · 5.3 文档 · 5.4 回归 | **G5** D1–D7 全绿 |
| M6 | 6.1 翻译基建 · 6.2 全界面中文 · 6.3 平板适配 · 6.4 验收 | **G6** 中文界面 + 手机/平板 × 竖横全通过 |

**顺序不能跳**：`M2.1`（探路）必须在写业务代码之前完成 —— 如果 `libcrypto`/`ripemd160` 走不通，整个方案成本翻倍。

---

## 3. 现在执行到哪一步

| 项 | 状态 |
|---|---|
| M1 构建链路 | ✅ 完成（详见 `PLAN.md` §7.5） |
| M2.1.1 启动自检探针 | ✅ 完成（run 44024863827，设备 9 行 PROBE） |
| M2.1.2 能力矩阵 | ✅ 完成（见 `EVIDENCE.md` §1.1） |
| M2.1.3 RIPEMD-160 兜底 | ⏭ 未触发（`ripemd160 = OK`） |
| M2.1.4 pyelliptic ctypes 修复 | ✅ 完成（`ecies = OK`，见 commit `2b4898ed`） |
| **G2.1 加密闸门** | ✅ **已通过** |
| M2.2.1 py3 硬退出改告警 | ✅ 完成（`depends.py`） |
| M2.2.2 桌面 `-t` 跑通 | ✅ 完成（退出码 0，生成 keys.dat/messages.dat/knownnodes.dat） |
| M2.2.3 Android 依赖检查容错 | ✅ 完成（设备探针 8/9 OK） |
| **G2.2 启动闸门** | ✅ **已通过** |
| M2.3.1 新入口 `src/main.py` | ✅ 完成（探针 → BITMESSAGE_HOME → `state.kivy` → core） |
| M2.3.2 `main()` 走 Kivy 分支 | ✅ 完成（含 `tr.py` / `singleinstance` 去 PyQt 化） |
| M2.3.3 p4a 入口指向真实入口 | ✅ 完成（Mock 入口保留为 `main_mock.py`） |
| **G2.3 核心启动闸门** | ✅ **已通过**（App 存活、DB 已建 10 表、真实引导页） |
| M2.4.1 `BITMESSAGE_HOME` | ✅ 完成（私有目录已建 keys.dat 等） |
| M2.4.2 单实例锁降级 | ✅ 完成（`204b753d`） |
| M2.4.3 重启后地址不变 | ✅ 完成（force-stop 重启后仍为同一地址） |
| **G2.4 闸门** | ✅ **已通过** |
| M2.5.2 INTERNET 权限 | ✅ 完成（API 已能在设备上响应） |
| M2.7.1 API 可用 | ✅ 完成（`clientStatus` 正常返回） |
| M2.4.5 地址创建通路 | ✅ 设备验证通过：`createRandomAddress` **3.7s** 返回 `BM-2cX1KSM87DGtSZcerwLi8a1zgmkAc2nTcD` |
| 其他 | ⬜ 未开始 |

**当前代码状态**

```
branch: android-port（= 仓库默认分支）
remote: origin → git@github.com:k19810703/pybitmessage-android.git
```

**当前可用的东西**

- 能出包：push 到 `android-port` 即触发，约 9–15 分钟
- 能装机：模拟器 `Pixel_6_API_33`（arm64-v8a / Android 13）
- 已有：`INTERNET` 权限、本地 API 可用（`clientStatus` 正常）
- 已有：真实地址 `BM-2cX1KSM87DGtSZcerwLi8a1zgmkAc2nTcD`（生成 3.7s，重启不丢）
- 联网：✅ `networkConnections=1`，`fullyEstablished=1`（连的是宿主节点 10.0.2.2:8444）

---

## 4. 标准工作流（每个任务都走这一遍）

```bash
# 0) 读任务：在 MILESTONES.md 找到 Mx.y.z，确认前置 Gate 已过、验收标准是什么

# 1) 改代码
cd PyBitmessage

# 2) 本地最低限度自检（必须 0 错误）
python3 -m compileall -q src | grep -c "Error compiling"   # 期望 0

# 3) 提交并推送（提交信息必须以任务号开头）
git add -A
git commit -m "M2.1.1: add startup env probe (python/ripemd160/pyelliptic/msgpack)"
git push origin android-port

# 4) 等 CI 并下载产物
gh run watch --repo k19810703/pybitmessage-android
gh run download --repo k19810703/pybitmessage-android -D ../PyBitmessage-android/artifacts

# 5) 装机 + 验收（按 L/F/A/S/T 逐条打勾）
~/Documents/platform-tools/adb install -r ../PyBitmessage-android/artifacts/*/*.apk
~/Documents/platform-tools/adb logcat -c
~/Documents/platform-tools/adb shell am start -n at.bitmessage.pybitmessage/org.kivy.android.PythonActivity
~/Documents/platform-tools/adb logcat | grep -iE "python|PROBE"

# 6) 记录证据
#    在 EVIDENCE.md 追加：任务号 / 日期 / 结论 / 命令输出或截图路径 / 备注
```

**提交信息规范**：`Mx.y.z: 一句话`。修复构建问题用 `ci(android): …` 或 `build(android): …`（无任务号）。

---

## 5. 每一步怎么验收（只有 5 种，不接受主观判断）

| 代号 | 类型 | 命令/形式 |
|---|---|---|
| **L** | logcat 断言 | `adb logcat -d \| grep "PROBE ripemd160=OK"` |
| **F** | 文件断言 | `adb shell run-as at.bitmessage.pybitmessage ls files/`；`cat files/keys.dat \| grep BM-` |
| **A** | API 断言 | `adb forward tcp:8442 tcp:8442` → `curl` 调 `clientStatus` |
| **S** | 截图断言 | `adb exec-out screencap -p > shot.png`，界面上必须有/没有某元素 |
| **T** | 计时断言 | 地址生成 < 60s；PoW < 120s；1 小时耗电 ≤ 8% |

**API 断言模板**（M2.7.1 之后可用，需先在 `keys.dat` 开 `apienabled`）

```bash
adb forward tcp:8442 tcp:8442
curl -s --user user:pass -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"clientStatus","params":[],"id":1}' \
  http://127.0.0.1:8442/ | python3 -m json.tool
# 期望字段：networkConnections / networkStatus / numberOfMessagesProcessed
```

**Gate（阶段闸门，不达标不许进入下一阶段）**

| Gate | 条件 |
|---|---|
| G2.1 | `PROBE ripemd160=OK` 且 `PROBE openssl=OK`；2 天内修不好 → 停止并重新评估方案 |
| G2.2 | 桌面 `python3 … -t` 能生成 `keys.dat`（退出码 0） |
| G2.3 | APK 启动后核心线程确实运行（以 `messages.dat` 建表为证），10 秒内不崩 |
| G2.4 | `keys.dat` 在私有目录，重启后地址不变 |
| G2.5 | `aapt2 dump badging` 显示正确包名 + `INTERNET` 权限 |
| G2.6 | 界面数据全部来自真实核心（地址与 `keys.dat` 一致） |
| **G2** | A1 地址生成 <60s · A2 连接数 ≥1 · A3 重启地址不变 · A4 无 FATAL |
| G3 | B1 双向互通 · B2 ≤5 分钟 · B3 中英 emoji 正常 · B4 ack 可见 |
| G4 | C1 锁屏 30 分钟能收 · C2 强杀重启不丢 · C3 ≤8%/小时 · C4 私钥非明文 |
| G5 | D1–D7 全绿 |

---

## 6. 出问题怎么回溯

### 6.1 先定位层次（90% 的问题在这四层之一）

| 层 | 典型症状 | 先看哪里 |
|---|---|---|
| **CI 构建** | Actions 红，没有 APK | `gh run view <id> --log-failed`；先比对 `PLAN.md` §7.5 的七轮失败表 |
| **APK 启动** | 装上闪退 / 卡 Loading | `adb logcat -s python:* AndroidRuntime:E` |
| **核心运行** | 起来了但连不上/没地址 | App 内日志 + `run-as` 看 `keys.dat` |
| **协议交互** | 连上了但收不到消息 | `clientStatus`、`pendingDownload`、对端 logcat |

### 6.2 常用回溯命令

```bash
# CI 日志（全部 / 仅失败步骤）
gh run view <run_id> --repo k19810703/pybitmessage-android --log        > /tmp/ci.log
gh run view <run_id> --repo k19810703/pybitmessage-android --log-failed

# 列出最近构建，按时间找到"最后一次是好的"
gh run list --repo k19810703/pybitmessage-android --limit 10

# 设备侧全量日志
adb logcat -d > /tmp/device.log && grep -iE "FATAL|Traceback|Error" /tmp/device.log

# 应用私有目录（debug 包可用 run-as）
adb shell run-as at.bitmessage.pybitmessage ls -l files/
adb shell run-as at.bitmessage.pybitmessage cat files/keys.dat

# 清空重来（验证"首次启动"路径）
adb shell pm clear at.bitmessage.pybitmessage

# 截图
adb exec-out screencap -p > PyBitmessage-android/artifacts/shot-$(date +%H%M).png
```

### 6.3 本地最小复现（不用等 CI）

```bash
cd PyBitmessage
python3 -m compileall -q src | grep -c "Error compiling"    # 语法层，期望 0
BITMESSAGE_HOME=/tmp/bm python3 src/bitmessagemain.py -t    # M2.2 完成前会报 py3 不支持，属预期
```

### 6.4 代码回滚

```bash
git -C PyBitmessage log --oneline -10                 # 找到最后一个好提交
git -C PyBitmessage revert <bad_commit>               # 推荐：保留历史
git -C PyBitmessage checkout <good_commit> -- <path>  # 只回退单个文件
```

**产物回滚**：`artifacts/pybitmessage-apk-N/` 里的 N 就是 run 号，可以随时回装旧包对比行为。

### 6.5 失败也必须记录

`EVIDENCE.md` 不只记成功。**每次失败都追加一条**：症状 → 定位到的层 → 根因 → 修复 commit。这样同一类问题第二次出现时能直接搜到。

### 6.7 纯 Python 改动的热补丁调试法（网络差时非常有用）

APK 动辄 25 MB，网络不稳时下载很痛。**只改 `.py`** 的改动可以直接推进已安装的应用：

```bash
PKG=at.bitmessage.pybitmessagemock
for f in api.py class_addressGenerator.py main.py; do
  adb push PyBitmessage/src/$f /data/local/tmp/$f
  adb shell "run-as $PKG sh -c 'cat /data/local/tmp/$f > files/app/$f && rm -f files/app/${f%.py}.pyc'"
done
adb shell am force-stop $PKG && adb shell am start -n $PKG/org.kivy.android.PythonActivity
```

原理：p4a 的 `ANDROID_ENTRYPOINT` 是 `main.py`（源码），删掉旧 `.pyc` 后重启会重新编译。
**局限**：新增依赖、C 扩展、`buildozer.spec` 改动仍必须走 CI 出包。

### 6.6 已知的"看着像 bug 其实是环境"清单

| 症状 | 其实是 | 处理 |
|---|---|---|
| `Cache save failed` | 缓存 key 已存在，属正常噪音 | 忽略 |
| 启动卡 "Loading..." 30–60 秒 | 首次解压 `_python_bundle` | 等；第二次启动秒开 |
| `PyBitmessage does not support Python 3+` | `depends.py` 的 py3 拦截（M2.2 才修） | 预期行为，不是新 bug |
| 构建报 `class file major 69` | JDK 版本错（应 17） | 检查 workflow `setup-java` |
| 构建报 `Compatibility with CMake < 3.5` | CMake 4.x | 检查 `Pin CMake 3.31` 步骤 |
| 构建报 `unordered_map` | numpy 2.x 与 NDK r25b | 检查 requirements 是否又引入 opencv/pyzbar |
| 对端回 `Your time is too far in the past` | 模拟器时钟漂移（宿主休眠后差几小时） | `adb root && adb shell "date -s @$(date +%s)"` |
| 所有节点都连不上 | 默认 knownnodes（2017 年）已全部下线 | 用 `dig bootstrap8444.bitmessage.org` 的活 IP 覆盖 `knownnodes.dat` |

---

## 7. 约定与红线

**必须**

- 每次推送带任务号（`M2.1.1: …`），便于 `git log` 回溯到里程碑
- 任务完成即在 `MILESTONES.md` 勾选，并在 `EVIDENCE.md` 追加证据
- 改动 `buildozer.spec` / workflow 后，同步更新 `PLAN.md` §7.5 的配置清单
- 只能推本仓库 `origin`（`upstream` 只读参考）

**禁止**

- 提交 `keys.dat`、`*.keystore`、token、`~/.buildozer` 内容
- 删除 `src/mockbm/`（`tests-kivy.py` 依赖）
- 引入任何遥测、上报、外部服务调用（Bitmessage 的设计前提就是无中心）
- 在未过 Gate 的情况下跳阶段开发（尤其 M2.1 未验证就写 M3）
- 把"看起来正常"当验收结论

---

## 8. 常用命令速查

```bash
# 改码 → 出包 → 装机 → 看日志（一条龙）
cd PyBitmessage && git add -A && git commit -m "Mx.y.z: ..." && git push origin android-port \
  && gh run watch --repo k19810703/pybitmessage-android \
  && gh run download --repo k19810703/pybitmessage-android -D ../PyBitmessage-android/artifacts \
  && ~/Documents/platform-tools/adb install -r ../PyBitmessage-android/artifacts/*/*.apk

# 启模拟器（arm64 / Android 13）
~/Library/Android/sdk/emulator/emulator -avd Pixel_6_API_33 \
  -no-snapshot-save -no-audio -no-boot-anim -gpu swiftshader_indirect &

# 包信息
~/Library/Android/sdk/build-tools/36.0.0/aapt2 dump badging <apk> | head -6

# 强制停止 / 清数据
adb shell am force-stop at.bitmessage.pybitmessage
adb shell pm clear at.bitmessage.pybitmessage
```

---

## 9. 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-11-17 | v1 | 首版：建立入口索引、当前进度、验收模板、回溯流程 |
| 2026-11-17 | v1.1 | 补充包名现状/目标对照（`pybitmessagemock` → `pybitmessage`），避免命令里的包名对不上 |
| 2026-11-17 | v1.2 | M2.1 完成：更新当前进度（G2.1 通过）、HEAD、最近构建与基线 APK |
| 2026-11-17 | v1.3 | M2.2 完成（G2.2 通过）：更新进度、HEAD `829f0b02`、构建 run 44027789116 |
| 2026-11-17 | v1.4 | M2.3 完成（G2.3 通过）：真实核心在 APK 内启动；HEAD `d6e76bde` |
| 2026-11-17 | v1.5 | M2.4 部分完成：API 打通、权限就位；记录 M2.4.5 地址创建阻塞 |
| 2026-11-17 | v1.6 | 新增产品需求：UI 中文化 + 平板适配（M6，13 任务，6–8 天） |
| 2026-11-17 | v2.0 | 仓库重建：不在上游 clone 上开发，改为单仓库（代码+文档），CI workflow 移到仓库根 |
| 2026-11-17 | v2.1 | M2.4.5 代码修复完成（本地验证）；设备复验被网络阻塞 |
| 2026-11-18 | v2.2 | M2.4 完成：G2.4 通过、A1 达成（3.7s）；新增热补丁调试法 §6.7 |
| 2026-11-18 | v2.3 | M2.7 进展：dontconnect/时钟/assembleErrorMessage 三坑已修；握手到 version，未 fullyEstablished |
| 2026-11-18 | v2.4 | **G2 通过**：CreatePacket str 命令 + userAgent bytearray 两个 bug 修掉后连接建立 |
