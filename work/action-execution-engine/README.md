# 动作执行引擎 MVP

这是“任务二：动作执行引擎”的第一版 MVP。

它负责：

- 轮询任务一生成的到期 `action_task`。
- 按 `action_type` 执行动作。
- 把成功或失败结果回传给任务一。
- 用模拟适配器跑通企业微信、登记、视频、付款等执行流程。

它不负责：

- 判断客户业务状态。
- 决定下一步动作。
- 直接访问任务一数据库。
- 第一版不接真实企业微信、视频软件、支付系统或 RPA。

## 1. 运行方式

先启动任务一客户状态中台：

```bash
python app.py
```

默认任务一地址：

```text
http://127.0.0.1:8787
```

再启动任务二：

```bash
python engine.py
```

## 2. 配置

通过环境变量配置：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `STATE_CENTER_BASE_URL` | `http://127.0.0.1:8787` | 任务一 HTTP 服务地址 |
| `POLL_INTERVAL_SECONDS` | `2` | 没有到期动作时的轮询间隔 |
| `DRY_RUN` | `false` | 标记模拟执行结果 |
| `SIMULATE_CUSTOMER_DELETED_ACTION_IDS` | 空 | 用逗号分隔 action id，命中时模拟客户删除 |

PowerShell 示例：

```powershell
$env:STATE_CENTER_BASE_URL = "http://127.0.0.1:8787"
$env:POLL_INTERVAL_SECONDS = "2"
python engine.py
```

## 3. 支持的动作

第一版支持：

- `SEND_LINK`
- `ASK_FOR_IMAGE_INFO`
- `ASK_MISSING_BIRTHDAY`
- `ASK_MISSING_NAME`
- `ASK_CLICK_LINK`
- `REGISTER_CUSTOMER`
- `SEND_WAIT_20_MIN_MESSAGE`
- `CREATE_VIDEO`
- `SEND_VIDEO`
- `SEND_PAYMENT_LINK`
- `SEND_PAYMENT_QR`
- `SEND_RED_PACKET_REPLY`
- `ASK_DONATION_AMOUNT`
- `FINISH_TASK`
- `CHECK_LINK_CLICKED_AFTER_2MIN`

`CHECK_LINK_CLICKED_AFTER_2MIN` 是内部事件类动作，会调用任务一 `POST /events` 触发检查，再回传动作完成结果。

## 4. 回传格式

成功动作会回传：

```json
{
  "status": "success",
  "result": {
    "message_id": "MSG_xxx"
  }
}
```

模拟客户删除会回传：

```json
{
  "status": "failed",
  "result": {
    "error_code": "CUSTOMER_DELETED",
    "reason": "客户已删除或无法触达"
  }
}
```

## 5. 测试

运行：

```bash
python -m unittest -v test_engine.py
```

测试覆盖：

- 主要动作类型分发和成功回传。
- 模拟客户删除失败回传。
- `CHECK_LINK_CLICKED_AFTER_2MIN` 触发任务一事件接口。
- 未知动作类型回传失败。

## 6. 后续替换真实执行

真实接入企业微信、视频软件、支付工具或 RPA 时，优先替换 `adapters.py` 里的 `SimulatedActionAdapter`，保留 `engine.py` 的轮询、分发和回传主流程。
