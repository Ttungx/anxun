#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安巡系统服务启动脚本
自动启动后端API服务器和前端Streamlit应用
"""

import subprocess
import sys
import os
import time
import threading
import requests
from pathlib import Path

def check_service(url, service_name, max_retries=10):
    """检查服务是否启动成功"""
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print(f"✅ {service_name} 启动成功")
                return True
        except:
            pass
        time.sleep(1)
    print(f"❌ {service_name} 启动失败")
    return False

def start_backend():
    """启动后端API服务器"""
    print("🚀 正在启动后端API服务器...")
    backend_dir = Path(__file__).parent / "back"
    
    try:
        # 切换到后端目录并启动API服务器
        process = subprocess.Popen(
            [sys.executable, "api_server.py"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待服务启动
        time.sleep(3)
        
        # 检查服务是否启动成功
        if check_service("http://localhost:5000/api/health", "后端API服务器"):
            return process
        else:
            process.terminate()
            return None
            
    except Exception as e:
        print(f"❌ 启动后端服务失败: {str(e)}")
        return None

def start_frontend():
    """启动前端Streamlit应用"""
    print("🚀 正在启动前端Streamlit应用...")
    frontend_dir = Path(__file__).parent / "front"
    
    try:
        # 启动Streamlit应用
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port=8501"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待服务启动
        time.sleep(5)
        
        # 检查服务是否启动成功
        if check_service("http://localhost:8501", "前端Streamlit应用"):
            return process
        else:
            process.terminate()
            return None
            
    except Exception as e:
        print(f"❌ 启动前端服务失败: {str(e)}")
        return None

def check_ollama():
    """检查Ollama服务状态"""
    print("🔍 检查Ollama服务状态...")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama服务运行正常")
            return True
        else:
            print("❌ Ollama服务异常")
            return False
    except:
        print("❌ Ollama服务未启动，请先启动Ollama")
        print("   提示: 请运行 'ollama serve' 命令启动Ollama服务")
        return False

def main():
    """主函数"""
    print("="*50)
    print("🛡️  安巡 - 校园网络风险感知智能体")
    print("="*50)
    
    # 检查Ollama服务
    if not check_ollama():
        print("\n⚠️  请先启动Ollama服务，然后重新运行此脚本")
        return
    
    # 启动后端服务
    backend_process = start_backend()
    if not backend_process:
        print("\n❌ 后端服务启动失败，程序退出")
        return
    
    # 启动前端服务
    frontend_process = start_frontend()
    if not frontend_process:
        print("\n❌ 前端服务启动失败，正在关闭后端服务...")
        backend_process.terminate()
        return
    
    print("\n" + "="*50)
    print("🎉 所有服务启动成功！")
    print("📱 前端应用: http://localhost:8501")
    print("🔧 后端API: http://localhost:5000")
    print("🤖 Ollama服务: http://localhost:11434")
    print("="*50)
    print("\n💡 提示:")
    print("   - 按 Ctrl+C 停止所有服务")
    print("   - 在浏览器中打开 http://localhost:8501 使用应用")
    print("\n🔄 服务运行中...")
    
    try:
        # 保持程序运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 正在停止所有服务...")
        
        # 停止前端服务
        if frontend_process:
            frontend_process.terminate()
            print("✅ 前端服务已停止")
        
        # 停止后端服务
        if backend_process:
            backend_process.terminate()
            print("✅ 后端服务已停止")
        
        print("\n👋 安巡系统已关闭，感谢使用！")

if __name__ == "__main__":
    main()