# PyBitmessage 安卓版（可侧载 APK）开发计划

> 状态：规划稿 v1 · 2026-11-17
> 代码基座：`PyBitmessage` 仓库 `v0.6` 分支（HEAD `dcbcc4a2`，版本 0.6.3.2）
> 交付形态：**单个 APK，adb install / 直接拷进设备安装，不上架任何应用商店**
> **执行计划见 [`MILESTONES.md`](MILESTONES.md)**（里程碑拆解、任务清单、验收标准）

> ⚠️ **重要更正（2026-11-17 实测）**：`v0.6` 虽然能在 Python 3 下编译、单测也能跑，
> 但客户端入口 `depends.check_dependencies()` 里有 `if six.PY3: sys.exit()`，
> **真实运行时会直接退出**（实测 `python3 src/bitmessagemain.py -t` → `PyBitmessage does not support Python 3+`）。
> 因此"接真实核心"必须包含解除该拦截，这已列为 `MILESTONES.md` 的 M2-1。

---

## 1. 交付物

| # | 交付物 | 说明 |
|---|---|---|
| D1 | `pybitmessage-<ver>-arm64-v8a-debug.apk` | 可在目标设备安装运行；debug 签名即可（侧载不需要商店签名） |
| D2 | 可重复构建脚本 | 一条命令在 Linux 容器内出包，避免"只有我这台机器能编" |
| D3 | 验收记录 | 收发消息截图、后台存活记录、日志片段 |
| D4 | 本文件（持续更新） | 计划、环境、改动清单、风险 |

**非目标**：Google Play 上架、AAB 格式、iOS、平板/横屏适配、多语言 UI 打磨、性能对标商业 IM。

---

## 2. 目标（MVP 定义）

### 2.1 必须实现

1. **身份**：首次启动生成 `keys.dat` 与 `BM-2...` 地址；支持导入已有 keys.dat。
2. **点对点收发**：与桌面端 v0.6 互发加密消息，含 PoW、签名、ack 回执全链路。
3. **地址管理**：地址列表、当前地址切换、地址二维码展示。
4. **后台存活**：退到后台/锁屏后仍保持 P2P 连接（前台服务 + 常驻通知）。
5. **基础设置**：PoW 难度、连接数、代理（可选）、语言。

### 2.2 二期（可选）

- 订阅广播（broadcast）与 Chan 收发
- 二维码扫描（现有 `pyzbar`/`zbarcam` 依赖）
- 黑白名单、地址簿
- 省电模式（仅 Wi-Fi/充电时同步）

### 2.3 验收标准（可测，不达标不算完成）

| # | 标准 | 测量方式 |
|---|---|---|
| A1 | 冷启动到出现可用地址 ≤ 60s | 秒表 + logcat 时间戳 |
| A2 | 与桌面端互发 3 条消息全部到达 | 双端截图 |
| A3 | 切后台/锁屏 30 分钟后仍在线（`getStatus` 连接数 > 0） | 定时轮询 |
| A4 | 冷启动界面可见 ≤ 8s（中端机） | 秒表 |
| A5 | 低功耗模式连续 1 小时耗电 ≤ 8% | `dumpsys battery` 差值 |
| A6 | 崩溃后能自动重启服务，不丢消息 | 手动 kill 测试 |

---

## 3. 技术路线

**沿用 v0.6 的 Kivy 界面 + python-for-android（p4a）打包，不用 PyQt。**

```
┌─────────────────────────────────────────────┐
│ Kivy/KivyMD UI  (bitmessagekivy/, 现有 19 屏) │  ← 主线程
│   Clock.schedule_once 跨线程回调               │
├─────────────────────────────────────────────┤
│ core threads: sqlThread / addressGenerator / │  ← 普通线程
│               objectProcessor / network      │
├─────────────────────────────────────────────┤
│ SQLite(messages.dat) + bitmsghash(PoW) + ECC │
└─────────────────────────────────────────────┘
        ↑ 由 Android Foreground Service 托管
```

关键取舍：

