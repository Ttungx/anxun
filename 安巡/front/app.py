import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pyshark
import threading
import time
import os
from datetime import datetime
import base64

# 页面配置
st.set_page_config(
    page_title="安巡 - 校园网络风险感知智能体",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 强制设置为浅色主题
st.markdown("""
<style>
    /* 强制浅色主题 */
    .stApp {
        color-scheme: light !important;
        background-color: #ffffff !important;
    }
    [data-testid="stSidebar"] {
        background-color: #f8f9fa !important;
    }
    .main .block-container {
        background-color: #ffffff !important;
    }
    /* 覆盖所有可能的深色主题设置 */
    .stApp > header {
        background-color: transparent !important;
    }
    .stApp [data-testid="stHeader"] {
        background-color: transparent !important;
    }
    /* 确保文本颜色为深色 */
    .stApp, .stApp * {
        color: #262730 !important;
    }
    /* 输入框样式 */
    .stTextInput > div > div > input {
        background-color: #ffffff !important;
        color: #262730 !important;
    }
    /* 选择框样式 */
    .stSelectbox > div > div > div {
        background-color: #ffffff !important;
        color: #262730 !important;
    }
</style>
""", unsafe_allow_html=True)

# 初始化session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = "智能对话"  # 默认进入对话页面
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'capture_status' not in st.session_state:
    st.session_state.capture_status = False
if 'page_data_cache' not in st.session_state:
    st.session_state.page_data_cache = {}
if 'last_status_check' not in st.session_state:
    st.session_state.last_status_check = 0
# 思考模式状态记忆
if 'enable_thinking_chat' not in st.session_state:
    st.session_state.enable_thinking_chat = False  # 默认关闭思考模式
if 'enable_thinking_traffic' not in st.session_state:
    st.session_state.enable_thinking_traffic = False  # 默认关闭思考模式

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        padding: 1rem;
        background: linear-gradient(90deg, #f0f8ff, #e6f3ff);
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
    }
    .feature-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
        border-left: 4px solid #1f77b4;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .assistant-message {
        background-color: #f1f8e9;
        border-left: 4px solid #4caf50;
    }
    .stButton > button {
        background-color: #1f77b4;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #1565c0;
    }
    .sidebar .stButton > button {
        width: 100%;
        margin: 0.5rem 0;
        padding: 0.75rem 1rem;
        border-radius: 12px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        background: linear-gradient(135deg, #1f77b4, #42a5f5);
        color: white;
        border: none;
        box-shadow: 0 2px 6px rgba(31, 119, 180, 0.3);
    }
    .sidebar .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(31, 119, 180, 0.4);
        background: linear-gradient(135deg, #1565c0, #1976d2);
    }
    .sidebar .stButton > button:active {
        transform: translateY(0px);
        box-shadow: 0 2px 4px rgba(31, 119, 180, 0.3);
    }
</style>
""", unsafe_allow_html=True)

if 'captured_packets' not in st.session_state:
    st.session_state.captured_packets = []

# 处理AI响应的函数
def process_ai_response(response_text, enable_thinking=True):
    """处理AI响应，根据思考模式设置决定是否显示思考标签"""
    if not enable_thinking and response_text:
        # 移除<think></think>标签及其内容
        import re
        # 匹配<think>...</think>标签（支持多行）
        pattern = r'<think>.*?</think>'
        cleaned_response = re.sub(pattern, '', response_text, flags=re.DOTALL)
        # 清理多余的空行
        cleaned_response = re.sub(r'\n\s*\n', '\n\n', cleaned_response.strip())
        return cleaned_response
    return response_text

# 状态检查函数
def check_backend_status():
    """检查后端服务状态"""
    try:
        response = requests.get("http://localhost:5000/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def check_ollama_status():
    """检查Ollama服务状态"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

# 缓存状态检查结果（增加缓存时间到120秒）
@st.cache_data(ttl=120, show_spinner=False)
def get_cached_status():
    """获取缓存的状态检查结果"""
    import concurrent.futures
    
    def check_backend():
        try:
            response = requests.get("http://localhost:5000/api/health", timeout=1)
            return response.status_code == 200
        except:
            return False
    
    def check_ollama():
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=1)
            return response.status_code == 200
        except:
            return False
    
    # 并行检查状态以提高速度
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            backend_future = executor.submit(check_backend)
            ollama_future = executor.submit(check_ollama)
            
            backend_status = backend_future.result(timeout=2)
            ollama_status = ollama_future.result(timeout=2)
    except:
        backend_status, ollama_status = False, False
    
    return backend_status, ollama_status

# 左上角项目名
st.markdown("""
<div style="
    position: fixed;
    top: 60px;
    left: 20px;
    z-index: 999;
    background: rgba(255,255,255,0.95);
    padding: 8px 15px;
    border-radius: 20px;
    font-weight: bold;
    color: #1f77b4;
    font-size: 1.1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    border: 1px solid #e0e0e0;
">
🛡️ 安巡
</div>
""", unsafe_allow_html=True)

