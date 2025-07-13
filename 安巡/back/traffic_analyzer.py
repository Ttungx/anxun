import os
import subprocess
import json
import time
from datetime import datetime
import requests
from typing import List, Dict, Any
import tempfile
import pyshark
import threading

class TrafficAnalyzer:
    """网络流量分析器"""
    
    def __init__(self, data_dir='data', model='qwen3:8b'):
        self.data_dir = data_dir
        self.model = model
        self.ensure_data_dir()
        
    def ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # 创建子目录
        subdirs = ['captured_traffic', 'analysis_results', 'ai_responses']
        for subdir in subdirs:
            path = os.path.join(self.data_dir, subdir)
            if not os.path.exists(path):
                os.makedirs(path)
    
    def load_pcap_with_tshark(self, pcap_file: str) -> List[str]:
        """使用tshark解析pcap文件"""
        build_data = []
        tmp_path = os.path.join(tempfile.gettempdir(), "traffic_analysis_tmp.txt")
        
        # 删除旧的临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        
        # 定义要提取的字段
        fields = [
            "frame.encap_type", "frame.time", "frame.offset_shift", "frame.time_epoch", 
            "frame.time_delta", "frame.time_relative", "frame.number", "frame.len", 
            "frame.marked", "frame.protocols", "eth.dst", "eth.dst_resolved", "eth.src", 
            "eth.src_resolved", "eth.type", "ip.version", "ip.hdr_len", "ip.dsfield", 
            "ip.dsfield.dscp", "ip.len", "ip.id", "ip.flags", "ip.flags.rb", "ip.flags.df", 
            "ip.flags.mf", "ip.frag_offset", "ip.ttl", "ip.proto", "ip.checksum", 
            "ip.checksum.status", "ip.src", "ip.dst", "tcp.srcport", "tcp.dstport", 
            "tcp.stream", "tcp.len", "tcp.seq", "tcp.nxtseq", "tcp.ack", "tcp.hdr_len", 
            "tcp.flags", "tcp.flags.res", "tcp.flags.cwr", "tcp.flags.urg", "tcp.flags.ack", 
            "tcp.flags.push", "tcp.flags.reset", "tcp.flags.syn", "tcp.flags.fin", 
            "tcp.flags.str", "tcp.window_size", "tcp.window_size_scalefactor", 
            "tcp.checksum", "tcp.checksum.status", "tcp.urgent_pointer", "tcp.time_relative", 
            "tcp.time_delta", "tcp.analysis.bytes_in_flight", "tcp.analysis.push_bytes_sent", 
            "tcp.segment", "tcp.segment.count", "tcp.reassembled.length", "tcp.payload", 
            "udp.srcport", "udp.dstport", "udp.length", "udp.checksum", "udp.checksum.status", 
            "udp.stream", "data.len"
        ]
        
        fields_part = " ".join(f"-e {field}" for field in fields)
        cmd = f'tshark -r "{pcap_file}" {fields_part} -T fields -Y "tcp or udp" > "{tmp_path}"'
        
        print(f"[INFO] Running tshark command: {cmd}")
        
        try:
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            
            if proc.returncode != 0:
                print(f"[ERROR] Tshark failed with exit code {proc.returncode}")
                print(f"[STDERR]: {stderr.decode('utf-8', errors='ignore')}")
                return []
            
            if not os.path.exists(tmp_path):
                print("[ERROR] Temporary file was not created.")
                return []
            
            with open(tmp_path, "r", encoding="utf-8", errors="ignore") as fin:
                lines = fin.readlines()
                print(f"[INFO] Read {len(lines)} packets from temporary file")
            
            # 处理数据，限制数量避免撑爆模型上下文
            max_packets = 100  # 限制最大包数量
            processed_count = 0
            
            for line in lines[:max_packets]:  # 只处理前100个包
                packet_data = ""
                values = line.strip('\n').split("\t")
                
                if not values or values == ['']:
                    continue
                
                packet_data += fields[0] + ": " + values[0]
                for field, value in zip(fields[1:], values[1:]):
                    if field == "tcp.flags.str":
                        value = value.encode("unicode_escape").decode("unicode_escape")
                    if field == "tcp.payload":
                        value = value[:200] if len(value) > 200 else value  # 限制payload长度
                    if value == "":
                        continue
                    packet_data += ", "
                    packet_data += field + ": " + value
                
                build_data.append(packet_data)
                processed_count += 1
            
            print(f"[SUCCESS] Processed {processed_count} packets")
            
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
        except Exception as e:
            print(f"[ERROR] Exception during tshark processing: {str(e)}")
            return []
        
        return build_data
    
    def get_network_interfaces(self):
        """获取可用的网络接口列表"""
        interfaces = []
        try:
            # 使用tshark -D命令获取接口列表
            cmd = 'tshark -D'
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            
            if proc.returncode == 0 and stdout:
                lines = stdout.decode('utf-8', errors='ignore').strip().split('\n')
                for line in lines:
                    if line.strip():
                        # 解析接口信息，格式通常为: "1. \Device\NPF_{GUID} (接口名称)"
                        parts = line.split(' ', 1)
                        if len(parts) >= 2:
                            interface_id = parts[0].rstrip('.')
                            interface_info = parts[1]
                            
                            # 提取接口名称
                            if '(' in interface_info and ')' in interface_info:
                                interface_name = interface_info.split('(')[-1].rstrip(')')
                                interface_device = interface_info.split('(')[0].strip()
                            else:
                                interface_name = interface_info
                                interface_device = interface_info
                            
                            interfaces.append({
                                'id': interface_id,
                                'device': interface_device,
                                'name': interface_name,
                                'display_name': f"{interface_id}. {interface_name}"
                            })
                
                # 添加默认的WLAN接口（如果没有找到）
                wlan_found = any('wlan' in iface['name'].lower() or 'wi-fi' in iface['name'].lower() 
                               for iface in interfaces)
                if not wlan_found:
                    # 尝试查找常见的WLAN接口
                    for iface in interfaces:
                        if any(keyword in iface['name'].lower() 
                              for keyword in ['wireless', '无线', 'wifi', 'wi-fi']):
                            wlan_found = True
                            break
                
                print(f"[INFO] Found {len(interfaces)} network interfaces")
                for iface in interfaces:
                    print(f"[INFO] Interface: {iface['display_name']}")
                    
            else:
                print(f"[ERROR] Failed to get interfaces: {stderr.decode('utf-8', errors='ignore')}")
                # 提供默认接口
                interfaces = [
                    {'id': '1', 'device': 'any', 'name': 'Any available interface', 'display_name': '1. Any available interface'}
                ]
                
        except Exception as e:
            print(f"[ERROR] Exception getting interfaces: {str(e)}")
            # 提供默认接口
            interfaces = [
                {'id': '1', 'device': 'any', 'name': 'Any available interface', 'display_name': '1. Any available interface'}
            ]
        
        return interfaces
    
    def capture_live_traffic(self, interface='any', duration=30, packet_count=50):
        """实时捕获网络流量"""
        captured_packets = []
        
        try:
            print(f"[INFO] Starting live capture on interface {interface} for {duration} seconds")
            
            # 使用tshark命令行工具进行捕获，避免事件循环问题
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_pcap = os.path.join(tempfile.gettempdir(), f"temp_capture_{timestamp}.pcap")
            
            # 如果是Windows且interface为'any'，尝试使用第一个可用接口
            if interface == 'any' and os.name == 'nt':
                interfaces = self.get_network_interfaces()
                if interfaces:
                    # 优先选择WLAN接口
                    wlan_interface = None
                    for iface in interfaces:
                        if any(keyword in iface['name'].lower() 
                              for keyword in ['wlan', 'wi-fi', 'wireless', '无线', 'wifi']):
                            wlan_interface = iface['id']
                            break
                    
                    if wlan_interface:
                        interface = wlan_interface
                        print(f"[INFO] Using WLAN interface: {wlan_interface}")
                    else:
                        interface = interfaces[0]['id']
                        print(f"[INFO] Using first available interface: {interface}")
            
            # 限制最大数据包数量
            max_packets = min(packet_count, 100)
            
            # 构建tshark捕获命令
            cmd = f'tshark -i {interface} -a duration:{duration} -c {max_packets} -w "{temp_pcap}"'
            
            print(f"[INFO] Running capture command: {cmd}")
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            
            if proc.returncode != 0:
                print(f"[ERROR] Capture failed with exit code {proc.returncode}")
                print(f"[STDERR]: {stderr.decode('utf-8', errors='ignore')}")
                return []
            
            # 检查是否成功创建了pcap文件
            if not os.path.exists(temp_pcap) or os.path.getsize(temp_pcap) == 0:
                print("[WARNING] No packets captured or file is empty")
                return []
            
            # 使用tshark解析捕获的文件
            parse_cmd = f'tshark -r "{temp_pcap}" -T json'
            proc = subprocess.Popen(parse_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            
            if proc.returncode == 0 and stdout:
                try:
                    # 解析JSON输出
                    packets_json = json.loads(stdout.decode('utf-8'))
                    
                    for packet in packets_json:
                        try:
                            layers = packet.get('_source', {}).get('layers', {})
                            
                            packet_info = {
                                'timestamp': layers.get('frame', {}).get('frame.time', 'N/A'),
                                'protocol': layers.get('frame', {}).get('frame.protocols', 'N/A'),
                                'length': layers.get('frame', {}).get('frame.len', 'N/A'),
                                'src_ip': layers.get('ip', {}).get('ip.src', 'N/A'),
                                'dst_ip': layers.get('ip', {}).get('ip.dst', 'N/A'),
                                'src_port': layers.get('tcp', {}).get('tcp.srcport') or layers.get('udp', {}).get('udp.srcport', 'N/A'),
                                'dst_port': layers.get('tcp', {}).get('tcp.dstport') or layers.get('udp', {}).get('udp.dstport', 'N/A')
                            }
                            captured_packets.append(packet_info)
                        except Exception as e:
                            print(f"[WARNING] Error processing packet: {str(e)}")
                            continue
                            
                except json.JSONDecodeError as e:
                    print(f"[ERROR] Failed to parse JSON output: {str(e)}")
            
            # 清理临时文件
            if os.path.exists(temp_pcap):
                os.remove(temp_pcap)
            
            # 保存捕获的数据
            if captured_packets:
                filename = f"live_capture_{timestamp}.json"
                filepath = os.path.join(self.data_dir, 'captured_traffic', filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(captured_packets, f, ensure_ascii=False, indent=2)
                
                print(f"[SUCCESS] Captured {len(captured_packets)} packets, saved to {filepath}")
            else:
                print("[WARNING] No packets were successfully processed")
            
        except Exception as e:
            print(f"[ERROR] Live capture failed: {str(e)}")
        
        return captured_packets
    
    def analyze_with_ai(self, traffic_data: List[str], model=None, enable_thinking=True) -> Dict[str, Any]:
        """使用AI模型分析流量数据"""
        
        # 构建分析提示词
        thinking_prefix = "" if enable_thinking else "/no_think"
        prompt = f"""{thinking_prefix}
你是一个专业的校园网络安全分析师。请分析以下校园网络流量数据，并提供详细的安全评估报告。

流量数据（共{len(traffic_data)}个数据包）：
{"".join(traffic_data[:10])}  # 只发送前10个包避免上下文过长

请从校园网络环境的角度进行分析，重点关注：
1. 流量概况（协议分布、通信模式，结合校园网络特点如学生宿舍、教学区域、实验室等）
2. 校园网络常见威胁识别（P2P下载、游戏流量、恶意软件传播、网络攻击、违规访问等）
3. 异常行为检测（异常时间访问、大流量传输、可疑连接等）
4. 风险等级评估（低/中/高）
5. 校园网络管理建议（带宽管理、访问控制、安全策略、学生行为规范等）

请以JSON格式返回分析结果，包含以下字段：
- summary: 对流量文件分析的简要总结，包含主要发现和关键指标，不要包含思考过程
- threats: 发现的威胁列表，重点关注校园网络常见问题
- risk_level: 风险等级
- recommendations: 针对校园网络管理的具体安全建议
- detailed_analysis: 对流量文件分析的详细总结报告，包含具体数据和结论，不要包含分析思考过程

重要提示：
1. summary和detailed_analysis字段必须是对分析结果的总结，而不是分析思考过程
2. 避免在这两个字段中包含"我需要分析"、"首先"、"接下来"等思考性语言
3. 直接提供分析结论和发现的问题
4. 使用具体的数据和事实来支撑结论
"""
        
        try:
            if model is None:
                model = self.model
            url = "http://localhost:11434/api/chat"
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            print("[INFO] Sending traffic data to AI model for analysis...")
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                ai_response = response.json().get('message', {}).get('content', '')
                
                # 尝试解析JSON响应
                try:
                    analysis_result = json.loads(ai_response)
                    # 确保必要字段存在
                    if "summary" not in analysis_result:
                        analysis_result["summary"] = "流量分析已完成，请查看详细报告"
                    if "risk_level" not in analysis_result:
                        analysis_result["risk_level"] = "中"
                    if "threats" not in analysis_result:
                        analysis_result["threats"] = []
                    if "recommendations" not in analysis_result:
                        analysis_result["recommendations"] = ["建议进一步分析流量模式"]
                except json.JSONDecodeError:
                    # 如果不是JSON格式，尝试从文本中提取关键信息
                    summary = "基于流量特征的安全分析已完成"
                    risk_level = "中"
                    threats = []
                    recommendations = ["建议持续监控网络流量"]
                    
                    # 简单的关键词检测
                    if any(keyword in ai_response.lower() for keyword in ['攻击', '恶意', '威胁', '异常', '入侵']):
                        risk_level = "高"
                        threats.append("检测到潜在安全威胁")
                    elif any(keyword in ai_response.lower() for keyword in ['正常', '安全', '无异常']):
                        risk_level = "低"
                    
                    # 尝试提取摘要信息
                    lines = ai_response.split('\n')
                    for line in lines:
                        if '摘要' in line or '概况' in line:
                            summary = line.strip()
                            break
                    
                    analysis_result = {
                        "summary": summary,
                        "threats": threats,
                        "risk_level": risk_level,
                        "recommendations": recommendations,
                        "detailed_analysis": ai_response
                    }
                
                # 保存AI分析结果
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"ai_analysis_{timestamp}.json"
                filepath = os.path.join(self.data_dir, 'ai_responses', filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(analysis_result, f, ensure_ascii=False, indent=2)
                
                print(f"[SUCCESS] AI analysis completed, saved to {filepath}")
                return analysis_result
                
            else:
                print(f"[ERROR] AI API call failed with status code: {response.status_code}")
                return {"error": f"API调用失败，状态码: {response.status_code}"}
                
        except Exception as e:
            print(f"[ERROR] AI analysis failed: {str(e)}")
            return {"error": f"AI分析失败: {str(e)}"}
    
    def process_pcap_file(self, pcap_file_path: str, enable_thinking=True) -> Dict[str, Any]:
        """处理pcap文件的完整流程"""
        print(f"[INFO] Starting analysis of pcap file: {pcap_file_path}")
        
        # 1. 解析pcap文件
        traffic_data = self.load_pcap_with_tshark(pcap_file_path)
        
        if not traffic_data:
            return {"error": "无法解析pcap文件或文件为空"}
        
        # 2. 保存结构化数据
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        structured_filename = f"structured_data_{timestamp}.json"
        structured_filepath = os.path.join(self.data_dir, 'analysis_results', structured_filename)
        
        structured_data = {
            "timestamp": timestamp,
            "source_file": os.path.basename(pcap_file_path),
            "packet_count": len(traffic_data),
            "packets": traffic_data
        }
        
        with open(structured_filepath, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)
        
        # 3. AI分析
        ai_result = self.analyze_with_ai(traffic_data, enable_thinking=enable_thinking)
        
        # 4. 合并结果
        final_result = {
            "structured_data_file": structured_filepath,
            "ai_analysis": ai_result,
            "processing_time": datetime.now().isoformat()
        }
        
        return final_result

# 测试函数
if __name__ == "__main__":
    analyzer = TrafficAnalyzer()
    
    # 测试实时捕获（需要管理员权限）
    # captured = analyzer.capture_live_traffic(duration=10)
    # print(f"Captured {len(captured)} packets")
    
    print("Traffic Analyzer initialized successfully!")