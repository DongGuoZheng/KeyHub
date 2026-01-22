# KeyHub 数据库设计 - 简化版 ER 图

## 设计理念

**简化设计**：一张 `licenses` 表管理所有授权密钥，支持自定义密钥格式。

---

## 实体关系图 (ER Diagram)

```
┌─────────────────────────────────────────────────────────────┐
│                    KeyHub 简化数据库架构                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│    projects         │
├─────────────────────┤
│ PK id               │◄────┐
│    name (UNIQUE)    │      │
│    description      │      │
│    created_at       │      │
│    is_default       │      │
└─────────────────────┘      │
                             │
                             │ 1:N
                             │
┌─────────────────────┐      │
│     licenses        │      │
├─────────────────────┤      │
│ PK id               │      │
│ FK project_id       │──────┘
│    license_key      │      (UNIQUE(project_id, license_key))
│    is_active        │
│    remarks          │
│    created_at       │
└─────────────────────┘

┌─────────────────────┐
│   admin_users       │      (独立表，不关联)
├─────────────────────┤
│ PK id               │
│    username (UNIQUE)│
│    password         │
│    created_at       │
└─────────────────────┘
```

---

## 表结构详细说明

### 1. projects（项目表）
**用途**：管理不同的产品/项目

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | 项目ID |
| `name` | TEXT | UNIQUE, NOT NULL | 项目名称（唯一） |
| `description` | TEXT | | 项目描述 |
| `created_at` | TEXT | NOT NULL | 创建时间（ISO格式） |
| `is_default` | INTEGER | DEFAULT 0 | 是否为默认项目（0/1） |

**索引**：
- `name` (UNIQUE)

---

### 2. licenses（授权表）
**用途**：统一管理所有类型的授权（替代原来的 keys 表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | 授权ID |
| `project_id` | INTEGER | FOREIGN KEY → projects.id | 关联的项目ID |
| `license_key` | TEXT | NOT NULL | 授权密钥（用于验证，格式：KH-XXXXXXXX-XXXXXXXX 或自定义） |
| `is_active` | INTEGER | DEFAULT 1 | 是否启用（0=禁用，1=启用） |
| `remarks` | TEXT | | 备注信息（如"VIP用户"、"试用版"等） |
| `created_at` | TEXT | NOT NULL | 创建时间（ISO格式） |

**索引**：
- `(project_id, license_key)` (UNIQUE) - **同一项目下密钥唯一**
- `project_id` (INDEX) - 快速查询项目的所有授权
- `license_key` (INDEX) - 验证接口快速查找

**外键约束**：
- `FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE`

**示例数据**：

```json
// 授权密钥示例
{
  "id": 1,
  "project_id": 1,
  "license_key": "KH-A1B2C3D4-E5F6G7H8",
  "is_active": 1,
  "remarks": "VIP用户",
  "created_at": "2024-01-01T10:00:00"
}

// 自定义密钥示例
{
  "id": 2,
  "project_id": 2,
  "license_key": "13800138000",
  "is_active": 1,
  "remarks": "企业授权",
  "created_at": "2024-01-01T10:00:00"
}
```

---

### 3. admin_users（管理员表）
**用途**：后台管理员账户（独立于业务用户）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | 管理员ID |
| `username` | TEXT | UNIQUE, NOT NULL | 管理员用户名 |
| `password` | TEXT | NOT NULL | 管理员密码 |
| `created_at` | TEXT | NOT NULL | 创建时间（ISO格式） |

**索引**：
- `username` (UNIQUE)

---

## 关系说明

### 核心关系

```
projects (1) ──< (N) licenses
```

**详细说明**：
- **projects ↔ licenses**：一对多
  - 一个项目可以有多个授权
  - 一个授权只属于一个项目
- **admin_users**：独立表，不与其他业务表关联

---

## 业务场景示例

### 场景 1：创建授权密钥
**需求**：为项目A创建一个授权密钥

**数据示例**：
```sql
INSERT INTO licenses (project_id, license_key, remarks, created_at)
VALUES (1, 'KH-A1B2C3D4-E5F6G7H8', 'VIP用户', '2024-01-01T10:00:00');
```

**验证逻辑**：
- 客户端调用 `/api/verify`，传入 `key='KH-A1B2C3D4-E5F6G7H8'`
- 服务端查找 `license_key`，检查 `is_active` 状态
- 通过即可

---

### 场景 2：自定义密钥格式
**需求**：项目B使用手机号作为密钥

**数据示例**：
```sql
INSERT INTO licenses (project_id, license_key, remarks, created_at)
VALUES (2, '13800138000', '企业授权', '2024-01-01T10:00:00');
```

**验证逻辑**：
- 客户端调用 `/api/verify`，传入 `key='13800138000'`
- 服务端查找 `license_key`，检查状态
- 通过即可

---

### 场景 3：按项目管理授权
**需求**：查看项目A的所有授权

**SQL查询**：
```sql
SELECT l.*, p.name as project_name
FROM licenses l
JOIN projects p ON l.project_id = p.id
WHERE l.project_id = ?
ORDER BY l.created_at DESC;
```

**结果**：可以看到该项目下的所有授权，每个授权的状态、备注等。

---

## 验证接口简化

### `/api/verify` 接口逻辑

**请求**：
```json
{
  "key": "13800138000"  // 或 "KH-A1B2C3D4-E5F6G7H8"
}
```

**服务端逻辑**：
1. 查找 `license_key = ?`
2. 检查 `is_active = 1`
3. 返回验证结果

**响应**：
```json
{
  "valid": true,
  "message": "验证通过",
  "project_name": "项目A"
}
```

**优势**：
- ✅ 不需要机器绑定，逻辑简单
- ✅ 支持自定义密钥格式（可以是手机号、邮箱、随机字符串等）

---

## 迁移方案

### 从现有 keys 表迁移到 licenses 表

**步骤 1**：创建新表 `licenses`

**步骤 2**：数据迁移脚本

```sql
-- 迁移策略：直接迁移基本字段
INSERT INTO licenses (
    project_id, 
    license_key, 
    is_active, 
    remarks, 
    created_at
)
SELECT 
    project_id,
    key as license_key,
    is_active,
    remarks,
    created_at
FROM keys;
```

**步骤 3**：删除旧表（可选，建议先备份）
```sql
-- 先备份
-- DROP TABLE IF EXISTS keys_backup;
-- CREATE TABLE keys_backup AS SELECT * FROM keys;

-- 删除旧表
-- DROP TABLE IF EXISTS machine_bindings;
-- DROP TABLE IF EXISTS keys;
```

---

## 总结

### 优势
1. ✅ **简单**：只有3张表（projects, licenses, admin_users）
2. ✅ **灵活**：支持自定义密钥格式（可以是手机号、邮箱、随机字符串等）
3. ✅ **项目维度管理**：保持现有的按项目管理授权的能力
4. ✅ **无机器绑定**：验证逻辑更简单，不需要管理机器绑定关系

### 关键设计点
- **`(project_id, license_key)` UNIQUE**：保证同一项目下密钥唯一
- **无机器绑定**：简化验证流程，适合大多数场景
- **自定义密钥格式**：支持任意格式的密钥，包括手机号、邮箱等

### 适用场景
- ✅ 项目需要密钥授权
- ✅ 项目使用手机号作为密钥
- ✅ 项目使用自定义格式的密钥
- ✅ 不需要机器绑定功能
