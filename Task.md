# 任务一交付说明：客户状态中台 MVP

## 1. 已完成内容

已经完成“任务一：客户状态中台”的第一版 MVP。

位置：

```text
work/customer-state-center
```

核心文件：

```text
state_center.py  # 状态机、数据库、动作任务生成
app.py           # HTTP 服务
demo_flow.py     # 演示流程
README.md        # 接口说明
```

## 2. 这个模块负责什么

客户状态中台负责“判断”，不负责真正执行动作。

它负责：

- 创建客户任务。
- 保存客户状态。
- 判断客户是否点链接。
- 判断客户消息是否有用。
- 判断姓名、出生年、出生月日是否完整。
- 判断缺什么字段。
- 判断 2 分钟后是否仍未点链接。
- 登记客户后生成视频任务。
- 视频发送后生成 6 分钟付款链接任务。
- 客户删除时结束任务并取消后续动作。
- 红包、付款失败、化解咨询等异常分支识别。

它不负责：

- 真正发企业微信消息。
- 真正操作视频软件。
- 真正发送付款链接。
- 真正做 RPA。

这些是任务二“动作执行引擎”的工作。

## 3. 技术实现

当前为了快速跑通，用的是：

```text
Python 3.11
http.server
sqlite3
```

没有使用外部依赖包。

原因：

- 当前环境 Node/npm 不可用。
- Python 可直接运行。
- sqlite3 是标准库，适合 MVP。
- 后面可以平滑迁移到 PostgreSQL + Redis + Fastify/FastAPI。

## 4. 运行方式

进入目录：

```bash
cd work/customer-state-center
```

启动服务：

```bash
python app.py
```

服务地址：

```text
http://127.0.0.1:8787
```

健康检查：

```bash
curl http://127.0.0.1:8787/health
```

运行演示：

```bash
python demo_flow.py
```

## 5. 已验证的业务逻辑

演示脚本已经验证：

| 场景 | 结果 |
|---|---|
| 新客户进入 | 生成 `SEND_LINK` |
| 链接发送成功 | 状态变为 `LINK_SENT` |
| 客户点链接 | 状态变为 `LINK_CLICKED` |
| 客户只发截图没资料 | 生成 `ASK_FOR_IMAGE_INFO` |
| 客户补完整资料 | 取消旧的催资料动作，生成登记和视频动作 |
| 未点链接但发完整资料 | 生成 `ASK_CLICK_LINK` 和 2 分钟检查 |
| 2 分钟后仍未点链接 | 也登记并进入视频流程 |
| 视频发送成功 | 自动生成 6 分钟后的 `SEND_PAYMENT_LINK` |
| 客户发红包 | 生成 `SEND_RED_PACKET_REPLY` |
| 客户问化解 | 生成 `ASK_DONATION_AMOUNT` |
| 客户说付不了款 | 生成 `SEND_PAYMENT_QR` |

本轮继续补强后，还验证了：

| 边界 | 结果 |
|---|---|
| 重复新客户事件 | 不重复生成 `SEND_LINK` |
| 客户先发姓名、后发出生年月日 | 自动合并历史资料，资料完整后登记 |
| 未点链接但发资料后，2分钟内又点链接 | 取消2分钟检查，立即登记 |
| 补齐资料后 | 自动取消旧的要资料/补字段动作 |
| 登记后 | 自动取消旧的催点链接/2分钟检查动作 |
| 视频发送成功后 | 状态进入 `WAITING_PAYMENT_LINK`，生成6分钟后的 `SEND_PAYMENT_LINK` |
| 查询 due 动作 | `GET /actions?status=pending&due=1` 不返回未来任务 |
| 客户删除后再发消息 | 事件被忽略，不再生成动作 |

## 6. 主要接口

### 创建事件

```http
POST /events
```

请求示例：

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

### 查询动作任务

```http
GET /actions?status=pending
```

任务二后续就读取这里。

也可以只读取已经到执行时间的任务：

```http
GET /actions?status=pending&due=1
```

后续任务二建议优先消费 `due=1`，避免提前执行 20 分钟后的视频或 6 分钟后的付款链接。

### 回传动作执行结果

```http
POST /actions/{action_id}/complete
```

成功：

```json
{
  "status": "success",
  "result": {
    "message_id": "MSG_001"
  }
}
```

客户删除或无法触达：

```json
{
  "status": "failed",
  "result": {
    "error_code": "CUSTOMER_DELETED",
    "reason": "客户已删除或无法触达"
  }
}
```

## 7. 支持的事件类型

| event_type | 说明 |
|---|---|
| NEW_CUSTOMER | 新客户进入 |
| LINK_SENT | 链接已发送 |
| LINK_CLICKED | 客户已点链接 |
| CUSTOMER_MESSAGE | 客户发消息 |
| CHECK_LINK_CLICKED_AFTER_2MIN | 2分钟后检查是否点链接 |
| CUSTOMER_DELETED | 客户删除或无法触达 |

## 8. 支持的动作类型

| action_type | 说明 |
|---|---|
| SEND_LINK | 发送排队链接 |
| ASK_FOR_IMAGE_INFO | 请客户把图片信息发来 |
| ASK_MISSING_BIRTHDAY | 补问出生年月日 |
| ASK_MISSING_NAME | 补问姓名 |
| ASK_CLICK_LINK | 要客户点链接参与排队 |
| CHECK_LINK_CLICKED_AFTER_2MIN | 2分钟后检查点击 |
| SEND_WAIT_20_MIN_MESSAGE | 发送“好的，请稍等20分钟左右” |
| REGISTER_CUSTOMER | 登记客户 |
| CREATE_VIDEO | 创建视频任务 |
| SEND_VIDEO | 发送视频 |
| SEND_PAYMENT_LINK | 视频后6分钟发送付款链接 |
| SEND_PAYMENT_QR | 付不了款时发送二维码 |
| SEND_RED_PACKET_REPLY | 红包拒收/道观话术 |
| ASK_DONATION_AMOUNT | 问“随喜了多少呢？” |
| FINISH_TASK | 结束客户任务 |

## 9. 与任务二的拼接方式

任务二只需要做三件事：

```text
1. 读取 GET /actions?status=pending&due=1
2. 根据 action_type 执行动作
3. 调用 POST /actions/{action_id}/complete 回传结果
```

任务一不关心任务二是用：

- 企业微信 API
- RPA
- 人工辅助工具
- 视频软件 API
- 支付系统 API

只要任务二按接口回传结果，任务一就能继续推进状态。

## 10. 当前版本边界

当前 MVP 已经跑通核心状态机，并补齐了主要业务边界，但还不是生产版。

后续要补：

- 接入真实企业微信客户 ID。
- 接入真实短链点击回调。
- 接入真实 OCR。
- 接入真实 AI 信息判断。
- 接入 PostgreSQL。
- 接入 Redis/BullMQ 或其他任务队列。
- 接入任务二动作执行引擎。
- 增加后台页面查看客户任务。

## 11. 下一步建议

如果继续完善任务一，可以做：

```text
客户任务后台页面
真实短链点击回调
真实 OCR/AI 资料识别
更多话术配置化
状态迁移审计报表
```

任务二由其他人做时，只要按 `action_task` 接口消费即可。

任务二第一版只需要支持：

```text
读取 pending action_task
发送固定话术
回传执行结果
模拟视频发送
模拟付款链接发送
客户删除时回传 CUSTOMER_DELETED
```

这样两个模块就能拼起来跑完整闭环。