- **GUI 只走 Kivy**：`bitmessageqt/`（PyQt4）完全不参与，启动时绕开 `depends.check_pyqt()`。
- **PoW 先降级**：C++ 扩展 `bitmsghash` 需交叉编译，MVP 阶段先用纯 Python PoW 跑通，再把 recipe 补上（否则首条消息可能要几十秒）。
- **架构只出 arm64-v8a**：目标设备是近几年的 Android 机，`armeabi-v7a` 让体积翻倍、收益极低；模拟器用 arm64 镜像即可。
- **debug 签名直装**：侧载场景不需要 release keystore；`buildozer android debug` 即可。

### 3.1 两个容易混淆的点（重要）

**① Docker 只是"编译车间"，不是运行时要连的服务器**

Docker 只出现在**构建阶段**：把 Linux 版的编译器、Android NDK、JDK、buildozer 打包成一个可复现的编译环境。
`buildozer` / `python-for-android` 官方只支持 **Linux 宿主**，macOS 上无法直接产出 APK，所以在 Mac 上必须借一个 Linux 环境（容器或虚拟机）来跑编译。

```
[Mac] 源码 ──► [Docker: Linux 容器] 交叉编译 ──► APK ──► 装进手机
                                                        │
                                             容器到此为止，可删除
                                                        ▼
                                              手机 ──► 直接连其他节点（P2P）
```

APK 里没有任何"指向 Docker 的地址"，装完删掉 Docker 也不影响运行。

**② 运行时不经过任何服务器，但也**不是**"两台手机直连"**

- **没有服务器**：无账号、无注册、无中心中继、无遥测上报、无在线更新检查（代码里已确认）。
- **协议是 P2P 洪泛**：手机把加密对象发给自己的几个邻居节点（默认出站 8 条连接、总连接上限 200，TCP 8444），邻居再转发给它们的邻居；所有订阅了同一 stream（默认 stream 1）的节点都会**暂存**这个对象直到 TTL 到期；收件人上线后从**自己的**邻居那里拉取并解密。

```
发送方 ──► 邻居A ──► 邻居B ──► …（全网暂存，最长 28 天）
                                    │
收件方 ◄── 邻居X ◄── 邻居Y ◄────────┘
```

所以：

- 收件人**不必在线**（对象在网络里等着，不是服务器里等着）；
- 但发送方**至少要连上 1 个可达节点**，网络里也**至少有节点在线**帮你暂存；
- "服务器"这个角色被**分摊到所有节点**身上了 —— 这就是 Bitmessage 用 PoW 和 TTL 换来的去中心化代价。
- 唯一的"中心化"痕迹是**节点发现**：内置若干硬编码 IP + `bootstrap*.bitmessage.org` 的 DNS 种子（相当于比特币的 seed 节点），只用来找到第一批邻居。这些不可用时可以手动加 peer。
- 本机的 `127.0.0.1:8442` API 只监听回环，供本地自动化用，可以完全关闭，与外部世界无关。

---

## 4. 里程碑与工作量

| 阶段 | 内容 | 产出 | 预估（1 人） |
|---|---|---|---|
| **M0** | 打通构建环境（Docker + buildozer + p4a 缓存） | 能反复出包 | 0.5–1 天 |
| **M1** | 基线 APK（现有 Mock 界面）装进设备 | 验证构建链路 | 0.5 天 |
| **M2** | 核心在设备上跑通（无 UI，daemon + API） | `getStatus` 有连接、能建地址 | 3–5 天 |
| **M3** | Mock → 真实核心接线，界面能收发消息 | MVP APK | 5–7 天 |
| **M4** | 前台服务、WakeLock、存储路径、权限、targetSdk | 后台可用 | 5–7 天 |
| **M5** | 侧载验收（A1–A6）、打包交付 | D1–D3 | 1–2 天 |

**合计约 3–4 周**。M2 是分水岭：M2 过不了，后面都是空谈。

---

## 5. 本机环境体检结论（2026-11-17 实测）

### 5.1 已有（可直接用）

