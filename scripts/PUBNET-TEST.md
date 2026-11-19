# 公网收发验证 Runbook（Mac 脚本节点 + 平板热点）

> **2026-11-19 15:45 状态**：热点实验已完成并成功（平板 2 连接 + 对象下载，
> EVIDENCE.md §1.25）；公司出口 IP 被种子粘性拒绝（今早轰炸残留）。
> **下一步：晚上家里网络（新 IP）跑本文 §6。**

## 6. 今晚家里的流程（2026-11-19 晚）

前置：Mac、平板都连家里网络；平板 USB 连 Mac。**平板已配置完毕**
（API u:p@8442、地址 `BM-2cU2vEDgphdWHe4Ucp1gSigCwDrJTRfyYV`），无需再跑 setup。

```bash
# 1) Mac 节点（家里 IP 干净，wait-conn 应在 1-3 分钟内成功）
cd /Users/wuhuidong/Documents/Workspace/for_shizong
./scripts/pubnet_node.py                 # 终端 A，前台跑
./scripts/pubnet_ctl.py wait-conn 300    # 终端 B
./scripts/pubnet_ctl.py create mac-test  # 记下 mac 地址

# 2) 平板状态（App 若卡住：force-stop 后 am start，等 90s）
~/Documents/platform-tools/adb -s b45f8e87 forward tcp:8445 tcp:8442
python3 scripts/pubnet_ctl.py --port 8445 status      # 期望 networkConnections>=1
python3 scripts/pubnet_ctl.py --port 8445 addresses   # 确认仍是 BM-2cU2vEDg...

# 3) Mac -> 平板
./scripts/pubnet_ctl.py send BM-2cU2vEDgphdWHe4Ucp1gSigCwDrJTRfyYV <mac地址> '公网测试' 'hello via public net'
./scripts/pubnet_ctl.py sent                          # awaitingpubkey -> msgsent
python3 scripts/pubnet_ctl.py --port 8445 inbox       # 平板收件箱验证

# 4) 平板 -> Mac（UI：收件人贴 mac 地址，内容随意，点发送）
./scripts/pubnet_ctl.py inbox                         # Mac 收件箱验证
```

**判定**：
- Mac `wait-conn` 失败且日志仍见 `Too many connections from your IP` → 家里 IP
  也被拒（异常！说明可能不是 IP 维度），用备用方案（§7）并抓包
- 双向消息到达 → **G3 公网版闭环达成**，记录 EVIDENCE 并推送 commits

## 7. 备用方案

- **USB 桥**：`adb -s b45f8e87 forward tcp:18444 tcp:8444` 后把
  `--peer 127.0.0.1:18444` 加给 `pubnet_node.py`（Mac 直连平板节点，
  已见 verack 回包未完整验证）；消息仍经平板的公网连接扩散
- **双热点**：两台设备各连不同手机热点直接走公网（热点实验已证明可行）

---

（以下为原 runbook，历史参考）

目的：验证「不同 IP + 单连接」下公网连接与加密消息收发（对应
EVIDENCE.md §1.24/§1.25 的假设验证 + G3 公网版闭环）。
热点连接部分已于 2026-11-19 15:16 验证通过。

## 0. 前置

- 平板已连**手机热点**（关键：换 IP，验证是否 IP 级拒绝）
- 平板已装 TLS 修复包（run 44464696554，`scripts/resign-apk.sh` 个钥签）
- Mac 上已编译本机 PoW 库：`./scripts/build-bitmsghash-native.sh`（一次性）

## 1. Mac 节点

```bash
./scripts/pubnet_node.py            # 前台跑，Ctrl-C 停；数据在 /tmp/pubnet
```

另开终端：

```bash
./scripts/pubnet_ctl.py wait-conn 300     # 等 networkConnections>=1
./scripts/pubnet_ctl.py create mac-test   # 建地址（首次，秒级），记下 BM-…
```

- **判定 A**（连接）：5 分钟内 `wait-conn` 成功 → 家里 IP 单连接可过种子
  检查（混合键型假设成立）；仍失败 → 看 `pubnet_node.py` 终端里
  `Too many connections from your IP` 是否依旧，依旧则倾向 IP ban
- 建地址后 `sendMessage` 触发的 pubkey PoW 用本机 C 库，秒级

## 2. 平板（热点）

```bash
./scripts/pubnet_tablet_setup.sh b45f8e87   # 注 API+活节点并重启
python3 scripts/pubnet_ctl.py --port 8445 wait-conn 300
python3 scripts/pubnet_ctl.py --port 8445 addresses   # 记下平板地址
```

- **判定 B**（换 IP 连接）：热点 IP 上能连 → 证实之前是 IP 级问题；
  仍被拒 → 我方握手问题（下一步抓包比对）
- 平板 UI（中文界面）应显示网络状态正常

## 3. 双向消息

```bash
# Mac -> 平板
./scripts/pubnet_ctl.py send <平板地址> <mac地址> 'test' 'hello from mac'
./scripts/pubnet_ctl.py sent        # awaitingpubkey -> msgsent -> ackreceived
# 平板收件箱（UI 5s 刷新，或）：
python3 scripts/pubnet_ctl.py --port 8445 inbox
```

反向：平板 UI 收件人填 mac 地址，发送；Mac 侧
`./scripts/pubnet_ctl.py inbox` 验证。

## 4. 预期时间线

| 阶段 | 预期 |
|---|---|
| 双方连接 | 各 1–3 分钟 |
| getpubkey/pubkey 交换 | 数分钟（新地址首次互通） |
| PoW | Mac C 库秒级；平板 ~4s/对象 |
| 消息到达 | 全程 5–15 分钟 |

卡在 `awaitingpubkey` 超过 10 分钟 → 检查双方 `status` 的
`networkConnections` 是否仍 ≥1（连接掉了 pubkey 就传不过来）。

## 5. 备注

- Mac 节点 API 端口 8451（避开 adb forward 的 8442）；平板走 8445
- Mac 在公司网，无公网入站没关系，出站即可
- 结束后：`pkill -f pubnet_node.py`；平板可切回原 Wi-Fi
