"""
JSON解析器测试
运行: python test_json_parser.py
"""

import json
from analyzer import extract_json_text, normalize_json, try_repair_json

# 测试用例 - 模拟模型可能输出的各种格式
test_cases = [
    # 正常情况
    ('{"key": "value"}', True, "标准JSON"),

    # Markdown代码块
    ('```json\n{"key": "value"}\n```', True, "Markdown代码块"),

    # 嵌入其他文本
    ('Here is the result: {"key": "value"} Thank you!', True, "嵌入文本"),

    # 尾部逗号问题（常见错误）
    ('{"a": 1, "b": 2,}', True, "对象尾部逗号"),
    ('[1, 2, 3,]', True, "数组尾部逗号"),

    # 不完整JSON
    ('{"a": 1, "b": 2', True, "缺少闭合括号"),
    ('[1, 2, 3', True, "缺少闭合中括号"),

    # 布尔值格式错误
    ('{"flag": True}', True, "Python布尔值"),
    ('{"flag": False}', True, "Python布尔值"),
    ('{"value": None}', True, "Python None"),

    # 中文引号
    ('{"key": "value"}', True, "中文引号"),  # 注意：这里应该是中文引号

    # 复杂嵌套
    ('''{
        "players": {
            "1": {"role": "werewolf",}
        },
        "events": [1, 2, 3,],
    }''', True, "复杂嵌套带逗号"),

    # 多层不完整
    ('{"a": {"b": {"c": 1', True, "多层嵌套不完整"),
]

print("="*60)
print("JSON解析器测试")
print("="*60)

passed = 0
failed = 0

for test_input, should_pass, description in test_cases:
    try:
        # 处理中文引号
        test_input = test_input.replace('"', '"').replace('"', '"')

        extracted = extract_json_text(test_input)
        normalized = normalize_json(extracted)
        repaired = try_repair_json(normalized)
        parsed = json.loads(repaired)

        if should_pass:
            print(f"✓ {description}: 解析成功")
            passed += 1
        else:
            print(f"✗ {description}: 应该失败但成功了")
            failed += 1

    except Exception as e:
        if should_pass:
            print(f"✗ {description}: 解析失败 - {e}")
            print(f"   输入: {test_input[:50]}...")
            print(f"   提取: {extracted[:50] if 'extracted' in locals() else 'N/A'}...")
            print(f"   修复: {repaired[:50] if 'repaired' in locals() else 'N/A'}...")
            failed += 1
        else:
            print(f"✓ {description}: 正确失败")
            passed += 1

print("="*60)
print(f"结果: {passed} 通过, {failed} 失败")
print("="*60)

if failed > 0:
    print("\n建议:")
    print("1. 检查normalize_json函数是否处理了所有边界情况")
    print("2. 考虑使用json5库作为后备解析器")
    print("3. 在prompt中强调模型输出合法JSON")
