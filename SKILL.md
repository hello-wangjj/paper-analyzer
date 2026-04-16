---
name: paper-analyzer
description: 深度分析自动驾驶领域的学术论文（计算机视觉、雷达信号处理），提取论文框架结构、算法逻辑，并生成基于PaddlePaddle 3.2的Python代码实现。当用户上传PDF论文、提供arXiv链接、上传markdown格式论文、粘贴论文内容、或要求分析/实现/解读论文时触发此技能。特别适用于目标检测、跟踪、传感器融合、多目标跟踪、雷达信号处理、深度学习在自动驾驶中的应用等方向。支持多种论文格式：PDF、Markdown（.md）、纯文本、arXiv链接。
---

# Paper Analyzer - 学术论文深度分析与代码实现

## 技能概述

此技能专门用于深度分析自动驾驶领域的学术论文，包括计算机视觉和雷达信号处理方向。它能够：
- 提取论文的完整框架结构
- 梳理算法的核心逻辑和数学原理
- 生成基于PaddlePaddle 3.2的Python代码实现

## 何时使用

**当用户进行以下操作时，触发此技能**：
- 上传PDF格式的学术论文文件
- 提供arXiv论文链接
- 粘贴论文内容要求分析
- 要求"分析这篇论文"、"解读算法"、"实现这个方法"
- 提及"目标检测"、"多目标跟踪"、"传感器融合"、"雷达信号处理"等关键词
- 要求生成PaddlePaddle/飞桨框架的深度学习代码

## 输入处理

### 1. PDF文件处理
如果用户提供PDF文件：
1. 使用PDF提取工具读取文本内容
2. 保留章节结构、公式、图表说明
3. 提取参考文献列表

### 2. arXiv链接处理
如果用户提供arXiv链接：
1. 识别arXiv ID（如 https://arxiv.org/abs/2304.xxxxx → 2304.xxxxx）
2. 下载PDF或获取摘要
3. 按PDF文件流程处理

### 3. Markdown格式论文处理
如果用户提供markdown格式的论文（`.md`文件或粘贴markdown内容）：
1. **章节识别**：识别markdown标题（`#`, `##`, `###`）作为论文结构
2. **公式提取**：识别LaTeX公式（`$...$` 或 `$$...$$` 或 `\\(...\\)`）
3. **图表保留**：保留markdown中的图表标记（`![alt](url)`, `| table |`）
4. **代码块处理**：保留或忽略代码块（根据分析需要）
5. **链接提取**：提取arXiv链接、引用链接等

**Markdown论文特征识别**：
```markdown
# 论文标题                    → 标题
**作者**: [作者列表]          → 作者
**摘要**: [摘要内容]          → Abstract
## 1. Introduction            → 章节结构
## 2. Methodology             → 章节结构
### 2.1 Subsection            → 子章节
公式: $E = mc^2$              → 数学公式
```python
code block
```                           → 代码块
```

### 4. 文本粘贴处理
如果用户直接粘贴论文内容：
1. 识别章节标题（使用Markdown标题格式）
2. 提取数学公式（LaTeX格式）
3. 保留图表说明

## 输出处理

### 输出方式
**重要**：分析结果必须直接写入论文同目录下的markdown文件，**不要在对话窗口流式输出内容**。

### 输出文件命名规则
1. **如果分析PDF文件**：输出文件名为 `[论文标题]_分析_YYYYMMDD.md`
2. **如果分析markdown文件**：输出文件名为 `[原文件名]_分析_YYYYMMDD.md`
3. **如果分析arXiv链接**：输出文件名为 `arXiv_[arXiv_ID]_分析_YYYYMMDD.md`
4. **如果分析粘贴的文本**：输出文件名为 `论文分析_YYYYMMDD.md`

其中 `YYYYMMDD` 为分析日期（如 20260416）。

### 输出路径
输出文件必须保存在**被分析论文的同目录**下：
- PDF论文：PDF文件所在目录
- Markdown论文：Markdown文件所在目录
- arXiv论文：当前工作目录
- 粘贴文本：当前工作目录