# 侧边栏导航
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #1f77b4; margin: 0;">🛡️ 安巡</h2>
        <p style="color: #666; font-size: 14px; margin: 5px 0;">校园网络风险感知智能体</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 导航菜单
    st.markdown("### 📋 功能导航")
    
    # 使用按钮样式的导航
    col1, col2, col3 = st.columns(1), st.columns(1), st.columns(1)
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "🤖 智能对话"
    
    if st.button("🤖 智能对话", key="chat_btn", use_container_width=True):
        st.session_state.current_page = "🤖 智能对话"
    
    if st.button("📊 流量分析", key="analysis_btn", use_container_width=True):
        st.session_state.current_page = "📊 流量分析"
    
    if st.button("📚 教育资源", key="education_btn", use_container_width=True):
        st.session_state.current_page = "📚 教育资源"
    
    page = st.session_state.current_page
    
    # 系统状态
    st.markdown("---")
    st.markdown("### 📡 系统状态")
    
    # 使用缓存的状态检查结果
    backend_status, ollama_status = get_cached_status()
    
    if backend_status:
        st.success("✅ 后端服务正常")
    else:
        st.error("❌ 后端服务异常")
    
    if ollama_status:
        st.success("✅ Ollama服务正常")
    else:
        st.error("❌ Ollama服务异常")
    
    # 底部信息
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; font-size: 12px; color: #666;">
        <p><strong>安巡</strong></p>
        <p>让网络安全更智能、更有温度</p>
        <p style="margin-top: 10px;">技术支持: Streamlit + Ollama + PyShark</p>
    </div>
    """, unsafe_allow_html=True)

# 后端API调用函数
def call_backend_api(endpoint, method="GET", data=None, files=None):
    """调用后端API"""
    try:
        backend_url = "http://localhost:5000"
        url = f"{backend_url}{endpoint}"
        
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            if files:
                response = requests.post(url, files=files, timeout=60)
            else:
                response = requests.post(url, json=data, timeout=60)
        else:
            return {"error": "不支持的HTTP方法"}
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API调用失败，状态码: {response.status_code}"}
    except Exception as e:
        return {"error": f"连接后端服务失败: {str(e)}"}

# 模型预加载函数
def preload_model(model="qwen2.5:7b"):
    """预加载模型，避免首次对话延迟"""
    try:
        # 检查是否已经预加载过
        if f'model_preloaded_{model}' in st.session_state:
            return "already_loaded"
        
        # 发送一个简单的预热请求到Ollama直接API
        import requests
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": "qwen3:8b" if model == "qwen2.5:7b" else model,
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            # 标记模型已预加载
            st.session_state[f'model_preloaded_{model}'] = True
            return "success"
        else:
            return "failed"
    except Exception as e:
        print(f"Model preload failed: {str(e)}")
        return "failed"

# Ollama API调用函数（带记忆功能）
def call_ollama_api(message, model="qwen2.5:7b", session_id="default"):
    """调用后端的聊天API，支持记忆功能"""
    data = {
        "message": message,
        "model": model,
        "session_id": session_id
    }
    result = call_backend_api("/api/chat", "POST", data)
    
    if "error" in result:
        return result["error"]
    else:
        return result.get("response", "抱歉，无法获取回复")

# 流量包分析函数（Demo模式）
def analyze_pcap_file(uploaded_file, enable_thinking=True):
    """分析上传的pcap文件（Demo模式，使用预设数据）"""
    try:
        import time
        import json
        
        # 模拟分析时间（30秒）
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i in range(30):
            progress_bar.progress((i + 1) / 30)
            status_text.text(f"正在分析流量包... {i + 1}/30秒")
            time.sleep(1)
        
        progress_bar.empty()
        status_text.empty()
        
        # 加载预设的分析结果
        demo_file_path = "d:\\CTF\\tech-study\\Agent\\安巡\\data\\demo_analysis_result.json"
        with open(demo_file_path, 'r', encoding='utf-8') as f:
            demo_data = json.load(f)
        
        # 构造返回结果格式
        result = {
            "success": True,
            "filename": uploaded_file.name,
            "analysis_result": {
                "ai_analysis": demo_data["ai_analysis"],
                "structured_data_file": demo_file_path,
                "processing_time": "2025-07-11T22:15:00"
            },
            "timestamp": "2025-07-11T22:15:00"
        }
        
        # 保存完整的demo数据到session state（包含可视化数据）
        st.session_state.analysis_result = result
        st.session_state.demo_data = demo_data
        
        return result
        
    except Exception as e:
        st.error(f"分析文件时发生错误: {str(e)}")
        return None

# 从分析结果生成DataFrame用于可视化
def create_visualization_data(analysis_result):
    """从分析结果创建可视化数据（使用demo数据）"""
    if not analysis_result or "analysis_result" not in analysis_result:
        return None
    
    # 使用demo数据中的五元组信息
    if 'demo_data' in st.session_state:
        demo_data = st.session_state.demo_data
        five_tuple_data = demo_data.get('five_tuple_data', [])
        
        if five_tuple_data:
            return pd.DataFrame(five_tuple_data)
    
    # 如果没有demo数据，返回默认数据
    sample_data = {
        '源IP': ['192.168.10.156', '192.168.10.89', '192.168.10.234', '192.168.10.67'],
        '目标IP': ['203.208.60.1', 'malicious-domain.com', 'game-server.net', '192.168.10.1'],
        '源端口': [12345, 54321, 6789, 22],
        '目标端口': [80, 443, 7777, 22],
        '协议': ['TCP', 'TCP', 'UDP', 'TCP'],
        '数据包大小': [1024, 512, 256, 64]
    }
    return pd.DataFrame(sample_data)

# 网络流量捕获函数
def capture_network_traffic(duration=10, interface='any', packet_count=50):
    """调用后端API进行网络流量捕获"""
    try:
        st.session_state.capture_status = True
        
        # 调用后端API进行流量捕获
        data = {
            "duration": duration,
            "interface": interface,
            "packet_count": packet_count
        }
        
        with st.spinner(f"正在捕获网络流量 ({duration}秒)..."):
            result = call_backend_api("/api/capture_traffic", "POST", data)
        
        if "error" in result:
            st.error(f"捕获失败: {result['error']}")
            st.session_state.capture_status = False
            return []
        
        captured_data = result.get("data", [])
        st.session_state.captured_packets = captured_data
        st.session_state.capture_status = False
        
        if captured_data:
            st.success(f"成功捕获 {len(captured_data)} 个数据包")
        else:
            st.warning("未捕获到数据包")
        
        return captured_data
        
    except Exception as e:
        st.error(f"捕获失败: {str(e)}")
        st.session_state.capture_status = False
        return []

# 页面内容
if page == "🤖 智能对话":
    # 模型预加载（仅在首次访问时执行）
    if 'model_preloaded' not in st.session_state:
        with st.spinner("正在预加载模型，请稍候..."):
            preload_status = preload_model()
            st.session_state.model_preloaded = True
            if preload_status == "success":
                st.success("✅ 模型预加载完成，对话响应将更快！")
            else:
                st.warning("⚠️ 模型预加载失败，首次对话可能较慢")
    
    # 创建聊天界面容器
    chat_container = st.container(height=500)
    
    with chat_container:
        if not st.session_state.chat_history:
            # 欢迎消息
            st.markdown("""
            <div style="
                text-align: center;
                padding: 50px 20px;
                color: #666;
            ">
                <h3>👋 你好！我是安巡智能助手</h3>
                <p>我可以帮助你解答网络安全相关问题，分析流量包，提供安全建议。</p>
                <p>请在下方输入你的问题开始对话吧！</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # 显示聊天历史
            for i, chat in enumerate(st.session_state.chat_history):
                if chat['role'] == 'user':
                    st.markdown(f"""
                    <div style="
                        display: flex;
                        justify-content: flex-end;
                        margin: 10px 0;
                    ">
                        <div style="
                            background: #007bff;
                            color: white;
                            padding: 10px 15px;
                            border-radius: 18px 18px 4px 18px;
                            max-width: 70%;
                            word-wrap: break-word;
                        ">
                            {chat["content"]}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # 为助手消息添加流式显示效果
                    message_container = st.empty()
                    message_container.markdown(f"""
                    <div style="
                        display: flex;
                        justify-content: flex-start;
                        margin: 10px 0;
                    ">
                        <div style="
                            background: #f1f3f4;
                            color: #333;
                            padding: 10px 15px;
                            border-radius: 18px 18px 18px 4px;
                            max-width: 70%;
                            word-wrap: break-word;
                        ">
                            {chat["content"]}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # 添加自动滚动到底部的JavaScript
            st.markdown("""
            <script>
            setTimeout(function() {
                var chatContainer = parent.document.querySelector('[data-testid="stVerticalBlock"] > div > div > div');
                if (chatContainer) {
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }
            }, 100);
            </script>
            """, unsafe_allow_html=True)
    
    # AI思考开关
    col_switch1, col_switch2 = st.columns([1, 4])
    with col_switch1:
        enable_thinking = st.toggle("🧠 AI思考", value=st.session_state.enable_thinking_chat, key="enable_thinking_chat_toggle", help="开启后AI会显示思考过程")
        # 更新session state
        st.session_state.enable_thinking_chat = enable_thinking
    
    # 流量包上传模块
    with st.expander("📁 流量包上传分析", expanded=False):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            uploaded_file = st.file_uploader(
                "上传流量包文件进行分析",
                type=['pcap', 'pcapng', 'cap'],
                help="支持pcap、pcapng、cap格式的流量包文件",
                key="chat_upload"
            )
        
        with col2:
            if uploaded_file is not None:
                st.success(f"✅ {uploaded_file.name}")
        
        with col2:
            # 思考模式开关
            enable_thinking_upload = st.toggle("🧠 思考模式", value=st.session_state.enable_thinking_traffic, key="enable_thinking_traffic_toggle", help="开启后显示AI思考过程")
            st.session_state.enable_thinking_traffic = enable_thinking_upload
        
        with col3:
            if uploaded_file is not None:
                if st.button("🔍 开始分析", key="chat_analyze_btn", use_container_width=True):
                    # Demo模式：使用预设数据
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # 模拟30秒分析过程
                    for i in range(30):
                        progress_bar.progress((i + 1) / 30)
                        status_text.text(f"正在分析流量包... {i + 1}/30秒")
                        time.sleep(1)
                    
                    # 加载预设的demo数据
                    try:
                        import json
                        import os
                        demo_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..\data', 'demo_data.json')
                        with open(demo_file_path, 'r', encoding='utf-8') as f:
                            demo_data = json.load(f)
                        
                        # 存储demo数据到session state
                        st.session_state.demo_data = demo_data
                        ai_analysis = demo_data['analysis_result']
                        
                        # 将demo数据发送给模型以建立上下文，但不在前端显示
                        context_message = f"""系统已加载校园网络流量分析数据，包含以下信息：
- 风险等级：{ai_analysis.get('risk_level', '未知')}
- 高风险IP数量：{len(demo_data.get('high_risk_ips', []))}
- 涉及学生：{', '.join([ip['student_name'] for ip in demo_data.get('high_risk_ips', [])])}
- 主要威胁：{', '.join(ai_analysis.get('threats', [])[:3])}
- 协议分布：{demo_data.get('protocol_distribution', {})}
- 数据包统计：{demo_data.get('packet_size_distribution', {})}
请基于这些数据回答用户关于网络安全的问题。"""
                        
                        # 发送上下文给模型（不显示在前端）
                        try:
                            session_id = st.session_state.get('session_id', 'default')
                            call_ollama_api("/no_think " + context_message, session_id=session_id)
                        except:
                            pass  # 静默处理错误，不影响用户体验
                        
                        summary = ai_analysis.get("summary", "流量分析已完成")
                        risk_level = ai_analysis.get("risk_level", "未知")
                        threats = ai_analysis.get("threats", [])
                        recommendations = ai_analysis.get("recommendations", [])
                        detailed_analysis = ai_analysis.get("detailed_analysis", "")
                        
                        # 构建完整的分析结果显示
                        risk_color = {"低": "🟢", "中": "🟡", "高": "🔴"}.get(risk_level, "⚪")
                        
                        # 格式化显示分析结果
                        threats_text = "\n".join([f"• {threat}" for threat in threats]) if threats else "• 未发现明显威胁"
                        recommendations_text = "\n".join([f"• {rec}" for rec in recommendations]) if recommendations else "• 建议持续监控"
                        
                        analysis_result = f"""🤖 **AI分析报告 - {uploaded_file.name}**

**风险等级**: {risk_color} {risk_level}

**分析摘要**:
{summary}

**发现威胁**: {len(threats)} 个
{threats_text}

**安全建议**: {len(recommendations)} 条
{recommendations_text}

**详细分析**:
{detailed_analysis[:800] + '...' if len(detailed_analysis) > 800 else detailed_analysis}

---
💡 完整的可视化分析结果可在'流量分析'页面查看。"""
                        
                        # 添加分析结果到对话历史
                        st.session_state.chat_history.append({"role": "assistant", "content": analysis_result})
                        
                        progress_bar.empty()
                        status_text.empty()
                        st.success("分析完成！")
                        
                    except Exception as e:
                        progress_bar.empty()
                        status_text.empty()
                        st.error(f"加载demo数据失败: {str(e)}")
                    
                    st.rerun()
    
    # 输入框固定在底部
    st.markdown("""
    <style>
    .chat-input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        padding: 20px;
        border-top: 1px solid #e0e0e0;
        z-index: 1000;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 输入区域
    col1, col2, col3 = st.columns([6, 1, 1])
    
    with col1:
        # 使用动态key来强制重新创建输入框
        if 'input_key' not in st.session_state:
            st.session_state.input_key = 0
        
        user_input = st.text_input(
            "请输入您的问题",
            key=f"chat_input_{st.session_state.input_key}",
            placeholder="请输入您的问题...",
            label_visibility="collapsed"
        )   
    
    with col2:
        send_clicked = st.button("发送", key="send_btn", use_container_width=True)
    
    with col3:
        clear_clicked = st.button("清空", key="clear_btn", use_container_width=True)
    
    # 处理发送消息
    if send_clicked and user_input:
        # 保存用户输入
        user_message = user_input
        
        # 更新input_key来清空输入框
        st.session_state.input_key += 1
        
        # 根据思考开关决定是否添加nothink前缀
        actual_input = user_message
        if not st.session_state.enable_thinking_chat:
            actual_input = "/no_think " + user_message
        
        # 添加用户消息到历史（显示原始输入，不包含nothink前缀）
        st.session_state.chat_history.append({"role": "user", "content": user_message})
        
        # 显示加载状态
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("🤔 正在思考中...")
            
            try:
                # 调用后端API（带记忆功能），发送实际输入（可能包含nothink前缀）
                session_id = st.session_state.get('session_id', 'default')
                response = call_ollama_api(actual_input, session_id=session_id)
                
                # 处理AI响应，根据思考模式决定是否显示思考标签
                processed_response = process_ai_response(response, st.session_state.enable_thinking_chat)
                
                # 显示最终回复
                message_placeholder.markdown(processed_response)
                
                # 添加助手回复到历史（保存处理后的响应）
                st.session_state.chat_history.append({"role": "assistant", "content": processed_response})
                
            except Exception as e:
                error_msg = f"抱歉，服务暂时不可用: {str(e)}"
                message_placeholder.markdown(error_msg)
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
        
        # 重新运行以更新界面
        st.rerun()
    
    # 处理清空对话
    if clear_clicked:
        st.session_state.chat_history = []
        st.rerun()

elif page == "📊 流量分析":
    st.header("网络流量获取与分析")
    
    # 显示校园网络实时监测状态
    st.markdown("""
    <div style="background: linear-gradient(90deg, #4CAF50, #45a049); color: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h3 style="margin: 0; font-size: 18px;">🌐 校园网络实时监测中</h3>
        <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">系统正在持续监控校园网络安全状态</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["实时捕获", "文件分析", "分析结果"])
    
    with tab1:
        st.subheader("实时网络流量捕获")
        
        # 获取网络接口列表
        @st.cache_data(ttl=60)  # 缓存60秒
        def get_network_interfaces():
            try:
                result = call_backend_api("/api/get_network_interfaces", "GET")
                if "error" not in result:
                    return result.get("interfaces", [])
            except:
                pass
            return [{'id': 'any', 'name': 'Any available interface', 'display_name': 'Any available interface'}]
        
        interfaces = get_network_interfaces()
        
        # 捕获参数设置
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            duration = st.slider("捕获时长(秒)", 5, 60, 10)
        
        with col2:
            # 网卡选择
            interface_options = {iface['display_name']: iface['id'] for iface in interfaces}
            
            # 默认选择WLAN接口
            default_interface = 'Any available interface'
            for iface in interfaces:
                if any(keyword in iface['name'].lower() for keyword in ['wlan', 'wi-fi', 'wireless', '无线', 'wifi']):
                    default_interface = iface['display_name']
                    break
            
            selected_interface_name = st.selectbox(
                "选择网络接口",
                options=list(interface_options.keys()),
                index=list(interface_options.keys()).index(default_interface) if default_interface in interface_options else 0,
                help="选择要监听的网络接口，建议选择WLAN接口"
            )
            selected_interface = interface_options[selected_interface_name]
        
        with col3:
            if st.button("开始捕获", disabled=st.session_state.capture_status):
                # 初始化捕获状态
                st.session_state.capture_status = True
                st.session_state.captured_packets = []
                
                # 显示捕获进度
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # 调用后端API进行流量捕获
                    data = {
                        "duration": duration,
                        "interface": selected_interface,
                        "packet_count": 100
                    }
                    
                    status_text.text(f"正在使用接口 {selected_interface_name} 捕获网络流量...")
                    
                    # 调用后端API
                    result = call_backend_api("/api/capture_traffic", "POST", data)
                    
                    # 模拟进度更新
                    for i in range(duration):
                        progress_bar.progress((i + 1) / duration)
                        status_text.text(f"正在捕获网络流量... {i + 1}/{duration}秒")
                        time.sleep(1)
                    
                    if "error" in result:
                        st.error(f"捕获失败: {result['error']}")
                        st.session_state.capture_status = False
                    else:
                        captured_data = result.get("data", [])
                        st.session_state.captured_packets = captured_data
                        st.session_state.capture_status = False
                        
                        if captured_data:
                            st.success(f"成功捕获 {len(captured_data)} 个数据包")
                        else:
                            st.warning("未捕获到数据包，请检查网络接口权限或尝试其他接口")
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                except Exception as e:
                    st.error(f"捕获失败: {str(e)}")
                    st.session_state.capture_status = False
                    progress_bar.empty()
                    status_text.empty()
        
        with col3:
            if st.button("停止捕获"):
                st.session_state.capture_status = False
                st.warning("已停止捕获")
        
        # 显示捕获状态
        if st.session_state.capture_status:
            st.info("🔄 正在捕获网络流量...")
        
        # 显示捕获的数据
        if st.session_state.captured_packets:
            st.subheader("捕获的流量数据")
            df = pd.DataFrame(st.session_state.captured_packets)
            st.dataframe(df, use_container_width=True)
            
            # 添加开始分析按钮
            st.markdown("---")
            if st.button("🔍 开始分析", type="primary", use_container_width=True, help="对捕获的流量数据进行安全分析"):
                # 开始分析流程
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 模拟分析过程
                for i in range(20):
                    progress_bar.progress((i + 1) / 20)
                    status_text.text(f"正在分析流量数据... {i + 1}/20秒")
                    time.sleep(1)
                
                # 由于这不是真实校园网络流量，生成简化的分析结果
                try:
                    # 创建分析结果数据结构
                    analysis_result = {
                        "summary": "已完成对捕获流量的安全分析。在个人网络环境中检测到正常的网络活动，未发现明显的安全威胁。",
                        "risk_level": "低",
                        "threats": [],
                        "recommendations": [
                            "继续监控网络流量",
                            "定期更新安全策略",
                            "加强网络安全防护"
                        ],
                        "detailed_analysis": "个人网络环境流量分析显示网络活动正常，未检测到异常行为模式或恶意流量。建议继续保持监控状态。",
                        "protocol_distribution": {
                            "HTTP": 45,
                            "HTTPS": 35,
                            "DNS": 15,
                            "TCP": 5
                        },
                        "packet_size_distribution": {
                            "0-100字节": 120,
                            "100-500字节": 80,
                            "500-1000字节": 45,
                            "1000+字节": 25
                        },
                        "source_ip_stats": {
                            "192.168.1.100": 85,
                            "192.168.1.101": 62,
                            "192.168.1.102": 48,
                            "192.168.1.103": 35,
                            "192.168.1.104": 28
                        }
                    }
                    
                    # 创建可视化数据（基于捕获的数据）
                    visualization_data = []
                    for i, packet in enumerate(st.session_state.captured_packets[:50]):  # 只取前50条
                        visualization_data.append({
                            '序号': i + 1,
                            '源IP': packet.get('src_ip', '未知'),
                            '目标IP': packet.get('dst_ip', '未知'),
                            '协议': packet.get('protocol', '未知'),
                            '端口': packet.get('port', '未知'),
                            '数据包数': 1,
                            '字节数': packet.get('length', 0)
                        })
                    
                    # 存储分析结果到session state
                    st.session_state.analysis_result = pd.DataFrame(visualization_data)
                    st.session_state.ai_analysis = analysis_result
                    st.session_state.demo_data = analysis_result  # 确保可视化数据可用
                    
                    # 由于不是真实校园流量，不设置高危IP信息
                    
                    progress_bar.empty()
                    status_text.empty()
                    st.success("✅ 分析完成！请切换到'分析结果'标签页查看详细结果。")
                    
                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"分析失败: {str(e)}")
    
    with tab2:
        st.subheader("流量包文件分析")
        
        # AI思考开关
        enable_thinking_traffic = st.toggle("🧠 AI思考", value=st.session_state.enable_thinking_traffic, key="enable_thinking_traffic_main", help="开启后AI会显示思考过程")
        st.session_state.enable_thinking_traffic = enable_thinking_traffic
        
        uploaded_file = st.file_uploader(
            "选择流量包文件",
            type=['pcap', 'pcapng', 'cap'],
            key="analysis_upload"
        )
        
        if uploaded_file is not None:
            st.success(f"已选择文件: {uploaded_file.name}")
            
            if st.button("开始分析", key="start_analysis"):
                # Demo模式：使用预设数据
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 模拟30秒分析过程
                for i in range(30):
                    progress_bar.progress((i + 1) / 30)
                    status_text.text(f"正在分析流量包... {i + 1}/30秒")
                    time.sleep(1)
                
                # 加载预设的demo数据
                try:
                    import json
                    import os
                    demo_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..\data', 'demo_data.json')
                    with open(demo_file_path, 'r', encoding='utf-8') as f:
                        demo_data = json.load(f)
                    
                    # 存储demo数据到session state
                    st.session_state.demo_data = demo_data
                    st.session_state.ai_analysis = demo_data['analysis_result']
                    
                    # 创建可视化数据
                    visualization_data = []
                    for conn in demo_data['top_connections']:
                        visualization_data.append({
                            '源IP': conn['src_ip'],
                            '目标IP': conn['dst_ip'],
                            '协议': conn['protocol'],
                            '端口': conn['port'],
                            '数据包数': conn['packets'],
                            '字节数': conn['bytes']
                        })
                    
                    st.session_state.analysis_result = pd.DataFrame(visualization_data)
                    
                    progress_bar.empty()
                    status_text.empty()
                    st.success("分析完成！")
                    
                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"加载demo数据失败: {str(e)}")
    
    with tab3:
        st.subheader("流量分析结果可视化")
        
        # 检查是否有分析结果
        if 'analysis_result' in st.session_state and st.session_state.analysis_result is not None:
            df = st.session_state.analysis_result
            
            # 确保df是DataFrame类型
            if not isinstance(df, pd.DataFrame):
                st.error("分析结果格式错误，请重新分析")
                st.session_state.analysis_result = None
                st.stop()
            
            # 显示AI分析结果
            if 'ai_analysis' in st.session_state:
                ai_analysis = st.session_state.ai_analysis
                
                # AI分析摘要
                st.subheader("🤖 AI分析报告")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    risk_level = ai_analysis.get("risk_level", "未知")
                    risk_color = {"低": "🟢", "中": "🟡", "高": "🔴"}.get(risk_level, "⚪")
                    st.metric("风险等级", f"{risk_color} {risk_level}")
                
                with col2:
                    threats = ai_analysis.get("threats", [])
                    st.metric("发现威胁", len(threats))
                
                with col3:
                    recommendations = ai_analysis.get("recommendations", [])
                    st.metric("安全建议", len(recommendations))
                
                # 详细分析
                if "summary" in ai_analysis:
                    st.write("**分析摘要:**")
                    st.info(ai_analysis["summary"])
                
                if threats:
                    st.write("**发现的威胁:**")
                    for i, threat in enumerate(threats, 1):
                        st.warning(f"{i}. {threat}")
                
                if recommendations:
                    st.write("**安全建议:**")
                    for i, rec in enumerate(recommendations, 1):
                        st.success(f"{i}. {rec}")
                
                # 显示高危IP和学生信息（demo数据）
                if 'demo_data' in st.session_state:
                    demo_data = st.session_state.demo_data
                    high_risk_ips = demo_data.get('high_risk_ips', [])
                    
                    if high_risk_ips:
                        st.write("**🚨 高危IP及关联学生信息:**")
                        
                        # 创建表格显示高危IP信息
                        display_data = []
                        for ip_info in high_risk_ips:
                            display_data.append({
                                'IP地址': ip_info['ip'],
                                '风险等级': ip_info['risk_level'],
                                '威胁类型': ip_info['threat_type'],
                                '学生姓名': ip_info['student_name'],
                                '学号': ip_info['student_id'],
                                '联系电话': ip_info['phone'],
                                '宿舍': ip_info['dormitory'],
                                '学院': ip_info['department'],
                                '最后活动时间': ip_info['last_activity']
                            })
                        
                        risk_df = pd.DataFrame(display_data)
                        
                        # 使用颜色编码显示风险等级
                        def color_risk_level(val):
                            if val == '高':
                                return 'background-color: #ffebee; color: #c62828'
                            elif val == '中':
                                return 'background-color: #fff3e0; color: #ef6c00'
                            else:
                                return 'background-color: #e8f5e8; color: #2e7d32'
                        
                        styled_df = risk_df.style.applymap(color_risk_level, subset=['风险等级'])
                        st.dataframe(styled_df, use_container_width=True)
                        
                        # 显示统计信息
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            high_count = len([ip for ip in high_risk_ips if ip['risk_level'] == '高'])
                            st.metric("高风险IP", high_count, delta=f"{high_count}个需要立即处理")
                        
                        with col2:
                            medium_count = len([ip for ip in high_risk_ips if ip['risk_level'] == '中'])
                            st.metric("中风险IP", medium_count, delta=f"{medium_count}个需要关注")
                        
                        with col3:
                            total_students = len(set([ip['student_name'] for ip in high_risk_ips]))
                            st.metric("涉及学生", total_students, delta="人")
                        
                        # 一键预警和推送功能
                        st.markdown("---")
                        col1, col2, col3 = st.columns([1, 1, 1])
                        with col1:
                            if st.button("🚨 一键预警", type="primary", use_container_width=True, help="向所有涉及学生发送安全预警信息"):
                                # 显示预警成功信息
                                st.session_state.show_alert_success = True
                        
                        with col2:
                            if st.button("📚 一键推送相关学习资源", type="secondary", use_container_width=True, help="向高危IP学生推送相关教育资源"):
                                # 显示推送成功信息
                                st.session_state.show_push_success = True
                        
                        # 预警成功弹窗
                        if st.session_state.get('show_alert_success', False):
                            st.success("✅ 预警成功！学生已全部收到预警信息")
                            if st.button("确认", key="confirm_alert"):
                                st.session_state.show_alert_success = False
                                st.rerun()
                        
                        # 推送成功弹窗
                        if st.session_state.get('show_push_success', False):
                            st.success("✅ 推送成功！相关学习资源已发送给高危IP学生")
                            if st.button("确认", key="confirm_push"):
                                st.session_state.show_push_success = False
                                st.rerun()
                
                st.divider()
            
            # 数据可视化
            st.subheader("📊 流量数据可视化")
            
            # 协议分布饼图
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**协议分布**")
                # 使用demo数据中的协议分布
                if 'demo_data' in st.session_state:
                    protocol_data = st.session_state.demo_data.get('protocol_distribution', {})
                    if protocol_data:
                        fig_pie = px.pie(values=list(protocol_data.values()), names=list(protocol_data.keys()), title="网络协议分布")
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        # 回退到DataFrame数据
                        if '协议' in df.columns:
                            protocol_counts = df['协议'].value_counts()
                            fig_pie = px.pie(values=protocol_counts.values, names=protocol_counts.index, title="网络协议分布")
                            st.plotly_chart(fig_pie, use_container_width=True)
                        elif 'protocol' in df.columns:
                            protocol_counts = df['protocol'].value_counts()
                            fig_pie = px.pie(values=protocol_counts.values, names=protocol_counts.index, title="网络协议分布")
                            st.plotly_chart(fig_pie, use_container_width=True)
                        else:
                            st.warning("未找到协议字段")
                else:
                    st.warning("未找到协议分布数据")
            
            with col2:
                st.write("**数据包大小分布**")
                # 使用demo数据中的数据包大小分布
                if 'demo_data' in st.session_state:
                    size_data = st.session_state.demo_data.get('packet_size_distribution', {})
                    if size_data:
                        fig_hist = px.bar(x=list(size_data.keys()), y=list(size_data.values()), title="数据包大小分布")
                        fig_hist.update_xaxes(title="数据包大小范围(字节)")
                        fig_hist.update_yaxes(title="数据包数量")
                        st.plotly_chart(fig_hist, use_container_width=True)
                    else:
                        # 回退到DataFrame数据
                        size_col = None
                        for col in ['数据包大小', 'packet_size', 'length', 'size']:
                            if col in df.columns:
                                size_col = col
                                break
                        
                        if size_col:
                            fig_hist = px.histogram(df, x=size_col, title="数据包大小分布")
                            st.plotly_chart(fig_hist, use_container_width=True)
                        else:
                            st.warning("未找到数据包大小字段")
                else:
                    st.warning("未找到数据包大小分布数据")
            
            # 五元组信息表格
            st.subheader("📋 详细信息")
            st.dataframe(df, use_container_width=True)
            
            # 源IP统计
            st.subheader("📈 源IP访问统计")
            # 使用demo数据中的源IP统计
            if 'demo_data' in st.session_state:
                ip_stats = st.session_state.demo_data.get('source_ip_stats', {})
                if ip_stats:
                    # 取前10个IP
                    sorted_ips = sorted(ip_stats.items(), key=lambda x: x[1], reverse=True)[:10]
                    ips = [item[0] for item in sorted_ips]
                    counts = [item[1] for item in sorted_ips]
                    
                    fig_bar = px.bar(x=ips, y=counts, title="Top 10 源IP访问次数")
                    fig_bar.update_xaxes(title="源IP地址")
                    fig_bar.update_yaxes(title="访问次数")
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    # 回退到DataFrame数据
                    ip_col = None
                    for col in ['源IP', 'src_ip', 'source_ip', 'src']:
                        if col in df.columns:
                            ip_col = col
                            break
                    
                    if ip_col:
                        ip_counts = df[ip_col].value_counts().head(10)
                        fig_bar = px.bar(x=ip_counts.index, y=ip_counts.values, title="Top 10 源IP访问次数")
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.warning("未找到源IP字段")
            else:
                st.warning("未找到源IP统计数据")
        
        else:
            st.info("请先在'实时捕获'或'文件分析'标签页中获取数据")

