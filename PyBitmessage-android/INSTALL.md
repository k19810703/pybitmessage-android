# 安装与升级（侧载）

> 面向拿到 `pybitmessage-*.apk` 的人。命令以 macOS + adb 为例，包名
> `at.bitmessage.pybitmessage`。

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

## 3. PoW 难度（extralowdifficulty）

设备上没有 C 版 PoW，默认难度下一条消息要 ~10 分钟。因此：

- **从 2026-11-18 之后的构建开始，APK 首次启动会自动写入
  `extralowdifficulty = true`**，不需要手动操作
  （logcat 里能看到 `POW: defaulting to extralowdifficulty on Android`）。
- 想手动开关（debug 包 + adb 才可行）：

  ```bash
  ./scripts/enable-low-pow.sh          # 打开并重启
  ./scripts/enable-low-pow.sh off      # 关闭
  ```

- 它改的是 App 私有目录里的 `keys.dat`：

  ```bash
  adb shell run-as at.bitmessage.pybitmessage grep extralowdifficulty files/bitmessage/keys.dat
  ```

⚠️ **对端也要低难度**：PoW 目标由发送方声明、接收方校验，双方都开才稳定互通。
两个都装本项目 APK 时，双方默认都开。

## 4. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 签名不同（本次构建 vs 已装） | 见 §2：重签或卸载 |
| 启动后长时间白屏 | 首次解压运行时 | 等 60 秒 |
| 发消息一直 `doingmsgpow` | 没有开低难度 | `./scripts/enable-low-pow.sh` |
| 连不上任何节点 | 默认种子节点已下线 | 需要配置可用 `knownnodes`（见 AGENTS §6.6） |
