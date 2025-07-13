from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import os
import tempfile
import json
from datetime import datetime
from traffic_analyzer import TrafficAnalyzer
import requests
from typing import Dict, List, Any
import threading
import time
import functools

# 性能监控装饰器
def performance_monitor(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        if execution_time > 2.0:  # 记录超过2秒的慢查询
            print(f"[SLOW] {func.__name__} took {execution_time:.2f}s")
        elif execution_time > 1.0:
            print(f"[INFO] {func.__name__} took {execution_time:.2f}s")
        
        return result
    return wrapper

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 初始化流量分析器
analyzer = TrafficAnalyzer()

# 存储对话历史的字典（简单实现，生产环境应使用数据库）
chat_sessions = {}

class ChatMemory:
    """聊天记忆管理"""
    def __init__(self, max_history=10):  # 增加历史记录到10轮
        self.max_history = max_history
        self.sessions = {}
    
    def get_session(self, session_id="default"):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        return self.sessions[session_id]
    
    def add_message(self, session_id, role, content):
        session = self.get_session(session_id)
        session.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        
        # 保持历史记录在限制范围内
        if len(session) > self.max_history * 2:  # *2 因为有用户和助手消息
            session = session[-self.max_history * 2:]
            self.sessions[session_id] = session
    
    def get_context(self, session_id, include_system_prompt=True):
        session = self.get_session(session_id)
        messages = []
        
        if include_system_prompt:
            messages.append({
                "role": "system",
                "content": "你是安巡智能体，一个专业的校园网络安全助手。你能够分析网络流量、识别安全威胁、提供安全建议。\n\n请在回答时遵循以下格式：\n1. 使用<think>在这里展示你的思考过程和分析步骤</think>标签\n2. 然后给出简洁明确的回答\n3. 用专业但易懂的语言解释技术概念\n\n示例：\n<think>用户询问网络安全问题，我需要分析具体的威胁类型，考虑防护措施...</think>\n\n根据你的描述，这可能是..."
            })
        
        # 添加历史对话
        for msg in session:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        return messages

# 初始化聊天记忆
chat_memory = ChatMemory()

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/chat', methods=['POST'])
@performance_monitor
def chat_with_ai():
    """与AI对话接口（支持记忆功能）"""
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        model = data.get('model', 'qwen2.5:7b')
        
        if not message:
            return jsonify({"error": "消息内容不能为空"}), 400
        
        # 添加用户消息到记忆
        chat_memory.add_message(session_id, "user", message)
        
        # 获取带上下文的消息
        messages = chat_memory.get_context(session_id)
        
        # 调用Ollama API
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": "qwen3:8b" if model == "qwen2.5:7b" else model,
            "messages": messages,
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=60)
        
        if response.status_code == 200:
            ai_response = response.json().get('message', {}).get('content', '抱歉，无法获取回复')
            
            # 添加AI回复到记忆
            chat_memory.add_message(session_id, "assistant", ai_response)
            
            return jsonify({
                "response": ai_response,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": f"AI服务调用失败，状态码: {response.status_code}"}), 500
            
    except Exception as e:
        return jsonify({"error": f"处理请求时发生错误: {str(e)}"}), 500

@app.route('/api/chat/stream', methods=['POST'])
@performance_monitor
def chat_with_ai_stream():
    """与AI对话接口（流式响应）"""
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        model = data.get('model', 'qwen2.5:7b')
        
        if not message:
            return jsonify({"error": "消息内容不能为空"}), 400
        
        # 添加用户消息到记忆
        chat_memory.add_message(session_id, "user", message)
        
        # 获取带上下文的消息
        messages = chat_memory.get_context(session_id)
        
        def generate_stream():
            try:
                # 调用Ollama API（流式）
                url = "http://localhost:11434/api/chat"
                payload = {
                    "model": "qwen3:8b" if model == "qwen2.5:7b" else model,
                    "messages": messages,
                    "stream": True
                }
                
                response = requests.post(url, json=payload, stream=True, timeout=60)
                
                if response.status_code == 200:
                    full_response = ""
                    
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk_data = json.loads(line.decode('utf-8'))
                                if 'message' in chunk_data and 'content' in chunk_data['message']:
                                    content = chunk_data['message']['content']
                                    full_response += content
                                    
                                    # 发送流式数据
                                    yield f"data: {json.dumps({'content': content, 'session_id': session_id})}\n\n"
                                
                                # 检查是否完成
                                if chunk_data.get('done', False):
                                    # 添加完整回复到记忆
                                    chat_memory.add_message(session_id, "assistant", full_response)
                                    yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'timestamp': datetime.now().isoformat()})}\n\n"
                                    break
                                    
                            except json.JSONDecodeError:
                                continue
                else:
                    yield f"data: {json.dumps({'error': f'AI服务调用失败，状态码: {response.status_code}'})}\n\n"
                    
            except Exception as e:
                yield f"data: {json.dumps({'error': f'处理请求时发生错误: {str(e)}'})}\n\n"
        
        return Response(
            generate_stream(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )
        
    except Exception as e:
        return jsonify({"error": f"处理请求时发生错误: {str(e)}"}), 500

@app.route('/api/analyze_pcap', methods=['POST'])
@performance_monitor
def analyze_pcap():
    """分析上传的pcap文件"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "没有上传文件"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "文件名为空"}), 400
        
        # 获取思考开关参数
        enable_thinking = request.form.get('enable_thinking', 'true').lower() == 'true'
        
        # 检查文件扩展名
        allowed_extensions = {'.pcap', '.pcapng', '.cap'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({"error": "不支持的文件格式，请上传pcap、pcapng或cap文件"}), 400
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            file.save(tmp_file.name)
            tmp_file_path = tmp_file.name
        
        try:
            # 分析文件
            result = analyzer.process_pcap_file(tmp_file_path, enable_thinking=enable_thinking)
            
            # 清理临时文件
            os.unlink(tmp_file_path)
            
            return jsonify({
                "success": True,
                "filename": file.filename,
                "analysis_result": result,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            # 确保清理临时文件
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
            raise e
            
    except Exception as e:
        return jsonify({"error": f"分析文件时发生错误: {str(e)}"}), 500

@app.route('/api/capture_traffic', methods=['POST'])
@performance_monitor
def capture_traffic():
    """实时捕获网络流量"""
    try:
        data = request.json or {}
        duration = data.get('duration', 30)
        interface = data.get('interface', 'any')
        packet_count = data.get('packet_count', 50)
        
        # 验证参数
        if duration > 300:  # 最大5分钟
            return jsonify({"error": "捕获时长不能超过300秒"}), 400
        
        if packet_count > 100:  # 最大100个包
            return jsonify({"error": "包数量不能超过100"}), 400
        
        # 在后台线程中执行捕获
        def capture_in_background():
            try:
                captured_data = analyzer.capture_live_traffic(
                    interface=interface, 
                    duration=duration, 
                    packet_count=packet_count
                )
                return captured_data
            except Exception as e:
                print(f"[ERROR] Background capture failed: {str(e)}")
                return []
        
        # 启动捕获
        captured_data = capture_in_background()
        
        return jsonify({
            "success": True,
            "captured_packets": len(captured_data),
            "data": captured_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": f"捕获流量时发生错误: {str(e)}"}), 500

@app.route('/api/get_analysis_history', methods=['GET'])
def get_analysis_history():
    """获取分析历史记录"""
    try:
        # 获取分析结果目录中的文件
        results_dir = os.path.join(analyzer.data_dir, 'analysis_results')
        ai_dir = os.path.join(analyzer.data_dir, 'ai_responses')
        
        history = []
        
        # 读取分析结果文件
        if os.path.exists(results_dir):
            for filename in os.listdir(results_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(results_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            history.append({
                                "type": "analysis",
                                "filename": filename,
                                "timestamp": data.get('timestamp', ''),
                                "packet_count": data.get('packet_count', 0),
                                "source_file": data.get('source_file', '')
                            })
                    except Exception as e:
                        print(f"[WARNING] Error reading {filepath}: {str(e)}")
        
        # 按时间戳排序
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            "success": True,
            "history": history[:20],  # 返回最近20条记录
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": f"获取历史记录时发生错误: {str(e)}"}), 500

@app.route('/api/get_chat_history', methods=['GET'])
def get_chat_history():
    """获取聊天历史"""
    try:
        session_id = request.args.get('session_id', 'default')
        session = chat_memory.get_session(session_id)
        
        return jsonify({
            "success": True,
            "chat_history": session,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": f"获取聊天历史时发生错误: {str(e)}"}), 500

@app.route('/api/clear_chat_history', methods=['POST'])
def clear_chat_history():
    """清空聊天历史"""
    try:
        data = request.json or {}
        session_id = data.get('session_id', 'default')
        
        if session_id in chat_memory.sessions:
            chat_memory.sessions[session_id] = []
        
        return jsonify({
            "success": True,
            "message": "聊天历史已清空",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": f"清空聊天历史时发生错误: {str(e)}"}), 500

@app.route('/api/get_network_interfaces', methods=['GET'])
def get_network_interfaces():
    """获取可用的网络接口列表"""
    try:
        interfaces = analyzer.get_network_interfaces()
        
        return jsonify({
            "success": True,
            "interfaces": interfaces,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": f"获取网络接口时发生错误: {str(e)}"}), 500

@app.route('/api/system_status', methods=['GET'])
def system_status():
    """获取系统状态"""
    try:
        # 检查Ollama服务状态
        ollama_status = "unknown"
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            ollama_status = "running" if response.status_code == 200 else "error"
        except:
            ollama_status = "offline"
        
        # 检查数据目录状态
        data_dir_status = "ok" if os.path.exists(analyzer.data_dir) else "error"
        
        return jsonify({
            "success": True,
            "ollama_service": ollama_status,
            "data_directory": data_dir_status,
            "active_sessions": len(chat_memory.sessions),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": f"获取系统状态时发生错误: {str(e)}"}), 500

if __name__ == '__main__':
    print("[INFO] Starting API Server...")
    print("[INFO] Available endpoints:")
    print("  - POST /api/chat - 与AI对话")
    print("  - POST /api/chat/stream - 与AI对话（流式响应）")
    print("  - POST /api/analyze_pcap - 分析pcap文件")
    print("  - POST /api/capture_traffic - 实时捕获流量")
    print("  - GET /api/get_network_interfaces - 获取网络接口列表")
    print("  - GET /api/get_analysis_history - 获取分析历史")
    print("  - GET /api/get_chat_history - 获取聊天历史")
    print("  - POST /api/clear_chat_history - 清空聊天历史")
    print("  - GET /api/system_status - 获取系统状态")
    print("  - GET /api/health - 健康检查")
    
    app.run(host='0.0.0.0', port=5000, debug=True)