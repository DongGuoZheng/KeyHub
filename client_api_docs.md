# KeyHub 客户端 API 文档

本文档详细介绍了如何集成 KeyHub 授权验证接口。

## 验证接口 (Verify API)

用于验证客户端授权 Key 并绑定当前机器。

### 接口信息
- **地址**: `POST /api/verify`
- **数据格式**: `application/json`

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `key` | String | 是 | 授权密钥 (格式: `KH-XXXXXXXX-XXXXXXXX`) |
| `machine_id` | String | 是 | 机器硬件指纹/唯一标识符(客户端生成) |

### 请求示例 (JSON)
```json
{
    "key": "KH-A1B2C3D4-E5F6G7H8",
    "machine_id": "CPU-8888-9999-UUID"
}
```

### 返回参数说明

返回 JSON 格式数据：

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `valid` | Boolean | 验证是否通过 (`true` 表示授权有效，`false` 表示授权无效) |
| `message` | String | 提示信息 (中文) |

### 响应示例

#### 1. 验证成功 (新绑定)
状态码: `200 OK`
```json
{
    "valid": true,
    "message": "验证通过 (新绑定已创建)"
}
```

#### 2. 验证成功 (已绑定机器)
状态码: `200 OK`
```json
{
    "valid": true,
    "message": "验证通过 (已绑定)"
}
```

#### 3. 验证失败 (密钥不存在)
状态码: `404 Not Found`
```json
{
    "valid": false,
    "message": "未找到密钥"
}
```

#### 4. 验证失败 (密钥被禁用)
状态码: `403 Forbidden`
```json
{
    "valid": false,
    "message": "密钥已禁用"
}
```

## 集成建议

1. **机器码获取**: 建议使用 CPU ID 或 主板序列号生成的哈希值作为 `machine_id`。
2. **频率控制**: 验证请求不宜过于频繁，建议在程序启动时验证一次，之后每隔数小时在后台静默验证。
3. **超时处理**: 客户端应处理网络超时或服务器宕机的情况，建议在这种情况下设置一定的宽限期。