### 输出文件结构
输出文件应包含完整的分析结果，按以下顺序组织：
1. **元数据部分**：分析日期、论文信息
2. **框架结构部分**：使用 `<框架结构>` 标签
3. **算法逻辑部分**：使用 `<算法逻辑>` 标签
4. **代码实现部分**：使用 `<代码>` 标签
5. **总结部分**：使用 `## 总结` 标题

### 文件写入流程
1. 完成分析后，**不要在对话中输出完整分析内容**
2. 使用 `Write` 工具将分析结果写入文件
3. 在对话中仅输出简短的完成通知，包含：
   - 分析完成确认
   - 输出文件路径
   - 简要的文件内容概览（2-3句话）
   - 下一步建议

**示例通知**：
```
爸爸，论文分析已完成！✨

📄 输出文件：[完整路径]

分析包含：
- 完整框架结构提取（5个核心模块）
- 详细算法逻辑梳理（含公式推导）
- 可运行的PaddlePaddle代码实现（约XXX行）

代码已可直接运行，使用命令：
```bash
python [输出文件中的代码文件名].py
```
```

## 分析流程

### 第一阶段：框架结构提取

**目标**：建立论文的完整知识图谱

**步骤**：
1. **识别章节结构**
   - Abstract（摘要）
   - Introduction（引言）
   - Related Work（相关工作）
   - Method/Approach（方法）
   - Experiments（实验）
   - Conclusion（结论）
   - References（参考文献）

2. **提取关键信息**
   - 论文标题、作者、发表年份
   - 核心贡献（通常在Introduction和Abstract中）
   - 方法论的核心思想
   - 实验设置和数据集
   - 主要结果和结论

3. **深度分析要素**
   - **数学公式**：提取所有关键公式，解释符号含义
   - **算法流程**：绘制算法的输入-处理-输出流程
   - **网络架构**：如果是深度学习论文，画出模型架构图
   - **实验设计**：分析对比实验、消融实验的设计逻辑
   - **性能指标**：列出评估指标和基准对比结果

**输出格式**：写入文件的 `<框架结构>` 部分
```
<框架结构>
## 论文基本信息
- 标题：[论文标题]
- 作者：[作者列表]
- 发表：[会议/期刊] [年份]
- 领域：[CV/雷达/融合等]

## 章节结构
### 1. Abstract（摘要）
- 核心问题：[论文解决的问题]
- 主要方法：[方法概述]
- 关键结果：[关键结果]

### 2. Introduction（引言）
- 研究背景：[背景说明]
- 现有方法局限：[局限性分析]
- 本文贡献：[列出3-5个核心贡献]

### 3. Related Work（相关工作）
- 主要相关工作：[分类梳理]
- 与本文区别：[对比说明]

### 4. Method（方法）
- 方法概述：[核心思想]
- 技术细节：[详细说明]
- 理论分析：[理论保证]

### 5. Experiments（实验）
- 数据集：[列出数据集]
- 实验设置：[训练细节]
- 对比实验：[与SOTA对比]
- 消融实验：[组件有效性分析]
- 结果分析：[关键发现]

### 6. Conclusion（结论）
- 总结：[主要贡献回顾]
- 局限性：[承认的局限]
- 未来工作：[方向建议]

## 核心公式
- 公式1：[LaTeX格式] - [物理含义]
- 公式2：[LaTeX格式] - [物理含义]
...

## 关键图表
- 图1：[标题] - [说明]
- 表1：[标题] - [说明]
...
</框架结构>
```

### 第二阶段：算法逻辑梳理

**目标**：让用户完全理解算法如何工作

**步骤**：
1. **明确问题定义**
   - 输入：数据格式、维度、预处理
   - 输出：目标格式、后处理
   - 约束：计算复杂度、实时性要求

2. **拆解算法步骤**
   - 将算法分解为多个模块/步骤
   - 说明每个步骤的输入输出
   - 解释步骤间的数据流动

3. **核心思想解读**
   - 算法的创新点在哪里
   - 为什么这样设计有效
   - 理论或直觉上的解释

4. **数学原理**
   - 关键公式的推导过程
   - 损失函数的设计思路
   - 优化方法的选择理由

