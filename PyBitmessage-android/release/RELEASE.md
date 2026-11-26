# PyBitmessage Android · 0.6.3.2

> 侧载安装包，不上架任何应用商店。装了的设备之间经 Bitmessage 公网收发端到端加密消息，
> 不需要自建服务器、不需要注册账号。

## 下载

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `pybitmessage-0.6.3.2-arm64-v8a.apk` | 28 MB | `179d54304a37e3ea5565080a779312e227551ffd8a5add8e09fde3e0c148643a` |

校验：

```bash
shasum -a 256 -c SHA256SUMS
```

## 安装

```bash
adb install pybitmessage-0.6.3.2-arm64-v8a.apk
# 或在手机上点开 APK 安装
```

- Android **7.0+**（minSdk 24），**arm64-v8a** 架构（主流手机都满足；x86 模拟器不行）
- **首次启动等 3–5 分钟**（解压 Python 运行时），期间黑屏/白屏属正常
- 之后可用同一签名直接覆盖升级，**数据不丢**：

```bash
adb install -r pybitmessage-0.6.3.2-arm64-v8a.apk
```

签名指纹（核对是不是同一把钥匙）：

```
SHA-256: 82463dfe0a7ef14821c33fef5e462e1f7bed070387de2bee7e9dd4fdebc551c7
CN=PyBitmessage Android, O=PyBitmessage, C=CN
```

若从**别的签名**的旧包升级，会报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`；此时必须卸载重装，
而卸载会删掉 `keys.dat`（地址与私钥不可恢复）——**先备份**：

```bash
adb shell run-as at.bitmessage.pybitmessage cat files/bitmessage/keys.dat   > keys.dat.bak
adb shell run-as at.bitmessage.pybitmessage cat files/bitmessage/keys.vault > keys.vault.bak
```

（`keys.dat` 已加密，两个文件缺一不可。）

## 这个版本有什么

| 能力 | 状态 |
|---|---|
| 生成地址、重启不丢 | ✅ |
| 公网连接真实节点 | ✅ 实测稳定 5 条连接 ≥15 分钟 |
| 中英文消息双向收发 + 送达回执 | ✅ |
| 中文界面（主界面 / 收件箱 / 已发送 / 草稿 / 回收站 / 全部邮件） | ✅ 部分页面仍有英文 |
| 前台服务保活 + WakeLock | ✅ |
| 新消息系统通知（含中文主题） | ✅ |
| 自己的启动图（不再是 Kivy 风筝） | ✅ |
| 地址簿 / 订阅 / 黑白名单 API 可用（非空时不崩） | ✅ |
| Android 13 通知权限运行时申请 | ✅ |
| 私钥加密（Android Keystore 包裹，`keys.dat` 为密文） | ✅ |
| 中文应用图标 + 自己的启动图 | ✅ |
| 横竖屏自适应（运行时切换） | ✅ |
| 学到的节点会落盘（重启不用重新抽签） | ✅ |
| 能连上公网节点（TLS 卡死已修） | ✅ 实测 0→2 条 |
| 诊断日志（3 天）+ 抽屉里一键分享 | ✅ |
| 界面内两栏布局（平板横屏） | ✅ |
| 收件箱可删除（回收站可恢复/彻底删除） | ✅ |
| 发消息页：发件地址下拉、粘贴按钮、地址联想 | ✅ |
| 硬件返回键/左上箭头：返回上一页而不是退出 | ✅ |

## 已知限制

- 连接数还会在 0–2 之间抖动（M4.8.11），但已能建立连接、能发出并收到回执
- **锁屏 30 分钟仍能收消息（D5）尚未验收** —— 演示时请保持亮屏
  （D1–D4、D6、D7 已全绿，见 `EVIDENCE.md` §1.59）
- 私钥加密依赖设备 Keystore；换机 = 换身份，必须同时迁移 `keys.dat` + `keys.vault`
- 消息经 P2P 网络转发，**不是即时通讯**：首次给新地址发消息 1–5 分钟，正常送达 23 秒–3 分钟
- 部分页面仍是英文（搜索框提示、个别设置项）
- 横屏可用；平板横屏已改成两栏（收件箱 + 写信）
- emoji 显示为 ⊠（CJK 字体无 emoji 字形）
- 首次启动解压慢（3–5 分钟）

## 需要更新的节点列表

Bitmessage 公网节点变动频繁，`knownnodes.dat` 里的节点死掉时会表现为"连不上任何节点"。
排查与恢复见 `README-ANDROID.md` §5.1。

## 文档

- 使用说明（安装 / 首配 / 互换地址 / 故障排查）：`README-ANDROID.md`
- 安装与升级细节、签名配置：`INSTALL.md`
- 验收证据与踩坑记录：`EVIDENCE.md`
- 任务与验收标准：`MILESTONES.md`
