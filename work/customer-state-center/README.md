# 客户状态中台 MVP

这是“任务一：客户状态中台”的第一版 MVP。

它负责：

- 创建客户任务。
- 保存客户当前状态。
- 判断客户消息是否有用。
- 判断资料是否完整。
- 根据业务逻辑生成 `action_task`。
- 等任务二执行动作后，接收执行结果并更新状态。

它不负责：

- 真正发企业微信消息。
- 真正操作视频软件。
- 真正发送付款链接。
- 真正做 RPA。

这些属于任务二“动作执行引擎”。

## 1. 运行方式

不依赖外部包，只需要 Python 3.11。

```bash
python app.py
```

默认服务：

```text
http://127.0.0.1:8787
```

打开本地可视化测试窗口：

```text
http://127.0.0.1:8787/
```

局域网访问：

```bash
python app.py --host 0.0.0.0 --port 8787
```

同一局域网设备访问本机 IP：

```text
http://192.168.1.11:8787/
```

聊天输入框里，`Enter` 直接发送，`Shift+Enter` 换行。

测试窗口侧边栏包含“小企盾”文字转换工具，会按 12 字分段、倒序并包 Unicode BiDi 控制符。

当前业务约束：

- 客户未点链接前，只发送点链接引导，不发送其它业务话术。
- 2 分钟检查时客户仍未点链接，则结束该客户流程。
- 客户点链接后，才继续资料、红包、化解、付款失败等后续判断。

健康检查：

```bash
curl http://127.0.0.1:8787/health
```

## 2. 演示流程

```bash
python demo_flow.py
```

演示内容包括：

- 新客户进入。
- 自动生成发送链接动作。
- 客户点链接。
- 客户发截图但没资料。
- 客户补完整资料。
- 未点链接但发资料，2分钟后也登记。
- 红包场景。
- 化解咨询。
- 付款失败。

## 3. 核心数据

### customer_task

每个客户一条主任务。

关键字段：

```text
id
customer_id
current_status
link_id
link_clicked
useful_info_received
info_complete
missing_fields
customer_name
birth_year
birth_month
birth_day
registered_at
video_sent_at
payment_link_sent_at
deleted_by_customer
final_status
```

### action_task

任务一生成动作，任务二消费动作。

关键字段：

```text
id
customer_task_id
action_type
payload
status
scheduled_at
executed_at
result
```

## 4. 事件接口

### POST /events

请求：

```json
{
  "event_type": "NEW_CUSTOMER",
  "customer_id": "wx_customer_001",
  "payload": {}
}
```

返回：

```json
{
  "customer_task": {},
  "actions": []
}
```

## 5. 支持的事件类型

| event_type | 说明 |
|---|---|
| NEW_CUSTOMER | 新客户进入 |
| LINK_SENT | 链接已发送 |
| LINK_CLICKED | 客户已点链接 |
| CUSTOMER_MESSAGE | 客户发消息 |
| CHECK_LINK_CLICKED_AFTER_2MIN | 2分钟后检查客户是否点链接 |
| CUSTOMER_DELETED | 客户删除或无法触达 |

## 6. 客户消息示例

### 客户发截图但没资料

```json
{
  "event_type": "CUSTOMER_MESSAGE",
  "customer_id": "wx_customer_001",
  "payload": {
    "text": "【截图】什么都没有",
    "has_screenshot": true
  }
}
```

系统会生成动作：

```text
ASK_FOR_IMAGE_INFO
```

话术：

```text
请把上面图片的信息发我一下
```

### 客户发完整资料

```json
{
  "event_type": "CUSTOMER_MESSAGE",
  "customer_id": "wx_customer_001",
  "payload": {
    "text": "张三，1998年5月12日"
  }
}
```

如果客户已经点链接，系统会生成：

```text
REGISTER_CUSTOMER
SEND_WAIT_20_MIN_MESSAGE
CREATE_VIDEO
SEND_VIDEO
```

其中 `SEND_VIDEO` 默认排到 20 分钟后。

### 客户只发姓名

```json
{
  "event_type": "CUSTOMER_MESSAGE",
  "customer_id": "wx_customer_001",
  "payload": {
    "text": "张三"
  }
}
```

系统会生成：

```text
ASK_MISSING_BIRTHDAY
```

话术：

```text
把出生年月日发我一下
```

### 未点链接但发完整资料

```json
{
  "event_type": "CUSTOMER_MESSAGE",
  "customer_id": "wx_customer_002",
  "payload": {
    "text": "李四，2001年8月12日"
  }
}
```

系统会生成：

```text
ASK_CLICK_LINK
CHECK_LINK_CLICKED_AFTER_2MIN
```

2分钟后如果仍未点链接，但资料有效完整，也会登记。

## 7. 动作完成接口

### POST /actions/{action_id}/complete

请求：

```json
{
  "status": "success",
  "result": {
    "message_id": "MSG_001"
  }
}
```

如果发送视频成功，任务一会自动生成：

```text
SEND_PAYMENT_LINK
```

并且排到 6 分钟后执行。

### 客户删除失败回传

```json
{
  "status": "failed",
  "result": {
    "error_code": "CUSTOMER_DELETED",
    "reason": "客户已删除或无法触达"
  }
}
```

系统会：

- 标记客户 `CUSTOMER_DELETED`。
- 设置 `final_status = FINISHED`。
- 取消所有未执行的后续动作。

## 8. 查询接口

### GET /customers

查询所有客户任务。

### GET /customers/{customer_task_id}

查询单个客户任务。

### GET /actions

查询所有动作任务。

### GET /actions?status=pending

查询待执行动作任务。

### GET /actions?status=pending&due=1

只查询已经到执行时间的待执行动作任务。

后续任务二建议优先使用这个接口，避免提前执行 `SEND_VIDEO`、`SEND_PAYMENT_LINK` 这类延迟任务。

## 10. 已处理的关键边界

当前版本已经处理：

- 重复 `NEW_CUSTOMER` 不会重复生成 `SEND_LINK`。
- 客户先发姓名、后补出生年月日，会合并历史资料重新判断完整度。
- 未点链接但发完整资料，会先发 `ASK_CLICK_LINK`，并安排 2 分钟检查。
- 2 分钟内客户补点链接，会立即取消检查任务并登记。
- 2 分钟后仍未点链接，但资料完整，也会登记。
- 资料补全后，会取消旧的“要资料/补姓名/补生日”动作。
- 登记后，会取消旧的“点链接/2分钟检查”等动作。
- 视频发送成功后，会自动生成 6 分钟后的 `SEND_PAYMENT_LINK`。
- 客户删除或无法触达后，会结束任务并取消后续所有待执行动作。
- 任务结束后再收到客户消息，会被忽略，不再生成新动作。

## 11. 测试

运行：

```bash
python -m unittest -v test_state_center.py
```

当前覆盖：

- 新客户重复事件幂等。
- 分段资料合并。
- 等待点链接期间客户点链接后立即登记。
- 视频发送后生成 6 分钟付款链接。
- 客户删除后取消所有待执行动作。

## 9. 与任务二的拼接口

任务二只需要做三件事：

1. 读取 `GET /actions?status=pending`。
2. 按 `action_type` 执行动作。
3. 调用 `POST /actions/{action_id}/complete` 回传结果。

任务一不关心任务二是用企业微信 API，还是 RPA，还是人工工具。

这就是两个模块像乐高一样拼接的接口。
