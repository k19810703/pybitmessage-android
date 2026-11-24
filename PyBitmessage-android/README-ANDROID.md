# PyBitmessage Android · 使用说明

> 面向**拿到 APK 想装到手机上用**的人。10 分钟能装完并发出第一条消息。
> 开发者文档见 `HANDOFF.md` / `MILESTONES.md` / `EVIDENCE.md`。

---

## 0. 这是什么，能做到什么

一个把 PyBitmessage（Bitmessage 协议，去中心化加密消息）搬到 Android 的 APK。
装了的设备之间**经 Bitmessage 公网收发端到端加密消息**，不需要自建服务器、不需要注册账号。

**已经验证可用的**（都有设备实测记录，见 `EVIDENCE.md`）：

| 能力 | 状态 |
|---|---|
| 生成地址（首次约 4 秒） | ✅ |
| 公网连接真实节点、保持在线 | ✅ 稳定 5 条连接 |
| 中文 / 英文消息收发 | ✅ 实测 23 秒–3 分钟送达 |
| 送达回执（ack） | ✅ |
| 中文界面（主界面 + 收件箱 + 四个邮件页 + 抽屉） | ✅ 部分页面仍有英文 |
| 前台服务保活 + WakeLock | ✅ |
| 新消息系统通知 | ✅ 含中文主题 |

**还没做的**（别指望）：
- 横屏布局（当前锁竖屏）
- 界面没有语言切换（中文是内置的）
- 锁屏超长时间的收消息能力**尚未完成 30 分钟验收**

---

## 1. 安装

### 1.1 前提

- Android **7.0+**（minSdk 24），**arm64-v8a**（主流手机都满足；x86 模拟器不行）
- 允许「安装未知来源应用」
- 一个能访问 Bitmessage 公网的网络（家庭 Wi-Fi / 手机流量都行，公司网络常封 8444）

### 1.2 装（二选一）

**A. 直接在手机上装**：把 APK 拷到手机，用文件管理器点开安装。

**B. 用 adb 装**（推荐，能看日志）：

```bash
adb install pybitmessage-0.1.2-arm64-v8a-debug.apk
adb shell am start -n at.bitmessage.pybitmessage/org.kivy.android.PythonActivity
```

> **第一次启动要等 3–5 分钟**（解压 Python 运行时，实测值），这期间是黑屏/白屏，
> 下拉通知栏也看不到任何东西，**不是卡死**。第二次启动秒开。
> 判断是否还在解压：`adb logcat -s python:* | grep extracting` 还在输出就说明在跑。

### 1.3 升级不丢地址

CI 每次构建的签名不同，直接覆盖会报
`INSTALL_FAILED_UPDATE_INCOMPATIBLE`。两条路：

- **推荐**：每次下载的 APK 先用自己的钥匙重签一次（`scripts/resign-apk.sh`），
  之后所有版本共用同一签名，`adb install -r` 直接覆盖、数据不丢。详见 `INSTALL.md` §2。
- **省事但危险**：卸载再装 —— **会连 `keys.dat` 一起删掉，地址和私钥就没了**。
  真要这么做，先备份：

  ```bash
  adb shell run-as at.bitmessage.pybitmessage cat files/bitmessage/keys.dat > keys.dat.bak
  ```

---

## 2. 首次配置（3 件事）

### 2.1 允许通知

Android 13+ 首次进入会弹「是否允许 PyBitmessage 发送通知」→ 点**允许**。
不许也能用，只是新消息不会有系统通知。

（万一误点了拒绝：设置 → 应用 → PyBitmessage → 通知 → 打开。）

### 2.2 允许后台运行（**很重要**）

`keys.dat` 在应用私有目录，正常情况下不需要管。但 MIUI / HyperOS / 部分国产 ROM 会
**锁屏后冻结后台**，导致收不到消息。进入 App 后如果系统弹「允许后台运行」就允许；
否则手动去：

- 小米：设置 → 应用设置 → PyBitmessage → **省电策略 → 无限制**，并打开**自启动**
- 其他 ROM：设置 → 电池 → 找到 PyBitmessage → 允许后台活动

App 启动时会写一条日志确认状态（`adb logcat | grep KEEPALIVE`）：

```
KEEPALIVE active: wakeLock=True batteryExempt=False
```

`wakeLock=True` 表示 CPU 不会被休眠；`batteryExempt=False` 表示还没拿到免电池优化，
按上面的步骤去打开。

### 2.3 确认连上了

下拉通知栏应看到 **「PyBitmessage 正在运行」**（前台服务）。
App 内左上角菜单 → 网络状态，应显示连接数 ≥ 1。

---

## 3. 互换地址

地址形如 `BM-2cXrmLDcoGry6Z4kRWqCthD7kuhRxkzaWx`（34 位，以 `BM-` 开头）。

### 3.1 拿到自己的地址

App 主界面第一行就是 **「我的地址：BM-…」**，右边有 **「复制」** 按钮。
一台设备可以有多个地址（菜单 → 我的地址），每个地址有独立私钥。

### 3.2 把地址给对方

- **复制粘贴**（最方便）：点「复制」，用微信/邮件发给对方
- **二维码**：菜单 → 我的地址 → 二维码，对方扫码即可

### 3.3 收到对方地址后

不需要「添加好友」。直接在主界面：

1. 粘到 **「收件人地址」** 输入框
2. 填 **「内容」**
3. 点 **「发送」**

> **第一次给某个新地址发消息会慢**：需要先向全网索取对方的公钥
> （`awaitingpubkey` 状态），再计算工作量证明。中文状态下界面会显示
> 中文化的发送进度（`awaitingpubkey`→等待对方公钥、`doingmsgpow`→计算消息 PoW、
> `msgsent`→已发送、`ackreceived`→对方已确认）。