| 项 | 实测值 | 用途 |
|---|---|---|
| 主机 | macOS 26.6.2 / arm64（Apple Silicon） | — |
| 磁盘 | 131 GiB 可用 | buildozer 缓存约 20–30 GB，够 |
| Python | 3.11.12（pyenv shim）+ pip 25.3 | p4a 支持 3.11，合适 |
| Cython | 3.1.4 | p4a 需要（buildozer 会锁定版本，可另装） |
| JDK | 17.0.15（Homebrew）/ 17.0.21（IBM），`JAVA_HOME` 已设 | buildozer/p4a 要求 JDK 17 ✔ |
| Android SDK | `~/Library/Android/sdk`：build-tools 28/30/33/34/35/36、platforms 33/34/35/36、cmdline-tools latest、licenses 已接受 | `android.api = 33` 满足 |
| adb | 36.0.0（`~/Documents/platform-tools/adb`） | 装包/日志 |
| 模拟器 | AVD `Pixel_6_API_33`，**arm64-v8a / API 33 / google_apis** | 无真机时的验收环境 |
| 构建工具 | Xcode + CLT、Homebrew 7.0.9、cmake、autoconf、pkg-config、libtool、zip/unzip/curl | 宿主侧辅助 |
| 源码 | `PyBitmessage` 已 clone，`origin` 指向 GitHub，当前在 `v0.6` | — |

### 5.2 缺失 / 不满足（这是要补的）

| # | 缺什么 | 影响 | 处理 |
|---|---|---|---|
| G1 | ~~Docker daemon 未运行~~ **已解决（2026-11-17 复测通过）** | — | — |
| G2 | **buildozer 未安装**（`pip show buildozer` 为空，无 `~/.buildozer`） | 无法出包 | 在容器内装（镜像已带）或宿主装 |
| G3 | **宿主是 macOS，buildozer/p4a 官方不支持在 macOS 上编 Android** | 宿主直接 `buildozer android debug` 会失败 | **必须走 Linux 容器**（本计划默认方案） |
| G4 | NDK 只有 27.1 / 28.2，而 `buildozer.spec` 指定 **25b** | p4a 会自己下到 `~/.buildozer`（首次约 1 GB+），不算硬阻塞 | 首次构建留足时间与网络 |
| G5 | 没有连接的 Android 真机（`adb devices` 为空） | 不能真机验收 | 用 AVD 先验收，或插真机开 USB 调试 |
| G6 | `pyzbar` / `xcamera` / `opencv` 在 p4a 下需要 recipe 与系统库 | 可能卡住构建（M1 就会暴露） | M1 先把二维码相关依赖从 `requirements` 摘掉，二期再加 |

### 5.3 一句话结论

> **本机约 95% 就绪**：Docker 已启动、出网正常、仓库可挂载，Android SDK/JDK/adb/模拟器齐全。
> 剩下的只有两件事：**调整 VM 资源与 Rosetta（否则编译慢 8 倍）→ 建 `bm-android` 镜像**。

### 5.4 Docker 启动后的复测（2026-11-17）

**已通**

| 检查 | 结果 |
|---|---|
| `docker version` | client `29.6.2-rd` / server **`29.5.3`** ✔ |
| `docker info` | `linux` / `aarch64` / **2 CPU** / **5.8 GiB** |
| 容器出网 | `docker run alpine wget https://api.github.com/zen` → 5.7s（含拉镜像）✔ |
| 仓库挂载 | `-v ".../PyBitmessage:/src"` → 容器内可见全部源码 ✔ |
| `bm-android` 镜像 | **尚未构建**（`docker images` 里只有 `rdx-proxy`） |

**两个关键发现**

1. **Apple Silicon 上必须用 `linux/amd64` 容器**。仓库的 Dockerfile 下载的是 `android-ndk-r25b-linux.zip` —— 这是 **x86_64 宿主**版本，NDK 没有 arm64 Linux 发行包；官方 CI 跑在 x86_64 Ubuntu 上。在 arm64 容器里，NDK 的 clang 会直接 `exec format error`。
2. **当前模拟速度极差**。实测同一段 shell 循环：arm64 原生 `0.50s`，amd64 模拟 `4.17s` → **慢 8.3 倍**。
   根因在 Rancher Desktop 的 VM 配置（`~/Library/Application Support/rancher-desktop/lima/0/lima.yaml`）：

   ```yaml
   cpus: 2
   memory: 6442450944        # 6 GiB
   vmType: qemu              # 不是 vz
   mountType: reverse-sshfs  # 不是 virtiofs
   vz:
     rosetta:
       enabled: false        # Rosetta 关闭 → amd64 全靠 QEMU 翻译
   ```

   按这个配置编 p4a（要交叉编译 CPython + OpenSSL + SQLite + 加密库），**首次构建预计 4–8 小时**；开 Rosetta 后通常能压到 1 小时以内。

**建议调整**（Rancher Desktop → Settings）

