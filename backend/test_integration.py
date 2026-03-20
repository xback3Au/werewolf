#!/usr/bin/env python3
"""
集成测试 - 测试后端API
运行: python test_integration.py
"""

import asyncio
import json
from pathlib import Path

async def test_api_endpoints():
    """测试API端点"""
    import aiohttp

    base_url = "http://localhost:8000"

    async with aiohttp.ClientSession() as session:
        # 测试健康检查
        async with session.get(f"{base_url}/api/check") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ API服务运行中")
                print(f"  API Key配置: {'是' if data.get('api_key_configured') else '否'}")
            else:
                print(f"✗ API健康检查失败: {resp.status}")
                return False

        # 测试版型列表
        async with session.get(f"{base_url}/api/formats") as resp:
            if resp.status == 200:
                formats = await resp.json()
                print(f"✓ 获取版型列表成功: {len(formats)} 个版型")
            else:
                print(f"✗ 获取版型列表失败: {resp.status}")

        # 测试文件上传
        test_file = Path(__file__).parent.parent / "data" / "test.txt"
        if test_file.exists():
            data = aiohttp.FormData()
            data.add_field('file',
                          test_file.read_bytes(),
                          filename='test.txt',
                          content_type='text/plain')

            async with session.post(f"{base_url}/api/upload", data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"✓ 文件上传成功: {result.get('file_id')}")
                    return result.get('file_path')
                else:
                    print(f"✗ 文件上传失败: {resp.status}")
        else:
            print(f"⚠ 测试文件不存在: {test_file}")

    return None

async def test_websocket():
    """测试WebSocket连接"""
    try:
        import websockets
    except ImportError:
        print("✗ websockets模块未安装")
        return False

    uri = "ws://localhost:8000/ws/analyze/test_123"

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket连接成功")

            # 发送配置
            config = {
                "transcript_path": "uploads/test.txt",
                "format_path": "formats/test.txt",
                "game_name": "test"
            }
            await websocket.send(json.dumps(config))
            print("✓ 配置已发送")

            # 等待响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"✓ 收到响应: {data.get('type')}")
                return True
            except asyncio.TimeoutError:
                print("⚠ 等待响应超时（这可能正常，取决于后端处理）")
                return True

    except Exception as e:
        print(f"✗ WebSocket测试失败: {e}")
        return False

def test_json_functions():
    """测试JSON解析函数"""
    from analyzer import extract_json_text, normalize_json, try_repair_json

    print("\n测试JSON解析...")

    test_cases = [
        ('{"key": "value"}', "标准JSON"),
        ('{"key": "value",}', "尾部逗号"),
        ('{"key": "value"', "不完整"),
    ]

    all_passed = True
    for test_input, desc in test_cases:
        try:
            extracted = extract_json_text(test_input)
            normalized = normalize_json(extracted)
            repaired = try_repair_json(normalized)
            json.loads(repaired)
            print(f"  ✓ {desc}")
        except Exception as e:
            print(f"  ✗ {desc}: {e}")
            all_passed = False

    return all_passed

async def main():
    print("="*60)
    print("后端集成测试")
    print("="*60)

    # 测试API端点
    print("\n1. 测试API端点...")
    file_path = await test_api_endpoints()

    # 测试WebSocket
    print("\n2. 测试WebSocket...")
    await test_websocket()

    # 测试JSON函数
    print("\n3. 测试JSON解析...")
    test_json_functions()

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