**输出格式**：写入文件的 `<算法逻辑>` 部分
```
<算法逻辑>
## 问题定义
### 输入
- 数据类型：[图像/点云/序列等]
- 数据维度：[具体维度]
- 预处理：[归一化/裁剪等]

### 输出
- 输出类型：[分类/检测/跟踪等]
- 输出格式：[具体格式]
- 后处理：[NMS/聚类等]

### 约束条件
- 实时性：[帧率要求]
- 精度：[精度指标]
- 资源：[内存/计算限制]

## 算法流程
### 概览
[算法的整体流程图描述]

### 详细步骤

#### 步骤1：[步骤名称]
**输入**：[数据格式]
**处理**：
- 子步骤1.1：[详细说明]
- 子步骤1.2：[详细说明]
**输出**：[数据格式]
**核心思想**：[为什么这样做]

#### 步骤2：[步骤名称]
**输入**：[来自步骤1的输出]
**处理**：[详细说明]
**输出**：[数据格式]
**核心思想**：[为什么这样做]

[继续所有步骤...]

## 核心贡献与创新
### 贡献1：[贡献名称]
**内容**：[详细说明]
**创新点**：[与现有方法的区别]
**有效性**：[理论分析或实验验证]

### 贡献2：[贡献名称]
[同上结构]

[列出所有贡献...]

## 数学原理
### 关键公式推导
**公式**：[LaTeX格式]

**符号说明**：
- [符号1]：[含义]
- [符号2]：[含义]

**推导过程**：
1. [推导步骤1]
2. [推导步骤2]
3. [最终得到]

**物理/几何意义**：[直观解释]

### 损失函数设计
**总损失**：[LaTeX格式]

**各项含义**：
- [损失项1]：[作用]
- [损失项2]：[作用]

**设计思路**：[为什么这样设计]

## 复杂度分析
- 时间复杂度：[O(·)表示]
- 空间复杂度：[O(·)表示]
- 优化策略：[加速方法]
</算法逻辑>
```

### 第三阶段：代码实现

**目标**：生成可运行的高质量PaddlePaddle代码

**代码生成原则**：
1. **灵活处理**：根据算法复杂度选择实现深度
   - 简单算法：完整实现
   - 复杂算法：核心模块 + 接口定义
   - 超大算法：关键组件 + 实现指导

2. **代码质量**：
   - 完整的类型注解
   - 详细的文档字符串
   - 清晰的变量命名
   - 模块化设计

3. **PaddlePaddle规范**：
   - 使用PaddlePaddle 3.2 API
   - 遵循飞桨官方代码风格
   - 使用paddle.nn、paddle.optimizer等模块

**代码结构**：
```python
# ... [代码模板] ...
```

**特殊情况处理**：

**情况1：论文算法过于复杂**
- 实现核心模块
- 提供完整接口定义
- 给出实现指导和伪代码

**情况2：依赖未开源的预训练模型**
- 定义模型结构
- 提供权重加载接口
- 给出训练指导

**情况3：涉及多模态/传感器融合**
- 实现各模态的编码器
- 实现融合模块
- 提供数据格式转换工具