| 项 | 当前 | 建议 |
|---|---|---|
| Virtual Machine Type | qemu | **VZ**（Apple Virtualization） |
| Emulation / Rosetta | 关闭 | **开启**（amd64 近原生速度） |
| CPUs | 2 | **6–8** |
| Memory | 6 GiB | **12–16 GiB** |
| Mount type | reverse-sshfs | **virtiofs**（大文件编译快很多） |

> 若不想折腾 Rosetta，备选方案：把构建搬到远程 x86_64 Linux（或写一个 GitHub Actions workflow 出 APK 产物），本机只负责 `adb install`。

---

## 6. 环境配置步骤（按序执行）

### Step 0 · 启动 Docker（对应 G1）

```bash
# 图形方式：打开 Rancher Desktop，等托盘图标变绿
open -a "Rancher Desktop"

# 命令行验证（必须能打印 Server Version）
docker version --format '{{.Server.Version}}'
docker info --format '{{.OSType}}/{{.Architecture}}'
```

> 若不想用 Rancher Desktop，可换 `brew install colima && colima start --cpu 4 --memory 8`，效果等价。

### Step 1 · 构建 Android 构建镜像（用仓库自带配方）

```bash
cd /Users/wuhuidong/Documents/Workspace/for_shizong/PyBitmessage

# 镜像内已含：JDK17、SDK cmdline-tools、build-tools 34、NDK 25b、buildozer、cython
# 首次构建 15–30 分钟（下载 SDK/NDK）；注意必须显式指定 amd64，见 §5.4
docker build --platform linux/amd64 -t bm-android -f .buildbot/android/Dockerfile .
```

### Step 2 · 起容器，准备源码树

```bash
docker run --rm -it --platform linux/amd64 -v "$PWD":/src -w /src bm-android bash
```

容器内执行（buildozer 不认仓库里的 `pybitmessage -> src` 软链，按官方 CI 的做法铺平）：

```bash
rm -rf src/pybitmessage && mkdir -p src/pybitmessage
cp src/*.py src/pybitmessage
cp -r src/bitmessagekivy src/backend src/mockbm src/images src/pybitmessage

# gradle 内存限制（官方 workaround）
mkdir -p ~/.gradle
echo "org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=512m -Dfile.encoding=UTF-8" > ~/.gradle/gradle.properties

# p4a 工具链缓存持久化（可选但强烈建议，避免每次重下 SDK/NDK）
# 宿主侧另开终端：docker volume create p4a-cache，然后用 -v p4a-cache:/root/.buildozer 起容器
```

### Step 3 · 先出基线 APK（M1，不改任何代码）

```bash
cd packages/android
buildozer android debug          # 首次 40–90 分钟（编译 CPython + Kivy + 依赖）
ls -lh bin/*.apk
```

### Step 4 · 装到设备 / 模拟器（M1 验收）

```bash
# 真机（先开 开发者选项 → USB 调试）
adb devices
adb install -r packages/android/bin/*.apk
adb logcat -s python:* SDL:* AndroidRuntime:E

# 或模拟器
~/Library/Android/sdk/emulator/emulator -avd Pixel_6_API_33 -no-snapshot &
```

### Step 5 · 采集目标设备参数（决定 `archs/minapi/权限`）

```bash
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release   # Android 版本
adb shell getprop ro.build.version.sdk       # API level
adb shell getprop ro.product.cpu.abi         # arm64-v8a / armeabi-v7a
```

> 这三个值请回填到本文件 §9，`buildozer.spec` 的 `android.archs` 与 `android.minapi` 以它为准。

### Step 6 · 日常迭代命令

```bash
buildozer android debug deploy run logcat     # 编译+安装+启动+跟日志，一条龙
buildozer -v android debug                    # 出问题时看详细日志
```

---

## 7. 代码改动清单（M2/M3 要动的文件）