---

## 4. 发送与接收的耗时预期

| 环节 | 典型耗时 | 说明 |
|---|---|---|
| 生成地址 | ~4 秒 | 只在首次 |
| 计算一条消息的 PoW | ~4 秒 | 设备上有 C 版加速库 |
| 首次给新地址发送 | 1–5 分钟 | 等公钥交换 |
| 送达 | 23 秒 – 3 分钟 | 取决于双方连到的节点 |

**不是即时通讯**。它经 P2P 网络转发，慢是协议特性，不是 bug。

---

## 5. 故障排查

### 5.1 连不上任何节点

最典型的原因是**本机 `knownnodes.dat` 里全是死节点**（Bitmessage 公网节点变动快）。
诊断：

```bash
adb forward tcp:8445 tcp:8442      # 需先在 keys.dat 开 apienabled
curl -s --user u:p -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"clientStatus","params":[],"id":1}' \
  http://127.0.0.1:8445/ | python3 -m json.tool
```

- `"networkStatus": "notConnected"` 且 `networkConnections: 0` → 没连上
- 再看详细连接：把 `clientStatus` 换成 `listConnections`，如果返回一堆
  `"fullyEstablished": false` 且 `"userAgent": ""`，就是**对端全死了**

处理：换几个当前的活节点。设备上操作需要 adb：

```bash
# 1) 停 App
adb shell am force-stop at.bitmessage.pybitmessage
# 2) 写入已知活节点（格式见 scripts/pubnet_node.py 里的 DEFAULT_PEERS）
#    文件路径：/data/data/at.bitmessage.pybitmessage/files/bitmessage/knownnodes.dat
# 3) 重新启动
adb shell am start -n at.bitmessage.pybitmessage/org.kivy.android.PythonActivity
```

> 公司/校园网常年封 8444 出站，表现也是连不上。换到家庭网络或手机热点再试。

### 5.2 显示已发送但对方收不到

按顺序排查：

| 检查 | 方法 | 说明 |
|---|---|---|
| 对方公钥拿到了没 | 发送状态卡在 `awaitingpubkey` | 对方从未在线过；等他上线 |
| 消息过期了没 | 消息 TTL 默认 4 天多（`ttl = 367200` 秒） | 超过就真的丢了，只能重发 |
| 对方地址对不对 | 34 位、`BM-` 开头 | 少一位就是另一个地址 |

**Bitmessage 没有「服务器」帮你补发**：消息发出去靠网络里的节点转发，双方都断网就没人转。

### 5.3 中文消息对方显示乱码 / 收不到

本项目的 APK ↔ 本项目的 APK 之间中文正常（已修字节长度 bug）。
如果和**老版本 PyBitmessage 桌面端**互通出现乱码，是对方的解码问题，不是你这边。

### 5.4 收不到系统通知

1. 检查权限：设置 → 应用 → PyBitmessage → 通知 → 是否关闭
2. 检查是否在「专注模式 / 免打扰」里
3. 只有**新消息入库**才通知；打开 App 时看到的旧消息不会补通知

### 5.5 掉电快

后台保活持有 WakeLock，**持续联网会耗电**。缓解：

- 不用时把 App 从最近任务里划掉（会停止节点）
- 关闭「自启动」，只在用的时候打开 App

（电量策略 `M4.7.1` 尚未实现，1 小时 ≤8% 的指标还没测。）

### 5.6 界面文字显示成方框（豆腐块）

老版本才会出现（字体没注册 CJK）。当前版本内置 `NotoSansCJK`，如仍有问题请记录
机型 + Android 版本。**emoji 会显示成 ⊠**，属已知限制（CJK 字体无 emoji 字形）。

---

## 6. 隐私与安全

- 消息**端到端加密**（ECIES），P2P 链路本身可为明文或 TLS，不中继到任何服务器
- **没有任何遥测/上报**，App 只做 Bitmessage 协议本身的事
- 私钥存在 `keys.dat`，**已加密**（M4.5.2）：master 密钥由 AndroidKeyStore 包裹
  （密钥材料不出 TEE），`keys.dat` 本身是 AES-256-CBC + HMAC 密文
- ⚠️ **备份/迁移必须把 `keys.dat` 和 `keys.vault` 两个文件一起拷**。只拷 `keys.dat`
  在新设备上打不开（会提示 `KEYSTORE FATAL: cannot decrypt` 并新建身份）
- 换机 = 换身份。地址和私钥不会跟着你走，除非手动备份
  `keys.dat` **和** `keys.vault`

---

## 7. 常用 adb 命令

```bash
PKG=at.bitmessage.pybitmessage

# 启动 / 强停
adb shell am start -n $PKG/org.kivy.android.PythonActivity
adb shell am force-stop $PKG

# 看日志（Python 侧的 print 都在 python 这个 tag 下）
adb logcat | grep -E "python|PROBE|NOTIFY|KEEPALIVE"

# 看数据目录（debug 包才能 run-as）
adb shell run-as $PKG ls -l files/bitmessage/
adb shell run-as $PKG grep BM- files/bitmessage/keys.dat

# 备份身份（两个文件都要！缺一不可）
adb shell run-as $PKG cat files/bitmessage/keys.dat  > keys.dat.bak
adb shell run-as $PKG cat files/bitmessage/keys.vault > keys.vault.bak

# 截图
adb exec-out screencap -p > shot.png
```

⚠️ **绝对不要** `adb shell pm clear at.bitmessage.pybitmessage` —— 它会清掉 `keys.dat`，
**私钥不可恢复**，地址和所有历史消息一起没。