**输出格式**：写入文件的 `<代码>` 部分
```
<代码>
"""
[论文标题] - PaddlePaddle 3.2实现

本代码实现了论文[论文标题]中提出的[方法名称]。
论文链接：[arXiv/项目链接]

环境要求：
- Python 3.12.10
- PaddlePaddle 3.2
- Windows 11

作者：[您的名字]
日期：2026-04-16
"""

# ============================================================================
# 1. 导入和配置
# ============================================================================

import paddle
import paddle.nn as nn
import paddle.optimizer as optim
from paddle.io import Dataset, DataLoader
import numpy as np
from typing import Tuple, Dict, List, Optional

# 设置随机种子
paddle.seed(42)

# ============================================================================
# 2. 数据加载模块
# ============================================================================

class [DatasetName](Dataset):
    """
    [数据集名称]数据集类

    Args:
        data_path: 数据路径
        transform: 数据变换
    """

    def __init__(self, data_path: str, transform=None):
        self.data_path = data_path
        self.transform = transform
        # 加载数据
        self.data = self._load_data()

    def _load_data(self) -> List:
        """加载数据"""
        # 实现数据加载逻辑
        pass

    def __getitem__(self, idx: int) -> Tuple:
        """
        获取单个样本

        Returns:
            (data, label) 数据和标签
        """
        sample = self.data[idx]
        if self.transform:
            sample = self.transform(sample)
        return sample

    def __len__(self) -> int:
        """返回数据集大小"""
        return len(self.data)

# ============================================================================
# 3. 模型定义
# ============================================================================

class [ModelName](nn.Layer):
    """
    [模型名称] - [论文中的方法]

    论文中的核心创新点：
    1. [创新点1]
    2. [创新点2]

    Args:
        input_dim: 输入维度
        hidden_dim: 隐藏层维度
        output_dim: 输出维度
    """

    def __init__(self,
                 input_dim: int,
                 hidden_dim: int,
                 output_dim: int):
        super([ModelName], self).__init__()

        # 定义网络层
        self.layer1 = nn.Linear(input_dim, hidden_dim)
        self.layer2 = nn.Linear(hidden_dim, output_dim)

        # [其他层...]

    def forward(self, x: paddle.Tensor) -> paddle.Tensor:
        """
        前向传播

        Args:
            x: 输入tensor，shape=[batch_size, input_dim]

        Returns:
            output: 输出tensor，shape=[batch_size, output_dim]
        """
        # 实现前向传播逻辑
        x = self.layer1(x)
        x = paddle.nn.functional.relu(x)
        x = self.layer2(x)
        return x

# ============================================================================
# 4. 损失函数
# ============================================================================

def [loss_name](pred: paddle.Tensor,
                target: paddle.Tensor,
                [其他参数]) -> paddle.Tensor:
    """
    [损失函数名称] - 论文公式[X]

    论文中的公式：
    L = [LaTeX格式]

    Args:
        pred: 预测值
        target: 目标值
        [其他参数]

    Returns:
        loss: 损失值
    """
    # 实现损失函数
    loss = paddle.nn.functional.mse_loss(pred, target)
    return loss

# ============================================================================
# 5. 训练和评估
# ============================================================================

def train(model: nn.Layer,
          train_loader: DataLoader,
          optimizer: optim.Optimizer,
          epoch: int) -> float:
    """
    训练一个epoch

    Args:
        model: 模型
        train_loader: 训练数据加载器
        optimizer: 优化器
        epoch: 当前epoch

    Returns:
        avg_loss: 平均损失
    """
    model.train()
    total_loss = 0
    for batch_idx, (data, target) in enumerate(train_loader):
        # 前向传播
        output = model(data)
        loss = [loss_name](output, target)

        # 反向传播
        loss.backward()
        optimizer.step()
        optimizer.clear_grad()

        total_loss += loss.numpy()[0]

    avg_loss = total_loss / len(train_loader)
    return avg_loss

def evaluate(model: nn.Layer,
             test_loader: DataLoader) -> Dict[str, float]:
    """
    评估模型

    Args:
        model: 模型
        test_loader: 测试数据加载器

    Returns:
        metrics: 评估指标字典
    """
    model.eval()
    total_loss = 0
    correct = 0

    with paddle.no_grad():
        for data, target in test_loader:
            output = model(data)
            loss = [loss_name](output, target)
            total_loss += loss.numpy()[0]

            # 计算准确率
            pred = output.argmax(axis=1, keepdim=True)
            correct += (pred == target).sum().numpy()[0]

    avg_loss = total_loss / len(test_loader)
    accuracy = correct / len(test_loader.dataset)

    return {
        'loss': avg_loss,
        'accuracy': accuracy
    }

# ============================================================================
# 6. 主程序
# ============================================================================

def main():
    """主函数"""
    # 1. 准备数据
    train_dataset = [DatasetName]('data/train')
    test_dataset = [DatasetName]('data/test')

    train_loader = DataLoader(
        train_dataset,
        batch_size=32,
        shuffle=True
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=32,
        shuffle=False
    )

    # 2. 创建模型
    model = [ModelName](
        input_dim=[维度],
        hidden_dim=[维度],
        output_dim=[维度]
    )

    # 3. 创建优化器
    optimizer = optim.Adam(
        parameters=model.parameters(),
        learning_rate=0.001
    )

    # 4. 训练模型
    num_epochs = 100
    for epoch in range(1, num_epochs + 1):
        train_loss = train(model, train_loader, optimizer, epoch)
        metrics = evaluate(model, test_loader)

        print(f'Epoch {epoch}: '
              f'Train Loss: {train_loss:.4f}, '
              f'Test Loss: {metrics["loss"]:.4f}, '
              f'Accuracy: {metrics["accuracy"]:.4f}')

    # 5. 保存模型
    paddle.save(model.state_dict(), 'model.pdparams')

if __name__ == '__main__':
    main()
</代码>
```