| 文件 | 改什么 | 目的 |
|---|---|---|
| `src/main-android-live.py` | 删掉 `print('kivy is not supported...')` + `sys.exit()`；保留 `state.kivy = True` 后调 `main()` | 打开真实启动入口 |
| `src/bitmessagemain.py` | ① `check_pyqt()` 判断加 `and not state.kivy`；② GUI 分发处补 `elif state.kivy: NavigateApp().run()` | 绕开 PyQt4 依赖 |
| `src/bitmessagekivy/mpybit.py` | `from pybitmessage.mockbm.helper_startup import ...` → 真实 `helper_startup` | UI 读真实配置/地址 |
| `src/mockbm/*` | 保留给 `tests-kivy.py`；用环境变量（如 `BITMESSAGE_MOCK=1`）切换，不直接删 | 不破坏现有测试 |
| `packages/android/buildozer.spec` | `title/package.name` 去掉 Mock；`requirements` 加 `pycryptodome,msgpack,six,psutil`、`python3` 锁版本；`android.permissions = INTERNET,ACCESS_NETWORK_STATE,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK`；`services = bitmessage:service.py:foreground`；`android.archs = arm64-v8a` | 从 Demo 变客户端 |
| `src/paths.py` 或启动处 | Android 下把 `BITMESSAGE_HOME` 指向 `app_storage_path()` | 现在会落到 `HOME/.config`，HOME 为空会崩 |
| `src/proofofwork.py` | MVP 阶段禁用 C PoW（`BITMSGLIB` 加载失败自动回退），二期限 p4a recipe | 先跑通再提速 |
| 新增 `service.py` | p4a 前台服务入口：起 core 线程 + 通知 + WakeLock | 后台存活 |

---

## 7.5 GitHub Actions 远程构建：已跑通（2026-11-17 实测）

### 结论

> 说明：本节记录的是仓库重建**之前**在旧 clone/fork 上的构建（历史证据，链接仍可访问）。
> 重建后 CI 在 `k19810703/pybitmessage-android` 的仓库根 workflow 上运行，命令见 `MILESTONES.md` §11。

**远程构建 + 本机侧载的链路已闭环**，单次出包 **约 9 分钟**（含缓存命中）。

| 项 | 值 |
|---|---|
| Fork 仓库 | <https://github.com/k19810703/pybitmessage-android>（public） |
| 工作分支 | `android-port`（也是 fork 的默认分支，`workflow_dispatch` 需要在默认分支上） |
| Workflow | `.github/workflows/android-apk.yml` |
| 成功 run | <https://github.com/k19810703/pybitmessage-android/actions/runs/44013702969>（9 分 06 秒） |
| 产物 | `pybitmessagemock-0.1.2-arm64-v8a-debug.apk`（25 MB） |
| 本机落盘 | `PyBitmessage-android/artifacts/pybitmessage-apk-7/` |
| 设备验证 | `Pixel_6_API_33`（arm64-v8a / Android 13）：安装成功、启动成功、界面正常（截图 `artifacts/screenshot-2.png`） |

### 关键配置（缺一不可）

`packages/android/buildozer.spec`：

```ini
android.minapi = 24          # numpy 要求 >=24，21 会直接报错
android.ndk_api = 24
android.archs = arm64-v8a    # 只编一个架构，快 3 倍
p4a.branch = v2024.01.21     # 该 tag 的 python3 recipe 是 3.11.5
requirements = python3,kivy,sqlite3,kivymd==1.0.2,Pillow,kivy-garden.qrcode,qrcode,typing_extensions,pypng
```

`.github/workflows/android-apk.yml`：

- `actions/setup-java@v4` + `temurin 17`（runner 默认 JDK 25 → Gradle 报 `class file major 69`）
- `pip install cmake==3.31.6` 并软链到 `/usr/local/bin/cmake`（runner 的 CMake 4.x 拒绝 libjpeg-turbo 2.0.1 的 `cmake_minimum_required(2.8.12)`）
- `actions/cache/restore` + `actions/cache/save`（`if: always()`）缓存 `~/.buildozer`

### 六轮踩坑记录（每轮都是一次真实环境不兼容）