elif page == "📚 教育资源":
    st.header("🎓 网络安全教育资源")
    
    # 推送功能区域
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("📤 选择推送", type="primary", use_container_width=True, help="选择学院专业后推送资源"):
            st.session_state.show_select_push = True
    
    with col2:
        if st.button("📢 一键推送", type="secondary", use_container_width=True, help="直接选择资源推送给所有学生"):
            st.session_state.show_direct_push = True
    
    # 选择推送弹窗
    if st.session_state.get('show_select_push', False):
        with st.expander("📋 选择推送对象", expanded=True):
            # 定义学院和对应专业的映射关系
            department_majors = {
                "计算机科学与技术学院": ["计算机科学与技术", "软件工程", "信息安全"],
                "网络工程学院": ["网络工程", "物联网工程", "通信工程"],
                "电子信息工程学院": ["电子信息工程", "电子科学与技术", "微电子科学与工程"],
                "人工智能学院": ["人工智能", "机器学习", "数据科学与大数据技术"],
                "数据科学与大数据技术学院": ["数据科学与大数据技术", "统计学", "应用数学"],
                "软件工程学院": ["软件工程", "数字媒体技术", "游戏开发"],
                "信息管理与信息系统学院": ["信息管理与信息系统", "电子商务", "信息资源管理"],
                "经济管理学院": ["工商管理", "会计学", "市场营销", "金融学"],
                "外国语学院": ["英语", "日语", "德语", "翻译"],
                "文学院": ["汉语言文学", "新闻学", "广告学"],
                "法学院": ["法学", "知识产权", "社会工作"],
                "艺术学院": ["视觉传达设计", "环境设计", "产品设计"],
                "教育学院": ["教育学", "心理学", "学前教育"],
                "化学与材料工程学院": ["化学工程与工艺", "材料科学与工程", "应用化学"],
                "生物科学学院": ["生物科学", "生物技术", "生物工程"]
            }
            
            # 从demo_data获取学院信息，如果没有则使用默认列表
            if 'demo_data' in st.session_state:
                demo_data = st.session_state.demo_data
                high_risk_ips = demo_data.get('high_risk_ips', [])
                available_departments = list(set([ip['department'] for ip in high_risk_ips]))
                # 确保所有学院都在映射表中
                departments = [dept for dept in available_departments if dept in department_majors]
                if not departments:
                    departments = list(department_majors.keys())
            else:
                departments = list(department_majors.keys())
            
            selected_department = st.selectbox("选择学院", departments, key="select_dept")
            
            # 根据选择的学院显示对应的专业
            if selected_department in department_majors:
                majors = department_majors[selected_department]
            else:
                majors = ["计算机科学与技术", "网络工程", "信息安全"]
            
            selected_major = st.selectbox("选择专业", majors, key="select_major")
            
            # 显示选择的班级（年级+专业）
            grades = ["2021级", "2022级", "2023级", "2024级"]
            selected_grade = st.selectbox("选择年级", grades, key="select_grade")
            
            st.info(f"将推送给：{selected_department} - {selected_grade}{selected_major}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("确认选择", key="confirm_selection"):
                    st.session_state.show_resource_selection = True
                    st.session_state.show_select_push = False
                    st.session_state.selected_target = f"{selected_department} - {selected_grade}{selected_major}"
                    st.rerun()
            
            with col2:
                if st.button("取消", key="cancel_selection"):
                    st.session_state.show_select_push = False
                    st.rerun()
    
    # 直接推送弹窗
    if st.session_state.get('show_direct_push', False):
        st.session_state.show_resource_selection = True
        st.session_state.show_direct_push = False
        st.rerun()
    
    # 资源选择弹窗
    if st.session_state.get('show_resource_selection', False):
        with st.expander("📚 选择推送资源", expanded=True):
            st.write("请选择要推送的教育资源模块：")
            
            resource_modules = [
                "网络安全基础",
                "威胁检测与分析", 
                "电信诈骗防护",
                "密码与认证安全",
                "应急响应与处置",
                "校园网络安全",
                "安全测试"
            ]
            
            selected_resources = []
            for module in resource_modules:
                if st.checkbox(module, key=f"resource_{module}"):
                    selected_resources.append(module)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("确认推送", key="confirm_push_resources"):
                    if selected_resources:
                        st.session_state.show_push_resource_success = True
                        st.session_state.selected_push_resources = selected_resources
                        st.session_state.show_resource_selection = False
                        st.rerun()
                    else:
                        st.warning("请至少选择一个资源模块")
            
            with col2:
                if st.button("取消", key="cancel_push"):
                    st.session_state.show_resource_selection = False
                    st.rerun()
    
    # 推送成功提示
    if st.session_state.get('show_push_resource_success', False):
        selected_resources = st.session_state.get('selected_push_resources', [])
        selected_target = st.session_state.get('selected_target', '所有学生')
        st.success(f"✅ 推送成功！已将以下资源推送给 {selected_target}：{', '.join(selected_resources)}")
        if st.button("确认", key="confirm_push_success"):
            st.session_state.show_push_resource_success = False
            st.session_state.selected_push_resources = []
            st.session_state.selected_target = ''
            st.rerun()
    
    st.markdown("---")
    
    # 加载教育资源数据
    @st.cache_data
    def load_education_resources():
        try:
            with open('d:/CTF/tech-study/Agent/安巡/data/education_resources.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"加载教育资源失败: {e}")
            return None
    
    resources_data = load_education_resources()
    
    if resources_data:
        # 精选资源展示
        if "featured_resources" in resources_data:
            st.subheader("⭐ 精选资源")
            featured = resources_data["featured_resources"]
            
            cols = st.columns(len(featured))
            for i, resource in enumerate(featured):
                with cols[i]:
                    difficulty = resource.get('difficulty', '未知')
                    st.markdown(f"""
                    <div style="
                        border: 2px solid #ff6b6b;
                        border-radius: 10px;
                        padding: 15px;
                        margin: 10px 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    ">
                        <h4>🌟 {resource['title']}</h4>
                        <p>{resource['description']}</p>
                        <small>难度: {difficulty} | 类型: {resource['type']}</small>
                    </div>
                    """, unsafe_allow_html=True)
        
        # 资源分类标签页
        categories = [cat["name"] for cat in resources_data["categories"]]
        tabs = st.tabs([f"📚 {cat}" for cat in categories] + ["🧪 安全测试"])
    
        # 为每个分类创建标签页
        for i, category_data in enumerate(resources_data["categories"]):
            with tabs[i]:
                st.subheader(f"{category_data['name']}")
                
                # 显示分类描述
                if "description" in category_data:
                    st.info(category_data["description"])
                
                # 显示资源列表
                if "resources" in category_data:
                    for resource in category_data["resources"]:
                        difficulty = resource.get('difficulty', '未知')
                        with st.expander(f"📖 {resource['title']} - {difficulty}"):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.write(f"**描述**: {resource['description']}")
                                st.write(f"**类型**: {resource['type']}")
                                if "tags" in resource:
                                    tags = " ".join([f"`{tag}`" for tag in resource["tags"]])
                                    st.write(f"**标签**: {tags}")
                                if "source" in resource:
                                    st.write(f"**来源**: {resource['source']}")
                            
                            with col2:
                                 # 显示缩略图（根据资源类型）
                                 resource_type = resource['type'].lower()
                                 if resource_type in ['video', '视频']:
                                     st.markdown("""
                                     <div style="
                                         width: 100px;
                                         height: 80px;
                                         background: linear-gradient(45deg, #ff6b6b, #ee5a24);
                                         border-radius: 8px;
                                         display: flex;
                                         align-items: center;
                                         justify-content: center;
                                         color: white;
                                         font-size: 12px;
                                     ">
                                         🎥 视频
                                     </div>
                                     """, unsafe_allow_html=True)
                                 elif resource_type in ['article', '文章', 'document', '文档']:
                                     st.markdown("""
                                     <div style="
                                         width: 100px;
                                         height: 80px;
                                         background: linear-gradient(45deg, #2ed573, #1e90ff);
                                         border-radius: 8px;
                                         display: flex;
                                         align-items: center;
                                         justify-content: center;
                                         color: white;
                                         font-size: 12px;
                                     ">
                                         📄 文档
                                     </div>
                                     """, unsafe_allow_html=True)
                                 elif resource_type in ['course', '课程']:
                                     st.markdown("""
                                     <div style="
                                         width: 100px;
                                         height: 80px;
                                         background: linear-gradient(45deg, #667eea, #764ba2);
                                         border-radius: 8px;
                                         display: flex;
                                         align-items: center;
                                         justify-content: center;
                                         color: white;
                                         font-size: 12px;
                                     ">
                                         🎓 课程
                                     </div>
                                     """, unsafe_allow_html=True)
                                 elif resource_type in ['tutorial', '教程']:
                                     st.markdown("""
                                     <div style="
                                         width: 100px;
                                         height: 80px;
                                         background: linear-gradient(45deg, #ffa726, #ff7043);
                                         border-radius: 8px;
                                         display: flex;
                                         align-items: center;
                                         justify-content: center;
                                         color: white;
                                         font-size: 12px;
                                     ">
                                         📚 教程
                                     </div>
                                     """, unsafe_allow_html=True)
                                 else:
                                     st.markdown("""
                                     <div style="
                                         width: 100px;
                                         height: 80px;
                                         background: linear-gradient(45deg, #9c27b0, #673ab7);
                                         border-radius: 8px;
                                         display: flex;
                                         align-items: center;
                                         justify-content: center;
                                         color: white;
                                         font-size: 12px;
                                     ">
                                         📋 资源
                                     </div>
                                     """, unsafe_allow_html=True)
                            
                            # 如果有URL，显示访问按钮
                            if "url" in resource and resource["url"]:
                                st.markdown(f"[🔗 访问资源]({resource['url']})")
                else:
                    st.warning("该分类暂无学习资源，敬请期待更多内容！")
        
        # 安全知识测试标签页
        with tabs[-1]:
            st.subheader("安全知识测试")
            
            # 简单的知识测试
            st.markdown("### 📝 快速测试你的安全知识")
            
            # 问题1
            q1 = st.radio(
                "1. 以下哪种密码最安全？",
                ["123456", "password", "Tr0ub4dor&3", "qwerty"],
                key="quiz_q1"
            )
            
            # 问题2
            q2 = st.radio(
                "2. 收到可疑邮件时应该怎么做？",
                ["立即点击链接查看", "转发给朋友", "删除邮件并报告", "回复邮件询问"],
                key="quiz_q2"
            )
            
            # 问题3
            q3 = st.radio(
                "3. 公共WiFi环境下，以下哪种行为最安全？",
                ["直接访问网银", "使用VPN连接", "下载未知软件", "关闭防火墙"],
                key="quiz_q3"
            )
            
            if st.button("提交答案", key="submit_quiz"):
                score = 0
                if q1 == "Tr0ub4dor&3":
                    score += 1
                if q2 == "删除邮件并报告":
                    score += 1
                if q3 == "使用VPN连接":
                    score += 1
                
                st.write(f"### 你的得分: {score}/3")
                
                if score == 3:
                    st.success("🎉 优秀！你的安全意识很强！")
                elif score == 2:
                    st.info("👍 不错！还有提升空间")
                else:
                    st.warning("⚠️ 需要加强安全知识学习")
        
        # 快速提示和紧急联系方式
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            if "quick_tips" in resources_data:
                st.subheader("💡 安全小贴士")
                for tip in resources_data["quick_tips"]:
                    st.info(f"{tip.get('icon', '💡')} **{tip['title']}**: {tip['content']}")
        
        with col2:
            if "emergency_contacts" in resources_data:
                st.subheader("🆘 紧急联系方式")
                contacts = resources_data["emergency_contacts"]
                for contact in contacts:
                    st.error(f"**{contact['name']}**: {contact['phone']}")
                    if 'description' in contact:
                        st.caption(contact['description'])
else:
    st.error("无法加载教育资源数据，请检查数据文件是否存在。")

# 页脚
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #666; padding: 1rem;">
        <p>🛡️ 安巡 - 校园网络风险感知智能体 | 让网络安全更智能、更有温度</p>
        <p>技术支持: Streamlit + Ollama + PyShark</p>
    </div>
    """,
    unsafe_allow_html=True
)