## 领域特定指导

### 计算机视觉论文
- **重点**：网络架构设计、特征提取、检测/分割头
- **代码模块**：数据增强、backbone、neck、head
- **评估指标**：mAP、IoU、FPS等

### 雷达信号处理论文
- **重点**：信号处理流程、点云生成、跟踪算法
- **代码模块**：雷达仿真、CFAR检测、聚类、卡尔曼滤波
- **评估指标**：检测率、虚警率、跟踪精度等

### 传感器融合论文
- **重点**：多模态数据对齐、融合策略
- **代码模块**：数据同步、特征融合、决策融合
- **评估指标**：融合精度提升、鲁棒性等

## 输出总结

在完成分析后，给出一个简洁的总结：

```
## 总结

本文提出了[方法名称]，用于解决[问题]。

**核心创新**：
1. [创新点1]
2. [创新点2]

**实现要点**：
- 数据格式：[说明]
- 关键模块：[说明]
- 训练技巧：[说明]

**代码可用性**：
- 完整度：[完整/核心模块/接口定义]
- 依赖：[PaddlePaddle版本、其他库]
- 运行环境：[Windows 11/Python 3.12.10]

**下一步建议**：
- [改进建议1]
- [实验建议2]
```

## 注意事项

1. **输出方式**：分析结果必须写入文件，不要在对话窗口流式输出完整内容
2. **准确性优先**：如果论文内容不清楚，明确说明而不是猜测
3. **代码实用性**：生成的代码应该能直接运行或易于修改
4. **教学性**：代码注释应该详细，帮助用户理解实现
5. **PaddlePaddle版本**：严格使用PaddlePaddle 3.2 API，不要使用过时API
6. **Windows兼容**：确保代码路径、多进程等在Windows 11上正常工作
7. **文件编码**：输出markdown文件使用UTF-8编码
8. **代码分离**：如果代码部分超过1000行，考虑将代码保存为单独的 `.py` 文件，在分析文件中引用

## 大型论文处理

### Token限制处理
如果论文文件超过token限制（如UniAD论文30772 tokens），采用以下策略：

1. **分段读取**：使用 `Read` 工具的 `offset` 和 `limit` 参数分批读取
2. **多次提取**：对关键部分（Method、Experiments）重点读取
3. **结构优先**：优先读取Abstract、Introduction、Method章节
4. **代码提取**：如果代码部分很长，保存为独立 `.py` 文件

### 输出文件组织
对于大型论文（>20000 tokens），采用多文件组织：
```
[论文标题]_分析_YYYYMMDD.md  - 主分析文件
├── 包含：框架结构、算法逻辑、总结
└── 引用：[论文标题]_代码_YYYYMMDD.py  - 完整代码实现
```

在主分析文件中添加代码引用：
```markdown
## 代码实现

完整代码实现已保存至独立文件：
`[论文标题]_代码_YYYYMMDD.py`

包含以下模块：
- [模块列表]

运行方式：
```bash
python [论文标题]_代码_YYYYMMDD.py
```
```

## 代码文件生成

### 何时分离代码文件
当满足以下任一条件时，将代码保存为独立的 `.py` 文件：
1. 代码超过1000行
2. 代码包含多个复杂模块（>5个类）
3. 分析文件总大小超过50000字符

### 代码文件命名
- 文件名：`[论文标题]_代码_YYYYMMDD.py`
- 路径：与论文分析文件相同目录
- 编码：UTF-8

### 代码文件结构
```python
"""
[论文标题] - PaddlePaddle 3.2实现

本代码实现了论文[论文标题]中提出的[方法名称]。
论文链接：[arXiv/项目链接]
分析文档：[对应的markdown分析文件名]

环境要求：
- Python 3.12.10
- PaddlePaddle 3.2
- Windows 11

作者：Claude Sonnet
日期：YYYY-MM-DD
"""

# ... 完整代码实现 ...
```