| 轮 | 结果 | 现象 | 根因 | 修复 |
|---|---|---|---|---|
| 1 | ✗ 1.5 min | `In order to build 'numpy', you must set minimum ndk api to 24` | spec 里 minapi=21 | minapi/ndk_api → 24 |
| 2 | ✗ 11 min | `no template named 'unordered_map'` | p4a 拉 numpy 2.3.0（git master），与 NDK r25b libc++ 不兼容 | 去掉 opencv/xcamera/zbarcam/pyzbar（numpy 随之消失） |
| 3 | ✗ 10 min | Gradle 7s 失败：`Unsupported class file major version 69` | runner 默认 JDK 25，Gradle 8.14 支持到 24 | 钉 JDK 17 |
| 4 | ✓ 11 min | —— | —— | 产出 APK |
| 5 | ✗ 4 min | 启动即崩：`configparser has no attribute SafeConfigParser` | p4a master 的 python3 recipe 是 **3.14**；`SafeConfigParser`/`asyncore`/`smtpd` 已在 3.12 移除 | `p4a.branch = v2024.01.21`（CPython 3.11.5） |
| 6 | ✗ 4 min | CMake 配置失败：`Compatibility with CMake < 3.5 has been removed` | runner CMake 4.x + p4a 2024 的 libjpeg-turbo 2.0.1 | 钉 CMake 3.31.6 |
| 7 | ✓ 9 min | —— | —— | **APK 装上就能跑**（Python 3.11） |

### 日常用法

```bash
# 触发一次构建（也可直接 push 到 android-port）
gh workflow run "Android APK" --repo k19810703/pybitmessage-android --ref android-port

# 等它跑完并下载产物
gh run watch --repo k19810703/pybitmessage-android
gh run download --repo k19810703/pybitmessage-android -D PyBitmessage-android/artifacts

# 装机
~/Documents/platform-tools/adb install -r PyBitmessage-android/artifacts/*/*.apk
```

### 仍然遗留的问题

- `pybitmessagemock` 的包名/标题还是 Mock：改名要动 `buildozer.spec` 的 `title`/`package.name`
- APK 里没有 `INTERNET` 权限（`android.permissions` 仍是注释状态）→ 一旦接入真实核心就会连不上网
- 启动时有一次性的 bundle 解压（首启约 30–60 秒 "Loading..."），后续正常
- 缓存 key 命中后 `actions/cache/save` 会报 "Cache save failed"（key 已存在），属正常噪音

---

## 8. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| Kivy 2.1.0 / KivyMD 1.0.2 在 Android 14+ 上异常（键盘、返回键、edge-to-edge） | 高 | 界面不可用 | 先锁 build-tools/API 33 出包；不行再评估 KivyMD 升级（约 1 周） |
| `pyzbar/opencv/xcamera` 构建失败 | 高 | M1 卡住 | 立即从 requirements 移除，二期单独做二维码 |
| PoW 在手机上过慢/耗电 | 高 | 体验差 | 低功耗模式 + 仅充电同步 + 降低自身 `nonce_trials_per_byte` |
| Android 后台杀进程 | 高 | 收不到消息 | 前台服务 + 通知 + 引导关闭电池优化 |
| `pycryptodome` 交叉编译失败 | 中 | 无法加解密 | 优先用 p4a 官方 recipe；退路是 `cryptography` 或纯 Python ECC（慢但可用） |
| `bitmsghash` 无 recipe | 中 | PoW 慢 | MVP 用纯 Python，二期限 recipe 或预编译 `.so` 走 `android.add_libs_arm64_v8a` |
| 未审计的安全风险 × 移动端新攻击面 | 中 | 数据泄露 | 仅自用/内测，不对外分发；关闭不必要权限 |
| macOS 26 上 Docker 磁盘/文件共享异常 | 低 | 构建失败 | 用 named volume 放源码，避免 bind mount 性能问题 |

---

## 9. 待确认（影响出包参数）

- [ ] 目标设备：型号 / Android 版本 / ABI（填 Step 5 的三个 getprop 结果）
- [ ] 是否接受"常驻通知"（前台服务的必要代价）
- [ ] 是否需要与桌面端共用同一份 `keys.dat`（决定是否做导入功能）
- [ ] MVP 是否必须支持 Chan/订阅（不做可省 3–5 天）
- [ ] 是否允许本机常驻 Docker（构建期约 20–30 GB 磁盘）

---

## 10. 参考

- 仓库：<https://github.com/Bitmessage/PyBitmessage>（`v0.6` 分支）
- 协议规范：<https://wiki.bitmessage.org/index.php/Protocol_specification>
- buildozer 文档：<https://buildozer.readthedocs.io/>
- python-for-android：<https://python-for-android.readthedocs.io/>
- 仓库内构建配方：`PyBitmessage/.buildbot/android/Dockerfile`、`PyBitmessage/.github/workflows/android.yml`、`PyBitmessage/packages/android/buildozer.spec`
