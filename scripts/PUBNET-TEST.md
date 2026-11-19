# 公网收发验证 Runbook（Mac 脚本节点 + 平板热点）

目的：验证「不同 IP + 单连接」下公网连接与加密消息收发（对应
EVIDENCE.md §1.24 的两个假设验证 + G3 公网版闭环）。

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
