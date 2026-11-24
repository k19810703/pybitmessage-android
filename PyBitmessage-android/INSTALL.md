# 安装与升级（侧载）

> **本文只讲安装与升级。** 首次配置、互换地址、故障排查请看 `README-ANDROID.md`。
> 命令以 macOS + adb 为例，包名 `at.bitmessage.pybitmessage`。

## 1. 首次安装

```bash
adb install -r pybitmessage-0.1.2-arm64-v8a-debug.apk
adb shell am start -n at.bitmessage.pybitmessage/org.kivy.android.PythonActivity
```

首次启动要 30–60 秒解压 Python 运行时，界面出现前是黑屏/白屏，属正常。

> 架构只有 **arm64-v8a**，minSdk 24（Android 7.0+）。

## 2. 升级：为什么要先卸载

CI 每次构建都会生成**新的 debug 签名**，所以两个不同构建的签名不一致，安卓会拒绝覆盖：

```
INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package ... signatures do not match
```

两条路：

### A. 直接覆盖（推荐：先用自己的钥匙重签一次）

```bash
# 每个下载的 APK 都执行一次；钥匙存在 ~/.pybitmessage-android/signing.keystore
./scripts/resign-apk.sh pybitmessage-0.1.2-arm64-v8a-debug.apk

adb install -r pybitmessage-0.1.2-arm64-v8a-debug.apk   # 以后都能直接覆盖
```

重签之后的 APK 共用同一个签名，**后续版本可以 `install -r` 覆盖，数据不丢**。
第一次从「未重签的旧包」换到「重签包」仍需卸载一次。

### B. 卸载再装（会清空本地数据：地址、消息）

```bash
adb uninstall at.bitmessage.pybitmessage
adb install pybitmessage-0.1.2-arm64-v8a-debug.apk
```

> 注意：卸载会连 `keys.dat` 一起删掉，**地址和私钥就没了**。要保留身份，先用
> `adb shell run-as at.bitmessage.pybitmessage cat files/bitmessage/keys.dat > keys.dat.bak` 备份。

## 2.5 让 CI 直接产出「可覆盖安装」的包（M5.2.1）

现状：CI 用**临时 debug 签名**，每个构建签名都不同，所以下载的 APK 不能直接覆盖安装
（`INSTALL_FAILED_UPDATE_INCOMPATIBLE`）。有两种解法：

### A. 本地重签（默认，无需配置）

```bash
./scripts/resign-apk.sh pybitmessage-*.apk
```

第一次运行会在 `~/.pybitmessage-android/signing.keystore` 生成一把钥匙，
之后所有包都用它签，**后续版本可直接 `adb install -r` 覆盖，数据不丢**。

签名指纹（用来核对两个包是不是同一把钥匙）：

```
SHA-256: 82463dfe0a7ef14821c33fef5e462e1f7bed070387de2bee7e9dd4fdebc551c7
```

> ⚠️ **备份 `~/.pybitmessage-android/signing.keystore`**。丢了它，已经装出去的 App
> 只能卸载再装——而卸载会删掉 `keys.dat`，地址和私钥就没了。

### B. 交给 CI 签（一次配置，之后每个产物都能直接装）

在仓库 **Settings → Secrets and variables → Actions** 加三条：

| Secret | 值 |
|---|---|
| `RELEASE_KEYSTORE_B64` | `base64 -i ~/.pybitmessage-android/signing.keystore \| pbcopy`（macOS） |
| `RELEASE_KEYSTORE_PASS` | `pybitmessage`（或你自己的密码） |
| `RELEASE_KEY_ALIAS` | `pybitmessage` |

配好后 workflow 里的 `Sign with the release keystore (optional)` 步骤会自动启用，
日志里能看到 `certificate SHA-256 digest`；没配则跳过，产物仍是 debug 签名。

## 3. PoW 难度

> **2026-11-19 之后已不需要低难度。** 设备上有 C 版 PoW 加速库（`libbitmsghash.so`），
> 协议默认难度下**每个对象约 4 秒**（平板实测，见 `EVIDENCE.md` §1.22）。
>
> 早期构建曾默认打开 `extralowdifficulty`；现在**默认关闭**，因为公网节点会按协议要求
> 钳制难度，低难度对象会被丢弃（`insufficient PoW`）。启动日志会提示
> `POW: extralowdifficulty is on; messages may be dropped by public peers` —— 看到它说明
> 你的 `keys.dat` 里还留着旧值，应删掉。

检查当前值：

```bash
adb shell run-as at.bitmessage.pybitmessage grep extralowdifficulty files/bitmessage/keys.dat
# 无输出 = 使用协议默认难度（正确状态）
```

如确认要手动开关（仅调试用）：`./scripts/enable-low-pow.sh [off]`。

## 4. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 签名不同（本次构建 vs 已装） | 见 §2：重签或卸载 |
| 启动后长时间白屏 | 首次解压运行时 | 等 60 秒 |
| 发消息一直 `doingmsgpow` | 正常，PoW 约 4 秒/对象；超过 1 分钟才异常 | 见 `README-ANDROID.md` §5.2 |
| 连不上任何节点 | `knownnodes.dat` 里全是死节点 | 见 `README-ANDROID.md` §5.1 |
